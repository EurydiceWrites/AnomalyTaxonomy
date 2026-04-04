# SESSION RECAP — April 4, 2026 (Session 2)

**Phase:** Schema enrichment + analytical baseline
**Agent:** Eurydice + Claude Code (zealous-cori worktree)

---

## Accomplished

1. **Chapter IV typology analyzed.** Bullard's three story types extracted from Vol. 1: abduction (8-episode template, cases 32–222 + 246), teleportation (4-episode, cases 231–253), kidnapping (3-episode, cases 254–270). Case 246 dual-classification investigated — abduction governs per Bullard's explicit statement.

2. **Two analytical dimensions defined:**
   - **Case Type** — what content is present. Implemented.
   - **Conformance** — what order the episodes occur in. Implemented as transcription, computational derivation deferred.

3. **`case_type` column added and populated.** 255 abduction, 22 teleportation, 17 kidnapping, 39 unknown. Both databases.

4. **`conformance` column added and populated.** 180 orthodox (163 explicit + 17 from case 195 sub-cases), 30 deviant, 30 trivial, 3 fragmentary, 7 omit. Transcribed from Tables IV-1 and IV-3. Both databases.

5. **Test A (Case Type) — PASSED.** Binary presence/absence of motif families produces distinct signatures across the three types. Three-tier discriminator framework identified:
   - Hard discriminators (X, M, T, S, W — abduction-only)
   - Gradient discriminators (A, C — present across types at different rates)
   - Universal features (B, E, U)

6. **Test B (Conformance) — NEGATIVE RESULT.** Anchor method (MIN sequence_order of X, W, T, A) achieved 35.6% accuracy against Bullard's hand-classification. Failed because: (a) most orthodox cases have <2 anchor families present, making sequence untestable, (b) four anchors cover only four of eight episodes. Trivial category reproduced at 90%.

7. **Key insight from Test B failure:** Conformance operates on episodes (narrative scenes), not individual motif codes. The database lacks an episode layer. Episodes are groups of events forming coherent scenes. Bullard labels them with Roman numeral headers in Vol. 2. Next step: computational episode segmentation from motif clustering, validated against the book.

---

## Decisions Made

- **DEC-010:** Add case_type column (abduction/teleportation/kidnapping/unknown) from Bullard Ch. IV
- **DEC-011:** Two analytical dimensions (case_type + conformance) + Stage 1A metrics (binary presence/absence primary, proportional frequency secondary, raw counts excluded)

---

## Files Produced

- `test_results/stage_1a_results.csv` — Raw Stage 1A data (family distributions by type)
- `test_results/stage_1b_conformance_results.csv` — Raw Test B data (computed vs Bullard conformance)
- `Plans/Recaps/session_recap_2026-04-04_session2.md` — This file

## Files Modified

- `DECISION_LOG.md` — Added DEC-010, DEC-011
- `CLAUDE.md` — Added case_type to schema section
- `Plans/ROADMAP.md` — Stage 1A marked done, Test B added, medium-term updated
- `WORKFLOW_PROTOCOL.md` — Phase 4, issues log, project documents table, expanded source of truth
- `schema.sql` — Added case_type and conformance columns

## Databases Modified

- `ufo_matrix.db` — case_type populated (333 rows), conformance populated (251 rows)
- `ufo_matrix_staging.db` — case_type and conformance columns added (no Bullard data to populate)

---

## Also This Session (Session 1 — planning)

- Created `CLAUDE.md` (project root) — new sessions start with full context
- Created `Plans/ROADMAP.md` — three research north stars (R1, R2, R3) + prioritized work queue
- Updated `WORKFLOW_PROTOCOL.md` — Phase 2b → Phase 4, added issues log, project documents table
- Updated memory system — 6 files, all current

---

## Next Steps

1. **Episode segmentation** — Derive episode boundaries computationally from anchor families + cross-cutting code clustering, add episode tag to events, then retest conformance. Validate against Roman numeral headers in Vol. 2.
2. **Voice tag verification** — Rerun Ed with approved 3-tag rule
3. **ISS-001: Cache bleed** — CRITICAL, not started
