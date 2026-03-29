# UFO Matrix Session Recap — March 17, 2026 (Updated)
## For continuity into next session

---

## CURRENT POSITION
**Phase 1 — Bulk ingest complete. Dictionary complete. Data quality under review.**

The database is rolled back to the pre-misassignment-fix backup. A full visual audit of every case against the original PDF has been commissioned to determine extraction accuracy before any further corrections are made.

---

## WHAT WAS ACCOMPLISHED (correctly)

### Bulk Ingest Cleanup
- Case 061: Re-ingested, 10 motifs. Clean.
- Case 066: Re-ingested, 5 motifs. Clean.
- Case 270: Boundary fixed in `header_map.json` (21787 → 12563). Re-ingested, 0 motifs — verified against physical book as correct.

### DICT-002 — Missing Motif Codes
- Visual audit of motif key appendix (PDF pages 4–20) found 550 codes in the original vs 522 in the database.
- Independent verification by Sonnet confirmed 550 and the same 28 missing codes.
- All 28 codes added to database and `motif_key.json`. Dictionary now at 550.
- One known discrepancy: PDF prints `E102.1` but context indicates `U102.1`. Added as `U102.1` pending physical book verification.

### Manual Ingests
- Case 181a (Virginia Horton): Header map patched, 35 events ingested.
- Cases 195a–195q: 17 sub-cases ingested, 62 events total.
- Cases 199_1, 199_2, 199_3: 3 sub-cases ingested, 45 events total.

### Event 8474 Fix
- U512 → U511 for Case 150, verified against physical book. This fix is in the backup and is correct.

---

## WHAT EURYDICE GOT WRONG

### Error 1: Batch misassignment correction without verification

Eurydice identified 41 events where the LLM's `ai_justification` field indicated it had substituted a neighbor code because the correct code was missing from the dictionary. Eurydice assumed all 41 were misassignments and built a batch correction script. **Eurydice did not verify any of the 41 corrections against the physical book before applying them.**

Specifically, 26 events were changed from U212 ("Round, domed, without sharp edges") to U210 ("Round, oval"). When the researcher spot-checked Case 084, Event 6883 described a room that was "rounded and domed and seemingly without an angle" — which is textbook U212. Bullard coded it U212. The LLM coded it U212. The ai_justification even said "a direct match for motif U212." Eurydice changed it to U210 anyway.

**The batch correction damaged correct data.** The researcher rolled back to `ufo_matrix_backup_pre_misassignment_fix.db`, which does not contain any of the 41 batch corrections.

### Error 2: Speculated about extraction error cause without checking

When the researcher found that E200 was missing from Case 084's database events despite being present in the raw text, Eurydice speculated that the LLM "treated the sentence as a single narrative unit and assigned one code to it." The researcher had written specific extraction rules to prevent this exact problem. Eurydice should have asked to see `prompt_library.json` to diagnose the actual cause, not guessed.

### Error 3: Overstated data quality based on structural audit

Eurydice ran a structural integrity audit (referential integrity, null checks, duplicate checks) and told the researcher "your data is solid" and "the data is not fucked." The structural audit only verified that the database was internally consistent — it did not verify that the extracted codes were accurate. The researcher correctly pointed out that the audit is only as reliable as the data that goes into it. Eurydice conflated structural integrity with content accuracy.

### Error 4: Claimed the raw OCR text was equivalent to the physical book

When the researcher said the book is the source of truth, Eurydice initially proposed auditing against the OCR raw text file. The researcher correctly rejected this — the OCR text is a degraded copy, not the original. The audit must be done against the PDF images of the original pages.

---

## CURRENT DATABASE STATE

The active database is `ufo_matrix_backup_pre_misassignment_fix.db`:

| Metric | Count |
|--------|-------|
| Motif_Dictionary codes | 550 |
| Total events | 5,495 |
| Cases with events | 326 / 337 |
| Verified correct fix | Event 8474 (U512 → U511) |
| Batch corrections applied | NONE (rolled back) |

