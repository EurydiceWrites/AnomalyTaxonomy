"""
build_header_map.py — HDR-001 Fix
Scans bullard_vol2_raw.txt to produce header_map.json: a precise boundary
map telling bulk_ingest.py exactly where each case starts and ends.

See: Plans/build_header_map_handoff.md for full specification.
"""

import re
import json
import sqlite3
import argparse

# ---------------------------------------------------------------------------
# Command-line arguments
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description="Build header_map.json from bullard_vol2_raw.txt")
parser.add_argument("--text-file",   default="Sources/bullard_vol2_raw.txt")
parser.add_argument("--db-file",     default="ufo_matrix.db")
parser.add_argument("--output-file", default="header_map.json")
args = parser.parse_args()

# ---------------------------------------------------------------------------
# Constants — implementing EXACTLY as specified in the handoff document.
# Do not modify these tables without re-verifying against the physical book.
# ---------------------------------------------------------------------------

# Step 2: Known false positive — sentence fragment, not a case header.
FALSE_POSITIVE_LINES = {6570, 3174}

# Step 3a: Lines where the regex WILL find a match but with the WRONG
# case number. The value is the corrected case number.
REMAP_CORRECTIONS = {
    1938: '051',   # Regex finds 061; real 061 is at line 2200
    5516: '138',   # Regex finds 139; real 139 is at line 5579
    8186: '180a',  # Regex finds 190a; real 190a is at line 8999
}

# Step 3b: Lines where OCR damage prevented the regex from matching at all.
# These must be manually inserted. Value is the corrected case number.
MANUAL_ADD_CORRECTIONS = {
    2218:  '062',
    3763:  '111',
    3882:  '116',
    6240:  '149',
    6819:  '163',
    6927:  '164',
    7455:  '169',
    7688:  '174',
    8543:  '186b',
    8986:  '189b',
    9062:  '191a',
    9655:  '192i',
    9974:  '193f',
    10813: '199b',
}

# Step 4: Complex/master case headers — contain no extractable motifs.
# bulk_ingest.py will skip all entries with type='master'.
# Note: 201 is included even though it has an Encounter_ID (260) in the DB,
# because its text block is introductory only — no motifs to extract.
MASTER_HEADERS = {'187', '192', '193', '194', '195', '196', '198', '199', '201'}

# Step 5: Case 058 appears TWICE — two different cases Bullard both numbered 058.
# Hardcode the line → Encounter_ID mapping. This is the only true duplicate.
CASE_058_HARDCODE = {
    2130: 58,   # Juan Fatorell
    2149: 59,   # Stephane Gasparovic
}

# Step 6: Cases in DB with no identifiable header in the text.
# These are emitted as type='manual' with null line positions.
MANUAL_CASES = [
    '181a',
    '195a', '195b', '195c', '195d', '195e', '195f', '195g', '195h', '195i',
    '195j', '195k', '195l', '195m', '195n', '195o', '195p', '195q',
    '199_1', '199_2', '199_3',
]

# Non-Bullard DB entries — not in the text file, silently skipped.
NON_BULLARD = {'MACK_ED_01', 'BENITEZ_MR_HM_01', 'BEARDMAN_RITA_01'}

# Cases begin after line 968 (the motif dictionary ends before this).
CASES_START_LINE = 969  # 1-indexed

# ---------------------------------------------------------------------------
# Step 0: Load the raw text file
# ---------------------------------------------------------------------------
print(f"Loading {args.text_file}...")
with open(args.text_file, encoding='utf-8') as f:
    # Store as a list; index 0 = line 1 of the file (we use 1-indexed throughout)
    all_lines = f.readlines()

total_lines = len(all_lines)
print(f"  {total_lines} lines loaded.")

# ---------------------------------------------------------------------------
# Step 7 prep: Build a page-stamp lookup (pdf_page and bullard_page per line)
# Walk all lines once and record what page values are active at each line.
# ---------------------------------------------------------------------------
print("Building page stamp lookup...")
page_stamps = []   # index i holds stamps active at 1-indexed line (i+1)
current_pdf_page = None
current_bullard_page = None

for line in all_lines:
    stripped = line.rstrip('\n')
    pdf_match = re.match(r'\[--- START PAGE (\d+) ---\]', stripped)
    if pdf_match:
        current_pdf_page = pdf_match.group(1)

    bullard_match = re.match(r'^C-(\d+)', stripped)
    if bullard_match:
        current_bullard_page = 'C-' + bullard_match.group(1)

    page_stamps.append({
        'pdf_page': current_pdf_page,
        'bullard_page': current_bullard_page,
    })

