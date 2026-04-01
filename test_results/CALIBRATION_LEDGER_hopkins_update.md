## Hopkins Source Cases — Bullard Voice Baseline (Test A)
**Date validated:** April 1, 2026
**Profile:** baseline_test
**Extraction model:** Gemini 2.5 Pro
**Validated by:** Shawna (human reviewer) + Eurydice (triage instrument)

### Case 069 — Howard Rich
| Metric | Value |
|--------|-------|
| Fidelity | 72.2% (13/18) |
| Genuine Alternates | 5 |
| True Misses | 0 |
| Detection | 100% (18/18) |
| AI Extras | 6 |
**Notes:** All 5 divergences confirmed as genuine alternates. Zero true misses. A102 (energy drain) coded as ANOMALY — engine read dictionary definition too literally. Smallest case in Hopkins set (18 GT events, single chunk).

### Case 084 — Steven Kilburn
| Metric | Value |
|--------|-------|
| Fidelity | 88.5% (46/52) |
| Genuine Alternates | 4 |
| True Misses | 2 |
| Detection | 96.2% (50/52) |
| AI Extras | 23 |
**Notes:** Strongest fidelity in the Hopkins set. True misses: E200 (time lapse), E201 (doorway amnesia). E201 is a systematic failure mode — see below.

### Case 180a — Philip Osborne (childhood, Smoky Mountains)
| Metric | Value |
|--------|-------|
| Fidelity | 62.5% (10/16) |
| Genuine Alternates | 3 |
| True Misses | 3 |
| Detection | 81.3% (13/16) |
| AI Extras | 5 |
**Notes:** True misses: A110 (anxious without knowing why), E201 (doorway amnesia), U202 (examination room). E201 miss confirmed — systematic pattern. Lowest detection in Hopkins set after 180b.

### Case 180b — Philip Osborne (age 20, Pittsburgh)
| Metric | Value |
|--------|-------|
| Fidelity | 66.7% (12/18) |
| Genuine Alternates | 2 |
| True Misses | 4 |
| Detection | 77.8% (14/18) |
| AI Extras | 3 |
**Notes:** True misses: E201 (doorway amnesia), A225 (further abductions), E200×2 (double time lapse on same line). E200 double-miss is a mechanical failure — engine extracted only one motif when two shared a sentence. GT17/GT18 citations may be cross-contaminated from 181a (female pronouns in male witness case) — verify against physical book. E201 miss confirmed — systematic pattern.

### Case 181a — Virginia Horton (childhood, Manitoba)
| Metric | Value |
|--------|-------|
| Fidelity | 77.1% (27/35) |
| Genuine Alternates | 7 |
| True Misses | 1 |
| Detection | 97.1% (34/35) |
| AI Extras | 8 |
**Notes:** Largest Hopkins sub-encounter (35 GT events). 13-match consecutive run through B-family being description codes (GT12–GT24) — strongest sequential match streak in calibration set. Single true miss: B800 (leader). Engine coded B900 (friendly) from same passage but missed the leadership designation.

### Case 181b — Virginia Horton (childhood, Alsace)
| Metric | Value |
|--------|-------|
| Fidelity | 53.8% (7/13) |
| Genuine Alternates | 6 |
| True Misses | 0 |
| Detection | 100% (13/13) |
| AI Extras | 10 |
**Notes:** Lowest fidelity in calibration set but 100% detection — engine saw every event, routed 6 to adjacent codes. Structurally atypical case (celebration, girl-talk, deer apparition). Engine over-coded heavily (23 AI events vs 13 GT). AI compensates for structural uncertainty by coding more, not less.

---

## Systematic Failure Mode: E201 (Doorway Amnesia)

**Confirmed in:** 084, 180a, 180b
**Pattern:** Engine codes the destination (X155 table, U211 domed room, U230 sourceless light) but does not recognize the memory gap in the transition. Phrases like "found himself reclining" or "found herself suddenly inside" signal E201 but the engine reads them as descriptions of the new location, not as evidence of missing memory.
**Recommendation:** Candidate for prompt rule — instruct the engine to code E201 when a witness appears in a new location with no description of how they arrived.

## Mechanical Failure Mode: Single-motif-per-sentence

**Confirmed in:** 180b (GT17, GT18)
**Pattern:** When Bullard codes two motifs from the same sentence (E200, E201 on one line), the engine sometimes extracts only one.
**Status:** Needs further observation before rule design.
