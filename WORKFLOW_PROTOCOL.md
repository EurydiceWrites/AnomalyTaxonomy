# UFO Matrix — Multi-Agent Workflow Protocol

**Established:** March 29, 2026  
**Project:** Mack-Bullard UFO Matrix  
**Current Phase:** 4 — Mack Source Extraction with Advanced Credibility Scoring & Narrative Voice Classification

---

## AGENT ROLES

### Eurydice (Claude Project Chat)
- **Function:** Decision-making, reasoning, planning, research
- **Owns:** All architectural and methodological decisions
- **Produces:** Handoff blocks for other agents, session recaps, decision logs
- **Does NOT:** Execute code changes or generate QA spreadsheets directly

### Claude Code
- **Function:** Script and file modifications
- **Receives:** Handoff blocks from Eurydice with explicit instructions
- **Scope:** Edits to `llm_bridge.py`, `prompt_library.json`, `bulk_ingest.py`, database schema changes, and any other codebase modifications
- **Rule:** No autonomous design decisions. Every change must trace back to a decision made in Eurydice chat.

### Claude Cowork
- **Function:** QA triage, comparison work, and bulk data tasks
- **Receives:** Handoff blocks from Eurydice with explicit instructions
- **Scope:** Calibration spreadsheets, line-by-line comparison generation, data formatting
- **Note:** Eurydice can now run QA triage directly via skill. Cowork is used for heavier comparison work or when Eurydice's context is better preserved by delegating.
- **Rule:** No autonomous design decisions. Every change must trace back to a decision made in Eurydice chat.

---

## HANDOFF PROTOCOL

When a decision is made in the Eurydice chat, the following block format is used to pass work to Claude Code or Claude Cowork:

```
## HANDOFF — [Agent Target: Code or Cowork]
**Date:** [date]
**Decision made in:** Eurydice chat
**Task:** [one-sentence description]
**Details:**
[explicit, self-contained instructions — the receiving agent should need NO additional context]
**Files affected:** [list]
**Acceptance criteria:** [what "done" looks like]
```

---

## SESSION MANAGEMENT

### Decision Log Format
Every significant decision is recorded in-chat as:
```
**DECISION [number]:** [one-sentence summary]
**Rationale:** [why]
**Status:** AGREED / PENDING / REVERSED
```

### Context Window Degradation
- Eurydice monitors for signs of degradation: repetition, loss of specificity, failure to reference earlier decisions
- When degradation is suspected, Eurydice flags it explicitly and produces a **session recap** before the session ends
- The user may not notice degradation on their own — Eurydice is responsible for flagging it

### Session Recaps
- Produced at end of session or when context limits approach
- Format matches existing `session_recap_YYYY-MM-DD.md` files
- Stored in `Plans/Recaps/`
- Must include: decisions made, files modified, open items, next steps

### Issues Log
- Active issues are tracked with ISS-### identifiers (e.g., ISS-001)
- Each issue has a severity (CRITICAL, HIGH, MEDIUM, LOW) and status
- Current issues are listed in `CLAUDE.md` for quick reference across sessions
- Issues are resolved by linking to the decision or PR that fixed them

---

## THE HUMAN IN THE LOOP

- The user (Shawna) holds final authority on all research and design judgments
- No agent modifies prompt rules, schema definitions, or analytical methodology without Shawna's explicit approval in the Eurydice chat
- "The AI Never Holds the Pen" — all three governance layers apply across all agents

---

## MEASUREMENT METHODOLOGY

**Decided:** March 29, 2026

### Authoritative Comparison Instrument
The **QA triage spreadsheet** (produced by `qa_triage.py`) is the authoritative instrument for all cross-run calibration comparisons. Raw `phase2_blind_test.py` JSON results are input data only — never used directly for accuracy claims.

### Why
- The triage uses **greedy sequential matching**, which respects narrative order. The raw test uses frequency-based matching, which is position-agnostic.
- The triage produces **genuine alternate detection** (text-overlap linking) and **miss diagnostics**. The raw test does not.
- The triage is deliberately conservative and may slightly undercount matches — but this bias is **consistent across runs**, making it a calibrated instrument.
- The triage spreadsheet is the artifact the human reviewer actually works from.

