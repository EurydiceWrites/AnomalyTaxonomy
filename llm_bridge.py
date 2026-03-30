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
    memory_state: Literal["conscious", "hypnosis", "altered", "unconscious", "not_applicable"] = Field(description="The memory state of the subject during this event. 'conscious' = natural waking recall. 'hypnosis' = recovered via hypnotic regression. 'altered' = non-ordinary state like dream or trance. 'unconscious' = no memory of this period. 'not_applicable' = source is authored literature, mythology, or historical narrative, not a recalled personal experience.")
    source_page: str = Field(description="The physical page number(s) where this event is described, derived from the [--- START PAGE X ---] markers in the text (e.g., '42' or '42-43').")
    ai_justification: str = Field(description="When writing the ai_justification field, if the dictionary definition does not obviously match the text Bullard assigned the code to, do not assert that it fits. Instead, state what the dictionary defines the code as, state what the text actually describes, and acknowledge the gap. It is acceptable for Bullard's usage to stretch beyond the dictionary definition — your job is to be transparent about it, not to force a match.")

class EncounterProfile(BaseModel):
    """
    This schema defines the overall output for a complete UFO abduction case.
    It contains the core metadata and the list of chronological events.
    """
    pseudonym: str = Field(description="The name or pseudonym of the subject(s)")
    age: Optional[str] = Field(description="The age of the subject at the time of the encounter, if known")
    gender: Optional[Literal["male", "female", "nonbinary", "unknown"]] = Field(description="The gender of the primary subject, if known. Always lowercase.")
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
    memory_retrieval_method: Literal["conscious", "hypnosis", "altered", "mixed", "unknown", "not_applicable"]

import os
import sqlite3
import json
from datetime import datetime
from google import genai
from google.genai import types
from dotenv import load_dotenv


# --- Retrieval method context strings ---
# These tell the LLM how to assign memory_state based on how the case was investigated.
RETRIEVAL_CONTEXT_MAP = {
    'hypnosis':  'RETRIEVAL METHOD CONTEXT: This entire account was recovered under hypnotic regression with a clinical investigator. Every event in this text must be assigned memory_state="hypnosis" unless the text explicitly states otherwise for a specific event.',
    'conscious': 'RETRIEVAL METHOD CONTEXT: This account was recalled consciously by the witness without hypnotic regression. Every event must be assigned memory_state="conscious" unless the text explicitly states otherwise.',
    'altered':   'RETRIEVAL METHOD CONTEXT: This account was recalled in a non-ordinary state (dream, trance, or similar). Every event must be assigned memory_state="altered" unless the text explicitly states otherwise.',
    'mixed':     'RETRIEVAL METHOD CONTEXT: This account contains a mix of hypnotically and consciously recalled events. Assign memory_state on a per-event basis based on the text.',
    'unknown':        'RETRIEVAL METHOD CONTEXT: The retrieval method for this account is unknown. Assign memory_state based on any explicit cues in the text; default to "conscious" if no cue is present.',
    'not_applicable': 'RETRIEVAL METHOD CONTEXT: This source is authored literature, mythology, or historical narrative — not a recalled personal experience. Assign memory_state="not_applicable" for all events unless the text explicitly describes a character recalling an experience through a specific method.',
}


# --- Narrative structure context strings ---
# These tell the LLM how the text is structured so it can extract events correctly.
# Preambles will be written by Eurydice in a future session.
NARRATIVE_STRUCTURE_MAP = {
    'third_person_investigation': 'TODO: preamble pending Eurydice',
    'interview_dialogue':         'TODO: preamble pending Eurydice',
    'first_person_testimony':     'TODO: preamble pending Eurydice',
    'literary_narration':         'TODO: preamble pending Eurydice',
    'compiled_catalogue':         'TODO: preamble pending Eurydice',
    'not_applicable':             '',
}


def flatten_motif_key(nested_dict):
    """
    Walk the nested motif_key.json structure and return a flat {code: description} dict.

    motif_key.json is organized like:
        {"E--EFFECTS.": {"E100-199...": {"E100-109...": {"E100": "Vacuum effect..."}}}}

    This function recursively finds every leaf node (where the value is a plain string,
    meaning it's a code:description pair) and collects them all into one flat dictionary.
    """
    flat = {}
    for key, value in nested_dict.items():
        if isinstance(value, str):
            # This is a leaf node — an actual motif code and its description
            flat[key] = value
        elif isinstance(value, dict):
            # This is a category/subfamily — recurse deeper
            flat.update(flatten_motif_key(value))
    return flat