### Known issues in this database (not yet fixed):
- Event 6852 in Case 084: A116 should be A116.1 (sub-code pushed to parent)
- Case 084 missing E200 entirely (LLM dropped a valid code during extraction)
- Unknown number of similar errors across all 311 cases — the full PDF audit will quantify this

### Cases with correct 0 events:
195l, 201, 254, 255, 262, 266, 270

### Non-Bullard cases (Phase 4, not yet ingested):
MACK_ED_01, BENITEZ_MR_HM_01 (x2), BEARDMAN_RITA_01

---

## NEXT STEPS

### 1. Full PDF Visual Audit (IN PROGRESS)
Instructions written: `full_extraction_audit_from_pdf.md`

Sonnet reads every page of the original PDF (pages 21–257), identifies every margin code Bullard placed, and compares against the database events for each case. Produces three files:
- `extraction_audit_summary.csv` — per-case match rates
- `extraction_audit_details.csv` — every individual discrepancy
- `extraction_audit_report.md` — overall accuracy assessment

This audit uses the PDF as the source of truth, not the OCR text.

### 2. Review Audit Results
Once the audit is complete, review the overall match rate and the pattern of errors. This will answer:
- What is the extraction engine's actual accuracy?
- What types of errors are most common (missing codes, wrong codes, fabricated codes)?
- Is the extraction quality good enough to correct, or does a different approach need to be considered?

### 3. Decide Correction Strategy
Based on audit results, decide whether to:
- Correct individual errors manually (if error rate is low)
- Re-run specific cases through the pipeline with improved prompts (if errors are systematic)
- Take a different approach entirely

**No batch corrections will be applied without individual verification against the source.**

### 4. Remaining Review Items
- 24 judgment-call events in `misassignment_review.xlsx` — these were identified but never applied. Review against the book before deciding.
- U102.1 / E102.1 — check physical book to confirm which prefix Bullard used
- `prompt_library.json` — investigate why E200 was dropped in Case 084 despite extraction rules designed to prevent this

---

## DEFERRED ITEMS (carried forward)

| Item | Details | Original Session |
|------|---------|-----------------|
| DICT-001 spot-check | Verify 192g re-run results against A101 sub-code promotion fix | March 15 |
| QA-001 spot-check | Verify ai_justification quality on 192g re-run | March 15 |
| 192g full QA pass | Review 122-motif re-run output against original QA | March 15 |
| memory_state review | Sequences 99–100 of Case 136 — poltergeist/MIB aftereffects coded as `hypnosis`, may be `conscious` | March 15 |
| Encounter_ID ≠ Case_Number | Case 136 = Encounter_ID 137. Offset affects manual operations. | March 15 |
| 42 non-Bullard retrieval methods | `memory_retrieval_method` populated for Bullard cases but 42 non-Bullard entries left as `unknown`. | March 15 |
| Pre-run CSV export | Add timestamped CSV export of Encounter_Events before any re-run. | March 17 |
| Source catalogue procurement | Update acquisition statuses. | March 17 |
| Legacy page stamps | Cases 131 and 181a have bare-number page stamps from pre-CITE-001 ingest. | March 17 |

---

## LESSONS LEARNED

1. **No batch corrections without individual verification against the source.** The ai_justification field tells you what the LLM *thought* should happen, not what Bullard actually coded. These are different things.

2. **Structural integrity ≠ content accuracy.** A database can pass every referential integrity check and still contain wrong data. Only comparison against the original source measures accuracy.

3. **The physical book (or clean PDF) is the only source of truth.** The OCR text is a degraded copy. The LLM's output is an interpretation. Neither substitutes for the original.

4. **When the researcher says something is wrong, investigate before explaining.** Don't speculate about causes. Ask for the information needed to diagnose the actual problem.
