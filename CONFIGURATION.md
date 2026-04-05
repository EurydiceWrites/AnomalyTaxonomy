# Extraction Pipeline Configuration — Official Settings

**Purpose:** Single source of truth for all configurable settings in the extraction pipeline.
Every test run should be auditable against this document. If a setting changes, update this file and log the decision in DECISION_LOG.md.

---

## Active Configuration (Phase 4)

| Setting | Value | Where It Lives | Decision |
|---------|-------|----------------|----------|
| **Prompt profile** | `baseline_test` | `prompt_library.json` > profiles | — |
| **Extraction model** | `claude-opus-4-6` | `pipeline_ingest.py` CLI default, `llm_bridge.py` function default | DEC-001, DEC-009 |
| **Metadata scan model** | Gemini Flash | `pipeline_ingest.py` Steps 0-1 | — |
| **Volume 1 context** | OFF (dictionary-only) | `--include-vol1` flag, default False | DEC-008 |
| **Preambles** | ON (both narrative structure + retrieval method) | `llm_bridge.py` extract_narrative() | — |
| **Database target** | `ufo_matrix_staging.db` | `load_to_database()` db_path parameter | — |
| **Chunk size** | 3000 characters | `llm_bridge.py` line 175 (hardcoded) | — |
| **Temperature (Pass 1)** | 0.1 | `llm_bridge.py` extract_narrative() | DEC-013 |
| **Temperature (Pass 2)** | 0.1 | `llm_bridge.py` classify_voice_tags() | DEC-013 |

---

## What Each Setting Does

### Prompt profile: `baseline_test`
The named profile in `prompt_library.json` that controls which system instructions, few-shot examples, narrative context rules, and anti-hallucination rules are sent to the extraction model. Changes to prompt logic go into `baseline_test` first, then promote to `baseline` only after validated improvement.

### Extraction model: `claude-opus-4-6`
The LLM used for Pass 1 (motif extraction) and Pass 2 (voice classification). Switched from Gemini 3.1 Pro in DEC-001. Also available: `gemini-2.5-pro`, `gemini-3.1-pro-preview`.

### Metadata scan model: Gemini Flash
Used in `pipeline_ingest.py` Steps 0-1 for OCR (scanned PDFs only), front-matter attribution, and scanned metadata. Lightweight and cheap. Does NOT receive the motif dictionary or Volume 1 context.

### Volume 1 context: OFF
When ON, Bullard's full Volume 1 comparative analysis is included in the extraction prompt. When OFF (current default), the model only receives the flattened motif dictionary (code + description). Turned off in DEC-008 to prevent interpretive contamination.

### Preambles: ON
Two context preambles are injected into the extraction prompt:
1. **Narrative structure preamble** — loaded from `prompt_library.json` based on the `narrative_structure` value detected by Gemini in Step 1 (e.g., "investigation", "literary_narration"). Uses `{experiencer_name}` template substitution.
2. **Retrieval method preamble** — from `RETRIEVAL_CONTEXT_MAP` in `llm_bridge.py`. Sets the default `memory_state` for all events based on the encounter-level `memory_retrieval_method`.

### Database target: `ufo_matrix_staging.db`
All new AI-extracted data goes to staging first. Never write directly to `ufo_matrix.db` (production). Created by `create_staging_db.py`, which copies the schema and populates the Motif_Dictionary from production.

### Chunk size: 3000 characters
Text is split into chunks at paragraph boundaries, with a maximum of 3000 characters per chunk. Target is 500-800 words per prompt for maximum extraction detail. Hardcoded in `llm_bridge.py`.

### Temperature: 0.1
Controls output variation. 0.0 = fully deterministic (same input always produces same output). 0.1 = nearly deterministic but allows the model to consider near-miss alternatives on ambiguous text. Set for both passes in DEC-013. Future testing will evaluate 0.3 for comparison.

---

## Pipeline JSON Audit Fields

Every extraction run records these settings in `step_3_extraction` of the pipeline JSON:

```json
{
  "model_name": "claude-opus-4-6",
  "profile_used": "baseline_test",
  "run_timestamp": "2026-04-05T...",
  "include_vol1": false,
  "narrative_structure": "investigation",
  "retrieval_method": "hypnosis",
  "experiencer_name": "Ed",
  "chunk_size": 3000,
  "num_chunks": 12
}
```

If any of these values don't match this configuration document, the run used non-standard settings and results should be interpreted accordingly.

---

## How to Change Settings

1. Discuss the change (Eurydice chat or Claude Code walkthrough)
2. Log the decision in `DECISION_LOG.md`
3. Update this file
4. Update the code
5. Run a validation test with the new settings before using on new cases