# page_stamps[i] corresponds to 1-indexed line (i+1)
# Helper: get stamp for a 1-indexed line number
def get_stamp(line_1indexed):
    idx = line_1indexed - 1
    if 0 <= idx < len(page_stamps):
        return page_stamps[idx]
    return {'pdf_page': None, 'bullard_page': None}

# ---------------------------------------------------------------------------
# Step 1: Regex scan — find all candidate case headers from line 969 onward
# ---------------------------------------------------------------------------
print(f"Scanning for case headers from line {CASES_START_LINE}...")

case_header_re = re.compile(r'^(\d{3}[a-z]?)\.\s')
found_headers = []  # list of [line_number_1indexed, case_number]

for i, line in enumerate(all_lines):
    line_num = i + 1  # convert to 1-indexed
    if line_num < CASES_START_LINE:
        continue
    m = case_header_re.match(line)
    if m:
        found_headers.append([line_num, m.group(1)])

print(f"  Regex found {len(found_headers)} candidate headers.")

# ---------------------------------------------------------------------------
# Step 2: Remove known false positive(s)
# ---------------------------------------------------------------------------
before = len(found_headers)
found_headers = [h for h in found_headers if h[0] not in FALSE_POSITIVE_LINES]
removed = before - len(found_headers)
if removed:
    print(f"  Removed {removed} false positive(s) at lines: {FALSE_POSITIVE_LINES}")

# ---------------------------------------------------------------------------
# Step 3a: Apply remap corrections (regex found something, but wrong case number)
# ---------------------------------------------------------------------------
for h in found_headers:
    line_num = h[0]
    if line_num in REMAP_CORRECTIONS:
        old = h[1]
        h[1] = REMAP_CORRECTIONS[line_num]
        print(f"  Remapped line {line_num}: {old} → {h[1]}")

# ---------------------------------------------------------------------------
# Step 3b: Manually add headers the regex couldn't find
# ---------------------------------------------------------------------------
for line_num, case_num in MANUAL_ADD_CORRECTIONS.items():
    found_headers.append([line_num, case_num])
    print(f"  Manually added line {line_num}: {case_num}")

# Sort by line number now that we've added manual entries
found_headers.sort(key=lambda h: h[0])
print(f"  Total headers after corrections: {len(found_headers)}")

# ---------------------------------------------------------------------------
# Step 4 + 5 + 8: Build the entries list with type, line_end, and page stamps
# ---------------------------------------------------------------------------
print("Building map entries...")

# Convert to a working list of dicts (excluding duplicates for 058 momentarily)
entries = []
for h in found_headers:
    line_num, case_num = h

    # Determine type
    if case_num in MASTER_HEADERS:
        entry_type = 'master'
    else:
        entry_type = 'case'

    stamp = get_stamp(line_num)
    entries.append({
        'case_number': case_num,
        'encounter_id': None,       # filled in Step 9
        'line_start': line_num,
        'line_end': None,           # filled below
        'type': entry_type,
        'start_page_pdf': stamp['pdf_page'],
        'start_page_bullard': stamp['bullard_page'],
        'retrieval_method': 'unknown',  # filled in Step 9
    })

# ---------------------------------------------------------------------------
# Step 8: Compute line_end for all non-manual entries
# Entries are already sorted by line_start.
# Each entry's line_end = next entry's line_start - 1.
# The last entry's line_end = total number of lines in the file.
# ---------------------------------------------------------------------------
for i, entry in enumerate(entries):
    if i + 1 < len(entries):
        entry['line_end'] = entries[i + 1]['line_start'] - 1
    else:
        entry['line_end'] = total_lines

# ---------------------------------------------------------------------------
# Step 5: Handle the 058 duplicate — split into two entries
# ---------------------------------------------------------------------------
# The regex and corrections already produce two separate entries at lines
# 2130 and 2149, both with case_number '058'. They just need the right
# Encounter_IDs attached (handled in Step 9 using the hardcode map).
# No further splitting needed here.

# ---------------------------------------------------------------------------
# Step 6: Add manual/headerless cases
# ---------------------------------------------------------------------------
print("Adding manual (headerless) cases...")
for case_num in MANUAL_CASES:
    entries.append({
        'case_number': case_num,
        'encounter_id': None,
        'line_start': None,
        'line_end': None,
        'type': 'manual',
        'start_page_pdf': None,
        'start_page_bullard': None,
        'retrieval_method': 'unknown',
    })

