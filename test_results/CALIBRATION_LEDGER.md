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

## Validated Results

| Case | Profile | Date | GT Count | Fidelity | Genuine Alt | True Miss | Detection | AI Extras | Notes |
|------|---------|------|----------|----------|-------------|-----------|-----------|-----------|-------|
| 093 | baseline_test | 2026-03-29 | 24 | 66.7% (16/24) | 7 | 1 | 95.8% (23/24) | 5 | Only true miss: B225 (thin bodies). Dual-coding pattern in 3 alternates (E320→B610, B625→E106, E213→X205). |
| 192g | baseline_test | 2026-03-29 | 121 | 78.5% (95/121) | 13 | 14 | 88.4% (107/121) | 58 | 14 AI errors confirmed. 8 sequence-order flags noted. E120 duplicate coding persists (9x vs Bullard's 1x — blocked on Bullard reply). |
| 084 | baseline_test | 2026-03-29 | 52 | 88.5% (46/52) | 4 | 2 | 96.2% (50/52) | 23 | Both true misses are E200 (implicit memory gaps/time lapse). 3 ANOMALY flags confirmed genuine gaps (tubelike fingers, almond-shaped feet, luminous egg-shaped saucer). 3 duplicate codes noted. Strongest fidelity across all calibration cases. First Hopkins case tested. |

---

---

### Case 084 — Steve Kilburn (Hopkins)
Profile: baseline_test
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

## Notes on Methodology

- **Validation process:** Raw results from `phase2_blind_test.py` → QA triage via `qa_triage.py` → human review of triage spreadsheet → confirmed genuine alternates recorded here.
- **Genuine alternate criteria:** Text overlap between Bullard's source citation and AI's sentence fragment (minimum 2 shared content words after stopword removal). May cross motif families.
- **AI Extras after validation:** Raw AI extra count minus genuine alternates that were reclassified from the extra pool.
- **All numbers are triage-to-triage.** Never compare against raw JSON stats.
- **Triage algorithm v2 (2026-03-29):** Hybrid citation-aware matching for repeated codes (text overlap primary, sequence proximity tiebreaker). All results from this date forward use v2.
