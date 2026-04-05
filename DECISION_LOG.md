# Decision Log — Mack-Bullard UFO Matrix

**Purpose:** Permanent record of architectural, methodological, and design decisions.
Every entry traces to a specific rationale and evidence base. Decisions are never deleted — they are superseded with a pointer to the replacement.

---

## How to Read This Log

| Field | Definition |
|-------|------------|
| **ID** | Sequential, never reused (DEC-001, DEC-002, ...) |
| **Date** | When the decision was made |
| **Decision** | What was decided |
| **Rationale** | Why — the evidence or reasoning |
| **Evidence** | Test runs, comparisons, or data that informed it |
| **Status** | `ACTIVE`, `SUPERSEDED (by DEC-XXX)`, `REVERSED` |
| **Decided in** | Where the decision was made (Eurydice, Claude Code, human review) |

---

## Decisions

### DEC-001: Switch extraction model from Gemini 3.1 Pro to Claude Opus 4.6
- **Date:** 2026-04-01
- **Decision:** Replace Gemini 3.1 Pro with Claude Opus 4.6 as the primary extraction model.
- **Rationale:** Claude Opus 4.6 provides comparable or superior extraction quality with better prompt caching economics (Anthropic's ephemeral cache vs Gemini's file upload cache).
- **Evidence:** 6-case Hopkins baseline (TEST-001 through TEST-006). Aggregate detection: 93.4% across 151 GT events.
- **Status:** ACTIVE
- **Decided in:** Eurydice chat, 2026-04-01

---

### DEC-002: Build model-agnostic LLM bridge
- **Date:** 2026-04-01
- **Decision:** Consolidate all LLM communication into `llm_bridge.py` so any script can call any model through a single `--model` argument.
- **Rationale:** Avoids duplicating scripts per model. Changing the extraction model should require changing one argument, not rewriting code.
- **Evidence:** Prior state had Gemini API calls scattered across 5 files with independent prompt assembly (caused the narrative_context_rules loading bug).
- **Status:** ACTIVE
- **Decided in:** Eurydice chat, 2026-04-01

---

### DEC-003: Use 1-hour TTL for Claude prompt caching
- **Date:** 2026-04-01
- **Decision:** Set `cache_control: {"type": "ephemeral", "ttl": "1h"}` on the Claude system prompt block.
- **Rationale:** 5-minute default TTL risks cache misses between cases during manual runs or debugging pauses. 1-hour TTL costs 2x base write instead of 1.25x but prevents cache misses. Over 50 cases the savings from cache hits far exceed the write premium.
- **Evidence:** Confirmed in TEST-007: chunk 2+ showed `cache_read: 361,038 tokens`, `cache_write: 0` across all subsequent chunks and across cases run minutes apart.
- **Status:** ACTIVE
- **Decided in:** Eurydice chat, 2026-04-01

---

### DEC-004: Fix ground truth lookup to use exact Case_Number match
- **Date:** 2026-04-02
- **Decision:** `phase2_test.py` ground truth query uses `SELECT Encounter_ID FROM Encounters WHERE Case_Number = ?` instead of the manually-specified `encounter_id` argument.
- **Rationale:** Cases 180a/180b shared the same manually-passed encounter_id (167), which pulled in the wrong ground truth (66 events instead of 16/18). Exact Case_Number match eliminates this class of error.
- **Evidence:** Cases 180a, 180b, 181b all showed inflated GT counts (66, 66, 54) before the fix. After fix: 16, 18, 13 — matching the actual per-case event counts.
- **Status:** ACTIVE
- **Decided in:** Claude Code session, 2026-04-02

---

### DEC-005: Delete phantom E200 from case 084 ground truth
- **Date:** 2026-04-02
- **Decision:** Delete Encounter_Events seq 52 (E200, citation "he did not reMeMber undressing") from case 084. GT revised from 52 to 51.
- **Rationale:** Parser contamination — this citation duplicated content already captured by another event. Not a real Bullard coding.
- **Evidence:** Identified during TEST-001 triage review.
- **Status:** ACTIVE
- **Decided in:** Eurydice chat, 2026-04-01

