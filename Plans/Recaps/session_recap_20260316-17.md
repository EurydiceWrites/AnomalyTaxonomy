# UFO Matrix Session Recap — March 16–17, 2026
## For continuity into next session

---

## CURRENT POSITION
**Phase 1, Step 6 — Bulk ingest complete.**
310 of 311 processable cases ingested. 3 cases need re-run (061, 066, 270). 21 headerless cases deferred as `type: "manual"`. HDR-001 closed.

---

## WHAT WAS ACCOMPLISHED

### HDR-001 — CLOSED
**OCR-damaged case headers breaking bulk ingest boundaries.**

**Resolution:** Replaced runtime regex header detection with a pre-built JSON boundary map (`header_map.json`). Built `build_header_map.py` which scans `bullard_vol2_raw.txt`, applies 17 OCR corrections and 2 false positive exclusions, joins against the Encounters table, and outputs a deterministic boundary map. Modified `bulk_ingest.py`: replaced `extract_case_block()` with `slice_case_text()` using line boundaries from the map.

**17 OCR corrections applied:**

| Line | OCR Text | Correct Case | Damage Type |
|------|----------|-------------|-------------|
| 1938 | `061.` | 051 | digit swap 5→6 |
| 2218 | `62.` | 062 | missing leading zero |
| 3763 | `1 1 1 •` | 111 | spaces between chars |
| 3882 | `tt6.` | 116 | digit→letter 1→t |
| 5516 | `139.` | 138 | digit swap 8→9 |
| 6240 | `149·` | 149 | middle dot for period |
| 6819 | `163~.` | 163 | tilde after number |
| 6927 | `164·` | 164 | middle dot for period |
| 7455 | `169~` | 169 | tilde, no period |
| 7688 | `174·` | 174 | middle dot for period |
| 8186 | `190a.` | 180a | digit swap 8→9 |
| 8543 | `t86b.` | 186b | digit→letter 1→t |
| 8986 | `189b,` | 189b | comma for period |
| 9062 | `191 a.` | 191a | space in case number |
| 9655 | `1921.` | 192i | letter→digit i→1 |
| 9974 | `t93f.` | 193f | digit→letter 1→t |
| 10813 | `t99b.` | 199b | digit→letter 1→t |

**2 false positives excluded:** Line 3174 (`136.` — bibliography page range), Line 6570 (`175.` — sentence fragment).

**DB audit completed:** Full cross-reference of 335 DB case numbers vs raw text. Case 138/139 numbering confirmed against physical book (Hodges = 138, OCR 8→9 swap). Case 181a confirmed no header in physical book. Case 201 tagged as master (no extractable motifs).

**Verification:** Case 136 re-run: 151 motifs, 0 rejected — exact match to pre-HDR-001 QA.

### Bulk Ingest Results
**First run (cases 001–136):** All succeeded except 061 and 066 (empty Gemini responses).

**Second run (cases 137–270):** 173 of 174 succeeded. Case 270 failed — boundary issue (see below).

**Combined:** 310 of 311 processable cases ingested.

**Hallucination filter catches:** `U210` rejected on cases 074, 079, 080. `B805(?)` rejected on case 141. Filter working correctly.

### Scripts Created/Modified
| Script | Changes |
|--------|---------|
| `build_header_map.py` (NEW) | Pre-processing script. Scans raw text, applies OCR corrections, excludes false positives, joins against DB, outputs `header_map.json`. |
| `header_map.json` (NEW) | 341 entries: 311 case, 9 master, 21 manual. Consumed by `bulk_ingest.py`. |
| `bulk_ingest.py` | `extract_case_block()` replaced with `slice_case_text()`. Main loop iterates header map instead of Encounters table query. |

### Source Catalogue Built
Created `source_catalogue.xlsx` with 30 entries across Phases 1–6. Columns: Phase, Tier, Author, Title, Year, Type, What It Adds, Bullard Citations, Acquisition Status, Procurement Status, Format, Expert Required, Notes.

