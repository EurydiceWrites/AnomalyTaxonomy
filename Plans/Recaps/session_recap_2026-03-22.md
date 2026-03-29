# Session Recap: 2026-03-22

## What we did today

### 1. Triaged the 192g calibration QA spreadsheet

Case 192g (Betty Andreasson) was run through Phase 2b semantic calibration using the `baseline` profile. The QA comparison of Bullard's ground truth vs. the AI's blind-coded output produced:

- **173 total rows**
- **99 MATCH** (green, no action needed)
- **23 MISS** (orange, Bullard coded it, AI didn't)
- **50 AI EXTRA** (blue, AI coded it, Bullard didn't)
- **1 header row**

I (Claude) cross-referenced all 73 divergent rows against the motif dictionary in `ufo_matrix.db`, wrote a draft divergence type and rationale for each, and produced a triaged spreadsheet: `192g_calibration_qa_triaged.xlsx`. All draft entries were marked `[DRAFT]` in purple italic so Shawna could distinguish them from her own work.

### 2. Shawna reviewed and confirmed/corrected all 73 rows

Her final breakdown:
- **40 GENUINE ALTERNATE** — AI found real dictionary matches Bullard didn't code
- **16 AI ERROR** — including duplicates, overcoding, and category errors
- **4 REVIEW** — borderline, needs further judgment
- **3 ANOMALY** — genuine gaps in Bullard's dictionary
- **3 AI EXTRA** — valid but redundant codes

She also added source text fragments for all 23 MISSes and linked 4 MISSes to their AI alternate codes (B247->B242, B335->B330, M128->M111, E322->E322).

### 3. Three key findings surfaced from the QA

Shawna identified three systematic failure patterns that became prompt rule changes:

**Change 1: Prefix-Family Constraint** — B-codes describe beings only, not witnesses. The AI applied B762 ("defective/unsuitable") to describe Betty's hysterectomy — a category error. Shawna's catch: "Bs apply to Beings. E applies to effects on witness."

**Change 2: Multi-Motif-Per-Fragment** — The AI was only assigning one code per sentence, but Bullard routinely stacked codes. Shawna flagged this at rows 17 and 106. Multiple MISSes and the B330/B335 split trace to this constraint.

**Change 3: Fragment Provenance** — At row 122, the AI matched E322 correctly but cited a sentence from two paragraphs away. Light guardrail: cite where the event happens, not the best-fitting sentence elsewhere. Only 2 occurrences in 173 rows.

### 4. Handoff document written for Antigravity

File: `antigravity_handoff_192g_rule_changes.md`

Contains exact rule text, target JSON arrays, and insertion points for all three changes.

**Critical decision: all three rules go into `baseline_test` ONLY.** The `baseline` profile stays untouched until a re-run of 192g against `baseline_test` confirms improvement. Only then does Shawna promote the rules to `baseline`.

### 5. Rules were implemented in prompt_library.json

Antigravity added all three rules to `baseline_test`:
- Change 2 (multi-motif) added to `system_instruction` array
- Changes 1 and 3 (prefix constraint, provenance) added to `anti_hallucination_rules` array

### 6. First re-run attempt failed — wrong case text

The re-run of `phase2_test.py` against `baseline_test` pulled the wrong chunk of Volume 2. The results file (`phase2_results_192g_baseline_test.json`) contains text from cases in the 040s-050s range (ending with Carlos Acevedo, Case 051), not 192g (Betty Andreasson). Ground truth count was 9 instead of the expected 122. This needs to be re-run with the correct text.

## Current state

- `prompt_library.json` has all three rules in `baseline_test` profile
- `baseline` profile is unchanged
- The 192g re-run needs to be executed against the CORRECT text
- Pre-change baseline numbers to beat: 99 match / 23 miss / 50 AI extra out of 173 rows
- The triaged QA spreadsheet with Shawna's confirmed assessments is at `192g_calibration_qa_triaged.xlsx` (and her annotated copy is in uploads as `Copy of 192g_calibration_qa_triaged.xlsx`)

## Next step

Re-run 192g through `baseline_test` profile with the correct narrative text, then generate a new QA comparison to measure whether the three rule changes improved accuracy.
