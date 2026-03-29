from pydantic import BaseModel, Field
from typing import List, Optional, Literal


# Phase 3: AI Context and Structured Outputs
# We use Pydantic to strictly define the JSON structure we want the LLM to return.

class EncounterEvent(BaseModel):
    """
    This schema defines a single event (Motif) within a UFO encounter narrative.
    """
    sequence_order: int = Field(description="The chronological order of this event (1, 2, 3, etc.). If multiple traits/actions happen at the exact same moment, assign them the exact same sequence number.")
    motif_code: str = Field(description="The alphanumeric Motif Code assigned to this event (e.g., 'E300'). If the event is a novel concept not covered by Bullard, or if it doesn't perfectly match a dictionary definition (e.g., 'thin hair' is NOT 'sparse hair'), assign the exact string 'ANOMALY'. Do NOT force a fit.")
    source_citation: str = Field(description="The exact quote from the text that justifies this motif code")
    emotional_marker: Optional[str] = Field(description="The primary emotion the subject felt during this specific action (e.g., 'Terror', 'Calm', 'Confusion'). Leave null if not mentioned.")
    memory_state: Literal["conscious", "hypnosis", "altered", "unconscious"] = Field(description="The memory state of the subject during this event. 'conscious' = natural waking recall. 'hypnosis' = recovered via hypnotic regression. 'altered' = non-ordinary state like dream or trance. 'unconscious' = no memory of this period.")
    source_page: str = Field(description="The physical page number(s) where this event is described, derived from the [--- START PAGE X ---] markers in the text (e.g., '42' or '42-43').")
    ai_justification: str = Field(description="When writing the ai_justification field, if the dictionary definition does not obviously match the text Bullard assigned the code to, do not assert that it fits. Instead, state what the dictionary defines the code as, state what the text actually describes, and acknowledge the gap. It is acceptable for Bullard's usage to stretch beyond the dictionary definition — your job is to be transparent about it, not to force a match.")

class EncounterProfile(BaseModel):
    """
    This schema defines the overall output for a complete UFO abduction case.
    It contains the core metadata and the list of chronological events.
    """
    pseudonym: str = Field(description="The name or pseudonym of the subject(s)")
    age: Optional[str] = Field(description="The age of the subject at the time of the encounter, if known")
    gender: Optional[str] = Field(description="The gender of the primary subject (e.g., 'Male', 'Female'), if known")
    date_of_encounter: Optional[str] = Field(description="The date the encounter occurred")
    location: Optional[str] = Field(description="The geographic location of the encounter")
    encounter_duration: Optional[str] = Field(description="The estimated total duration of the encounter or 'missing time'")
    principal_investigator: Optional[str] = Field(description="The name and credentials of the primary investigator evaluating the case")
    number_of_witnesses: Optional[int] = Field(description="The number of people who witnessed the event (integer, e.g. 1)")
    entity_type: Optional[str] = Field(description="The physical typology of the entities (e.g., 'Grey', 'Humanoid', 'Reptilian', 'Nordic')")
    investigator_credibility: Literal["0", "1", "2", "3", "4", "5"] = Field(description="Using the Bullard scale (0-5), rate the credibility of the INVESTIGATION based on the methods used. e.g. '5' for highly reliable, '0' for known hoax.")
    witness_credibility: Literal["0", "1", "2", "3", "4", "5"] = Field(description="Using the Bullard scale (0-5), rate the credibility of the WITNESS report itself. e.g. '5' for multiple reliable witnesses, '0' for known hoax.")
    narrative_summary: str = Field(description="A brief 1-paragraph summary of the entire event")
    events: List[EncounterEvent] = Field(description="The chronological sequence of motif events in this encounter")

    pass

class CaseMetadata(BaseModel):
    hypnosis_used: Literal["YES", "NO"]
    memory_retrieval_method: Literal["conscious", "hypnosis", "altered", "mixed", "unknown"]

import os
import sqlite3
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

