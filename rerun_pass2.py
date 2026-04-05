"""
rerun_pass2.py — Re-run Pass 2 (voice classification) on existing pipeline JSON files.

Uses the extracted text from Step 0 to reconstruct chunks, then runs
classify_voice_tags on the existing events. Saves voice tags back to the JSON.

Usage:
    python rerun_pass2.py staging/steven_kilburn_missing_time_metadata.json
    python rerun_pass2.py staging/howard_rich_missing_time_metadata.json
"""

import json
import sys
import os

from llm_bridge import classify_voice_tags


def main():
    if len(sys.argv) < 2:
        print("Usage: python rerun_pass2.py <pipeline_json_path>")
        sys.exit(1)

    json_path = sys.argv[1]

    # Load pipeline JSON
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Get the source text path
    text_path = data["step_0"]["source_text_path"]
    if not os.path.exists(text_path):
        print(f"ERROR: Source text not found at {text_path}")
        sys.exit(1)

    # Read the source text
    with open(text_path, "r", encoding="utf-8") as f:
        text = f.read()

    # Reconstruct chunks using the same logic as extract_narrative
    paragraphs = text.split('\n')
    chunks = []
    current_chunk = ""
    for para in paragraphs:
        if len(current_chunk) + len(para) > 3000:
            chunks.append(current_chunk)
            current_chunk = para + "\n"
        else:
            current_chunk += para + "\n"
    if current_chunk.strip():
        chunks.append(current_chunk)

    print(f"[*] Reconstructed {len(chunks)} chunks from {text_path}")

    # Build events_json in the format classify_voice_tags expects
    events_json = []
    for ev in data["step_3_extraction"]["encounter_events"]:
        events_json.append({
            "sequence": ev["sequence_order"],
            "motif_code": ev["motif_code"],
            "citation": ev["source_citation"],
            "chunk": ev["chunk"],
            "reasoning": ev.get("ai_justification", ""),
            "emotional_marker": ev.get("emotional_marker"),
            "memory_state": ev.get("memory_state", "unknown"),
            "source_page": ev.get("source_page", ""),
            "pdf_page": ev.get("pdf_page", ""),
        })

    print(f"[*] {len(events_json)} events to classify")

    # Run Pass 2
    events_json = classify_voice_tags(events_json, chunks, model="claude-opus-4-6")

    # Merge voice tags back into pipeline JSON
    for ev_json, ev_stored in zip(events_json, data["step_3_extraction"]["encounter_events"]):
        ev_stored["voice_speaker"] = ev_json.get("voice_speaker", "investigator")
        ev_stored["voice_content_type"] = ev_json.get("voice_content_type", "testimony")

    # Save
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Summary
    exp = sum(1 for ev in events_json if ev.get("voice_speaker") == "experiencer")
    inv = sum(1 for ev in events_json if ev.get("voice_speaker") == "investigator")
    test = sum(1 for ev in events_json if ev.get("voice_content_type") == "testimony")
    comm = sum(1 for ev in events_json if ev.get("voice_content_type") == "commentary")
    print(f"\n[*] Voice tags saved to {json_path}")
    print(f"    Speaker: {exp} experiencer / {inv} investigator")
    print(f"    Content: {test} testimony / {comm} commentary")


if __name__ == "__main__":
    main()
