"""
run_mack_ch3.py — One-shot runner for Mack Chapter 3 (Ed) extraction + staging.

Runs the full pipeline (Steps 0, 1, 3) and loads results into ufo_matrix_staging.db.
"""

import os
import json

# Must run from the project root
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from pipeline_ingest import (
    scan_front_matter, extract_pdf_text, scan_metadata,
    _build_pipeline_json, _make_pipeline_json_path, make_output_stem,
)
from llm_bridge import extract_narrative, classify_voice_tags, load_to_database

# --- Configuration ---
PDF_PATH = "Sources/John E. Mack, MD - Abduction - Human Encounters with Aliens.pdf"
START_PAGE = 51
END_PAGE = 68
MODEL = "claude-opus-4-6"
STAGING_DB = "ufo_matrix_staging.db"
CASE_NUMBER = "MACK-003"   # Mack chapter 3

os.makedirs("staging", exist_ok=True)

# Step 0A: Front-matter scan (bibliographic attribution)
print("=" * 65)
print("  MACK CHAPTER 3 (ED) — FULL PIPELINE RUN")
print("=" * 65)

attribution = scan_front_matter(PDF_PATH, START_PAGE)

# Step 0B: Extract text from PDF pages 51–68
pages, full_text = extract_pdf_text(PDF_PATH, START_PAGE, END_PAGE)

# Save extracted text
stem = make_output_stem(PDF_PATH, START_PAGE, END_PAGE)
text_output_path = os.path.join("staging", f"extracted_text_{stem}.txt")
with open(text_output_path, "w", encoding="utf-8") as f:
    f.write(full_text)
print(f"\n[*] Extracted text saved to: {text_output_path}")

# Step 1: Metadata scan via Gemini Flash
metadata = scan_metadata(full_text, PDF_PATH, START_PAGE, END_PAGE,
                         attribution=attribution)

# Build and save pipeline JSON
pipeline_json = _build_pipeline_json(
    metadata, attribution, text_output_path,
    START_PAGE, END_PAGE, pages,
)
json_path = _make_pipeline_json_path(metadata, attribution)
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(pipeline_json, f, indent=2, ensure_ascii=False)
print(f"\n[*] Pipeline JSON saved to: {json_path}")

# Display metadata for review (no interactive prompt — just print)
s1 = pipeline_json["step_1_scanned_metadata"]
print()
print("=" * 65)
print("  METADATA SUMMARY (auto-confirmed)")
print("=" * 65)
print(f"  Experiencer:  {s1['experiencer_name'] or 'None'}")
print(f"  Structure:    {s1['narrative_structure']}")
print(f"  Retrieval:    {s1['memory_retrieval_method']}")
print(f"  Investigator: {s1['principal_investigator'] or 'None'}")
print("=" * 65)

# Step 3: Extraction via Claude Opus 4.6
print(f"\n[*] Starting Step 3: Extraction (model: {MODEL})...")
final_profile, all_events, ai_events_json, chunks = extract_narrative(
    pipeline_json_path=json_path,
    profile_name="baseline_test",
    model=MODEL,
    include_vol1=False,
)
print(f"\n[*] Pass 1 extraction complete: {len(all_events)} events")

# Step 3b: Voice classification (Pass 2)
ai_events_json = classify_voice_tags(ai_events_json, chunks, model=MODEL)

# Step 4: Load to staging database
print(f"\n[*] Loading results to staging database: {STAGING_DB}...")

# Build source citation from attribution
sa = pipeline_json["step_1_source_attribution"]
source_citation = f"{sa['author_name']}, {sa['title']}"
if sa.get("publication_year"):
    source_citation += f" ({sa['publication_year']})"

retrieval_method = s1["memory_retrieval_method"]

load_to_database(
    final_profile=final_profile,
    all_events=all_events,
    case_number=CASE_NUMBER,
    source_citation=source_citation,
    retrieval_method=retrieval_method,
    db_path=STAGING_DB,
    metadata_scan=s1,
    voice_data=ai_events_json,
)

print(f"\n{'=' * 65}")
print(f"  DONE — {len(all_events)} events staged in {STAGING_DB}")
print(f"  Case: {CASE_NUMBER} (Ed, Chapter 3)")
print(f"{'=' * 65}")
