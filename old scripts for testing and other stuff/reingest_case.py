"""
Single-case reingest using the full pipeline.
Runs the text through prompt_library.json + Gemini, exactly like bulk_ingest.
Usage: python reingest_case.py 131
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import json
import sqlite3
import argparse
from datetime import datetime, timezone
from google import genai
from dotenv import load_dotenv

from shared_ingestion import (
    slice_case_text,
    process_case,
    RETRIEVAL_CONTEXT_MAP,
)


# --- MAIN ---
parser = argparse.ArgumentParser(description="Reingest a single case through the full pipeline")
parser.add_argument("case_number", help="Case number to reingest (e.g., 131)")
args = parser.parse_args()
target_case = args.case_number.strip()

load_dotenv()
client = genai.Client()

print(f"{'=' * 70}")
print(f"SINGLE CASE REINGEST: Case {target_case}")
print(f"{'=' * 70}")

with open('prompt_library.json', 'r', encoding='utf-8') as f:
    prompt_lib = json.load(f)

profile = prompt_lib['profiles']['bullard_transcriber']
sys_inst = "\n".join(profile['system_instruction'])
anti_hall = "\n".join(profile['anti_hallucination_rules'])
few_shot = "\n\n".join(profile['few_shot_examples'])

conn = sqlite3.connect('ufo_matrix.db')
cursor = conn.cursor()

cursor.execute("SELECT Motif_Code, motif_description FROM Motif_Dictionary WHERE Motif_Code IS NOT NULL")
dict_rows = cursor.fetchall()
valid_motifs = {r[0] for r in dict_rows}
motif_dict_str = "\n".join([f"{r[0]}: {r[1]}" for r in dict_rows])
print(f"  {len(valid_motifs)} valid motif codes loaded.")

MASTER_PROMPT_TEMPLATE = f"""{sys_inst}

{anti_hall}

*** EXAMPLES OF SUCCESSFUL EXTRACTION ***
{few_shot}

*** VALID MOTIF CODES DICTIONARY ***
{motif_dict_str}

CRITICAL INSTRUCTIONS:
1. Extract ALL motifs presented in the 'TEXT TO EXTRACT FROM' block in exact chronological order.
2. Link every motif to its correct 'case_number' (For this text it is '__CASE_NUMBER__').
3. If a quote is missing or unclear, provide the surrounding sentence text verbatim as the source_citation.
4. YOU MUST RETURN ONLY A VALID JSON ARRAY OF OBJECTS containing keys: "case_number", "motif_code", "source_citation", "memory_state", "ai_justification". Do NOT include source_page — page numbers are handled by the pipeline.
5. For "memory_state", use the RETRIEVAL METHOD CONTEXT provided above as your primary guide.
6. For "ai_justification", provide a brief, logical explanation of why this specific Motif Code was chosen based on the text.

=== TEXT TO EXTRACT FROM ===
"""

with open('Sources/bullard_vol2_raw.txt', encoding='utf-8') as f:
    all_lines = f.readlines()

with open('header_map.json', encoding='utf-8') as f:
    header_map = json.load(f)

entry = next((e for e in header_map if e['case_number'].lower() == target_case.lower()), None)
if not entry:
    print(f"ERROR: Case {target_case} not found in header_map.json")
    sys.exit(1)

case_number = entry['case_number']
enc_id = entry['encounter_id']
line_start = entry['line_start']
line_end = entry['line_end']
retrieval_method = entry.get('retrieval_method') or 'unknown'

print(f"  Lines {line_start}-{line_end} | Encounter_ID: {enc_id} | Retrieval: {retrieval_method}")
retrieval_context = RETRIEVAL_CONTEXT_MAP.get(retrieval_method, RETRIEVAL_CONTEXT_MAP['unknown'])

extraction_text = slice_case_text(all_lines, line_start, line_end)
run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

try:
    inserted, rejected = process_case(
        case_number=case_number,
        enc_id=enc_id,
        extraction_text=extraction_text,
        master_prompt_template=MASTER_PROMPT_TEMPLATE,
        retrieval_context=retrieval_context,
        valid_motifs=valid_motifs,
        cursor=cursor,
        client=client,
        run_ts=run_ts,
    )
    conn.commit()
    print(f"\n  [OK] Case {case_number}: {inserted} inserted, {rejected} rejected")
except Exception as e:
    print(f"\n  [FAIL] Case {case_number}: {e}")
    conn.rollback()

conn.close()
