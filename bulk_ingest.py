import sys
import json
import sqlite3
import time
import argparse
from datetime import datetime, timezone
from dotenv import load_dotenv

from shared_ingestion import (
    slice_case_text,
    process_case,
    RETRIEVAL_CONTEXT_MAP,
)

# Force UTF-8 output on Windows to handle Unicode characters in raw text
sys.stdout.reconfigure(encoding='utf-8')


# ===========================================================================
# MAIN
# ===========================================================================
parser = argparse.ArgumentParser(description="Bulk Bullard Transcriber — processes all cases in the Encounters table")
parser.add_argument("--start-from", default=None,
                    help="Resume from this case number. All prior cases are skipped.")
parser.add_argument("--model", default="gemini-2.5-pro",
                    choices=["gemini-2.5-pro", "gemini-3.1-pro-preview", "claude-opus-4-6"],
                    help="Which LLM to use for extraction")
args = parser.parse_args()

load_dotenv()

print("=" * 70)
print("BULK INGEST — Bullard Volume 2 Transcriber")
print("=" * 70)

# --- Load prompt library once ---
print("Loading prompt_library.json...")
with open('prompt_library.json', 'r', encoding='utf-8') as f:
    prompt_lib = json.load(f)

profile = prompt_lib['profiles']['bullard_transcriber']
sys_inst = "\n".join(profile['system_instruction'])
anti_hall = "\n".join(profile['anti_hallucination_rules'])
few_shot = "\n\n".join(profile['few_shot_examples'])

# --- Open a single DB connection for the entire run ---
conn = sqlite3.connect('ufo_matrix.db')
cursor = conn.cursor()

# --- Load motif dictionary once ---
print("Loading Motif Dictionary...")
cursor.execute("SELECT Motif_Code, motif_description FROM Motif_Dictionary WHERE Motif_Code IS NOT NULL")
dict_rows = cursor.fetchall()
valid_motifs = {r[0] for r in dict_rows}
motif_dict_str = "\n".join([f"{r[0]}: {r[1]}" for r in dict_rows])
print(f"  {len(valid_motifs)} valid motif codes loaded.")

# --- Master prompt TEMPLATE: __CASE_NUMBER__ is replaced per case ---
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

# --- Load raw text once as a list of lines (for line-indexed slicing) ---
print("Loading bullard_vol2_raw.txt...")
with open('Sources/bullard_vol2_raw.txt', encoding='utf-8') as f:
    all_lines = f.readlines()  # preserves newlines; 0-indexed, but map is 1-indexed
print(f"  {len(all_lines)} lines loaded.")

# --- Load header map (replaces Encounters query for case iteration) ---
print("Loading header_map.json...")
with open('header_map.json', encoding='utf-8') as f:
    header_map = json.load(f)

# Filter to only processable entries:
# - type must be 'case' (skip 'master' and 'manual')
# - must have a non-null encounter_id
# - must have non-null line boundaries
all_encounters = [
    entry for entry in header_map
    if entry['type'] == 'case'
    and entry['encounter_id'] is not None
    and entry['line_start'] is not None
]
print(f"  {len(all_encounters)} processable case entries found in header map.")

# --- Apply --start-from skip ---
if args.start_from:
    skip_until = args.start_from.strip().lower()
    start_idx = next(
        (i for i, e in enumerate(all_encounters) if e['case_number'].lower() == skip_until),
        None
    )
    if start_idx is None:
        print(f"WARNING: --start-from case '{args.start_from}' not found in header map. Running all cases.")
    else:
        print(f"Resuming from case {args.start_from} — skipping {start_idx} previously completed cases.")
        all_encounters = all_encounters[start_idx:]

# --- Main loop ---
succeeded = []
failed = []
run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
print(f"Run timestamp: {run_ts}\n")

for current_idx, entry in enumerate(all_encounters, start=1):
    case_number = entry['case_number']
    enc_id      = entry['encounter_id']
    line_start  = entry['line_start']
    line_end    = entry['line_end']
    retrieval_method = entry.get('retrieval_method') or 'unknown'

    print(f"\n{'=' * 70}")
    print(f"=== Processing Case {case_number} ({current_idx}/{len(all_encounters)}) ===")
    print(f"{'=' * 70}")
    print(f"  Lines {line_start}–{line_end} | Retrieval: {retrieval_method}")

    retrieval_context = RETRIEVAL_CONTEXT_MAP.get(retrieval_method, RETRIEVAL_CONTEXT_MAP['unknown'])

    # Slice the exact text block for this case from the pre-loaded line array
    extraction_text = slice_case_text(all_lines, line_start, line_end)

    try:
        inserted, rejected = process_case(
            case_number=case_number,
            enc_id=enc_id,
            extraction_text=extraction_text,
            master_prompt_template=MASTER_PROMPT_TEMPLATE,
            retrieval_context=retrieval_context,
            valid_motifs=valid_motifs,
            cursor=cursor,
            run_ts=run_ts,
            model=args.model,
        )
        conn.commit()
        result_msg = f"{inserted} inserted, {rejected} rejected"
        print(f"  [OK] Case {case_number}: {result_msg}")
        succeeded.append((case_number, result_msg))

    except Exception as e:
        error_msg = str(e)
        print(f"  [FAIL] Case {case_number}: {error_msg}")
        failed.append((case_number, error_msg))
        conn.rollback()

    # Brief pause between cases to avoid sustained rate pressure
    if current_idx < len(all_encounters):
        time.sleep(5)

# --- Final summary ---
conn.close()
print(f"\n{'=' * 70}")
print("BULK INGEST COMPLETE")
print(f"{'=' * 70}")
print(f"  Total attempted:  {len(succeeded) + len(failed)}")
print(f"  Succeeded:        {len(succeeded)}")
print(f"  Failed:           {len(failed)}")
if failed:
    print("\nFailed cases:")
    for cn, msg in failed:
        print(f"  {cn}: {msg}")
