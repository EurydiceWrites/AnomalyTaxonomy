# Session Recap — Saturday, March 28, 2026 (Morning)

## Project: Mack-Bullard UFO Matrix
## Phase: 2b — Calibration & Infrastructure Governance

---

## WHAT WAS ACCOMPLISHED

### 1. Memory State Vocabulary Audit & Consolidation

**Problem:** Five columns across three tables were tracking the same concept (memory retrieval / hypnosis usage), with 19 inconsistent label variants in the event-level `memory_state` column.

**Redundant columns identified:**
- `Encounters.Conscious_Recall` — 5 rows populated, boolean
- `Encounters.is_hypnosis_used` — 5 rows populated, boolean  
- `Encounters.memory_retrieval_method` — 132 rows populated, VARCHAR (KEPT)
- `Encounter_Events.memory_state` — 5,570 rows populated, VARCHAR (KEPT)
- `Subjects.Hypnosis_Utilized` — boolean (KEPT, case-level fact)

**Actions taken:**
- DROPPED `Conscious_Recall` from Encounters table
- DROPPED `is_hypnosis_used` from Encounters table
- Collapsed 19 synonym labels into 4 canonical values on `Encounter_Events.memory_state`:
  - `conscious` (2,067 events) — natural waking recall, no intervention
  - `hypnosis` (3,235 events) — recovered via hypnotic regression
  - `altered` (160 events) — non-ordinary state (dream, trance, semi-conscious)
  - `unconscious` (107 events) — no memory of this period
  - `unknown` (1 event) — not determined
- Aligned `Encounters.memory_retrieval_method` to same vocabulary (renamed `dream` → `altered`)

### 2. Schema Enforcement — Pydantic Literal Constraint

**Problem:** `memory_state` in `llm_bridge.py` was defined as `str` (free text), allowing the LLM to generate any string. This is the root cause of the 19-synonym mess.

**Fix:** Changed `memory_state` from `str` to `Literal["conscious", "hypnosis", "altered", "unconscious"]` in the `EncounterEvent` Pydantic model. The Gemini API will now reject any value not on this list.

### 3. Prompt Library Update

**Problem:** Rule 4 (MEMORY STATE) in `prompt_library.json` only named two values (`hypnotic` and `conscious`) and used the wrong string for hypnosis.

**Fix:** Updated Rule 4 in both `baseline` and `baseline_test` profiles to list all four canonical values with definitions. This aligns the natural language instruction (Level 1) with the schema enforcement (Level 2).

### 4. Extraction Script Fixes (llm_bridge.py)

- Updated `RETRIEVAL_CONTEXT_MAP`: renamed `'dream'` key to `'altered'` with updated description
- Removed `Conscious_Recall` and `is_hypnosis_used` from the Encounters INSERT statement (lines 219-222) — prevents crash on next new case ingestion
- Identified and flagged `hypnosis_used` field in `CaseMetadata` class as needing `Literal["YES", "NO"]` constraint (status: TBD)

### 5. Suspicious Import Flagged

- Line 4: `from streamlit import cursor` — may be an accidental addition that could shadow SQLite's cursor. Flagged for review/removal.

---

## FILES MODIFIED

| File | Changes |
|------|---------|
| `ufo_matrix.db` | Dropped 2 columns, migrated 5,570 events to canonical vocabulary, aligned Encounters vocabulary |
| `llm_bridge.py` | Literal constraint on memory_state, updated RETRIEVAL_CONTEXT_MAP, fixed INSERT statement |
| `prompt_library.json` | Updated Rule 4 in baseline and baseline_test profiles |

## BACKUP CREATED

- `ufo_matrix_backup_20260328.db` — pre-migration snapshot

---

## SKILLS LEARNED

- SQL: SELECT, COUNT, GROUP BY, WHERE IN, UPDATE, ALTER TABLE DROP COLUMN
- Concept: Difference between `str` (any text) and `Literal` (constrained list) in Pydantic
- Concept: Two levels of structured output control — prompt instruction (Level 1) vs. schema enforcement (Level 2)
- Concept: Controlled vocabulary governance — defining canonical values and collapsing synonyms

---

## STILL TODO (Matrix)

- [ ] Populate remaining 205 `unknown` rows in `Encounters.memory_retrieval_method` from Bullard case headers (couch work with physical book)
- [ ] Confirm/remove `from streamlit import cursor` on line 4 of `llm_bridge.py`
- [ ] Change `hypnosis_used` in `CaseMetadata` from `str` to `Literal["YES", "NO"]`
- [ ] Awaiting Bullard reply on duplicate coding methodology (E120 question) — blocks deduplication rule
- [ ] Select and run third calibration case (Highway Hijack, Chapter 4)
- [ ] Update `prompt_library.json` Rule 4 default: if retrieval unclear, default to `conscious`

---

## GOVERNANCE FRAMEWORK IN ACTION

Today's work demonstrated all three layers of the "AI Never Holds the Pen" framework:

1. **Structural Constraint:** Pydantic `Literal` type prevents the LLM from outputting invalid memory state values
2. **Reconciliation:** SQL migration collapsed 19 inconsistent labels into 4 canonical values, with human review of each mapping
3. **Justified Matching:** Prompt library defines each value with clear criteria so the LLM's choice is auditable

---

## AFTERNOON PLAN

Switch to Project SENTINEL — Phase 0 setup (repo, schema, Streamlit skeleton)