def process_narrative(text: str, sticky_header: str, source_citation: str, case_number: str):
    """
    Processes a raw UFO narrative text block through Gemini, structuring the events
    based on the Motif Dictionary, and saves them to the ufo_matrix.db database.
    """
    load_dotenv()
    client = genai.Client()

    # --- CHUNKING LOGIC ---
    # The ideal ingestion size for maximum detail is about 500-800 words per prompt.
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
    
    print(f"Divided the narrative into {len(chunks)} high-detail chunks.")

    # Grab Motif Codes from database
    motif_rules = ""
    with sqlite3.connect('ufo_matrix.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT motif_number, motif_description FROM Motif_Dictionary")
        for row in cursor.fetchall():
            motif_rules += f"- {row[0]}: {row[1]}\n"

        # Query the pre-populated retrieval method for this specific case
        cursor.execute(
            "SELECT memory_retrieval_method FROM Encounters WHERE Case_Number = ? COLLATE NOCASE",
            (case_number,)
        )
        retrieval_row = cursor.fetchone()

    RETRIEVAL_CONTEXT_MAP = {
        'hypnosis':  'RETRIEVAL METHOD CONTEXT: This entire account was recovered under hypnotic regression with a clinical investigator. Every event in this text must be assigned memory_state="hypnosis" unless the text explicitly states otherwise for a specific event.',
        'conscious': 'RETRIEVAL METHOD CONTEXT: This account was recalled consciously by the witness without hypnotic regression. Every event must be assigned memory_state="conscious" unless the text explicitly states otherwise.',
        'altered':   'RETRIEVAL METHOD CONTEXT: This account was recalled in a non-ordinary state (dream, trance, or similar). Every event must be assigned memory_state="altered" unless the text explicitly states otherwise.',
        'mixed':     'RETRIEVAL METHOD CONTEXT: This account contains a mix of hypnotically and consciously recalled events. Assign memory_state on a per-event basis based on the text.',
        'unknown':   'RETRIEVAL METHOD CONTEXT: The retrieval method for this account is unknown. Assign memory_state based on any explicit cues in the text; default to "conscious" if no cue is present.',
    }

    retrieval_method = retrieval_row[0] if retrieval_row else 'unknown'
    retrieval_context = RETRIEVAL_CONTEXT_MAP.get(retrieval_method, RETRIEVAL_CONTEXT_MAP['unknown'])
    print(f"[*] Retrieval method for '{case_number}': {retrieval_method}")

    with open("prompt_library.json", "r", encoding="utf-8") as f:
        prompt_lib = json.load(f)
    
    profile = prompt_lib.get("profiles", {}).get("baseline", {})
    
    # Reassemble the string arrays
    sys_inst_text = "\n".join(profile.get("system_instruction", []))
    few_shot_examples = "\n".join(profile.get("few_shot_examples", []))
    anti_hallucination_rules = "\n".join(profile.get("anti_hallucination_rules", []))
    
    system_instruction = f"""
    {sys_inst_text}
    
    {few_shot_examples}
    
    {anti_hallucination_rules}
    
    BULLARD MOTIF DICTIONARY:
    {motif_rules}
    
    You MUST output valid JSON matching the requested schema.
    """

    print("Checking Google Servers to see if Volume 1 is already Cached...")
    cached_context = None
    try:
        caches = list(client.caches.list())
        if caches:
            cached_context = caches[0]
            print(f"[*] Found ACTIVE Cache ({cached_context.name}). Reusing it for $0 to save costs!\n")
    except Exception as e:
        print(f"DEBUG: Exception during cache listing: {e}")

    if not cached_context:
        print("Uploading Bullard Volume 1 Context Guide to Gemini API...")
        try:
            bullard_vol1 = client.files.upload(file=os.path.join("Sources", "bullard_vol1_raw.txt"))
            print(f"File uploaded! File URI: {bullard_vol1.uri}")
            
            print("Caching the book into the AI's permanent memory...")
            cached_context = client.caches.create(
                model='gemini-2.5-pro',
                config=types.CreateCachedContentConfig(
                    contents=[bullard_vol1],
                    system_instruction=system_instruction,
                    display_name="bullard_vol_1_cache",
                    ttl="3600s"
                )
            )
            print("Successfully cached!\n")
            
        except Exception as e:
            print(f"File upload to Gemini failed: {e}")
            print("Please check your API key quotas or file path.")
            return

    print("Sending raw text to Gemini using the Cached Brain...\n")

    all_events = []
    final_profile = None

    for chunk_idx, chunk_text in enumerate(chunks):
        print(f"\n--- PROCESSING CHUNK {chunk_idx + 1} OF {len(chunks)} ---")
        
        payload = f"{retrieval_context}\n\n{sticky_header}\n\n[NARRATIVE CHUNK]\n{chunk_text}"
        
        response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=payload,
            config=types.GenerateContentConfig(
                cached_content=cached_context.name,
                response_mime_type="application/json",
                response_schema=EncounterProfile,
                temperature=0.1
            ),
        )

        profile: EncounterProfile = response.parsed
        
        if chunk_idx == 0:
            final_profile = profile
            
        all_events.extend(profile.events)
        print(f"  -> Extracted {len(profile.events)} motif events from this chunk.")

    print("\nSUCCESS! Chunking complete. Committing to UFO Matrix Database...")
    print(f"Subject: {final_profile.pseudonym}")
    print(f"Date: {final_profile.date_of_encounter}")
    print(f"Summary: {final_profile.narrative_summary}\n")

    with sqlite3.connect('ufo_matrix.db', timeout=15) as conn:
        cursor = conn.cursor()
        
        # Determine Hypnosis state from Sticky Header dynamically
        hypnosis_val = "YES" if "HYPNOSIS" in sticky_header.upper() else "NO"
        case_meta = CaseMetadata(
            hypnosis_used=hypnosis_val,
            memory_retrieval_method=retrieval_method
        )

        cursor.execute("SELECT Encounter_ID, Subject_ID FROM Encounters WHERE Case_Number COLLATE NOCASE = ?", (case_number,))
        existing_encounter = cursor.fetchone()
        
        if existing_encounter:
            encounter_id = existing_encounter[0]
            subject_id = existing_encounter[1]
            print(f"[*] Found Existing Database Entry (Encounter ID: {encounter_id}) for Case '{case_number}'.")
            print(f"[*] AI Motifs will be appended to this existing historical index.")
            
            # Delete any previously extracted events for this specific Encounter to allow clean overwrites during prompt-tuning
            cursor.execute("DELETE FROM Encounter_Events WHERE Encounter_ID = ?", (encounter_id,))
            print(f"[*] Cleared previous events for Encounter {encounter_id} to prepare for fresh LLM extraction.")
            
        else:
            cursor.execute("""
                INSERT INTO Subjects (Pseudonym, Age, Gender, Baseline_Psychology, Hypnosis_Utilized)
                VALUES (?, ?, ?, ?, ?)
            """, (final_profile.pseudonym, final_profile.age, final_profile.gender, final_profile.narrative_summary, case_meta.hypnosis_used))
            
            subject_id = cursor.lastrowid
            print(f"[*] Created Subject Record (ID: {subject_id})")
            
            cursor.execute("""
                INSERT INTO Encounters (Subject_ID, Case_Number, Date_of_Encounter, Location_Type, Investigator_Credibility, Witness_Credibility, Source_Material, Encounter_Duration, Principal_Investigator, Number_of_Witnesses, Entity_Type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (subject_id, case_number, final_profile.date_of_encounter, final_profile.location, final_profile.investigator_credibility, final_profile.witness_credibility, source_citation, final_profile.encounter_duration, final_profile.principal_investigator, final_profile.number_of_witnesses, final_profile.entity_type))            
            encounter_id = cursor.lastrowid
            print(f"[*] Created Encounter Record (ID: {encounter_id})")

        print("\n--- PERMANENT SQL INGESTION ---")
        last_code_printed = None
        global_sequence = 1
        last_chunk_sequence = -1
        
        for event in all_events:
            if event.motif_code == last_code_printed and event.sequence_order == last_chunk_sequence:
                continue
                
            last_code_printed = event.motif_code
            
            if event.sequence_order != last_chunk_sequence:
                if last_chunk_sequence != -1:
                    global_sequence += 1
                last_chunk_sequence = event.sequence_order

            if event.motif_code == "ANOMALY":
                description = "[[NOVEL CONCEPT - NOT IN BULLARD]]"
            else:
                cursor.execute("SELECT motif_description FROM Motif_Dictionary WHERE motif_number = ?", (event.motif_code,))
                result = cursor.fetchone()
                description = result[0] if result else "[[WARNING: AI HALLUCINATED FAKE CODE]]"
            
            try:
                cursor.execute("""
                    INSERT INTO Encounter_Events (Encounter_ID, Sequence_Order, Motif_Code, Emotional_Marker, Source_Citation, memory_state, source_page, ai_justification)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (encounter_id, global_sequence, event.motif_code, event.emotional_marker, event.source_citation, event.memory_state, event.source_page, event.ai_justification))
                
                emotion_str = f"Emotion: {event.emotional_marker}" if event.emotional_marker else "No explicit emotion"
                
                # Sanitize output for Windows terminal, ignoring unmappable unicode characters from PDF artifacts
                safe_desc = description.encode('cp1252', errors='ignore').decode('cp1252')
                safe_quote = event.source_citation.encode('cp1252', errors='ignore').decode('cp1252')
                safe_logic = event.ai_justification.encode('cp1252', errors='ignore').decode('cp1252')

                print(f"[{global_sequence}] DATABASE INSERT -> {event.motif_code}: {safe_desc}")
                print(f"    Page {event.source_page} | State: {event.memory_state.upper()} | {emotion_str}")
                print(f"    Quote: '{safe_quote}'")
                print(f"    AI Logic: {safe_logic}\n")
                
            except sqlite3.IntegrityError:
                print(f"    [X] DB REJECTED HALLUCINATED CODE: {event.motif_code}")

        conn.commit()
        print(f"\n[!!!] Phase 9 Complete: Successfully wrote all validated events directly into ufo_matrix.db!")
