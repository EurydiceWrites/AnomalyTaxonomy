import argparse
import os
import sys
import json
import sqlite3
from datetime import datetime
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from dotenv import load_dotenv

from typing import Optional

class CaseMetadataFull(BaseModel):
    subject: str = Field(description="The name of the subject (e.g., 'Andreassen, Betty'). Do not include the case number.")
    age: Optional[int] = Field(description="The age of the subject if listed in the header. Usually not present.")
    gender: Optional[str] = Field(description="The gender of the subject based on the name.")
    investigator: str = Field(description="The primary investigator, derived from 'Inv:'.")
    hypnosis_used: bool = Field(description="Was hypnosis used? Derived from 'Hypnosis: Yes' or 'Hypnosis: No'.")
    date_of_encounter: str = Field(description="The date or season of the encounter (e.g., '1967' or 'Spring 1967').")
    location: str = Field(description="The geographic location (e.g., 'Mass.').")
    number_of_witnesses: Optional[int] = Field(description="The number of witnesses if explicitly listed. Default is 1 if not.")
    duration: Optional[str] = Field(description="The duration if explicitly listed in the header. Usually not present.")
    entity_type: Optional[str] = Field(description="The entity type if explicitly listed. Usually not present in the header.")

class ExtractionEvent(BaseModel):
    sequence_order: int = Field(description="Chronological order of the motif in the chunk (1, 2, 3...)")
    motif_code: str = Field(description="The exact alphanumeric code written by Bullard (or corrected OCR typo)")
    source_citation: str = Field(description="The exact quote from the text that Bullard attached this code to")
    source_page: str = Field(description="The physical page number(s) where this was extracted from")

class ExtractionProfile(BaseModel):
    events: list[ExtractionEvent] = Field(description="List of all motif codes explicitly typed by Bullard in this text")

