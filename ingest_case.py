import argparse
import pdfplumber
import os
import sys
import json
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from llm_bridge import process_narrative

from dotenv import load_dotenv

class CaseMetadata(BaseModel):
    subject: str = Field(description="The name or pseudonym of the subject and their age if available (e.g. 'Ed, mid-40s technician').")
    investigator: str = Field(description="The name and credentials of the primary investigator evaluating the case (e.g. 'Dr. John E. Mack, clinical psychiatrist').")
    hypnosis_used: str = Field(description="Was hypnosis used during this case evaluation? Answer exactly 'YES' or 'NO'.")
    case_id: str = Field(description="A unique, capitalized case ID containing the investigator and subject name (e.g., 'MACK_ED_01').")
    primary_event_summary: str = Field(description="A one-sentence summary of the primary abduction or encounter event that is the central focus of this chapter.")
    temporal_boundaries: str = Field(description="Instructions for the Motif AI extractor on which events to focus on and which peripheral memories (like childhood dreams or regressions not related to the primary event) to ignore. e.g., 'Focus ONLY on the 1989 abduction. Ignore mentions of childhood sightings.'")
    encounter_duration: str = Field(description="The estimated total duration of the encounter or 'missing time' (e.g., '3 Hours', '2 Days'). If no timeframe is explicitly stated or can be inferred, output 'Unknown'.")

def extract_metadata_with_ai(full_text: str) -> CaseMetadata:
    """Uses a Gemini call to read the full chapter text and determine the clinical metadata and temporal boundaries."""
    print("Engaging AI to automatically extract Subject, Investigator, and Temporal Boundaries...")
    load_dotenv()
    client = genai.Client()
    
    prompt = f"Analyze the following full narrative from a UFO abduction case study. Determine the subject's name and age, the primary investigator's credentials, whether hypnosis was utilized, and generate a temporal map for data extraction (a primary event summary and instructions on peripheral memories to ignore).\n\nTEXT:\n{full_text}"
    
    response = client.models.generate_content(
        model='gemini-3.1-pro-preview',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=CaseMetadata,
            temperature=0.1
        )
    )
    
    return response.parsed

def main():
    parser = argparse.ArgumentParser(description="Fully Automated Ingestion Pipeline for the UFO Matrix")
    
    parser.add_argument("--pdf", required=True, help="Path to the PDF source file.")
    parser.add_argument("--start", type=int, required=True, help="Starting page number (1-indexed).")
    parser.add_argument("--end", type=int, required=True, help="Ending page number (1-indexed, inclusive).")
    parser.add_argument("--source", required=True, help="Academic citation for the source material.")
    parser.add_argument("--case-id", required=False, help="Explicitly link the generated events to an existing historical DB index (e.g. '192g'). Overrides AI generation.")

    args = parser.parse_args()

    if not os.path.exists(args.pdf):
        print(f"Error: PDF file '{args.pdf}' not found.")
        sys.exit(1)

    print(f"\n[1/3] Reading '{args.pdf}' (Pages {args.start}-{args.end})...")
    
    raw_text = ""
    with pdfplumber.open(args.pdf) as pdf:
        for page_num in range(args.start - 1, args.end):
            if page_num < len(pdf.pages):
                extracted = pdf.pages[page_num].extract_text()
                if extracted:
                    # Injects Data Provenance Markers explicitly so the LLM chunker knows the physical page bounds
                    raw_text += f"\n\n[--- START PAGE {page_num + 1} ---]\n\n" + extracted + "\n"

    if not raw_text.strip():
        print("Error: No text extracted from the specified pages. Please check your page numbers.")
        sys.exit(1)

    print(f"Successfully extracted {len(raw_text)} characters.")
    
    # Phase 10 Upgrade: Send the FULL TEXT instead of just the first page to generate the Temporal Boundaries map
    print("\n[2/3] Automating Metadata Extraction (Full-Pass Mapping)...")
    metadata: CaseMetadata = extract_metadata_with_ai(raw_text)
    
    if args.case_id:
        metadata.case_id = args.case_id
        print(f"\n[*] DB OVERRIDE: Forcing AI Extractions to attach to Historical Encyclopedia Case '{args.case_id}'")
    
    print("--------------------------------------------------")
    print(f"Subject      : {metadata.subject}")
    print(f"Investigator : {metadata.investigator}")
    print(f"Hypnosis Used: {metadata.hypnosis_used}")
    print(f"Primary Event: {metadata.primary_event_summary}")
    print(f"Boundaries   : {metadata.temporal_boundaries}")
    print(f"Case ID      : {metadata.case_id}")
    print("--------------------------------------------------")
    
    sticky_header = f"""
    [CASE METADATA / STICKY HEADER]
    Subject: {metadata.subject}
    Investigator: {metadata.investigator}
    Hypnosis Used: {metadata.hypnosis_used}
    Primary Event Summary: {metadata.primary_event_summary}
    Temporal Boundaries: {metadata.temporal_boundaries}
    """

    print("\n[3/3] Handoff to LLM Bridge for Motif Extraction & Database Insertion...")
    process_narrative(
        text=raw_text,
        sticky_header=sticky_header,
        source_citation=args.source,
        case_number=metadata.case_id
    )

if __name__ == "__main__":
    main()
