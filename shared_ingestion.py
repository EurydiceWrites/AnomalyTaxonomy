"""
Shared ingestion utilities used by bulk_ingest.py and reingest_case.py.

Contains:
- build_page_map()      — tracks Bullard/PDF page markers per line
- slice_case_text()     — extracts text block using line boundaries
- build_chunks()        — splits text into page-stamped chunks
- process_case()        — sends chunks to Gemini and inserts results into DB
- RETRIEVAL_CONTEXT_MAP — maps retrieval methods to LLM context instructions
"""

import json
import re
import time

from google.genai import types


# ---------------------------------------------------------------------------
# Page mapping — tracks Bullard catalogue page (C-NNN) and PDF page per line
# ---------------------------------------------------------------------------
def build_page_map(text):
    """Walk through the text and record where each page marker appears."""
    page_map = []
    current_pdf_page = None
    current_bullard_page = None

    for i, line in enumerate(text.split('\n')):
        pdf_match = re.match(r'\[--- START PAGE (\d+) ---\]', line)
        if pdf_match:
            current_pdf_page = pdf_match.group(1)

        bullard_match = re.match(r'^C-(\d+)', line)
        if bullard_match:
            current_bullard_page = 'C-' + bullard_match.group(1)

        page_map.append({
            'line': i,
            'pdf_page': current_pdf_page,
            'bullard_page': current_bullard_page
        })

    return page_map


def slice_case_text(all_lines, line_start, line_end):
    """
    Extract the text block for a case using pre-computed line boundaries
    from header_map.json. line_start and line_end are 1-indexed.
    Returns the joined text string.
    """
    return ''.join(all_lines[line_start - 1 : line_end])


def build_chunks(extraction_text, chunk_size=3500):
    """Split extraction_text into page-stamped chunks."""
    page_map = build_page_map(extraction_text)
    lines = extraction_text.split('\n')
    char_to_line = []
    for line_idx, line in enumerate(lines):
        char_to_line.extend([line_idx] * (len(line) + 1))  # +1 for newline

    chunks = []
    for i in range(0, len(extraction_text), chunk_size):
        chunk_text = extraction_text[i:i + chunk_size]
        start_line = char_to_line[min(i, len(char_to_line) - 1)]
        page_entry = page_map[min(start_line, len(page_map) - 1)]
        chunks.append({
            'text': chunk_text,
            'bullard_page': page_entry['bullard_page'],
            'pdf_page': page_entry['pdf_page'],
        })
    return chunks, len(page_map)


def process_case(case_number, enc_id, extraction_text, master_prompt_template,
                 retrieval_context, valid_motifs, cursor, client, run_ts):
    """
    Extract motifs for one case and insert into DB.
    extraction_text is the pre-sliced text from header_map line boundaries.
    Returns (inserted, rejected) counts.
    Raises on unrecoverable failure so the caller can log and continue.
    """
    chunks, n_lines = build_chunks(extraction_text)
    print(f"  Found {len(extraction_text)} chars -> {len(chunks)} chunks, {n_lines} lines mapped.")

    # Render the case-specific master prompt
    master_prompt = master_prompt_template.replace('__CASE_NUMBER__', case_number)

    all_events = []
    for idx, chunk in enumerate(chunks):
        full_prompt = retrieval_context + "\n\n" + master_prompt + chunk['text']
        print(f"  Chunk {idx+1}/{len(chunks)} "
              f"[bullard: {chunk['bullard_page']}, pdf: {chunk['pdf_page']}]", end=' ')

        success = False
        retries = 3
        while not success and retries > 0:
            try:
                response = client.models.generate_content(
                    model='gemini-3.1-pro-preview',
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.0
                    )
                )
                data = json.loads(response.text)
                events = data if isinstance(data, list) else data.get('motifs', [])
                for ev in events:
                    ev['_bullard_page'] = chunk['bullard_page']
                    ev['_pdf_page'] = chunk['pdf_page']
                all_events.extend(events)
                print(f"→ {len(events)} motifs")
                success = True
                time.sleep(4)
            except Exception as e:
                if '429' in str(e) or (hasattr(e, 'code') and e.code == 429):
                    print(f"\n  Rate limit hit, sleeping 45s... ({retries} retries left)")
                    time.sleep(45)
                    retries -= 1
                else:
                    raise RuntimeError(f"API error on chunk {idx+1}: {e}") from e

        if not success:
            raise RuntimeError(f"Chunk {idx+1} failed after all retries (rate limit exhausted)")

    print(f"  Extraction complete: {len(all_events)} total motifs.")

    # --- Clear old events and insert ---
    cursor.execute("DELETE FROM Encounter_Events WHERE Encounter_ID = ?", (enc_id,))

    inserted = 0
    rejected = 0
    for seq, ev in enumerate(all_events):
        code = ev.get('motif_code')
        if code not in valid_motifs:
            print(f"    [X] REJECTED: {code}")
            rejected += 1
            continue
        cursor.execute('''
            INSERT INTO Encounter_Events
            (Encounter_ID, Motif_Code, Sequence_Order, Source_Citation,
             source_page, pdf_page, memory_state, ai_justification, run_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            enc_id,
            code,
            seq + 1,
            ev.get('source_citation'),
            ev.get('_bullard_page'),
            ev.get('_pdf_page'),
            ev.get('memory_state'),
            ev.get('ai_justification'),
            run_ts
        ))
        inserted += 1

    return inserted, rejected


RETRIEVAL_CONTEXT_MAP = {
    'hypnosis':  'RETRIEVAL METHOD CONTEXT: This entire account was recovered under hypnotic regression with a clinical investigator. Every event in this text must be assigned memory_state="hypnosis" unless the text explicitly states otherwise for a specific event.',
    'conscious': 'RETRIEVAL METHOD CONTEXT: This account was recalled consciously by the witness without hypnotic regression. Every event must be assigned memory_state="conscious" unless the text explicitly states otherwise.',
    'dream':     'RETRIEVAL METHOD CONTEXT: This account was recalled as a dream or vision. Every event must be assigned memory_state="dream" unless the text explicitly states otherwise.',
    'mixed':     'RETRIEVAL METHOD CONTEXT: This account contains a mix of hypnotically and consciously recalled events. Assign memory_state on a per-event basis based on the text.',
    'unknown':   'RETRIEVAL METHOD CONTEXT: The retrieval method for this account is unknown. Assign memory_state based on any explicit cues in the text; default to "conscious" if no cue is present.',
}
