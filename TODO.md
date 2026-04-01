# Mack-Bullard UFO Matrix — Master TODO

**Last updated:** 2026-03-29 (evening session)
**Maintained by:** Eurydice chat — update after each session

---

## PIPELINE BUILD (Phase 2b → Generalized Ingestion Engine)

- [ ] Fix source page detection in `extract_pdf_text()` — handoff sent to Claude Code
- [ ] Connect metadata scan (Step 1) to extraction engine (Step 3)
- [ ] Build wrapper script — single CLI entry point chaining Steps 0–4
- [ ] Test pipeline on Hopkins source text (Test B, Case 084 — pp. 50–88)
- [ ] Add model tracking to extraction output (`model_name`, `model_version`)
- [ ] Add `Gender` column to Subjects table in both `ufo_matrix.db` and `ufo_matrix_staging.db`, and add to Subjects INSERT in `load_to_database()`

## CALIBRATION & DATA WORK

- [ ] Populate 205 `unknown` rows in `Encounters.memory_retrieval_method` (book work — requires physical Bullard Vol. 2)
- [ ] Awaiting Bullard reply on E120 duplicate coding methodology (blocked — external)
- [ ] Select and run additional calibration cases from original investigator source books
- [ ] E200 (time lapse / implicit memory gap) — engine consistently misses these; needs prompt rule fix
- [ ] Deduplication weakness — engine produces duplicate codes for same narrative passage; consistent across all three calibration cases

### Calibration Ledger (completed cases)

| Case | Investigator | GT | Fidelity | Detection | AI Extras |
|------|-------------|-----|----------|-----------|-----------|
| 093  | Bryant/MUFON | 24 | 66.7% | 95.8% | 5 |
| 192g | Andreasson/Mack | 121 | 78.5% | 88.4% | 58 |
| 084  | Kilburn/Hopkins | 52 | 88.5% | 96.2% | 23 |

## WRITING & OUTREACH

- [ ] Follow-up letter to Bullard — four-part structure agreed (warm opener referencing his "Orpheus" line, 97% parsing result, Phase 2b benchmarking work, horizon gesture toward Mack comparison)
- [ ] "The AI Never Holds the Pen" — bridging paragraph on narrowing the probabilistic window as core hallucination risk management principle
- [ ] LinkedIn post — material identified from governance concepts session (generative vs. reasoning model deployment modes, extract→classify→generate pipeline architecture)

## REPO CLEANUP

- [ ] Remove `test_results/validated/test_run.xlsx` from git (acceptance criteria test file, no longer needed)

---

## COMPLETED (for reference)

- [x] Phase 1 complete — 270 cases, 5,570+ events, 550-code dictionary, 97% parse accuracy
- [x] Multi-agent workflow protocol formalized (`WORKFLOW_PROTOCOL.md`)
- [x] Calibration ledger created (`CALIBRATION_LEDGER.md`)
- [x] QA triage tool built and improved with hybrid matcher (`qa_triage.py`)
- [x] CaseMetadata Pydantic model with Literal constraints
- [x] `memory_retrieval_method` column added to Encounters table
- [x] `not_applicable` value added to all retrieval method Literal constraints
- [x] Staging database created (`ufo_matrix_staging.db`)
- [x] `llm_bridge.py` refactored — `extract_narrative()` + `load_to_database()` + backward-compatible `process_narrative()`
- [x] `hypnosis_used` removed from CaseMetadata (redundant)
- [x] Schema audit — all three layers reconciled (database, Pydantic, INSERT statements)
- [x] `pipeline_ingest.py` built — Steps 0 and 1 (PDF extraction + metadata scan)
- [x] Three input paths working: digital PDF, scanned PDF (Gemini OCR fallback), plain text (`--text`)
- [x] Pipeline validated on Gilgamesh (literary) and Hopkins Case 084 (investigation)
- [x] Streamlit import removed from `llm_bridge.py`
- [x] Test results folder structure created (`test_results/raw/`, `test_results/validated/`)
- [x] Git pipeline learned and first PR merged
- [x] Source PDFs removed from git tracking (`.gitignore`)