**Sources acquired this session:**
- Vallée, *Passport to Magonia* (PDF)
- Vallée, *Dimensions* (PDF)
- *Epic of Gilgamesh* — Benjamin Foster translation (PDF)
- Hopkins, *Missing Time* (acquired)
- Hopkins, *Intruders* (acquired)
- Lorenzen, *Encounters with UFO Occupants* (acquired)
- Fowler, *The Andreasson Affair* (acquired)
- Keel, *Operation Trojan Horse* (acquired)

**Total sources in hand:** 16 across Phases 1–6.

### Blog Post
`Empty_Space_v3.md` — draft complete. "When the Machine Couldn't Leave the Space Empty." About debugging the cascade error in 192g sequences 18–21 where the AI couldn't tolerate empty text fragments. Ready for final review.

### Utsuro-bune Research
Completed deep research into the 1803 Japanese hollow ship accounts. Identified 11–13 Edo-period manuscripts, key scholars (Tanaka Kazuo, Yanagita Kunio), primary English-language sources, and institutional holdings. Research document created as artifact.

---

## IMMEDIATE CLEANUP — DETAILED INSTRUCTIONS

### 1. Fix Case 270 Boundary
**Problem:** Case 270's `line_end` in `header_map.json` is 21787 (last line of file). This caused it to swallow the index, bibliography, appendices, and motif dictionary tables — 490,602 characters, 141 chunks, 0 motifs extracted.

**How to fix:**
1. Open `bullard_vol2_raw.txt` and find Case 270's header (line 12549).
2. Scan forward from line 12549 to find where Case 270's narrative ends. Look for the bibliography line (starts with `1)` or a numbered reference) followed by non-case content (index header, chapter break, etc.).
3. Record the line number of the last line of Case 270's narrative (including its bibliography).
4. Open `header_map.json`, find the entry with `"case_number": "270"`, and change `"line_end"` from 21787 to the correct value.
5. Re-run: `python build_header_map.py` OR manually edit the JSON. If manual edit, verify no overlap with the next entry.

### 2. Re-run Cases 061 and 066
**Problem:** Empty Gemini API responses (`the JSON object must be str, bytes or bytearray, not NoneType`). Transient API failures, not pipeline bugs.

**How to fix:**
```
python extract_and_insert_192g.py --case-number 061 --subject "Senora Alejandra Martinez de Pasucci"
python extract_and_insert_192g.py --case-number 066 --subject "Alejandro Hernandez Perez and son"
```
Note: `extract_and_insert_192g.py` still uses the old regex-based extraction, not the header map. These are small single-chunk cases so the regex should find them. If it fails, manually check that the case header is regex-compatible, or temporarily hardcode the line range.

**Alternative:** Wait until `extract_and_insert_192g.py` is updated to use `header_map.json`, then re-run.

### 3. Re-run Case 270
**After** fixing the boundary in Step 1:
```
python extract_and_insert_192g.py --case-number 270 --subject "Case 270 subject"
```
Look up the actual subject name from the Encounters table first:
```python
python -c "import sqlite3; c=sqlite3.connect('ufo_matrix.db'); print(c.execute(\"SELECT Encounter_ID, Case_Number FROM Encounters WHERE Case_Number='270'\").fetchone()); c.close()"
```

### 4. Spot-Check 5–10 Cases Against Physical Book
**Purpose:** Verify extraction accuracy across the full range, not just the cases we tested during development.

**Recommended cases to check:**
- Case 084 (51 motifs — large case in the middle range)
- Case 150 (Sgt. Charles Moody — well-documented case)
- Case 187a (Pascagoula — first sub-case of a complex)
- Case 210 or 211 (late simple case)
- Case 250 (teleportation category)

**What to check for each:**
1. Open the physical book to that case.
2. Count the margin codes Bullard placed.
3. Query the DB: `SELECT COUNT(*) FROM Encounter_Events WHERE Encounter_ID = ?`
4. Compare counts. If they differ, check which codes are missing or extra.
5. Spot-check 3–4 individual motif assignments: does the `source_citation` match the text next to that margin code?

### 5. Page-Range Sanity Query
**Purpose:** Verify no case's events have page stamps from a different case's section.

