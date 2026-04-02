# TEST LOG — Mack-Bullard UFO Matrix

Tracks every extraction test run: configuration, source, results, and disposition.

---

## COMPLETED RUNS

### TEST-001: Case 084 (Steven Kilburn) — Test A
- **Date:** 2026-04-01
- **Source text:** Bullard Vol. 2 catalogue summary
- **Source type:** compiled_catalogue
- **Model:** Claude Opus 4.6
- **Profile:** baseline_test (preamble ON, narrative_context_rules ON)
- **Ground truth:** 51 (corrected for phantom E200)
- **Results:**
  - Fidelity: 84.3% (43/51)
  - Genuine alternates: 4
  - True misses: 4 (B254, E200, X100, X200)
  - Detection: 92.2% (47/51)
  - AI extras: 17
- **Disposition:** VALIDATED
- **Notes:** Phantom E200 at seq 52 discovered and deleted. GT revised from 52 to 51.

---

### TEST-002: Case 069 (Howard Rich) — Test A
- **Date:** 2026-04-01
- **Source text:** Bullard Vol. 2 catalogue summary
- **Source type:** compiled_catalogue
- **Model:** Claude Opus 4.6
- **Profile:** baseline_test (preamble ON, narrative_context_rules ON)
- **Ground truth:** 18
- **Results:**
  - Fidelity: 77.8% (14/18)
  - Genuine alternates: 4
  - True misses: 0
  - Detection: 100% (18/18)
  - AI extras: 8
- **Disposition:** VALIDATED
- **Notes:** Perfect detection — every GT event detected. Lower fidelity driven by alternate code choices, not missed events.

---

### TEST-003: Case 180a (Philip Osborne — childhood) — Test A
- **Date:** 2026-04-01
- **Source text:** Bullard Vol. 2 catalogue summary
- **Source type:** compiled_catalogue
- **Model:** Claude Opus 4.6
- **Profile:** baseline_test (preamble ON, narrative_context_rules ON)
- **Ground truth:** 16
- **Results:**
  - Fidelity: 68.8% (11/16)
  - Genuine alternates: 3
  - True misses: 2 (E200, A110)
  - Detection: 87.5% (14/16)
  - AI extras: 7
- **Disposition:** VALIDATED
- **Notes:** E200 miss consistent with documented blind spot (ISS-002 pattern).

---

### TEST-004: Case 180b (Philip Osborne — Pittsburgh) — Test A
- **Date:** 2026-04-01
- **Source text:** Bullard Vol. 2 catalogue summary
- **Source type:** compiled_catalogue
- **Model:** Claude Opus 4.6
- **Profile:** baseline_test (preamble ON, narrative_context_rules ON)
- **Ground truth:** 18
- **Results:**
  - Fidelity: 72.2% (13/18)
  - Genuine alternates: 2
  - True misses: 3 (U230, E200, E200)
  - Detection: 83.3% (15/18)
  - AI extras: 5
- **Disposition:** VALIDATED
- **Notes:** Two E200 misses — reinforces time lapse blind spot. U230 (diffuse lighting) also missed.

---

### TEST-005: Case 181a (Virginia Horton — Manitoba) — Test A
- **Date:** 2026-04-01
- **Source text:** Bullard Vol. 2 catalogue summary
- **Source type:** compiled_catalogue
- **Model:** Claude Opus 4.6
- **Profile:** baseline_test (preamble ON, narrative_context_rules ON)
- **Ground truth:** 35
- **Results:**
  - Fidelity: 85.7% (30/35)
  - Genuine alternates: 5
  - True misses: 0
  - Detection: 100% (35/35)
  - AI extras: 8
- **Disposition:** VALIDATED
- **Notes:** Perfect detection. Strongest fidelity among the non-084 cases.

---

### TEST-006: Case 181b (Virginia Horton — Alsace) — Test A
- **Date:** 2026-04-01
- **Source text:** Bullard Vol. 2 catalogue summary
- **Source type:** compiled_catalogue
- **Model:** Claude Opus 4.6
- **Profile:** baseline_test (preamble ON, narrative_context_rules ON)
- **Ground truth:** 13
- **Results:**
  - Fidelity: 53.8% (7/13)
  - Genuine alternates: 5
  - True misses: 1 (B900)
  - Detection: 92.3% (12/13)
  - AI extras: 12
- **Disposition:** VALIDATED
- **Notes:** Lowest fidelity in the set but detection still strong. 5 genuine alternates suggest Bullard's coding choices diverge more from the dictionary on this case.

---

### TEST-007: Case 084 (Steven Kilburn) — Test B
- **Date:** 2026-04-02
- **Source text:** Hopkins, *Missing Time*, pp. 45–82 (PDF) / pp. 51–87 (source)
- **Source type:** investigation
- **Model:** Claude Opus 4.6
- **Profile:** baseline_test (**preamble OFF** — preamble text was overwritten to placeholder "todo")
- **Memory retrieval method:** hypnosis
- **Narrative structure:** third_person_investigation (pre-rename)
- **Experiencer name:** Steven Kilburn (identified by metadata scan but NOT injected — preamble was empty)
- **Ground truth:** 51 (corrected for phantom E200)
- **Results:**
  - AI events: 271 (30 chunks, 38 pages)
  - MATCH: 46
  - MISS: 5
  - AI EXTRA: 225 (210 after removing 15 cross-case contamination)
  - ANOMALY: 1 (tube-like fingers)
  - Match rate: 90.2%
