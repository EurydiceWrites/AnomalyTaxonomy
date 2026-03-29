# BUILD_HEADER_MAP.PY — Engineering Handoff

## What This Script Does

This script solves bug HDR-001 in the UFO Matrix pipeline. It pre-processes `bullard_vol2_raw.txt` to produce a JSON boundary map (`header_map.json`) that tells the bulk ingest script exactly where each case starts and ends in the raw text file. The bulk ingest script (`bulk_ingest.py`) will consume this map instead of using a fragile regex to find case headers at runtime.

## Why It's Needed

The raw text is an OCR scan of Bullard's 1987 UFO case catalogue (270 numbered cases, ~310 entries including sub-cases). The existing bulk ingest script uses a regex (`re.escape(case_number) + r'\. [A-Z]'`) to find case headers, but OCR damage garbles ~17 headers badly enough that the regex fails. When a header is invisible, the previous case's text block extends into the next case, contaminating both. At a 33% failure rate in testing, bulk ingest cannot proceed without this fix.

## Input Files

1. `bullard_vol2_raw.txt` — The OCR'd text file. Cases begin after line 968 (the motif dictionary ends before this). The file uses `[--- START PAGE N ---]` markers for PDF page breaks and `C-NNN` markers for Bullard's catalogue page numbers.

2. `ufo_matrix.db` — SQLite database. The `Encounters` table has columns `Encounter_ID`, `Case_Number`, and `memory_retrieval_method`. The script queries this to attach Encounter_IDs to each header entry.

## Output File

`header_map.json` — A JSON array of objects, one per case entry, ordered by line number. Each object has:

```json
{
  "case_number": "136",
  "encounter_id": 137,
  "line_start": 4730,
  "line_end": 5490,
  "type": "case",
  "start_page_pdf": "109",
  "start_page_bullard": "C-80",
  "retrieval_method": "hypnosis"
}
```

Field definitions:
- `case_number`: The corrected Bullard case number (string).
- `encounter_id`: Integer from `Encounters.Encounter_ID`, or `null` for master headers.
- `line_start`: 1-indexed line number where this case's text begins in `bullard_vol2_raw.txt`.
- `line_end`: 1-indexed line number of the last line of this case's text (i.e., `line_start` of next entry minus 1).
- `type`: One of `"case"`, `"master"`, or `"manual"`.
  - `"case"` = normal case with an Encounter_ID; bulk ingest should process it.
  - `"master"` = complex-case introductory text (e.g., "192. The Andreasson Complex..."); no Encounter_ID, no motifs to extract, used only as a boundary marker.
  - `"manual"` = case exists in DB but has no identifiable header in the text; bulk ingest should skip it and flag it for manual handling.
- `start_page_pdf`: The most recent `[--- START PAGE N ---]` value at or before `line_start`, or `null`.
- `start_page_bullard`: The most recent `C-NNN` value at or before `line_start`, or `null`.
- `retrieval_method`: Value from `Encounters.memory_retrieval_method`, or `"unknown"`.

## Algorithm

### Step 1: Regex Scan

Scan `bullard_vol2_raw.txt` starting from line 969 onward. Match lines against:

```python
re.compile(r'^(\d{3}[a-z]?)\.\s')
```

This catches all 3-digit case numbers with optional lowercase letter suffix, followed by period and space. Store each match as `(line_number, case_number, raw_line_text)`.

**Important**: Line numbers are 1-indexed throughout (line 1 = first line of file).

### Step 2: Remove Known False Positive

Remove the match at **line 6570** (`175. illustrate this possibility.`). This is a sentence fragment from a chapter introduction, not a case header. The real Case 175 is at line 7696.

### Step 3: Apply OCR Corrections

Some case headers are too damaged for the regex to catch, but we know exactly where they are and what they should be. Others are caught by the regex but with the wrong case number due to OCR digit errors.

Here is the complete corrections table. Apply these IN ORDER:

**Headers the regex WILL find, but with the WRONG case number (remap):**

| Line  | Regex Finds | Correct Case | Action |
|-------|------------|--------------|--------|
| 1938  | `061`      | `051`        | Change case_number from 061 to 051. The real 061 is at line 2200. |
| 5516  | `139`      | `138`        | Change case_number from 139 to 138. The real 139 is at line 5579. |
| 8186  | `190a`     | `180a`       | Change case_number from 190a to 180a. The real 190a is at line 8999. |

**Headers the regex WILL NOT find (manually add):**

| Line  | OCR Text   | Correct Case | Why Regex Misses It |
|-------|-----------|--------------|---------------------|
| 2218  | `62.`     | `062`        | Only 2 digits (missing leading zero) |
| 3763  | `1 1 1 •` | `111`        | Spaces between every character |
| 3882  | `tt6.`    | `116`        | Digits became letters (1→t) |
| 6240  | `149·`    | `149`        | Middle dot instead of period |
| 6819  | `163~.`   | `163`        | Tilde after number |
| 6927  | `164·`    | `164`        | Middle dot instead of period |
| 7455  | `169~`    | `169`        | Tilde, no period |
| 7688  | `174·`    | `174`        | Middle dot instead of period |
| 8543  | `t86b.`   | `186b`       | Digit became letter (1→t) |
| 8986  | `189b,`   | `189b`       | Comma instead of period |
| 9062  | `191 a.`  | `191a`       | Space between number and letter |
| 9655  | `1921.`   | `192i`       | Letter became digit (i→1) |
| 9974  | `t93f.`   | `193f`       | Digit became letter (1→t) |
| 10813 | `t99b.`   | `199b`       | Digit became letter (1→t) |