def extract_narrative(text=None, sticky_header="", retrieval_method="unknown",
                      profile_name="baseline", case_number=None,
                      pipeline_json_path=None, narrative_structure=None):
    """
    Sends narrative text to Gemini and returns structured extraction results.

    This function handles ONLY the AI extraction step — it does NOT touch any database.
    It loads the motif dictionary from motif_key.json (not the database), sends the text
    to Gemini in chunks, and returns the structured results.

    Can be called in two ways:
      1. Legacy mode (Phase 2b compatibility): pass text, sticky_header, etc. directly
      2. Pipeline mode: pass pipeline_json_path — reads text and settings from the JSON

    In pipeline mode, the extraction engine is temporally and culturally naive by design.
    Only the narrative text, motif dictionary, Vol 1 context, prompt library rules, and
    two preambles (retrieval method + narrative structure) enter the prompt. No dates,
    locations, investigator names, or other contextual metadata are passed.

    Parameters:
        text:                The raw narrative text to process (legacy mode)
        sticky_header:       Case metadata header passed to the LLM (legacy mode only)
        retrieval_method:    One of: conscious, hypnosis, altered, mixed, unknown
        profile_name:        Which prompt profile to use from prompt_library.json
        case_number:         Case identifier (e.g., "084"). Used for JSON output filename.
        pipeline_json_path:  Path to the pipeline JSON file (pipeline mode)
        narrative_structure: One of the NARRATIVE_STRUCTURE_MAP keys (optional)

    Returns:
        (final_profile, all_events, ai_events_json) where:
        - final_profile:   EncounterProfile object from the first chunk (has subject metadata)
        - all_events:      List of EncounterEvent objects (deduplicated, globally sequenced)
        - ai_events_json:  List of dicts in the format qa_triage.py expects
    """
    # --- PIPELINE MODE: read settings from JSON ---
    if pipeline_json_path:
        with open(pipeline_json_path, "r", encoding="utf-8") as f:
            pipeline_data = json.load(f)

        # Read narrative text from the path stored in the JSON
        text_path = pipeline_data["step_0"]["source_text_path"]
        with open(text_path, "r", encoding="utf-8") as f:
            text = f.read()

        # Get the two preamble fields from the JSON
        step1 = pipeline_data["step_1_scanned_metadata"]
        retrieval_method = step1.get("memory_retrieval_method", "unknown")
        narrative_structure = step1.get("narrative_structure", "not_applicable")

        # No sticky_header in pipeline mode — the engine is intentionally naive
        sticky_header = ""

        print(f"[*] Pipeline mode: reading from {pipeline_json_path}")
        print(f"    Text source: {text_path}")

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

    # Load the Motif Dictionary from the JSON file (no database needed)
    motif_key_path = os.path.join(os.path.dirname(__file__) or ".", "motif_key.json")
    with open(motif_key_path, "r", encoding="utf-8") as f:
        motif_key_nested = json.load(f)

    motif_dict = flatten_motif_key(motif_key_nested)
    print(f"[*] Loaded {len(motif_dict)} motif codes from motif_key.json")

    # Build the motif rules string for the system instruction
    motif_rules = ""
    for code, description in sorted(motif_dict.items()):
        motif_rules += f"- {code}: {description}\n"

    # Build the two preambles that enter the extraction prompt
    retrieval_context = RETRIEVAL_CONTEXT_MAP.get(retrieval_method, RETRIEVAL_CONTEXT_MAP['unknown'])
    print(f"[*] Retrieval method: {retrieval_method}")

    structure_context = ""
    if narrative_structure:
        structure_context = NARRATIVE_STRUCTURE_MAP.get(narrative_structure, "")
        if structure_context:
            print(f"[*] Narrative structure: {narrative_structure}")

    # Load the prompt library and select the requested profile
    with open("prompt_library.json", "r", encoding="utf-8") as f:
        prompt_lib = json.load(f)

    profile = prompt_lib.get("profiles", {}).get(profile_name, {})
    if not profile:
        print(f"WARNING: Profile '{profile_name}' not found in prompt_library.json. Using empty profile.")

    # Reassemble the string arrays from the profile into full instruction text
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

    # --- GEMINI CACHE MANAGEMENT ---
    # Volume 1 is cached on Google's servers so we don't re-upload it every time.
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
            return None, None, None

    # --- EXTRACTION: Send each chunk to Gemini ---
    print("Sending raw text to Gemini using the Cached Brain...\n")

    all_events = []       # List of (chunk_index, EncounterEvent) tuples
    final_profile = None

    for chunk_idx, chunk_text in enumerate(chunks):
        print(f"\n--- PROCESSING CHUNK {chunk_idx + 1} OF {len(chunks)} ---")

        # Build the payload: preambles + sticky header (if any) + narrative chunk.
        # In pipeline mode, sticky_header is empty and the two preambles guide extraction.
        preamble_parts = [retrieval_context]
        if structure_context:
            preamble_parts.append(structure_context)
        if sticky_header:
            preamble_parts.append(sticky_header)
        preamble = "\n\n".join(preamble_parts)
        payload = f"{preamble}\n\n[NARRATIVE CHUNK]\n{chunk_text}"

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

        chunk_profile: EncounterProfile = response.parsed

        # Keep the profile from the first chunk (it has the subject metadata)
        if chunk_idx == 0:
            final_profile = chunk_profile

        # Store each event with its chunk index so we can track provenance
        for event in chunk_profile.events:
            all_events.append((chunk_idx + 1, event))  # chunk is 1-indexed
        print(f"  -> Extracted {len(chunk_profile.events)} motif events from this chunk.")

    print(f"\nSUCCESS! Extraction complete.")
    print(f"Subject: {final_profile.pseudonym}")
    print(f"Date: {final_profile.date_of_encounter}")
    print(f"Summary: {final_profile.narrative_summary}\n")

    # --- DEDUPLICATION AND GLOBAL SEQUENCING ---
    # Events from different chunks may overlap. Deduplicate by skipping events
    # that have the same motif_code AND sequence_order as the previous event.
    deduped_events = []       # List of (chunk_index, EncounterEvent) — deduplicated
    ai_events_json = []       # List of dicts for JSON output (qa_triage format)

    global_sequence = 1
    last_code = None
    last_chunk_sequence = -1

    for chunk_idx, event in all_events:
        # Skip duplicates: same code and same sequence as last event
        if event.motif_code == last_code and event.sequence_order == last_chunk_sequence:
            continue

        last_code = event.motif_code

        # Increment global sequence when the chunk-local sequence changes
        if event.sequence_order != last_chunk_sequence:
            if last_chunk_sequence != -1:
                global_sequence += 1
            last_chunk_sequence = event.sequence_order

        deduped_events.append((chunk_idx, event))

        # Build the JSON dict in the format qa_triage.py expects
        ai_events_json.append({
            "sequence": global_sequence,
            "motif_code": event.motif_code,
            "citation": event.source_citation,
            "reasoning": event.ai_justification,
            "chunk": chunk_idx,
            "memory_state": event.memory_state,
            "emotional_marker": event.emotional_marker,
            "source_page": event.source_page,
        })

    print(f"[*] After deduplication: {len(deduped_events)} events (from {len(all_events)} raw)")

    # --- SAVE JSON OUTPUT ---
    # Save the results as JSON so qa_triage.py can consume them later
    if case_number:
        os.makedirs("test_results/raw", exist_ok=True)
        json_filename = f"extract_{case_number}_{profile_name}.json"
        json_path = os.path.join("test_results", "raw", json_filename)

        json_output = {
            "case_number": case_number,
            "profile": profile_name,
            "timestamp": datetime.now().isoformat(),
            "ai_count": len(ai_events_json),
            "ai_events": ai_events_json,
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_output, f, indent=2, ensure_ascii=False)
        print(f"[*] JSON results saved to: {json_path}")

    # --- MERGE BACK INTO PIPELINE JSON ---
    # If running in pipeline mode, write extraction results back into the JSON file
    if pipeline_json_path:
        pipeline_data["step_3_extraction"] = {
            "encounter_events": [
                {
                    "motif_code": ev["motif_code"],
                    "sequence_order": ev["sequence"],
                    "source_citation": ev["citation"],
                    "memory_state": ev["memory_state"],
                    "source_page": ev["source_page"],
                    "ai_justification": ev["reasoning"],
                    "emotional_marker": ev.get("emotional_marker"),
                    "chunk": ev["chunk"],
                }
                for ev in ai_events_json
            ],
            "model_name": "gemini-2.5-pro",
            "profile_used": profile_name,
            "run_timestamp": datetime.now().isoformat(),
        }

        with open(pipeline_json_path, "w", encoding="utf-8") as f:
            json.dump(pipeline_data, f, indent=2, ensure_ascii=False)
        print(f"[*] Extraction results merged back into: {pipeline_json_path}")

    # Return just the EncounterEvent objects (without chunk index) for load_to_database
    events_only = [event for (_chunk_idx, event) in deduped_events]

    return final_profile, events_only, ai_events_json


