import json
import sqlite3
import time
from datetime import datetime, timezone
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
client = genai.Client()

SUBCASES = [
    ('199_1', 252, 10735, 10753, 'C-196', '216'),
    ('199_2', 253, 10758, 10771, 'C-197', '217'),
    ('199_3', 256, 10772, 10781, 'C-197', '217'),
]

# Load raw text
with open('Sources/bullard_vol2_raw.txt', encoding='utf-8') as f:
    all_lines = f.readlines()

# Load prompt library
with open('prompt_library.json', 'r', encoding='utf-8') as f:
    prompt_lib = json.load(f)
profile = prompt_lib['profiles']['bullard_transcriber']
sys_inst = "\n".join(profile['system_instruction'])
anti_hall = "\n".join(profile['anti_hallucination_rules'])
few_shot = "\n\n".join(profile['few_shot_examples'])

# Load motif dictionary
conn = sqlite3.connect('ufo_matrix.db')
cursor = conn.cursor()
cursor.execute("SELECT Motif_Code, motif_description FROM Motif_Dictionary WHERE Motif_Code IS NOT NULL")
dict_rows = cursor.fetchall()
valid_motifs = {r[0] for r in dict_rows}
motif_dict_str = "\n".join([f"{r[0]}: {r[1]}" for r in dict_rows])

retrieval_context = (
    'RETRIEVAL METHOD CONTEXT: The retrieval method for this account is unknown. '
    'Assign memory_state based on any explicit cues in the text; default to "conscious" if no cue is present.'
)

run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
results = []

for case_number, enc_id, line_start, line_end, bullard_page, pdf_page in SUBCASES:
    extraction_text = ''.join(all_lines[line_start - 1 : line_end])
    print(f"\n{'='*60}")
    print(f"Processing {case_number} (Enc {enc_id}): lines {line_start}-{line_end}, {len(extraction_text)} chars")

    if len(extraction_text.strip()) < 20:
        print(f"  SKIPPED — text too short")
        results.append((case_number, 0, 0, 'skipped — too short'))
        continue

    master_prompt = f"""{sys_inst}

{anti_hall}

*** EXAMPLES OF SUCCESSFUL EXTRACTION ***
{few_shot}

*** VALID MOTIF CODES DICTIONARY ***
{motif_dict_str}

CRITICAL INSTRUCTIONS:
1. Extract ALL motifs presented in the 'TEXT TO EXTRACT FROM' block in exact chronological order.
2. Link every motif to its correct 'case_number' (For this text it is '{case_number}').
3. If a quote is missing or unclear, provide the surrounding sentence text verbatim as the source_citation.
4. YOU MUST RETURN ONLY A VALID JSON ARRAY OF OBJECTS containing keys: "case_number", "motif_code", "source_citation", "memory_state", "ai_justification". Do NOT include source_page — page numbers are handled by the pipeline.
5. For "memory_state", use the RETRIEVAL METHOD CONTEXT provided above as your primary guide.
6. For "ai_justification", provide a brief, logical explanation of why this specific Motif Code was chosen based on the text.

=== TEXT TO EXTRACT FROM ===
"""

    full_prompt = retrieval_context + "\n\n" + master_prompt + extraction_text

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
            success = True
        except Exception as e:
            if '429' in str(e):
                print(f"  Rate limit — sleeping 45s ({retries} retries left)")
                time.sleep(45)
                retries -= 1
            else:
                print(f"  API ERROR: {e}")
                results.append((case_number, 0, 0, str(e)))
                break

    if not success:
        continue

    cursor.execute("DELETE FROM Encounter_Events WHERE Encounter_ID = ?", (enc_id,))

    inserted = 0
    rejected = 0
    for idx, ev in enumerate(events):
        code = ev.get('motif_code')
        if code not in valid_motifs:
            print(f"  [X] REJECTED: {code}")
            rejected += 1
            continue
        cursor.execute('''
            INSERT INTO Encounter_Events
            (Encounter_ID, Motif_Code, Sequence_Order, Source_Citation,
             source_page, pdf_page, memory_state, ai_justification, run_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (enc_id, code, idx + 1, ev.get('source_citation'),
              bullard_page, pdf_page, ev.get('memory_state'),
              ev.get('ai_justification'), run_ts))
        inserted += 1

    conn.commit()
    print(f"  {inserted} inserted, {rejected} rejected")
    results.append((case_number, inserted, rejected, 'ok'))
    time.sleep(5)

conn.close()

print(f"\n{'='*60}")
print("SUMMARY — 199 Sub-Cases")
print(f"{'='*60}")
total_ins = total_rej = 0
for cn, ins, rej, status in results:
    print(f"  {cn}: {ins} inserted, {rej} rejected — {status}")
    total_ins += ins
    total_rej += rej
print(f"\nTotal: {total_ins} inserted, {total_rej} rejected across {len(SUBCASES)} sub-cases.")