---

### DEC-006: Rename `third_person_investigation` to `investigation`
- **Date:** 2026-04-02
- **Decision:** Rename the narrative structure category `third_person_investigation` to `investigation` across all code, Pydantic models, and staging data.
- **Rationale:** Shorter, clearer. The "third person" qualifier was redundant — investigations are inherently third-person narration.
- **Evidence:** N/A (naming decision).
- **Status:** ACTIVE
- **Decided in:** Eurydice chat, 2026-04-02

---

### DEC-007: Add `{experiencer_name}` template to narrative structure preambles
- **Date:** 2026-04-02
- **Decision:** Three preambles (`investigation`, `interview_dialogue`, `first_person_testimony`) inject the experiencer's name to constrain extraction to that individual's events only.
- **Rationale:** Cross-case contamination (ISS-003): when Hopkins interleaves multiple experiencers' narratives, the model coded events from other people. Name injection tells the model whose events to extract.
- **Evidence:** TEST-007 (pre-fix) had 15 cross-case contamination events from the Judy/Danon/Bodega Bay narrative. Post-fix runs (TEST-008 through TEST-012) showed 0 contamination on Philip Osborne and Virginia Horton. Howard Rich had 2 residual leaks from Hopkins' direct comparison passages.
- **Status:** ACTIVE
- **Decided in:** Eurydice chat, 2026-04-02

---

### DEC-008: Remove Bullard Volume 1 from extraction pipeline
- **Date:** 2026-04-02
- **Decision:** Volume 1 is no longer loaded into the extraction prompt. The motif dictionary alone drives extraction. Vol 1 loading preserved as opt-in flag (`--include-vol1`) for future A/B testing.
- **Rationale:** Dictionary-only mode produces identical match rate at 40x lower token cost.
- **Evidence:** Case 084 Hopkins full-text comparison — with Vol 1: 88.2% match, 268 events, 360,900 cached tokens. Without Vol 1: 88.2% match, 281 events, 9,013 cached tokens. Same detection ceiling, same miss count, complementary (not overlapping) miss profiles.
- **Status:** ACTIVE
- **Decided in:** Claude Code session, 2026-04-02

---

### DEC-009: Default pipeline model to Claude Opus 4.6
- **Date:** 2026-04-02
- **Decision:** `pipeline_ingest.py` defaults to `--model claude-opus-4-6`. `extract_narrative()` default changed from `baseline` to `baseline_test` profile.
- **Rationale:** Claude is the validated extraction model. baseline_test includes narrative_context_rules which improve detection.
- **Evidence:** All Hopkins baseline results used this configuration.
- **Status:** ACTIVE
- **Decided in:** Eurydice chat, 2026-04-02

---

