# Calibration Ledger — Mack-Bullard UFO Matrix

**Purpose:** Permanent record of all validated Phase 2b calibration results.  
**Rule:** Only human-validated numbers go here. Raw phase2 JSON results are input data, not ledger entries.

---

## How to Read This Ledger

| Column | Definition |
|--------|------------|
| **Fidelity** | Exact match rate — AI chose the same code as Bullard |
| **Genuine Alt** | AI saw the event but chose a different code (confirmed by text overlap) |
| **True Miss** | AI did not detect the event at all |
| **Detection** | (Fidelity + Genuine Alt) / Ground Truth — how many events the engine saw |
| **AI Extras** | Codes AI assigned that Bullard did not (after removing genuine alternates from extra pool) |

---

## Validated Results — Gemini (STATUS: superseded)

| Case | Profile | Date | GT Count | Fidelity | Genuine Alt | True Miss | Detection | AI Extras | Notes | Status |
|------|---------|------|----------|----------|-------------|-----------|-----------|-----------|-------|--------|
| 093 | baseline_test | 2026-03-29 | 24 | 66.7% (16/24) | 7 | 1 | 95.8% (23/24) | 5 | Only true miss: B225 (thin bodies). Dual-coding pattern in 3 alternates (E320→B610, B625→E106, E213→X205). | superseded |
| 192g | baseline_test | 2026-03-29 | 121 | 78.5% (95/121) | 13 | 14 | 88.4% (107/121) | 58 | 14 AI errors confirmed. 8 sequence-order flags noted. E120 duplicate coding persists (9x vs Bullard's 1x — blocked on Bullard reply). | superseded |
| 084 | baseline_test | 2026-03-29 | 52 | 88.5% (46/52) | 4 | 2 | 96.2% (50/52) | 23 | Both true misses are E200 (implicit memory gaps/time lapse). 3 ANOMALY flags confirmed genuine gaps (tubelike fingers, almond-shaped feet, luminous egg-shaped saucer). 3 duplicate codes noted. Strongest fidelity across all calibration cases. First Hopkins case tested. | superseded |

---

---

### Case 084 — Steve Kilburn (Hopkins) — STATUS: superseded
Profile: baseline_test (Gemini 3.1 Pro)
Date validated: 2026-03-29

| Metric             | Value         |
|--------------------|---------------|
| Ground Truth       | 52            |
| Fidelity           | 88.5% (46/52) |
| Genuine Alternates | 4             |
| True Misses        | 2             |
| Detection Rate     | 96.2% (50/52) |
| AI Extras          | 23            |

Notes:
- Both true misses are E200 (time lapse) — engine fails to recognize implicit memory gaps as temporal discontinuities
- 3 ANOMALY flags confirmed as genuine dictionary gaps (tubelike fingers, almond-shaped feet, luminous egg-shaped saucer)
- 3 duplicate codes identified (deduplication weakness consistent with 192g)
- Strongest fidelity result across all three calibration cases
- First Hopkins-investigated case tested

Decision authority: Eurydice session, 2026-03-29 evening

---

## Claude Opus 4.6 Baseline — Hopkins Source Cases (Bullard Voice)

Model: claude-opus-4-6
Profile: baseline_test (preamble ON, narrative_context_rules ON)
Date: April 1, 2026
Ground truth correction: Case 084 phantom E200 at seq 52 deleted (parser contamination). GT revised from 52 to 51.

### Case 084 — Steven Kilburn

| Metric | Value |
|--------|-------|
| Fidelity | 84.3% (43/51) |
| Genuine Alternates | 4 |
| True Misses | 4 (B254, E200, X100, X200) |
| Detection | 92.2% (47/51) |
| AI Extras | 17 |

### Case 069 — Howard Rich

| Metric | Value |
|--------|-------|
| Fidelity | 77.8% (14/18) |
| Genuine Alternates | 4 |
| True Misses | 0 |
| Detection | 100% (18/18) |
| AI Extras | 8 |

### Case 180a — Philip Osborne (childhood)

| Metric | Value |
|--------|-------|
| Fidelity | 68.8% (11/16) |
| Genuine Alternates | 3 |
| True Misses | 2 (E200, A110) |
| Detection | 87.5% (14/16) |
| AI Extras | 7 |

### Case 180b — Philip Osborne (Pittsburgh)

| Metric | Value |
|--------|-------|
| Fidelity | 72.2% (13/18) |
| Genuine Alternates | 2 |
| True Misses | 3 (U230, E200, E200) |
| Detection | 83.3% (15/18) |
| AI Extras | 5 |

### Case 181a — Virginia Horton (Manitoba)

| Metric | Value |
|--------|-------|
| Fidelity | 85.7% (30/35) |
| Genuine Alternates | 5 |
| True Misses | 0 |
| Detection | 100% (35/35) |
| AI Extras | 8 |

### Case 181b — Virginia Horton (Alsace)

| Metric | Value |
|--------|-------|
| Fidelity | 53.8% (7/13) |
| Genuine Alternates | 5 |
| True Misses | 1 (B900) |
| Detection | 92.3% (12/13) |
| AI Extras | 12 |

### Aggregate

| Metric | Value |
|--------|-------|
| Total GT Events | 151 |
| Detection | 93.4% (141/151) |
| True Misses | 10 |
| Documented blind spots | E200 (time lapse at narrative boundaries), single-motif-per-sentence on dense passages, vague retrospective language |

---

## Notes on Methodology

- **Validation process:** Raw results from `phase2_blind_test.py` → QA triage via `qa_triage.py` → human review of triage spreadsheet → confirmed genuine alternates recorded here.
- **Genuine alternate criteria:** Text overlap between Bullard's source citation and AI's sentence fragment (minimum 2 shared content words after stopword removal). May cross motif families.
- **AI Extras after validation:** Raw AI extra count minus genuine alternates that were reclassified from the extra pool.
- **All numbers are triage-to-triage.** Never compare against raw JSON stats.
- **Triage algorithm v2 (2026-03-29):** Hybrid citation-aware matching for repeated codes (text overlap primary, sequence proximity tiebreaker). All results from this date forward use v2.