### Step 4: Tag Master Headers

The following case numbers are master/complex-case introductory headers. They have NO Encounter_ID in the database and contain no extractable motifs. Tag them as `"type": "master"`:

```python
MASTER_HEADERS = {'187', '192', '193', '194', '195', '196', '198', '199'}
```

Note: Case `201` also has a master-style header in the text, BUT it has an Encounter_ID (260) in the database. However, it contains no extractable motifs. Tag `201` as `"type": "master"` as well.

### Step 5: Handle Duplicate Case Number 058

Case 058 appears twice in the text — two different cases that Bullard both numbered 058:
- Line 2130: Juan Fatorell (Encounter_ID 58)
- Line 2149: Stephane Gasparovic (Encounter_ID 59)

The database has both. The script must produce TWO entries for case_number `058`, distinguished by Encounter_ID. To resolve which DB row maps to which text block, query the Subjects table:

```sql
SELECT e.Encounter_ID, s.Pseudonym
FROM Encounters e
JOIN Subjects s ON e.Subject_ID = s.Subject_ID
WHERE e.Case_Number = '058'
```

Map by matching subject names to text content:
- Encounter_ID 58 (Juan Fatorell) → line 2130
- Encounter_ID 59 (Stephane Gasparovic) → line 2149

Hardcode this mapping. It's the only true duplicate.

### Step 6: Add Manual/Headerless Cases

The following cases exist in the database but have NO identifiable header in the text. Add them to the map with `"type": "manual"` and `line_start`/`line_end` set to `null`:

```python
MANUAL_CASES = [
    '181a',                      # Embedded between 180b and 181b, no header in physical book
    '195a', '195b', '195c', '195d', '195e', '195f', '195g', '195h', '195i',
    '195j', '195k', '195l', '195m', '195n', '195o', '195p', '195q',
                                 # 195 is one continuous narrative with date markers, not sub-case headers
    '199_1', '199_2', '199_3',   # Embedded in the 199 master narrative before 199a
]
```

For each, query the DB for Encounter_ID and retrieval_method, then emit:

```json
{
  "case_number": "195a",
  "encounter_id": 226,
  "line_start": null,
  "line_end": null,
  "type": "manual",
  "start_page_pdf": null,
  "start_page_bullard": null,
  "retrieval_method": "unknown"
}
```

### Step 7: Compute Page Stamps

Walk through `bullard_vol2_raw.txt` line by line, tracking two running values:
- `current_pdf_page`: Updated whenever a line matches `\[--- START PAGE (\d+) ---\]`
- `current_bullard_page`: Updated whenever a line matches `^C-(\d+)`

For each header entry, `start_page_pdf` and `start_page_bullard` are the values of these trackers at `line_start`.

### Step 8: Compute line_end

Sort all entries (excluding `"manual"` type) by `line_start`. For each entry, `line_end` = next entry's `line_start` minus 1. For the last entry in the file, `line_end` = total number of lines in the file.

### Step 9: Join Against Database

For each entry, query the Encounters table:

```sql
SELECT Encounter_ID, memory_retrieval_method
FROM Encounters
WHERE Case_Number = ? COLLATE NOCASE
```

Attach `encounter_id` and `retrieval_method` to the map entry. If the case is a master header or not in the DB, set `encounter_id` to `null` and `retrieval_method` to `"unknown"`.

Special case for `058`: use the hardcoded Encounter_ID mapping from Step 5 instead of the query (since both rows return Case_Number = '058').

### Step 10: Sort and Write

Sort the complete list by `line_start` (with `null` values sorted to the end). Write to `header_map.json` with `indent=2`.

## Validation

After writing the JSON, the script should print a summary:

```
Header Map Built:
  Total entries: XXX
  Type 'case': XXX
  Type 'master': XXX
  Type 'manual': XXX
  Cases with encounter_id: XXX
  Cases without encounter_id: XXX
```

And run these sanity checks (print warnings if any fail):
1. No two entries with `type != 'manual'` should have overlapping `line_start`/`line_end` ranges.
2. Every `line_end` should be >= `line_start`.
3. For adjacent entries (sorted by `line_start`), entry N's `line_end` should equal entry N+1's `line_start` minus 1 (no gaps, no overlaps).
4. Total `type='case'` entries with non-null `encounter_id` should be >= 308.

## Non-Bullard Cases to Exclude

The Encounters table contains these non-Bullard entries that are NOT in the text file. The script should silently skip them:

```python
NON_BULLARD = {'MACK_ED_01', 'BENITEZ_MR_HM_01', 'BEARDMAN_RITA_01'}
```

## File Paths

The script should accept command-line arguments for file paths with these defaults:

```python
--text-file   default: 'Sources/bullard_vol2_raw.txt'
--db-file     default: 'ufo_matrix.db'
--output-file default: 'header_map.json'
```

## Dependencies

Standard library only: `json`, `re`, `sqlite3`, `argparse`. No external packages.

## Code Style Notes

- The user is a Python beginner. Use clear variable names, add comments explaining non-obvious logic, and avoid clever one-liners.
- Print progress messages as the script runs so the user can see what's happening.
- If any sanity check fails, print a WARNING but still write the output file. Don't crash on validation failures.