### DEC-010: Add case_type column and three-stage type signature analysis
- **Date:** 2026-04-04
- **Decision:** Add `case_type` column to Encounters table (`abduction`, `teleportation`, `kidnapping`, `unknown`). Populate from Bullard Vol. 1, Chapter IV, Tables IV-1 through IV-3. Execute a three-stage analytical plan to test whether Bullard's case types produce distinct motif signatures.
- **Rationale:** R1 (case type signature analysis) requires knowing which cases belong to which type. Bullard defines three story types in Chapter IV with explicit case number assignments. The three-stage plan separates internal coherence (1A: do Bullard's own codes distinguish types?), narrative coherence (1B: does the prose itself carry the distinction?), and engine fidelity (2: does AI extraction preserve it?).
- **Assignment rules:**
  - Cases 32–222 and 246: `abduction`
  - Cases 231–253 (excluding 246): `teleportation`
  - Cases 254–270: `kidnapping`
  - Cases 1–31 and 223–230: `unknown`
  - Case 246: `abduction` — dual appearance investigated; Bullard's structural judgment governs; teleportation captured at motif level (E205)
- **Evidence:** Bullard Vol. 1, Chapter IV, pp. 47–57; Tables IV-1 (orthodox abductions), IV-2 (teleportations and kidnappings), IV-3 (deviant abductions).
- **Status:** ACTIVE
- **Decided in:** Eurydice chat, 2026-04-04

---

### DEC-011: Two analytical dimensions (case_type + conformance) and Stage 1A metrics
- **Date:** 2026-04-04
- **Decision:** Define two orthogonal analytical dimensions for Bullard's typology. (1) `case_type` — which episode template the narrative maps to (implemented, DEC-010). (2) `conformance` — how faithfully the episode sequence follows the prescribed template (`orthodox`, `deviant`, `trivial`, `fragmentary`). Conformance column is planned but not yet implemented; requires sequence-level comparison logic.
- **Metric decision for Stage 1A:** Primary metric is binary presence/absence per case per motif family, reported as percentage of cases per type. Secondary metric is proportional frequency (share of events within each type belonging to each family). Raw counts excluded due to group size imbalance (255 abductions vs 17 kidnappings).
- **Scope:** Stage 1A tests case_type discrimination only. Unknown cases (1–31, 223–230) excluded from primary analysis; run separately as follow-up. Conformance analysis is a separate future stage.
- **Rationale:** Separating type (content) from conformance (order) allows independent testing. Binary presence/absence avoids inflating results from cases with many sub-events in one family.
- **Evidence:** Bullard Vol. 1, Ch. IV: Table IV-1 (orthodox), Table IV-3 (deviant), trivial/fragmentary lists (p. 55).
- **Status:** ACTIVE
- **Decided in:** Eurydice chat, 2026-04-04

---

### DEC-012: A-code anchor exclusions for episode segmentation
- **Date:** 2026-04-04
- **Decision:** A-family motif codes are anchors for Episode 8 (Aftermath) in the walk-and-inherit episode segmentation algorithm, **except** A115 (nightmares/abduction dreams), A116 (memory return), A220 (other sightings), and A221 (other encounters). These four codes are treated as non-anchors and inherit their episode from context.
- **Rationale:** These four codes describe investigation context (why the case came to light) rather than the Aftermath episode (what happened after the abduction). A115/A116 relate to hypnotic memory recovery methodology; A220/A221 relate to prior sightings mentioned as background. All four have high early-appearance rates (21.6% average) compared to other A-codes (8.0%), causing false-deviant classifications when they fire Episode 8 before Examination.
- **Evidence:** v2→v4 comparison: excluding these 4 codes improved orthodox accuracy from 60.9% to 63.1% and overall accuracy from 55.6% to 56.8%. v3 (removing A entirely) showed that A still carries signal: deviant detection dropped from 26.7% to 16.7% without it.
- **Status:** ACTIVE
- **Decided in:** Eurydice chat, 2026-04-04

### DEC-013: Standardize LLM temperature at 0.1 for both extraction passes
- **Date:** 2026-04-05
- **Decision:** Set temperature=0.1 for both Pass 1 (motif extraction) and Pass 2 (voice classification). Previously Pass 1 was 0.1 and Pass 2 was 0.0. Neither setting had been formally decided or documented.
- **Rationale:** 0.0 (fully deterministic) locks the model into the single most probable token. For voice classification, this caused consistent misses on ambiguous cases — e.g., investigator sentences embedding direct experiencer quotes. 0.1 gives enough flexibility to consider near-miss alternatives without introducing creative drift. Future testing will evaluate 0.3 to see if additional flexibility improves accuracy on edge cases.
- **Evidence:** Observed voice classification misses during Ed (MACK-003) audit where experiencer direct quotes were classified as investigator voice.
- **Status:** ACTIVE
- **Decided in:** Claude Code walkthrough, 2026-04-05

---

## Conventions

- Decisions are numbered sequentially and never reused
- Every decision gets an entry, even if later reversed
- Reversed decisions link to the replacement
- "Decided in" tracks provenance — Eurydice for research/design, Claude Code for implementation discoveries
- Evidence field links to specific test IDs from TEST_LOG.md where applicable
