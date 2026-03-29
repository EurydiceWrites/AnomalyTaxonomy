import sys
import json
import sqlite3
import re
import time
import argparse
from datetime import datetime, timezone
from google import genai
from google.genai import types
from google.genai.errors import APIError
from dotenv import load_dotenv

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

# ---------------------------------------------------------------------------
# Argument parsing — makes this script work for ANY Bullard Volume 2 case
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description="Bullard Transcriber: extract and insert a single case from bullard_vol2_raw.txt")
parser.add_argument("--case-number", required=True, help="The Bullard case number to process (e.g. '192g', '136', '001')")
parser.add_argument("--subject", required=False, default=None, help="Optional subject pseudonym override for DB insert (e.g. 'Betty and Barney Hill')")
args = parser.parse_args()

CASE_NUMBER = args.case_number.strip()
SUBJECT_NAME = args.subject if args.subject else f"Case {CASE_NUMBER}"

load_dotenv()
client = genai.Client()

print(f"=== BULLARD TRANSCRIBER: Case {CASE_NUMBER} ===")
print("Loading prompt_library.json...")
with open('prompt_library.json', 'r', encoding='utf-8') as f:
    prompt_lib = json.load(f)

# Load the Transcriber profile
profile = prompt_lib['profiles']['bullard_transcriber']
sys_inst = "\n".join(profile['system_instruction'])
anti_hall = "\n".join(profile['anti_hallucination_rules'])
few_shot = "\n\n".join(profile['few_shot_examples'])

print("Fetching Motif Dictionary and retrieval method from Database...")
conn_dict = sqlite3.connect('ufo_matrix.db')
cursor_dict = conn_dict.cursor()
cursor_dict.execute("SELECT Motif_Code, motif_description FROM Motif_Dictionary WHERE Motif_Code IS NOT NULL")
dict_rows = cursor_dict.fetchall()

# Query retrieval method for this case from the pre-populated Encounters table
cursor_dict.execute(
    "SELECT memory_retrieval_method FROM Encounters WHERE Case_Number = ? COLLATE NOCASE",
    (CASE_NUMBER,)
)
retrieval_row = cursor_dict.fetchone()
conn_dict.close()

RETRIEVAL_CONTEXT_MAP = {
    'hypnosis':  'RETRIEVAL METHOD CONTEXT: This entire account was recovered under hypnotic regression with a clinical investigator. Every event in this text must be assigned memory_state="hypnosis" unless the text explicitly states otherwise for a specific event.',
    'conscious': 'RETRIEVAL METHOD CONTEXT: This account was recalled consciously by the witness without hypnotic regression. Every event must be assigned memory_state="conscious" unless the text explicitly states otherwise.',
    'dream':     'RETRIEVAL METHOD CONTEXT: This account was recalled as a dream or vision. Every event must be assigned memory_state="dream" unless the text explicitly states otherwise.',
    'mixed':     'RETRIEVAL METHOD CONTEXT: This account contains a mix of hypnotically and consciously recalled events. Assign memory_state on a per-event basis based on the text.',
    'unknown':   'RETRIEVAL METHOD CONTEXT: The retrieval method for this account is unknown. Assign memory_state based on any explicit cues in the text; default to "conscious" if no cue is present.',
}

retrieval_method = retrieval_row[0] if retrieval_row else 'unknown'
retrieval_context = RETRIEVAL_CONTEXT_MAP.get(retrieval_method, RETRIEVAL_CONTEXT_MAP['unknown'])
print(f"[*] Retrieval method for {CASE_NUMBER}: {retrieval_method}")

valid_motifs = {r[0] for r in dict_rows}
motif_dict_str = "\n".join([f"{r[0]}: {r[1]}" for r in dict_rows])

