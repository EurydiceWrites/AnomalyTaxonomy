from pydantic import BaseModel, Field
from typing import List, Optional


# Phase 3: AI Context and Structured Outputs
# We use Pydantic to strictly define the JSON structure we want the LLM to return.

class EncounterEvent(BaseModel):
    """
    This schema defines a single event (Motif) within a UFO encounter narrative.
    """
    sequence_order: int = Field(description="The chronological order of this event (1, 2, 3, etc.). If multiple traits/actions happen at the exact same moment, assign them the exact same sequence number.")
    motif_code: str = Field(description="The alphanumeric Motif Code assigned to this event (e.g., 'E300'). If the event is a novel concept not covered by Bullard, assign the exact string 'ANOMALY'.")
    source_citation: str = Field(description="The exact quote from the text that justifies this motif code")
    emotional_marker: Optional[str] = Field(description="The primary emotion the subject felt during this specific action (e.g., 'Terror', 'Calm', 'Confusion'). Leave null if not mentioned.")
    
    pass

class EncounterProfile(BaseModel):
    """
    This schema defines the overall output for a complete UFO abduction case.
    It contains the core metadata and the list of chronological events.
    """
    pseudonym: str = Field(description="The name or pseudonym of the subject(s)")
    age: Optional[str] = Field(description="The age of the subject at the time of the encounter, if known")
    date_of_encounter: Optional[str] = Field(description="The date the encounter occurred")
    location: Optional[str] = Field(description="The geographic location of the encounter")
    investigator_credibility: str = Field(description="Rate the credibility of the investigator based on their methods (Low, Medium, High). Provide a 1-sentence justification.")
    witness_credibility: str = Field(description="Rate the credibility of the witness based on their psychological state and consistency (Low, Medium, High). Provide a 1-sentence justification.")
    narrative_summary: str = Field(description="A brief 1-paragraph summary of the entire event")
    events: List[EncounterEvent] = Field(description="The chronological sequence of motif events in this encounter")

    pass

