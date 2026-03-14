from pydantic import BaseModel, Field
from typing import List, Optional


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
    memory_state: str = Field(description="The mental state of the subject when they recalled or experienced this specific event. Choose EXACTLY one: 'conscious', 'hypnotic', or 'dream'.")
    source_page: str = Field(description="The physical page number(s) where this event is described, derived from the [--- START PAGE X ---] markers in the text (e.g., '42' or '42-43').")
    ai_justification: str = Field(description="A brief explanation of why this specific Motif Code was chosen for this quote.")

class EncounterProfile(BaseModel):
    """
    This schema defines the overall output for a complete UFO abduction case.
    It contains the core metadata and the list of chronological events.
    """
    pseudonym: str = Field(description="The name or pseudonym of the subject(s)")
    age: Optional[str] = Field(description="The age of the subject at the time of the encounter, if known")
    date_of_encounter: Optional[str] = Field(description="The date the encounter occurred")
    location: Optional[str] = Field(description="The geographic location of the encounter")
    investigator_credibility: str = Field(description="Using the Bullard scale (1-5), rate the credibility of the INVESTIGATION based on the methods used. e.g. '5' for highly reliable, '1' for hearsay.")
    witness_credibility: str = Field(description="Using the Bullard scale (1-5), rate the credibility of the WITNESS report itself. e.g. '5' for multiple reliable witnesses, '1' for implausible story.")
    narrative_summary: str = Field(description="A brief 1-paragraph summary of the entire event")
    events: List[EncounterEvent] = Field(description="The chronological sequence of motif events in this encounter")

    pass

import os
import sqlite3
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

    few_shot_examples = """
    *** FEW-SHOT EXAMPLE (From Case 062: Jim and Sue) ***
    If the raw text says:
    "She tried to call her husband but the house lights suddenly went out. Jim found her on the floor, but she could not move and blacked out again. A light shone in and both witnesses floated up to the saucer-shaped craft. They gave both witnesses a drink. The beings told the witnesses to forget."
    
    You would extract the following chronological Motif Codes based on the dictionary:
    1. E400 (house lights suddenly went out)
    2. E315 (she could not move)
    2. E200 (blacked out again)  <-- NOTE: Same sequence number as above because it happened simultaneously!
    3. U120 (A light shone in)
    3. U100 (saucer-shaped craft) <-- NOTE: Same sequence number because it is described at the same time.
    4. X310 (gave both witnesses a drink)
    5. M119 (told the witnesses to forget)
    """

    system_instruction = f"""
    You are an objective folklorist analyzing UFO abduction narratives.
    Extract the subject metadata and break the narrative down into a chronological sequence of Motif events.
    
    CREDIBILITY SCORING RUBRIC (BULLARD SCALE 1-5):
    You must score the Investigator and Witness credibility based on the following scale:
    INVESTIGATION RATING:
    5 = Highly reliable investigation.
    4 = Probably well qualified.
    3 = Unfamiliar investigators or personal deposition from witness.
    2 = Report comes via good source but with no known investigation.
    1 = Newspaper, hearsay.
    
    WITNESS (CASE) RATING:
    5 = 2+ reliable witnesses testify.
    4 = 1 reliable witness testifies.
    3 = Witness of unknown reliability, but no reason to doubt.
    2 = Doubtful witness or insufficient information.
    1 = Very doubtful witness, scanty data, implausible story.

    CONTEXTUAL RULES FOR CLINICAL PSYCHIATRY:
    1. When evaluating Investigator Credibility, treat clinical psychiatric evaluation by licensed medical professionals (like Dr. John Mack) as the equivalent of a 'Highly Reliable Investigation' (Score 5), even though it is clinical rather than physical.
    2. When evaluating Witness Credibility for single-witness events, do not penalize the score for a lack of a second witness. Instead, evaluate the witness based on their psychological consistency, intense emotional affect, and lack of overt psychopathology as documented by the clinician. A highly consistent, deeply affected solo experiencer should score a 4 or 5.
    3. DATA PROVENANCE: Use the '[--- START PAGE X ---]' markers in the text to definitively populate the 'source_page' for each Motif.
    4. MEMORY STATE: Determine the 'memory_state' based on context. "Under hypnosis, he recalled..." = 'hypnotic'. Screen memories experienced prior = 'conscious'.
    5. TEMPORAL BOUNDARIES: Use the temporal boundaries in the Sticky Header to relentlessly filter out peripheral memories and extract ONLY Motifs related to the Primary Event.

    You MUST ONLY USE the Motif Codes from the strict dictionary provided below. Do not invent codes.
    WARNING: DO NOT FORCE A FIT. If the text describes a novel concept, or a descriptor that doesn't perfectly align with the dictionary (e.g., 'thin hair' does NOT mean 'sparse hair'), YOU MUST assign the exact string 'ANOMALY' instead of guessing a motif code. False positives are catastrophic to the matrix. If in doubt, use ANOMALY.
    
    {few_shot_examples}
    
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
        print("Uploading 1,000-page Bullard Volume 1 Context Guide to Gemini API...")
        try:
            bullard_vol1 = client.files.upload(file=os.path.join("Sources", "Bullard, Thomas - UFO Abductions, The Measure of a Mystery - Volume 1.pdf"))
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
        
        payload = f"{sticky_header}\n\n[NARRATIVE CHUNK]\n{chunk_text}"
        
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

    with sqlite3.connect('ufo_matrix.db') as conn:
        cursor = conn.cursor()
        
        # Determine Hypnosis state from Sticky Header dynamically
        hypnosis_used = "YES" in sticky_header.upper()

        cursor.execute("""
            INSERT INTO Subjects (Pseudonym, Age, Baseline_Psychology, Hypnosis_Utilized)
            VALUES (?, ?, ?, ?)
        """, (final_profile.pseudonym, final_profile.age, final_profile.narrative_summary, hypnosis_used))
        
        subject_id = cursor.lastrowid
        print(f"[*] Created Subject Record (ID: {subject_id})")
        
        cursor.execute("""
            INSERT INTO Encounters (Subject_ID, Case_Number, Date_of_Encounter, Location_Type, Conscious_Recall, Investigator_Credibility, Witness_Credibility, Source_Material, is_hypnosis_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (subject_id, case_number, final_profile.date_of_encounter, final_profile.location, not hypnosis_used, final_profile.investigator_credibility, final_profile.witness_credibility, source_citation, hypnosis_used))

        
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