# Construct the master prompt
master_prompt = f"""{sys_inst}

{anti_hall}

*** EXAMPLES OF SUCCESSFUL EXTRACTION ***
{few_shot}

*** VALID MOTIF CODES DICTIONARY ***
{motif_dict_str}

CRITICAL INSTRUCTIONS:
1. Extract ALL motifs presented in the 'TEXT TO EXTRACT FROM' block in exact chronological order.
2. Link every motif to its correct 'case_number' (For this text it is '{CASE_NUMBER}').
3. If a quote is missing or unclear, provide the surrounding sentence text verbatim as the source_citation.
4. YOU MUST RETURN ONLY A VALID JSON ARRAY OF OBJECTS containing keys: "case_number", "motif_code", "source_citation", "memory_state", "ai_justification". Do NOT include source_page — page numbers are handled by the pipeline.
5. For "memory_state", use the RETRIEVAL METHOD CONTEXT provided above as your primary guide.
6. For "ai_justification", provide a brief, logical explanation of why this specific Motif Code was chosen based on the text.

=== TEXT TO EXTRACT FROM ===
"""

# ---------------------------------------------------------------------------
# Extract case text from the raw source
# ---------------------------------------------------------------------------
print(f"Extracting case {CASE_NUMBER} narrative from bullard_vol2_raw.txt...")
txt = open('Sources/bullard_vol2_raw.txt', encoding='utf-8').read()

# The raw file contains both the dictionary appendix AND the case narratives.
# Cases begin after the first [--- START PAGE 20 ---] marker.
# We restrict our search to the cases section to avoid matching appendix row numbers.
cases_start = txt.find('[--- START PAGE 20 ---]')
if cases_start == -1:
    cases_start = 0  # fallback: search the whole file
cases_section = txt[cases_start:]

# Genuine case headers: digits + '. ' + capital letter, followed within a few
# lines by 'Duration' or 'Investigation'. Dictionary rows never have these fields.
header_found = None
for candidate in re.finditer(re.escape(CASE_NUMBER) + r'\. [A-Z]', cases_section):
    context = cases_section[candidate.start():candidate.start() + 400]
    if 'Duration' in context or 'Investigation' in context:
        header_found = candidate
        break

if not header_found:
    print(f"ERROR: Could not locate a genuine case header for {CASE_NUMBER} in bullard_vol2_raw.txt.")
    sys.exit(1)

# Extract from the confirmed header to the next genuine case header
search_from = header_found.start()
m = re.search(
    re.escape(CASE_NUMBER) + r'\. [A-Z].*?(?=\n\d{3}[a-z]?\. [A-Z])',
    cases_section[search_from:],
    flags=re.DOTALL
)
if not m:
    print(f"ERROR: Could not isolate case block for {CASE_NUMBER}.")
    sys.exit(1)

extraction_text = m.group(0)
print(f"Found case block: {len(extraction_text)} chars.")

# Build page map so each chunk can be stamped with the correct page values
page_map = build_page_map(extraction_text)
print(f"Built page map: {len(page_map)} lines mapped.")

# Build chunks, stamping each with the bullard_page and pdf_page active at
# the start character of that chunk
chunks = []
chunk_size = 3500
lines = extraction_text.split('\n')
char_to_line = []  # maps character offset -> line index
for line_idx, line in enumerate(lines):
    char_to_line.extend([line_idx] * (len(line) + 1))  # +1 for the newline

for i in range(0, len(extraction_text), chunk_size):
    chunk_text = extraction_text[i:i + chunk_size]
    start_line = char_to_line[min(i, len(char_to_line) - 1)]
    page_entry = page_map[min(start_line, len(page_map) - 1)]
    chunks.append({
        'text': chunk_text,
        'bullard_page': page_entry['bullard_page'],
        'pdf_page': page_entry['pdf_page'],
    })

print(f"Split into {len(chunks)} chunks.")
all_events = []