if __name__ == "__main__":
    import os
    from google import genai
    from google.genai import types

    # --- RUN CONFIGURATION ---
    # We use APA Academic Citation style to strictly track the original document.
    # Change this whenever you scan a new book into the pipeline!
    ACADEMIC_SOURCE_CITATION = "Mack, J. E. (1994). Abduction: Human Encounters with Aliens. Scribner."

    # 1. We tell the AI about its identity and goal
    system_instruction = """
    You are an objective folklore database manager and investigative assistant.
    Extract the subject metadata and break the narrative down into a chronological sequence of Motif events.
    
    You MUST ONLY USE the Motif Codes from the strict dictionary provided below. Do not invent codes.
    If you are unsure, pick the closest fitting code.
    
    {few_shot_examples}
    
    BULLARD MOTIF DICTIONARY:
    {motif_rules}
    
    You MUST output valid JSON matching the requested schema.
    """

    # 1. Initialize the modern Gemini API Client
    # It automatically looks for the GEMINI_API_KEY environment variable
    client = genai.Client()

    # 2. Here is a totally unstructured, raw chapter from John Mack's book ("Ed" Case)
    with open("mack_sample_text.txt", "r", encoding="utf-8") as f:
        raw_abduction_text = f.read()

    # --- CHUNKING LOGIC ---
    # The ideal ingestion size for maximum detail is about 500-800 words per prompt.
    # We split the massive text into chunks of ~3000 characters (about 500 words).
    paragraphs = raw_abduction_text.split('\n')
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
    
    print(f"Divided the 16-page narrative into {len(chunks)} high-detail chunks.")

    # 3. We define our instructions (The Prompt)
    import sqlite3
    
    # First, let's grab all 300+ real Motif Codes from your database!
    motif_rules = ""
    with sqlite3.connect('ufo_matrix.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT motif_number, motif_description FROM Motif_Dictionary")
        for row in cursor.fetchall():
            motif_rules += f"- {row[0]}: {row[1]}\n"

    # Now we provide the Few-Shot Examples from our perfect dataset (This teaches the AI the pattern!)
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

    # Now we inject BOTH the dictionary AND the examples directly into the AI's "brain" for this query
    system_instruction = f"""
    You are an objective folklorist analyzing UFO abduction narratives.
    Extract the subject metadata and break the narrative down into a chronological sequence of Motif events.
    
    You MUST ONLY USE the Motif Codes from the strict dictionary provided below. Do not invent codes.
    If you are unsure, pick the closest fitting code.
    
    {few_shot_examples}
    
    BULLARD MOTIF DICTIONARY:
    {motif_rules}
    
    You MUST output valid JSON matching the requested schema.
    """

    print("Checking Google Servers to see if Volume 1 is already Cached...")
    cached_context = None
    try:
        # Check if we already uploaded it in the last 60 minutes!
        caches = list(client.caches.list())
        if caches:
            cached_context = caches[0]
            print(f"[*] Found ACTIVE Cache ({cached_context.name}). Reusing it for $0 to save costs!\n")
    except Exception as e:
        print(f"DEBUG: Exception during cache listing: {e}")

    if not cached_context:
        print("Uploading 1,000-page Bullard Volume 1 Context Guide to Gemini API...")
        try:
            # 4. Upload the massive PDF directly to Gemini's secure file storage.
            bullard_vol1 = client.files.upload(file=os.path.join("Sources", "Bullard, Thomas - UFO Abductions, The Measure of a Mystery - Volume 1.pdf"))
            print(f"File uploaded! File URI: {bullard_vol1.uri}")
            
            # 5. CACHE THE FILE! This is the secret sauce.
            print("Caching the book into the AI's permanent memory...")
            cached_context = client.caches.create(
                model='gemini-2.5-flash',
                config=types.CreateCachedContentConfig(
                    contents=[bullard_vol1],
                    system_instruction=system_instruction,
                    display_name="bullard_vol_1_cache",
                    ttl="3600s" # Keep it in memory for 60 minutes
                )
            )
            print("Successfully cached!\n")
            
        except Exception as e:
            print(f"File upload to Gemini failed: {e}")
            print("Please check your API key quotas or file path.")
            exit(1)

    print("Sending raw text to Gemini using the Cached Brain. Forcing it to fit our Pydantic Schema...\n")

    import sqlite3

    all_events = []
    final_profile = None

    # We process each chunk sequentially through the cached model
    for chunk_idx, chunk_text in enumerate(chunks):
        print(f"\n--- PROCESSING CHUNK {chunk_idx + 1} OF {len(chunks)} ---")
        
        # 6. We make the API call. 
        # Notice we pass the `chunk_text`, but we use the `cached_content` so it instantly references the 1,000-page book without reloading it!
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=chunk_text,
            config=types.GenerateContentConfig(
                cached_content=cached_context.name,
                response_mime_type="application/json",
                response_schema=EncounterProfile,
                temperature=0.1
            ),
        )

        # 7. The SDK automatically parses the JSON back into our Pydantic Object!
        profile: EncounterProfile = response.parsed
        
        # Capture the overall subject metadata from the first chunk only
        if chunk_idx == 0:
            final_profile = profile
            
        all_events.extend(profile.events)
        print(f"  -> Extracted {len(profile.events)} motif events from this chunk.")

    print("\nSUCCESS! Chunking complete. Committing to UFO Matrix Database...")
    print(f"Subject: {final_profile.pseudonym}")
    print(f"Date: {final_profile.date_of_encounter}")
    print(f"Summary: {final_profile.narrative_summary}\n")

    # Connect to database to permanently insert the data!
    with sqlite3.connect('ufo_matrix.db') as conn:
        cursor = conn.cursor()
        
        # 1. Insert Subject Profile
        cursor.execute("""
            INSERT INTO Subjects (Pseudonym, Age, Baseline_Psychology, Hypnosis_Utilized)
            VALUES (?, ?, ?, ?)
        """, (final_profile.pseudonym, final_profile.age, final_profile.narrative_summary, True))  # John Mack uses hypnosis frequently
        
        subject_id = cursor.lastrowid
        print(f"[*] Created Subject Record (ID: {subject_id})")
        
        # 2. Insert Encounter Metadata
        case_id = f"JOHN_MACK_{final_profile.pseudonym.upper() if final_profile.pseudonym else '001'}"
        cursor.execute("""
            INSERT INTO Encounters (Subject_ID, Case_Number, Date_of_Encounter, Location_Type, Conscious_Recall, Investigator_Credibility, Witness_Credibility, Source_Material)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (subject_id, case_id, final_profile.date_of_encounter, final_profile.location, False, final_profile.investigator_credibility, final_profile.witness_credibility, ACADEMIC_SOURCE_CITATION))
        
        encounter_id = cursor.lastrowid
        print(f"[*] Created Encounter Record (ID: {encounter_id})")

        print("\n--- PERMANENT SQL INGESTION ---")
        last_code_printed = None
        global_sequence = 1
        last_chunk_sequence = -1
        
        for event in all_events:
            # Stutter protection within the same apparent sequence block
            if event.motif_code == last_code_printed and event.sequence_order == last_chunk_sequence:
                continue
                
            last_code_printed = event.motif_code
            
            # If the AI advanced its chunk sequence order, we advance our global continuous sequence
            if event.sequence_order != last_chunk_sequence:
                if last_chunk_sequence != -1:
                    global_sequence += 1
                last_chunk_sequence = event.sequence_order

            # Look up description for console print
            if event.motif_code == "ANOMALY":
                description = "[[NOVEL CONCEPT - NOT IN BULLARD]]"
            else:
                cursor.execute("SELECT motif_description FROM Motif_Dictionary WHERE motif_number = ?", (event.motif_code,))
                result = cursor.fetchone()
                description = result[0] if result else "[[WARNING: AI HALLUCINATED FAKE CODE]]"
            
            # 3. Permanently insert the isolated Event into the SQL Junction Table!
            try:
                cursor.execute("""
                    INSERT INTO Encounter_Events (Encounter_ID, Sequence_Order, Motif_Code, Emotional_Marker, Source_Citation)
                    VALUES (?, ?, ?, ?, ?)
                """, (encounter_id, global_sequence, event.motif_code, event.emotional_marker, event.source_citation))
                
                emotion_str = f"Emotion: {event.emotional_marker}" if event.emotional_marker else "No explicit emotion"
                print(f"[{global_sequence}] DATABASE INSERT -> {event.motif_code}: {description}")
                print(f"    {emotion_str}")
                print(f"    Quote: '{event.source_citation}'\n")
                
            except sqlite3.IntegrityError:
                # Our strict Database Foreign Keys automatically reject hallucinations!
                print(f"    [X] DB REJECTED HALLUCINATED CODE: {event.motif_code}")

        conn.commit()
        print(f"\n[!!!] Phase 5 Complete: Successfully wrote all validated events directly into ufo_matrix.db!")
