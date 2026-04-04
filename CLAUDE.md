# UFO Matrix — Claude Code Project Context

## What This Project Is

The Mack-Bullard UFO Matrix is a structured relational database encoding UFO encounter narratives using Thomas Bullard's 1987 motif taxonomy. The AI extraction pipeline reads investigator case files (PDFs and text), identifies Bullard motif codes in the narrative, and loads structured event sequences into a SQLite database. The goal is to enable cross-source, cross-era pattern analysis across hundreds of cases and thousands of coded events.

**Current state:** 270 Bullard cases (5,570+ events), 550-code motif dictionary, 6 Hopkins source cases baselined, Ed/MACK-003 (John Mack) extracted with 198 events.

## Current Phase: 4

Mack source extraction with advanced credibility scoring and narrative voice classification. The extraction engine is validated and the focus is on expanding the dataset beyond Bullard's original 270 cases.

## Architecture

### Database (SQLite)
- **ufo_matrix.db** — Production. 4 tables: Subjects, Encounters, Motif_Dictionary, Encounter_Events.
- **ufo_matrix_staging.db** — All new AI-extracted data goes here first. Never write directly to production.

### Core Scripts
- **llm_bridge.py** — Model-agnostic LLM interface. Contains Pydantic schemas, extraction logic (`extract_narrative()`), and database loading (`load_to_database()`). Primary extraction engine.
- **pipeline_ingest.py** — 4-step PDF ingestion: extract text, scan metadata, extract narratives, load to staging DB.
- **qa_triage.py** — Greedy sequential matching against ground truth. Produces validated .xlsx comparison spreadsheets.
- **phase2_test.py** — Blind calibration test runner. Produces raw JSON for qa_triage input.
- **dashboard.py** — Streamlit analytics UI.

### Key Data Files
- **prompt_library.json** — LLM extraction rules, narrative structure preambles, chain-of-thought templates.
- **motif_key.json** — Bullard motif dictionary (550+ codes with family mappings).
- **header_map.json** — Case boundary map for OCR'd Bullard Vol. 2.

### Schema
See `schema.sql` for the full 4-table definition. Key fields added in Phase 4:
- `AI_Event_Description` — Narrative voice-tagged event descriptions
- `voice_speaker` / `voice_content_type` — Two-field voice classification
- `AI_Investigator_Credibility_Justification` / `AI_Witness_Credibility_Justification` — Credibility scoring with chain-of-thought
- `case_type` — Bullard story type classification: `abduction`, `teleportation`, `kidnapping`, `unknown` (DEC-010)

## Rules

### "The AI Never Holds the Pen"
- The QA triage spreadsheet is the authoritative comparison instrument
- All accuracy claims use triage-to-triage numbers; never compare triage vs raw JSON
- Two-step calibration: Run (Claude Code) then Validate (Eurydice + Shawna)
- Prompt changes go into `baseline_test` profile first, promoted to `baseline` only after validated improvement
- Never write directly to `ufo_matrix.db` from pipeline code. Always use staging.

### Multi-Agent Governance
- **Eurydice** (Claude Project Chat): All decisions, reasoning, planning
- **Claude Code**: Script and file modifications via structured handoff blocks
- **Claude Cowork**: QA triage and comparison work
- No agent makes autonomous design decisions. Every change traces to a decision in Eurydice chat.

### Code Style
- Beginner-friendly: clear variable names, comments explaining non-obvious logic
- Print progress messages so the user can see what's happening
- Avoid clever one-liners or unnecessary abstractions

### Git Workflow
- All changes go through feature branches and pull requests. Never push directly to main.
- Claude Code works in worktrees, commits to feature branches, opens PRs.
- Local `main` should always match GitHub `main`.

## Governance Documents
- **WORKFLOW_PROTOCOL.md** — Multi-agent roles, handoff format, measurement methodology
- **DECISION_LOG.md** — 9 active architectural decisions (DEC-001 through DEC-009)
- **test_results/CALIBRATION_LEDGER.md** — Validated calibration results per case
- **Plans/ROADMAP.md** — Research north stars and prioritized work items

## Active Issues (as of 2026-04-04)

| # | Issue | Severity | Status |
|---|-------|----------|--------|
| ISS-001 | Cache bleed between runs | CRITICAL | Not started |
| ISS-002 | E205 blind spot (time lapse) | HIGH | Not started |
| ISS-003 | Cross-case contamination | HIGH | Fixed (experiencer_name preambles) |
| ISS-004 | Phantom E200 in uploaded DB | MEDIUM | Workaround in place |
| ISS-005 | memory_retrieval_method gaps | HIGH | Populated for MACK-003, bulk pending |
| ISS-006 | Vol 1 interpretive contamination | HIGH | Resolved (dictionary-only mode) |
| ISS-007 | Analytical tail contamination | MEDIUM | AI_Event_Description deployed, refining |

## Calibration Summary (Claude Opus 4.6)

6 Hopkins source cases baselined. Aggregate: **93.4% detection** across 151 ground-truth events.
Known blind spots: E200 (time lapse), deduplication on dense passages, vague retrospective language.
See `test_results/CALIBRATION_LEDGER.md` for per-case breakdown.