### Rule
All accuracy numbers cited in session recaps, comparisons, and reports must come from triage-to-triage comparisons. Never compare a triage number against a raw JSON number.

### Calibration Workflow (Two-Step Process)

Every calibration run follows this sequence. No step is skipped.

**Step 1 — Run (Claude Code):**
1. Claude Code executes `phase2_blind_test.py` with specified case, encounter ID, line range, and profile
2. Raw results JSON is produced
3. Claude Code reports summary stats

**Step 2 — Validate (Eurydice + Shawna):**
1. QA triage is run on the raw JSON (via `qa_triage.py`), producing a formatted spreadsheet
2. Shawna reviews the spreadsheet, confirming or reclassifying genuine alternates, true misses, and AI extras
3. Validated final numbers are recorded in `CALIBRATION_LEDGER.md`
4. No result is considered final until it appears in the ledger

### Calibration Ledger
- File: `CALIBRATION_LEDGER.md` (project root)
- Contains one row per validated calibration run
- Only human-confirmed numbers are recorded
- Tracks five metrics: Fidelity, Genuine Alternates, True Misses, Detection Rate, AI Extras

---

## PROJECT DOCUMENTS

| Document | Purpose |
|----------|---------|
| `CLAUDE.md` | Quick-start context for new Claude Code sessions |
| `WORKFLOW_PROTOCOL.md` | This file — multi-agent governance and SOP |
| `DECISION_LOG.md` | Permanent record of all architectural/methodological decisions (DEC-###) |
| `Plans/ROADMAP.md` | Research north stars, prioritized work queue, and calibration baseline |
| `test_results/CALIBRATION_LEDGER.md` | Validated per-case calibration results |
| `TODO.md` | Master task list (updated after each session) |

---

## SOURCE OF TRUTH

| Item | Source of Truth |
|------|----------------|
| Research decisions | `DECISION_LOG.md` + Eurydice chat history + session recaps |
| Research priorities | `Plans/ROADMAP.md` |
| Code state | Git / local files as modified by Claude Code |
| Data | `ufo_matrix.db` (SQLite) |
| Motif taxonomy | Bullard Vol. 2 (physical book + clean PDF) |
| Analytical framework | Bullard Vol. 1 |
| Prompt rules | `prompt_library.json` |
| Schema definitions | `llm_bridge.py` Pydantic models |
| Calibration accuracy | QA triage spreadsheets (not raw phase2 JSON) |
| Validated results | `test_results/CALIBRATION_LEDGER.md` |
| Active issues | `CLAUDE.md` issues table (ISS-###) |
| Session context for new agents | `CLAUDE.md` |


---

## GIT & DEPLOYMENT WORKFLOW

### Branch Strategy
All code changes go through feature branches and pull requests. **Never push directly to main.**

### Workflow Steps

1. **Claude Code works in a worktree** (e.g., `claude/stupefied-torvalds`)
   - The worktree is a separate checkout inside `.claude/worktrees/`
   - It shares the same git history as the main repo but is on its own branch

2. **Commits go on the feature branch**, not on local `main`
   - If scripts need to run from the main repo directory (for access to PDFs, databases, etc.), commits must be moved to the feature branch before pushing

3. **Push the feature branch to GitHub**
   - `git push -u origin claude/stupefied-torvalds`

4. **Open a Pull Request on GitHub**
   - The PR lets Shawna review all changes before they land on `main`
   - GitHub shows a "Compare & pull request" button after a branch is pushed

5. **Shawna reviews and merges on GitHub**
   - Only after PR approval does the work land on `main` on GitHub

6. **Sync local machine**
   - After merging on GitHub, run `git pull` in the local main repo to sync

### Rules
- **Local `main` should always match GitHub `main`** — no direct commits to local main
- **All changes flow through PRs** — this creates an audit trail on GitHub
- **Claude Code does not push to main** — it pushes feature branches and opens PRs