for idx, chunk in enumerate(chunks):
    full_prompt = retrieval_context + "\n\n" + master_prompt + chunk['text']
    print(f"Sending Chunk {idx+1}/{len(chunks)} to Gemini 2.5 Pro Transcriber... "
          f"[bullard: {chunk['bullard_page']}, pdf: {chunk['pdf_page']}]")

    success = False
    retries = 3
    while not success and retries > 0:
        try:
            response = client.models.generate_content(
                model='gemini-2.5-pro',
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0
                )
            )
            data = json.loads(response.text)
            events = data if isinstance(data, list) else data.get('motifs', [])
            # Stamp each event with the chunk's page values
            for ev in events:
                ev['_bullard_page'] = chunk['bullard_page']
                ev['_pdf_page'] = chunk['pdf_page']
            all_events.extend(events)
            print(f"  -> Extracted {len(events)} motifs from chunk {idx+1}.")
            success = True
            time.sleep(4)
        except Exception as e:
            if '429' in str(e) or (hasattr(e, 'code') and e.code == 429):
                print(f"Rate capacity hit. Sleeping for 45s... ({retries} retries left)")
                time.sleep(45)
                retries -= 1
            else:
                print(f"API Error processing chunk: {e}")
                break

print(f"\nExtraction complete! Total motifs extracted: {len(all_events)}")

# ---------------------------------------------------------------------------
# Database Insertion
# ---------------------------------------------------------------------------
print("Injecting into Database...")
try:
    conn = sqlite3.connect('ufo_matrix.db')
    cursor = conn.cursor()

    # Look up or create Subject
    cursor.execute("SELECT Subject_ID FROM Subjects WHERE Pseudonym LIKE ?", (f'%{SUBJECT_NAME}%',))
    res = cursor.fetchone()
    if res:
        sub_id = res[0]
    else:
        cursor.execute("INSERT INTO Subjects (Pseudonym) VALUES (?)", (SUBJECT_NAME,))
        sub_id = cursor.lastrowid
        print(f"[*] Created new Subject record: {SUBJECT_NAME} (ID: {sub_id})")

    # Look up or create Encounter
    cursor.execute("SELECT Encounter_ID FROM Encounters WHERE Case_Number = ? COLLATE NOCASE", (CASE_NUMBER,))
    res = cursor.fetchone()
    if res:
        enc_id = res[0]
        print(f"[*] Found existing Encounter ID: {enc_id} for case {CASE_NUMBER}")
    else:
        cursor.execute(
            "INSERT INTO Encounters (Subject_ID, Case_Number, Source_Material) VALUES (?, ?, ?)",
            (sub_id, CASE_NUMBER, 'Bullard Vol 2')
        )
        enc_id = cursor.lastrowid
        print(f"[*] Created new Encounter record (ID: {enc_id}) for case {CASE_NUMBER}")

    # Clear previous events for a clean re-run
    cursor.execute("DELETE FROM Encounter_Events WHERE Encounter_ID = ?", (enc_id,))
    print(f"[*] Cleared previous events for Encounter {enc_id}.")

    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[*] Run timestamp: {run_ts}")

    inserted = 0
    rejected = 0
    for idx, ev in enumerate(all_events):
        code = ev.get('motif_code')
        if code not in valid_motifs:
            print(f"    [X] REJECTED HALLUCINATED CODE: {code}")
            rejected += 1
            continue
        cursor.execute('''
            INSERT INTO Encounter_Events
            (Encounter_ID, Motif_Code, Sequence_Order, Source_Citation, source_page, pdf_page, memory_state, ai_justification, run_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            enc_id,
            code,
            idx + 1,
            ev.get('source_citation'),
            ev.get('_bullard_page'),     # script-stamped Bullard catalogue page
            ev.get('_pdf_page'),         # script-stamped PDF page number
            ev.get('memory_state'),
            ev.get('ai_justification'),
            run_ts
        ))
        inserted += 1

    conn.commit()
    conn.close()
    print(f"\nSUCCESS: Inserted {inserted} valid events for Case {CASE_NUMBER} into ufo_matrix.db!")
    if rejected > 0:
        print(f"WARNING: Rejected {rejected} hallucinated or malformed codes.")

except Exception as e:
    print(f"DATABASE ERROR: {e}")