**Run this in Python or DB Browser:**
```sql
SELECT 
    e.Case_Number,
    MIN(ee.source_page) as min_page,
    MAX(ee.source_page) as max_page,
    COUNT(*) as event_count
FROM Encounter_Events ee
JOIN Encounters e ON ee.Encounter_ID = e.Encounter_ID
WHERE ee.source_page IS NOT NULL
GROUP BY e.Case_Number
ORDER BY e.Case_Number;
```
Review the output: each case's min/max pages should be a contiguous range that doesn't overlap with adjacent cases. If Case 050's events show pages from C-30 to C-180, something is wrong.

---

## OPEN BUGS

### CASE-270 — Boundary Extends to EOF
| Field | Details |
|-------|---------|
| Component | `header_map.json` entry for Case 270 |
| Severity | Minor — affects 1 case |
| Root Cause | Case 270 is the last case in the catalogue. `line_end` was computed as last line of file (21787), but the file contains index, bibliography, and appendix material after Case 270's narrative. |
| Fix | Find actual narrative endpoint, update `header_map.json`. |
| Status | Open |

### INGEST-061, INGEST-066 — Empty API Responses
| Field | Details |
|-------|---------|
| Component | Gemini API |
| Severity | Minor — affects 2 cases |
| Root Cause | Transient 503/empty response from Gemini. Not a pipeline bug. |
| Fix | Re-run individually. |
| Status | Open |

---

## DEFERRED ITEMS (carried forward)

| Item | Details | Original Session |
|------|---------|-----------------|
| DICT-001 spot-check | Verify 192g re-run results against A101 sub-code promotion fix | March 15 |
| QA-001 spot-check | Verify ai_justification quality on 192g re-run | March 15 |
| 192g full QA pass | Review 122-motif re-run output against original QA | March 15 |
| memory_state review | Sequences 99–100 of Case 136 — poltergeist/MIB aftereffects coded as `hypnosis`, may be `conscious` | March 15 |
| Encounter_ID ≠ Case_Number | Case 136 = Encounter_ID 137. Offset affects manual operations. | March 15 |
| 21 headerless cases | 181a, 195a–q, 199_1/2/3 — tagged `type: "manual"` in header map. Need manual boundary assignment or parent-case extraction. | March 16 |
| 42 non-Bullard retrieval methods | `memory_retrieval_method` populated for Bullard cases but 42 non-Bullard entries (Mack, Benitez, etc.) left as `unknown`. | March 15 |
| Pre-run CSV export | Add timestamped CSV export of Encounter_Events before any re-run, to preserve old data for comparison. | March 17 |
| Source catalogue procurement | Update Hopkins, Intruders, Lorenzen Encounters, Fowler, Keel from "Sourced — pending acquisition" to "In evidence — queued". | March 17 |

---

## KEY DESIGN DECISIONS MADE (this session)

1. **Header map replaces runtime regex.** All case boundaries are pre-computed and stored in `header_map.json`. No regex runs during bulk ingest.

2. **OCR corrections are hardcoded, not heuristic.** The 17 corrections were verified against the physical book. No "smart" OCR-damage guesser — explicit corrections only.

3. **Case 201 is a master header.** Despite having an Encounter_ID (260), it contains no extractable motifs. Tagged as `type: "master"`.

4. **Case 195 is one continuous narrative.** 17 sub-cases in DB (195a–q) but no individual headers in text. Will require manual boundary assignment or single-block extraction.

5. **Phase 6 sources require expert collaboration.** Ancient texts (Vedic, Sumerian, Biblical) are catalogued but will not be ingested without subject-matter specialists confirming the translation layer.

6. **Shadow extraction pass deferred to post-Phase 2b.** Re-running Bullard to find motifs he didn't code is valuable but premature until the engine's accuracy is measured against original source documents.

---

## TOMORROW'S PRIORITIES
1. Fix Case 270 boundary.
2. Re-run 061, 066, 270.
3. Spot-check 5 cases against physical book.
4. Page-range sanity query.
5. Begin Phase 2b planning if cleanup is clean.
