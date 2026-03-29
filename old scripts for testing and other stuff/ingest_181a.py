import json
import sqlite3
import time
from datetime import datetime, timezone
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
client = genai.Client()

CASE_NUMBER = '181a'
ENC_ID = 183

# Load raw text and slice lines 8230-8272
with open('Sources/bullard_vol2_raw.txt', encoding='utf-8') as f:
    all_lines = f.readlines()
extraction_text = ''.join(all_lines[8229:8272])

print(f"Case {CASE_NUMBER}: {len(extraction_text)} chars extracted from lines 8230-8272")
print("--- TEXT PREVIEW (first 400 chars) ---")
print(extraction_text[:400])
print("--- END PREVIEW ---\n")

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
    'RETRIEVAL METHOD CONTEXT: This entire account was recovered under hypnotic regression '
    'with a clinical investigator. Every event in this text must be assigned memory_state="hypnosis" '
    'unless the text explicitly states otherwise for a specific event.'
)

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

full_prompt = retrieval_context + "\n\n" + master_prompt + extraction_text

print("Sending to Gemini...")
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
print(f"Extracted {len(events)} motifs.")

# Delete old events and insert
cursor.execute("DELETE FROM Encounter_Events WHERE Encounter_ID = ?", (ENC_ID,))
run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

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
    ''', (ENC_ID, code, idx + 1, ev.get('source_citation'),
          'C-147', '167', ev.get('memory_state'), ev.get('ai_justification'), run_ts))
    inserted += 1
    print(f"  [{idx+1:02d}] {code}: {ev.get('source_citation', '')[:70]}")

conn.commit()
conn.close()
print(f"\nSUCCESS: {inserted} inserted, {rejected} rejected for Case {CASE_NUMBER}.")