- **Miss breakdown:**
  - A116 → AI coded A116.1 — likely genuine alternate
  - B252 (nose absent) — possible true miss
  - X200 → AI coded X202 — likely genuine alternate
  - M118 → AI coded M119 — likely genuine alternate
  - E205 (relocation) — confirmed repeatable blind spot (ISS-002)
- **Cross-case contamination:** 15 events (seqs 142–156, chunk 19) from Judy/Danon/Bodega Bay narrative. Logged as ISS-003.
- **Disposition:** VALIDATED — error profile characterized, no new prompt rules required
- **Notes:** First Test B run. 3 more exact matches than Test A from same GT. **Pre-preamble baseline** — preamble was empty ("todo"), no narrative structure guidance or experiencer boundary given to the model. 15 cross-case contamination events resulted. Do not re-run; use TEST-008 as the post-fix comparison point.

---

## AGGREGATE — Opus Test A Baseline (Bullard Voice)

| Metric | Value |
|--------|-------|
| Total GT events | 151 |
| Detection | 93.4% (141/151) |
| True misses | 10 |
| Documented blind spots | E200 (time lapse at narrative boundaries), single-motif-per-sentence on dense passages, vague retrospective language |

---

## PENDING RUNS

### TEST-008: Case 069 (Howard Rich) — Test B
- **Source text:** Hopkins, *Missing Time*, pp. 83–104 (PDF)
- **Source type:** investigation
- **Model:** Claude Opus 4.6
- **Profile:** baseline_test (preamble ON, **WITH {experiencer_name} constraint**)
- **Experiencer name:** Howard Rich (injected into preamble at runtime)
- **Significance:** First live test of ISS-003 fix. Compare cross-case contamination count against TEST-007 (pre-fix baseline).
- **Blocked by:** Preamble restoration handoff (HANDOFF_preamble_restoration_2026-04-02.md)

### TEST-009: Case 180a (Philip Osborne — childhood) — Test B
- **Source text:** Hopkins, *Missing Time*, pp. 148–181 (PDF)
- **Source type:** investigation
- **Model:** Claude Opus 4.6
- **Profile:** baseline_test (preamble ON, **WITH {experiencer_name} constraint**)
- **Experiencer name:** Philip Osborne
- **Shared extraction:** Single pipeline run covers both 180a and 180b (same chapter, same experiencer). Triage runs separately against each sub-case GT.
- **Blocked by:** Preamble restoration handoff

### TEST-010: Case 180b (Philip Osborne — Pittsburgh) — Test B
- **Source text:** Hopkins, *Missing Time*, pp. 148–181 (PDF) — same extraction as TEST-009
- **Source type:** investigation
- **Model:** Claude Opus 4.6
- **Profile:** baseline_test (preamble ON, **WITH {experiencer_name} constraint**)
- **Experiencer name:** Philip Osborne
- **Shared extraction:** Uses same extraction output as TEST-009. Triage run against 180b GT only.
- **Blocked by:** Preamble restoration handoff

### TEST-011: Case 181a (Virginia Horton — Manitoba) — Test B
- **Source text:** Hopkins, *Missing Time*, pp. 182–213 (PDF)
- **Source type:** investigation
- **Model:** Claude Opus 4.6
- **Profile:** baseline_test (preamble ON, **WITH {experiencer_name} constraint**)
- **Experiencer name:** Virginia Horton
- **Shared extraction:** Single pipeline run covers both 181a and 181b (same chapter, same experiencer). Triage runs separately against each sub-case GT.
- **Blocked by:** Preamble restoration handoff

### TEST-012: Case 181b (Virginia Horton — Alsace) — Test B
- **Source text:** Hopkins, *Missing Time*, pp. 182–213 (PDF) — same extraction as TEST-011
- **Source type:** investigation
- **Model:** Claude Opus 4.6
- **Profile:** baseline_test (preamble ON, **WITH {experiencer_name} constraint**)
- **Experiencer name:** Virginia Horton
- **Shared extraction:** Uses same extraction output as TEST-011. Triage run against 181b GT only.
- **Blocked by:** Preamble restoration handoff

---

## SUPERSEDED RUNS (Gemini — March 2026)

Gemini 3.1 Pro runs for cases 093, 192g, and 084 are recorded in the Calibration Ledger with status SUPERSEDED. They are not repeated here. Model switch to Claude Opus 4.6 invalidated those results per the standing rule that calibration results are model-specific.

---

## CONVENTIONS

- Test numbers are sequential and never reused
- Every run gets an entry, even if it fails
- **Disposition** values: `VALIDATED`, `FAILED`, `PENDING REVIEW`, `INVALIDATED`
- **Test A** = extraction from Bullard Vol. 2 catalogue summary
- **Test B** = extraction from original source text (Hopkins, Mack, etc.)
- Cross-reference issues log by number (e.g., ISS-003)
- Record the configuration that actually ran, not what was intended
- All numbers are post-human-review unless labeled "raw"