def load_to_database(final_profile, all_events, case_number, source_citation,
                     retrieval_method="unknown", db_path="ufo_matrix.db"):
    """
    Takes the extraction output and writes it to a SQLite database.

    This function handles ONLY the database insertion step. It can target either
    the production database (ufo_matrix.db) or the staging database (ufo_matrix_staging.db)
    depending on the db_path parameter.

    Parameters:
        final_profile:    EncounterProfile object (from extract_narrative)
        all_events:       List of EncounterEvent objects (deduplicated, globally sequenced)
        case_number:      Case identifier (e.g., "084")
        source_citation:  Academic citation for the source material
        retrieval_method: One of: conscious, hypnosis, altered, mixed, unknown
        db_path:          Path to the target database (default: "ufo_matrix.db")
    """
    print(f"\nCommitting to database: {db_path}...")
    print(f"Subject: {final_profile.pseudonym}")

    case_meta = CaseMetadata(
        memory_retrieval_method=retrieval_method
    )

    with sqlite3.connect(db_path, timeout=15) as conn:
        cursor = conn.cursor()

        # Check if this case already exists in the database
        cursor.execute("SELECT Encounter_ID, Subject_ID FROM Encounters WHERE Case_Number COLLATE NOCASE = ?", (case_number,))
        existing_encounter = cursor.fetchone()

        if existing_encounter:
            encounter_id = existing_encounter[0]
            subject_id = existing_encounter[1]
            print(f"[*] Found Existing Database Entry (Encounter ID: {encounter_id}) for Case '{case_number}'.")
            print(f"[*] AI Motifs will be appended to this existing historical index.")

            # Delete any previously extracted events for this specific Encounter
            # to allow clean overwrites during prompt-tuning
            cursor.execute("DELETE FROM Encounter_Events WHERE Encounter_ID = ?", (encounter_id,))
            print(f"[*] Cleared previous events for Encounter {encounter_id} to prepare for fresh LLM extraction.")

        else:
            # Insert new Subject record
            cursor.execute("""
                INSERT INTO Subjects (Pseudonym, Age, Baseline_Psychology, Gender)
                VALUES (?, ?, ?, ?)
            """, (final_profile.pseudonym, final_profile.age, final_profile.narrative_summary, final_profile.gender))

            subject_id = cursor.lastrowid
            print(f"[*] Created Subject Record (ID: {subject_id})")

            # Insert new Encounter record
            cursor.execute("""
                INSERT INTO Encounters (Subject_ID, Case_Number, Date_of_Encounter, Location_Type, Investigator_Credibility, Witness_Credibility, Source_Material, memory_retrieval_method, Entity_Type, Principal_Investigator)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (subject_id, case_number, final_profile.date_of_encounter, final_profile.location, final_profile.investigator_credibility, final_profile.witness_credibility, source_citation, retrieval_method, final_profile.entity_type, final_profile.principal_investigator))
            encounter_id = cursor.lastrowid
            print(f"[*] Created Encounter Record (ID: {encounter_id})")

        # --- Insert events with global sequencing ---
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

            # Look up motif description for display purposes
            if event.motif_code == "ANOMALY":
                description = "[[NOVEL CONCEPT - NOT IN BULLARD]]"
            else:
                cursor.execute("SELECT motif_description FROM Motif_Dictionary WHERE motif_number = ?", (event.motif_code,))
                result = cursor.fetchone()
                description = result[0] if result else "[[WARNING: AI HALLUCINATED FAKE CODE]]"

            try:
                cursor.execute("""
                    INSERT INTO Encounter_Events (Encounter_ID, Sequence_Order, Motif_Code, Source_Citation, memory_state, source_page, ai_justification)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (encounter_id, global_sequence, event.motif_code, event.source_citation, event.memory_state, event.source_page, event.ai_justification))

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
        print(f"\n[!!!] Database write complete: all validated events written to {db_path}")


