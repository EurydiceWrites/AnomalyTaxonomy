# SESSION RECAP — April 4, 2026 (Session 3)

**Phase:** Stage 1B — Conformance analysis + episode segmentation
**Agent:** Eurydice
**Author:** eurydicewrites

---

## Accomplished

### 1. Episode segmentation algorithm designed and tested

Built a walk-and-inherit algorithm to assign every event in a case to an episode using anchor families, then check whether episodes appear in Bullard's prescribed order.

**Algorithm (final, v4):**
1. Read the event list for a case, ordered by sequence_order
2. Extract the first letter of each motif code (the family)
3. Flag anchors: X -> Episode 2 (Examination), W -> Episode 5 (Journey), T -> Episode 6 (Theophany), A -> Episode 8 (Aftermath) -- **excluding A115, A116, A220, A221** which are treated as non-anchors
4. Walk top to bottom: before the first anchor = Episode 1 (Capture); each anchor sets the current episode; non-anchor events inherit from the last anchor
5. Read the episode labels in order; if ascending -> orthodox; if not -> deviant; if only one distinct episode -> trivial

### 2. Four iterations tested

| Version | Anchors | Overall | Orthodox | Deviant | Trivial |
|---------|---------|---------|----------|---------|---------|
| v1 (prior) | X, W, T, A (position check only) | 35.6% | -- | -- | -- |
| v2 | X, W, T, A (walk-and-inherit) | 55.6% | 60.9% | 26.7% | 51.6% |
| v3 | X, W, T (A removed entirely) | 54.7% | 58.1% | 16.7% | 71.0% |
| v4 | X, W, T, A (minus 4 noisy codes) | 56.8% | 63.1% | 20.0% | 54.8% |

### 3. A-code noise diagnosed and fixed

Analysis of the 38 false-deviant cases in v2 revealed that A codes appearing before X codes were the primary source of error. Four specific A codes accounted for the majority of early-appearing noise:

- **A115** (nightmares/abduction dreams): 62% noise rate -- mentioned early as what prompted the investigation
- **A116** (memory return): 57% noise -- hypnotic memory recovery is methodology context
- **A220** (other sightings): 61% noise -- prior UFO sightings mentioned as background
- **A221** (other encounters): 55% noise -- same as A220

These codes describe **investigation context** (why the case came to light), not the **Aftermath episode** (what happened after the abduction). Excluding them from anchor status (v4) produced the highest orthodox accuracy (63.1%).

**Decision: DEC-012** -- A codes are anchors for Episode 8 (Aftermath), except A115, A116, A220, and A221, which are treated as non-anchors. Justified by content analysis (investigation context vs episode content) and positional data (21.6% early-appearance rate vs 8.0% for other A codes).

### 4. C and M codes analyzed -- null result for Conference anchor

Investigated whether C (communication) and M (messages) could serve as anchors for Episode 3 (Conference).

**Findings:**
- C+M codes are spread across the second half of the narrative (77% in the 50-100% range), not clustered in one episode region
- C and M behave differently: C peaks at 60-70%, M peaks at 90-100%
- Only 29 cases have a detectable cluster of 3+ isolated C/M codes (close to Bullard's restrictive Conference count of 23, but too thin to anchor reliably)
- Communication happens throughout the later episodes (Conference, Tour, Journey, Theophany), not just during Conference

**Conclusion:** Conference cannot be reliably detected from motif family codes alone. It is defined by narrative context -- the manner of communication, not the presence of communication codes. Documented as a null result.

### 5. Major finding: family distribution peaks independently recover Bullard's episode sequence

Analysis of where each motif family peaks in the narrative sequence revealed that the families sort themselves into Bullard's prescribed episode order without being told to:

| Family | Peak position | Maps to |
|--------|--------------|---------|
| E (effects) | 0-10% | Capture -- environmental disturbances open the narrative |
| B (beings) | 20-30% | Capture/early encounter -- beings appear |
| X (examination) | 50-60% | Examination -- the center of the story |
| C (communication) | 60-70% | Conference -- communication rises after the exam |
| M (messages) | 90-100% | Late narrative -- major messages cluster at the end |
| A (aftereffects) | 90-100% | Aftermath -- consequences close the narrative |

**Significance:** This is independent computational evidence that Bullard's episode structure exists in the data, not just in his interpretation. The positional distributions of motif families recover the episode sequence from 5,500+ events across 254 cases without any episode labels, headers, or structural guidance.

**Limitation:** Bullard assigned both the motif codes and proposed the episode structure. Full independence requires showing the same positional pattern in non-Bullard coded data (Phase 2b extraction engine output) and non-Bullard source material (Phase 4 Mack cases).

---

## Decisions Made

| # | Decision | Status |
|---|----------|--------|
| DEC-012 | A codes are anchors except A115, A116, A220, A221 (investigation context, not episode content) | IMPLEMENTED (v4) |
| -- | C and M codes are not anchors for Conference | DOCUMENTED (null result) |
| -- | v4 algorithm is the current baseline | ACTIVE |

---

## Files Produced

- `test_results/stage_1b_v2_episode_assignments.csv` -- Event-level episode assignments (v2)
- `test_results/stage_1b_v2_conformance_results.csv` -- Case-level conformance comparison (v2)
- `test_results/stage_1b_v2_summary.md` -- v2 summary
- `test_results/stage_1b_v3_episode_assignments.csv` -- v3 data
- `test_results/stage_1b_v3_conformance_results.csv` -- v3 data
- `test_results/stage_1b_v3_summary.md` -- v3 summary
- `test_results/stage_1b_v4_episode_assignments.csv` -- v4 data
- `test_results/stage_1b_v4_conformance_results.csv` -- v4 data
- `test_results/stage_1b_v4_summary.md` -- v4 summary

---

## Research Implications

### For R1 (Case Type Signature Analysis)
The family distribution finding is direct evidence for R1. Bullard's classification system reflects a real structural pattern in the narratives. The motif families independently sort into his prescribed episode order.

### For R2 (Cross-Source Comparison)
The positional pattern provides a baseline. When Mack and Hopkins cases are processed, comparing their family distributions against this baseline will reveal whether different investigators produce different narrative shapes -- or whether the shape is stable across sources.

### For the observer effect paper
The A-code noise finding connects to the observer effect: codes like A115 (nightmares) and A116 (memory return) describe the investigation process itself, not the experience. Their presence in the margin codes reflects Bullard's decision to document investigation context alongside narrative content -- an observer's fingerprint on the data.

---

## Next Steps

1. Update `DECISION_LOG.md` with DEC-012
2. Update `ROADMAP.md` -- Stage 1B conformance marked with current results, family distribution finding noted
3. Consider a visualization of the family distribution peaks for the dashboard or portfolio
4. Future iteration: test v4 algorithm on Phase 2b extraction engine output (AI-coded events) to check if the pattern holds without Bullard's hand-coding
5. Phase 4 Mack cases will provide the strongest independence test
