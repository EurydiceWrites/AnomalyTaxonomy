# Session Recap — March 29, 2026
**Agent:** Claude Code (brave-davinci worktree)
**Duration:** Full day session

---

## What We Did

### 1. llm_bridge.py — CaseMetadata Pydantic Model
- Removed accidental `from streamlit import cursor` import (would crash if streamlit not installed)
- Added `CaseMetadata` Pydantic model with two Literal-constrained fields:
  - `hypnosis_used: Literal["YES", "NO"]`
  - `memory_retrieval_method: Literal["conscious", "hypnosis", "altered", "mixed", "unknown"]`
- Replaced raw boolean `hypnosis_used` logic with validated `CaseMetadata` instance in `process_narrative()`
- Decision authority: Eurydice session, March 29 morning

### 2. Phase 2b Blind Calibration — Three Cases
Ran `phase2_test.py` against Bullard's ground truth on three cases:

| Case | GT | Fidelity | Detection | AI Extras |
|------|----|----------|-----------|-----------|
| 093 (Bryant/MUFON) | 24 | 66.7% | 95.8% | 5 |
| 192g (Andreasson/Mack) | 121 | 78.5% | 88.4% | 58 |
| 084 (Kilburn/Hopkins) | 52 | 88.5% | 96.2% | 23 |

- Case 084 is the strongest result to date
- Primary weakness across all cases: AI over-extracts (too many extras)
- E200 (time lapse/memory gap) is a consistent miss — AI doesn't recognize implicit temporal discontinuities

### 3. QA Triage Tool
- Added `qa_triage.py` to project root
- Takes a phase2 JSON result file + ufo_matrix.db and produces a formatted .xlsx for human review
- Three sheets: main comparison (colour-coded), Summary, Miss Analysis
- Ran triage on cases 084 and 192g

### 4. Project Infrastructure
- Created `test_results/Raw/` and `test_results/Validated/` folder structure
- Updated `phase2_test.py` to write output to `test_results/raw/` automatically
- Updated `CALIBRATION_LEDGER.md` with validated case 084 entry

### 5. Git / Version Control — Big Learning Day
- Learned the full git pipeline: **local files → staging → git folder → GitHub**
- Committed all accumulated work (hadn't committed since Ed's case)
- Removed PDFs and source documents from git tracking (added to .gitignore)
- Created and merged a Pull Request from `claude/brave-davinci` → `main`
- Ran `git pull` to sync the merged changes back to local PC

---

## Files Changed
- `llm_bridge.py` — CaseMetadata model
- `phase2_test.py` — output path + os import
- `qa_triage.py` — new file
- `test_results/CALIBRATION_LEDGER.md` — case 084 entry added
- `test_results/Raw/` — results for 084, 093, 192g
- `test_results/Validated/` — triage xlsx for 084 and 192g
- `.gitignore` — added Sources/, Training/, old scripts/, backups, temp files

---

## Key Decisions
- Source PDFs and research documents should NOT be tracked in git (too large, copyrighted)
- `old scripts for testing and other stuff/` removed from git tracking
- Calibration ledger is the authoritative record of validated results — raw JSON stats are not comparable

---

## Open Items
- E200 miss pattern needs a prompt fix — AI does not recognize implicit memory gaps as temporal discontinuities
- Deduplication weakness (duplicate codes for same quote) is consistent across cases
- PR merged but `test_results/validated/test_run.xlsx` (acceptance criteria test file) still in repo — can be cleaned up