def process_narrative(text: str, sticky_header: str, source_citation: str, case_number: str):
    """
    Backward-compatible wrapper that extracts motifs AND saves them to the production database.

    This is the original entry point used by ingest_case.py. It calls extract_narrative()
    and then load_to_database() in sequence, preserving the exact same behavior as before
    the refactor.

    For the new generalized pipeline, call extract_narrative() and load_to_database()
    separately instead.
    """
    # Look up the retrieval method from the production database
    # (In the new pipeline, this comes from the metadata scan instead)
    retrieval_method = "unknown"
    try:
        with sqlite3.connect('ufo_matrix.db') as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT memory_retrieval_method FROM Encounters WHERE Case_Number = ? COLLATE NOCASE",
                (case_number,)
            )
            retrieval_row = cursor.fetchone()
            if retrieval_row and retrieval_row[0]:
                retrieval_method = retrieval_row[0]
    except Exception:
        # If the column doesn't exist or query fails, fall back to unknown
        pass

    # Step 1: Extract (no database interaction)
    final_profile, all_events, _ai_events_json = extract_narrative(
        text=text,
        sticky_header=sticky_header,
        retrieval_method=retrieval_method,
        profile_name="baseline",
        case_number=case_number,
    )

    # If extraction failed (e.g., Gemini upload error), stop here
    if final_profile is None:
        return

    # Step 2: Load into production database
    load_to_database(
        final_profile=final_profile,
        all_events=all_events,
        case_number=case_number,
        source_citation=source_citation,
        retrieval_method=retrieval_method,
        db_path="ufo_matrix.db",
    )