# ---------------------------------------------------------------------------
# Step 9: Join against the database
# ---------------------------------------------------------------------------
print(f"Joining against {args.db_file}...")
conn = sqlite3.connect(args.db_file)
cursor = conn.cursor()

# Build a lookup: case_number (uppercase) → (encounter_id, retrieval_method)
# For non-duplicate cases only — 058 is handled separately.
cursor.execute("""
    SELECT Case_Number, Encounter_ID, memory_retrieval_method
    FROM Encounters
""")
db_rows = cursor.fetchall()

# Build a mapping. Most case numbers are unique.
db_lookup = {}
for case_num_db, enc_id, ret_method in db_rows:
    if case_num_db in NON_BULLARD:
        continue
    db_lookup[case_num_db.lower()] = (enc_id, ret_method or 'unknown')

conn.close()

# Apply to entries
for entry in entries:
    cn = entry['case_number'].lower()
    line_num = entry['line_start']

    # Special case: 058 duplicate — use hardcoded line → Encounter_ID map
    if cn == '058' and line_num in CASE_058_HARDCODE:
        entry['encounter_id'] = CASE_058_HARDCODE[line_num]
        # retrieval_method: query by encounter_id
        for case_num_db, enc_id, ret_method in db_rows:
            if enc_id == CASE_058_HARDCODE[line_num]:
                entry['retrieval_method'] = ret_method or 'unknown'
                break
        continue

    if cn in db_lookup:
        enc_id, ret_method = db_lookup[cn]
        entry['encounter_id'] = enc_id
        entry['retrieval_method'] = ret_method
    else:
        # Not in DB — leave encounter_id as null
        if entry['type'] != 'manual':
            print(f"  WARNING: case {entry['case_number']} not found in DB.")

# ---------------------------------------------------------------------------
# Step 10: Sort and write
# ---------------------------------------------------------------------------
# Sort by line_start; null values (manual cases) go to the end.
entries.sort(key=lambda e: (e['line_start'] is None, e['line_start'] or 0))

print(f"Writing {args.output_file}...")
with open(args.output_file, 'w', encoding='utf-8') as f:
    json.dump(entries, f, indent=2)

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
type_case    = [e for e in entries if e['type'] == 'case']
type_master  = [e for e in entries if e['type'] == 'master']
type_manual  = [e for e in entries if e['type'] == 'manual']
with_enc_id  = [e for e in entries if e['encounter_id'] is not None]
without_enc_id = [e for e in entries if e['encounter_id'] is None]

print()
print("Header Map Built:")
print(f"  Total entries:             {len(entries)}")
print(f"  Type 'case':               {len(type_case)}")
print(f"  Type 'master':             {len(type_master)}")
print(f"  Type 'manual':             {len(type_manual)}")
print(f"  Cases with encounter_id:   {len(with_enc_id)}")
print(f"  Cases without encounter_id:{len(without_enc_id)}")

# Sanity checks
print()
print("Running sanity checks...")
warnings = []

# Check 1: No overlapping line ranges among non-manual entries
positioned = sorted([e for e in entries if e['line_start'] is not None],
                    key=lambda e: e['line_start'])
for i in range(len(positioned) - 1):
    a = positioned[i]
    b = positioned[i + 1]
    if a['line_end'] >= b['line_start']:
        warnings.append(
            f"OVERLAP: {a['case_number']} (ends {a['line_end']}) overlaps "
            f"{b['case_number']} (starts {b['line_start']})"
        )

# Check 2: line_end >= line_start for all positioned entries
for e in positioned:
    if e['line_end'] is not None and e['line_end'] < e['line_start']:
        warnings.append(
            f"BAD RANGE: {e['case_number']} line_end ({e['line_end']}) < "
            f"line_start ({e['line_start']})"
        )

# Check 3: No gaps between adjacent entries
for i in range(len(positioned) - 1):
    a = positioned[i]
    b = positioned[i + 1]
    if a['line_end'] != b['line_start'] - 1:
        warnings.append(
            f"GAP/OVERLAP between {a['case_number']} (line_end={a['line_end']}) "
            f"and {b['case_number']} (line_start={b['line_start']})"
        )

# Check 4: At least 308 type='case' entries with a non-null encounter_id
processable = [e for e in type_case if e['encounter_id'] is not None]
if len(processable) < 308:
    warnings.append(
        f"Only {len(processable)} processable case entries — expected >= 308"
    )

if warnings:
    print(f"  {len(warnings)} WARNING(s):")
    for w in warnings:
        print(f"    [WARNING] {w}")
else:
    print("  All checks passed.")

print()
print(f"Done. Output written to: {args.output_file}")