def main():
    parser = argparse.ArgumentParser(description="Bullard Encyclopedia Transcription Tool")
    parser.add_argument("--start", type=int, required=True, help="Starting page number (1-indexed).")
    parser.add_argument("--end", type=int, required=True, help="Ending page number (1-indexed, inclusive).")
    parser.add_argument("--case-id", required=True, help="Historical Case ID to assign these events to (e.g. '192g').")
    args = parser.parse_args()

    # Phase 1, Step 1: Utilize previously generated Raw Text File
    txt_path = "Sources/bullard_vol2_raw.txt"
    if not os.path.exists(txt_path):
        print("Error: Vol 2 raw text file not found.")
        sys.exit(1)

    print(f"\n[1/3] Reading '{txt_path}' to extract Pages {args.start}-{args.end}...")
    with open(txt_path, "r", encoding="utf-8") as f:
        full_text = f.read()

    # Split by pages using the physical headers our extraction script injected
    pages = full_text.split("[--- START PAGE ")
    
    extracted_text = ""
    for page_chunk in pages[1:]:
        header_end = page_chunk.find("---]")
        if header_end != -1:
            try:
                page_num_str = page_chunk[:header_end].strip()
                page_num = int(page_num_str)
                if args.start <= page_num <= args.end:
                    extracted_text += f"\n\n[--- START PAGE {page_num} ---]\n\n{page_chunk[header_end + 4:]}"
            except ValueError:
                pass

    if not extracted_text.strip():
        print("Error: No text found for those pages.")
        sys.exit(1)

    print(f"Successfully extracted {len(extracted_text)} characters for Case {args.case_id}.")
    
    # Phase 1, Step 2: AI Typo Cleansing / Transcription
    print("\n[2/3] Calling Gemini for Strict Motifs Transcription...")
    load_dotenv()
    client = genai.Client()

    with open("prompt_library.json", "r", encoding="utf-8") as f:
        prompt_lib = json.load(f)
    profile = prompt_lib.get("profiles", {}).get("bullard_transcriber", {})
    
    sys_inst_text = "\n".join(profile.get("system_instruction", []))
    few_shot_examples = "\n".join(profile.get("few_shot_examples", []))
    anti_hallucination_rules = "\n".join(profile.get("anti_hallucination_rules", []))
    
    # Grab Motif Codes from database for OCR typo fixing
    print("Loading valid motif codes for OCR typo correction...")
    with sqlite3.connect('ufo_matrix.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT motif_number FROM Motif_Dictionary")
        valid_codes = [row[0] for row in cursor.fetchall()]

    system_instruction = f"{sys_inst_text}\n\n{few_shot_examples}\n\n{anti_hallucination_rules}\n\nVALID MOTIF CODES (FOR OCR TYPO CORRECTION ONLY):\n{', '.join(valid_codes)}"

    print("Generating structured output via Gemini 2.5 Pro...")
    try:
        response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=f"Extract all explicitly written Motif Codes from this text:\n\n{extracted_text}",
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=ExtractionProfile,
                temperature=0.0
            )
        )
        
        print("\n[2.5/3] Extracting top-level metadata from Case Headers...")
        metadata_response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"Read the structured header text at the very beginning of this case file and extract the data points. If a point isn't explicitly listed in the short header block, leave it null.\n\nTEXT:\n{extracted_text[:1500]}",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=CaseMetadataFull,
                temperature=0.0
            )
        )
    except Exception as e:
        print(f"Error calling Gemini: {e}")
        sys.exit(1)

    result_profile: ExtractionProfile = response.parsed
    if result_profile is None:
        print("\n[!] CRITICAL ERROR: Gemini API structured output failed to parse into Pydantic model.")
        try:
            print("Raw Output Dump:")
            print(response.text)
        except Exception:
            print("Could not retrieve raw text. Generation may have been blocked or aborted.")
        sys.exit(1)

    events = result_profile.events
    meta: CaseMetadataFull = metadata_response.parsed
    
    if not events:
        print("Warning: Gemini returned 0 explicitly written motif codes. Is this correct?")

    # Phase 1, Step 3: Rigid Database Insertion
    print(f"\n[3/3] Found {len(events)} Explicit Motifs. Appending to Database...")
    with sqlite3.connect('ufo_matrix.db', timeout=15) as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT Encounter_ID FROM Encounters WHERE Case_Number COLLATE NOCASE = ?", (args.case_id,))
        existing = cursor.fetchone()
        
        if not existing:
            # We must create a skeleton Subjects and Encounter record for this historical case
            cursor.execute("INSERT INTO Subjects (Pseudonym, Age, Gender, Baseline_Psychology, Hypnosis_Utilized) VALUES (?, ?, ?, ?, ?)", (meta.subject, meta.age, meta.gender, "N/A - Transcription", meta.hypnosis_used))
            subject_id = cursor.lastrowid
            
            cursor.execute("""
                INSERT INTO Encounters (Subject_ID, Case_Number, Date_of_Encounter, Location_Type, Conscious_Recall, Investigator_Credibility, Witness_Credibility, Source_Material, is_hypnosis_used, Encounter_Duration, Principal_Investigator, Number_of_Witnesses, Entity_Type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (subject_id, args.case_id, meta.date_of_encounter, meta.location, not meta.hypnosis_used, "3", "3", "Bullard Vol 2", meta.hypnosis_used, meta.duration, meta.investigator, meta.number_of_witnesses, meta.entity_type))
            encounter_id = cursor.lastrowid
            print(f"[*] Created Populated Header Record for Case {args.case_id} (Encounter ID: {encounter_id})")
        else:
            encounter_id = existing[0]
            print(f"[*] Found Existing Record for Case {args.case_id} (Encounter ID: {encounter_id}). Updating Metadata and clearing previous events...")
            
            # Update Existing Encounter with fresh Flash Metadata
            cursor.execute("""
                UPDATE Encounters 
                SET Date_of_Encounter = ?, Location_Type = ?, Conscious_Recall = ?, is_hypnosis_used = ?, Encounter_Duration = ?, Principal_Investigator = ?, Number_of_Witnesses = ?, Entity_Type = ?
                WHERE Encounter_ID = ?
            """, (meta.date_of_encounter, meta.location, not meta.hypnosis_used, meta.hypnosis_used, meta.duration, meta.investigator, meta.number_of_witnesses, meta.entity_type, encounter_id))
            
            # Update Existing Subject with fresh Flash Metadata
            cursor.execute("SELECT Subject_ID FROM Encounters WHERE Encounter_ID = ?", (encounter_id,))
            subj = cursor.fetchone()
            if subj:
                cursor.execute("""
                    UPDATE Subjects
                    SET Pseudonym = ?, Age = ?, Gender = ?, Hypnosis_Utilized = ?
                    WHERE Subject_ID = ?
                """, (meta.subject, meta.age, meta.gender, meta.hypnosis_used, subj[0]))
            
            cursor.execute("DELETE FROM Encounter_Events WHERE Encounter_ID = ?", (encounter_id,))

        # Capture the exact time the DB insertion begins (ISO 8601 format)
        current_timestamp = datetime.now().isoformat()

        for evt in events:
            # Check if code is valid
            code = evt.motif_code.upper()
            if code not in valid_codes and code != 'ANOMALY':
                code = 'ANOMALY' # enforce strictness if the AI failed
                
            cursor.execute("""
                INSERT INTO Encounter_Events (Encounter_ID, Sequence_Order, Motif_Code, Emotional_Marker, Source_Citation, memory_state, source_page, ai_justification, run_timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (encounter_id, evt.sequence_order, code, None, evt.source_citation, "N/A - Transcription", evt.source_page, "Bullard Master Transcriber", current_timestamp))
            
            safe_quote = evt.source_citation.encode('cp1252', errors='ignore').decode('cp1252')
            print(f"  [{evt.sequence_order}] INSERTED: {code} -> '{safe_quote}'")

    print(f"\n[!!!] Complete. {len(events)} verbatim motifs saved for {args.case_id}.")

if __name__ == "__main__":
    main()
