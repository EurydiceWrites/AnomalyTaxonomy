# UFO Matrix — Research Roadmap

**Last updated:** 2026-04-04
**Maintained by:** Eurydice + Shawna

---

## Research North Stars

These are the big analytical questions the Matrix is being built to answer. All technical work serves these goals.

### R1. Case Type Signature Analysis

Bullard classified his 270 cases into types (A through D+). Do different case types have distinctive motif signatures — a characteristic sequence or cluster of codes that acts as a "fingerprint" for each type? And when we extract non-Bullard cases (Mack, Hopkins, Fowler), do those cases resemble any of these type signatures even though they were classified independently?

**What this unlocks:** A quantitative test of Bullard's classification system. If type signatures exist and non-Bullard cases map onto them, the taxonomy has predictive power beyond the original dataset.

### R2. Cross-Source Comparison

How do motif patterns differ across investigators and source books? Do Mack experiencers show different motif distributions than Bullard's 270? Than Hopkins'? Are the differences investigator-driven (methodology, interview style) or experiencer-driven (era, geography, demographics)?

**What this unlocks:** Separating the investigator's influence from the experiencer's account. The observer effect finding (AI credibility scores reflect investigator methodology) is the first thread of this — R2 pulls it across the full dataset.

### R3. Temporal and Geographic Patterns

How does encounter phenomenology change over decades and across regions? When did specific motifs emerge or fade? Do certain motif families cluster geographically? The Matrix holds dates, location types, and 5,570+ coded events — the data exists, it just needs enough breadth to be statistically meaningful.

**What this unlocks:** A longitudinal view of the phenomenon. If E-family motifs (entity descriptions) shift over time while C-family (examination procedures) stay stable, that tells us something about which elements of the experience are culturally mediated.

---

## Current Position (April 2026)

- 270 Bullard cases in production DB (5,570+ events, 550-code dictionary)
- Extraction engine validated on Claude Opus 4.6 (93.4% detection across 6 Hopkins cases)
- Ed/MACK-003 extracted (198 events) with narrative voice classification
- Two-field voice classification and credibility scoring deployed
- 9 architectural decisions documented, 7 active issues tracked

---

## Immediate (current sprint)

1. **Case type classification** — DONE (DEC-010). `case_type` column added and populated: 255 abduction, 22 teleportation, 17 kidnapping, 39 unknown, 5 non-Bullard NULL.
2. **Stage 1A: Internal coherence analysis** — Group Bullard GT codes by case_type, compute motif family distributions per type. Test whether the three types produce distinct signatures. Metric decision pending (raw counts vs proportional vs binary).
3. **Voice tag verification** — Rerun Ed with the approved 3-tag narrative voice rule; verify distribution of Experiencer (direct) / Experiencer (reported) / Interpretation tags
4. **Weekend audit** — 10 scattered Ed events checked against physical Mack book (end-to-end validation)
5. **ISS-001: Cache bleed** — CRITICAL, not started. Investigate and fix.

## Short-term (next 1-2 weeks)

4. **Ed Phase 4 Pass 2-3** — Spot-check review of the 198 events
5. **ISS-002: E205 blind spot** — Prompt rule fix for time-lapse detection
6. **Sheila (MACK-004)** — Second Mack experiencer extraction (builds toward R2)
7. **Gender column** — Add to Subjects table (both DBs + INSERT statements)

## Medium-term (next month)

8. **Hopkins full ingestion** — Run the 6 baselined cases through full pipeline into production DB (not just calibration). First non-Bullard data at scale. *Enables R2.*
9. **Deduplication fix** — Address the consistent duplicate-code problem across all calibration cases
10. **memory_retrieval_method** — Populate remaining 205 unknown rows (requires physical Bullard Vol. 2)
11. **Bullard letter** — Send follow-up (4-part structure already agreed)
12. **Case type signature exploration** — Preliminary query: group Bullard 270 events by case type, compute motif frequency distributions per type. *First look at R1.*

## Horizon (future tracks)

13. **"Big Four" intake** — Ingest Jacobs, Hopkins full corpus, Fowler case files. *Enables R2 cross-source and R3 temporal breadth.*
14. **Entity tracking table** — Expand schema to track Species, Height, Eye Shape, Clothing in a new Entities table. *Extends analysis beyond motifs.*
15. **Dashboard upgrades** — Geographic heatmap (R3), time-series slider (R3), Substack export button
16. **RAG chatbot** — Natural language queries against the Matrix with sourced answers
17. **Schema expansion** — Invent new motif codes for post-2000s experiencer data beyond Bullard's 1987 taxonomy. *R1 extension.*

---

## Calibration Baseline

| Case | Investigator | GT | Fidelity | Detection | AI Extras |
|------|-------------|-----|----------|-----------|-----------|
| 084 | Kilburn/Hopkins | 51 | 84.3% | 92.2% | 17 |
| 069 | Howard Rich/Hopkins | 9 | 77.8% | 100% | 8 |
| 180a | Philip Osborne childhood/Hopkins | 16 | 68.8% | 87.5% | 7 |
| 180b | Philip Osborne Pittsburgh/Hopkins | 18 | 72.2% | 83.3% | 5 |
| 181a | Virginia Horton Manitoba/Hopkins | 14 | 85.7% | 100% | 8 |
| 181b | Virginia Horton Alsace/Hopkins | 13 | 53.8% | 92.3% | 12 |
| **Aggregate** | | **151** | | **93.4%** | |

Known blind spots: E200 (time lapse), single-motif-per-sentence on dense passages, vague retrospective language.
