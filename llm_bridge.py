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
import re
import sqlite3
import json
from datetime import datetime
from google import genai
from google.genai import types
from dotenv import load_dotenv
import anthropic


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
# Preambles are loaded from prompt_library.json["narrative_structure_preambles"].
# Three preambles contain {experiencer_name} template variables for name substitution.
def _load_narrative_structure_map():
    """Load narrative structure preambles from prompt_library.json."""
    try:
        lib_path = os.path.join(os.path.dirname(__file__) or ".", "prompt_library.json")
        with open(lib_path, "r", encoding="utf-8") as f:
            lib = json.load(f)
        return lib.get("narrative_structure_preambles", {})
    except Exception:
        return {}

NARRATIVE_STRUCTURE_MAP = _load_narrative_structure_map()


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
                      profile_name="baseline_test", case_number=None,
                      pipeline_json_path=None, narrative_structure=None,
                      model="gemini-3.1-pro-preview", experiencer_name=None):
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

        # Get preamble fields from the JSON
        step1 = pipeline_data["step_1_scanned_metadata"]
        retrieval_method = step1.get("memory_retrieval_method", "unknown")
        narrative_structure = step1.get("narrative_structure", "not_applicable")
        experiencer_name = step1.get("experiencer_name", None)

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
        preamble_template = NARRATIVE_STRUCTURE_MAP.get(narrative_structure, "")
        if preamble_template:
            if experiencer_name:
                structure_context = preamble_template.format(experiencer_name=experiencer_name)
            else:
                print(f"  WARNING: No experiencer_name available for preamble substitution. Using 'the experiencer'.")
                structure_context = preamble_template.replace("{experiencer_name}", "the experiencer")
            print(f"[*] Narrative structure: {narrative_structure}")
            if experiencer_name:
                print(f"[*] Experiencer name: {experiencer_name}")

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

    all_events = []       # List of (chunk_index, EncounterEvent) tuples
    final_profile = None

    if model.startswith("claude"):
        # --- CLAUDE PATH ---
        # Read Vol1 and prepend to system instruction for prompt caching.
        vol1_path = os.path.join(os.path.dirname(__file__) or ".", "Sources", "bullard_vol1_raw.txt")
        with open(vol1_path, "r", encoding="utf-8") as f:
            vol1_text = f.read()

        claude_system_prompt = f"""*** REFERENCE: BULLARD'S COMPARATIVE STUDY (Volume 1) ***
The following is Thomas Bullard's complete comparative analysis of UFO abduction reports.
This provides the theoretical framework, motif definitions, and coding methodology you should follow.
Use this to understand the INTENT and CONTEXT behind each motif code when making your assignments.

{vol1_text}

{system_instruction}

You MUST return your results as a JSON object matching this schema:
- "pseudonym" (string), "age" (string or null), "gender" (string or null),
  "date_of_encounter" (string or null), "location" (string or null),
  "encounter_duration" (string or null), "principal_investigator" (string or null),
  "number_of_witnesses" (integer or null), "entity_type" (string or null),
  "investigator_credibility" (string "0"-"5"), "witness_credibility" (string "0"-"5"),
  "narrative_summary" (string),
  "events" (array of objects with: "sequence_order" (int), "motif_code" (string),
    "source_citation" (string), "emotional_marker" (string or null),
    "memory_state" (string), "source_page" (string), "ai_justification" (string))
Return ONLY the JSON object with no preamble, commentary, or markdown formatting."""

        print(f"[*] Claude system prompt: {len(claude_system_prompt)} chars (will be cached by Anthropic)")
        print(f"Sending raw text to Claude using prompt caching...\n")

        for chunk_idx, chunk_text in enumerate(chunks):
            print(f"\n--- PROCESSING CHUNK {chunk_idx + 1} OF {len(chunks)} ---")

            preamble_parts = [retrieval_context]
            if structure_context:
                preamble_parts.append(structure_context)
            if sticky_header:
                preamble_parts.append(sticky_header)
            preamble = "\n\n".join(preamble_parts)
            payload = f"{preamble}\n\n[NARRATIVE CHUNK]\n{chunk_text}"

            raw_events = _call_claude(payload, claude_system_prompt, model, temperature=0.1)

            # The response may be a full profile dict or just an events list.
            # Try to extract the profile structure if present.
            if isinstance(raw_events, list) and raw_events and isinstance(raw_events[0], dict):
                # Check if this is a list of events (has motif_code) or a single profile dict
                if 'motif_code' in raw_events[0]:
                    # It's a flat list of events — wrap into a profile-like structure
                    chunk_data = {"events": raw_events}
                else:
                    chunk_data = raw_events[0]
            elif isinstance(raw_events, dict):
                chunk_data = raw_events
            else:
                chunk_data = {"events": raw_events if isinstance(raw_events, list) else []}

            # Build EncounterEvent objects from the parsed data
            events_data = chunk_data.get("events", raw_events if isinstance(raw_events, list) else [])
            chunk_events = []
            for ev in events_data:
                if not isinstance(ev, dict) or 'motif_code' not in ev:
                    continue
                chunk_events.append(EncounterEvent(
                    sequence_order=ev.get("sequence_order", ev.get("sequence", 0)),
                    motif_code=ev.get("motif_code", ""),
                    source_citation=ev.get("source_citation", ev.get("citation", "")),
                    emotional_marker=ev.get("emotional_marker"),
                    memory_state=ev.get("memory_state", "unknown"),
                    source_page=ev.get("source_page", ""),
                    ai_justification=ev.get("ai_justification", ev.get("reasoning", "")),
                ))

            # Build EncounterProfile from first chunk
            if chunk_idx == 0:
                final_profile = EncounterProfile(
                    pseudonym=chunk_data.get("pseudonym", "Unknown"),
                    age=chunk_data.get("age"),
                    gender=chunk_data.get("gender"),
                    date_of_encounter=chunk_data.get("date_of_encounter"),
                    location=chunk_data.get("location"),
                    encounter_duration=chunk_data.get("encounter_duration"),
                    principal_investigator=chunk_data.get("principal_investigator"),
                    number_of_witnesses=chunk_data.get("number_of_witnesses"),
                    entity_type=chunk_data.get("entity_type"),
                    investigator_credibility=chunk_data.get("investigator_credibility", "3"),
                    witness_credibility=chunk_data.get("witness_credibility", "3"),
                    narrative_summary=chunk_data.get("narrative_summary", ""),
                    events=chunk_events,
                )

            for event in chunk_events:
                all_events.append((chunk_idx + 1, event))
            print(f"  -> Extracted {len(chunk_events)} motif events from this chunk.")

    else:
        # --- GEMINI PATH ---
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
                    model=model,
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

        for chunk_idx, chunk_text in enumerate(chunks):
            print(f"\n--- PROCESSING CHUNK {chunk_idx + 1} OF {len(chunks)} ---")

            preamble_parts = [retrieval_context]
            if structure_context:
                preamble_parts.append(structure_context)
            if sticky_header:
                preamble_parts.append(sticky_header)
            preamble = "\n\n".join(preamble_parts)
            payload = f"{preamble}\n\n[NARRATIVE CHUNK]\n{chunk_text}"

            response = client.models.generate_content(
                model=model,
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
            "model_name": model,
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
                    INSERT INTO Encounter_Events (Encounter_ID, Sequence_Order, Motif_Code, Source_Citation, memory_state, source_page, ai_justification, Emotional_Marker)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (encounter_id, global_sequence, event.motif_code, event.source_citation, event.memory_state, event.source_page, event.ai_justification, event.emotional_marker))

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


# =============================================================================
# MODEL-AGNOSTIC EXTRACTION BRIDGE
# =============================================================================
# These functions provide a single interface for calling any supported LLM.
# Calling scripts use run_extraction() or call_model() instead of importing
# google.genai or anthropic directly.
# =============================================================================


def get_or_create_gemini_cache(model: str, system_prompt: str,
                               cache_contents: str, display_name: str,
                               ttl: str = "1800s") -> str:
    """
    Look up an existing Gemini context cache by display_name, or create one.

    Returns the cache name string for use with _call_gemini(cached_content=...).
    This keeps all google.genai imports inside llm_bridge.py.

    Parameters:
        model:          Gemini model identifier (e.g., 'gemini-3.1-pro-preview')
        system_prompt:  System instruction to bake into the cache
        cache_contents: Static content to cache (e.g., Vol1 text)
        display_name:   Human-readable cache identifier for lookup
        ttl:            Cache time-to-live (default '1800s' = 30 minutes)

    Returns:
        The cache name string (e.g., 'cachedContents/abc123')
    """
    load_dotenv()
    client = genai.Client()

    # Check for existing cache first
    print(f"  Checking for existing context cache '{display_name}'...")
    try:
        for c_item in client.caches.list():
            if hasattr(c_item, 'display_name') and c_item.display_name == display_name:
                print(f"  Found existing cache: {c_item.name}")
                return c_item.name
    except Exception as e:
        print(f"  Cache list check failed: {e}")

    # Create new cache
    print(f"  Creating new context cache '{display_name}'...")
    cache = client.caches.create(
        model=model,
        config=types.CreateCachedContentConfig(
            display_name=display_name,
            system_instruction=system_prompt,
            contents=[cache_contents],
            ttl=ttl,
        )
    )
    print(f"  Cache created: {cache.name}")
    return cache.name


def assemble_prompt(profile: dict) -> str:
    """
    Single source of truth for prompt assembly from a prompt_library.json profile.

    Takes the profile dict (already loaded by the caller) and concatenates all
    prompt components in the correct order. Missing keys are skipped silently.

    Parameters:
        profile: A profile dict from prompt_library.json (e.g., profiles["baseline_test"])

    Returns:
        The fully assembled system prompt string.
    """
    parts = []

    # System instruction (core rules and taxonomy)
    sys_inst = profile.get("system_instruction", [])
    if sys_inst:
        parts.append("\n".join(sys_inst))
        print(f"  System instruction: {len(sys_inst)} items")

    # Narrative context rules
    narr_ctx = profile.get("narrative_context_rules", [])
    if narr_ctx:
        parts.append("*** NARRATIVE CONTEXT RULES ***")
        parts.append("\n".join(narr_ctx))
    print(f"  Narrative context rules: {len(narr_ctx)} items")

    # Anti-hallucination rules (semantic boundaries)
    anti_hall = profile.get("anti_hallucination_rules", [])
    if anti_hall:
        parts.append("*** SEMANTIC BOUNDARIES & NEGATIVE PROMPTING ***")
        parts.append("\n".join(anti_hall))
    print(f"  Anti-hallucination rules: {len(anti_hall)} items")

    # Few-shot examples
    few_shot = profile.get("few_shot_examples", [])
    if few_shot:
        parts.append("*** FEW-SHOT EXAMPLES ***")
        parts.append("\n\n".join(few_shot))
    print(f"  Few-shot examples: {len(few_shot)} items")

    # Load and append the motif dictionary
    motif_key_path = os.path.join(os.path.dirname(__file__) or ".", "motif_key.json")
    with open(motif_key_path, "r", encoding="utf-8") as f:
        motif_key_nested = json.load(f)

    motif_dict = flatten_motif_key(motif_key_nested)
    motif_rules = "\n".join(f"- {code}: {desc}" for code, desc in sorted(motif_dict.items()))
    parts.append("*** MOTIF DICTIONARY ***")
    parts.append(f"You must ONLY use codes from this dictionary. If a concept is entirely novel, assign 'ANOMALY'.\n\n{motif_rules}")
    print(f"  Motif dictionary: {len(motif_dict)} codes loaded")

    # JSON output instruction — works for all models
    parts.append(
        'You MUST return your results as a JSON array. Each element must be an object '
        'with these exact keys: "sequence" (integer), "motif_code" (string), '
        '"citation" (string), "reasoning" (string), "memory_state" (string), '
        '"chunk" (integer). Return ONLY the JSON array with no preamble, commentary, '
        'or markdown formatting.'
    )

    return "\n\n".join(parts)


def _find_motif_list(obj):
    """
    Recursively search a parsed JSON structure for the list of motif event dicts.

    Gemini sometimes wraps the event list inside a dict (e.g., {"events": [...]}).
    This function walks nested dicts and lists looking for a list whose first
    element is a dict containing a 'motif_code' key.
    """
    if isinstance(obj, list) and obj and isinstance(obj[0], dict) and 'motif_code' in obj[0]:
        return obj
    if isinstance(obj, dict):
        for v in obj.values():
            result = _find_motif_list(v)
            if result is not None:
                return result
    if isinstance(obj, list):
        for item in obj:
            result = _find_motif_list(item)
            if result is not None:
                return result
    return None


def parse_extraction_response(raw_text: str) -> list[dict]:
    """
    Parse raw LLM response text into a normalized list of event dicts.

    Handles:
    - Markdown code fences (```json ... ``` or ``` ... ```)
    - Nested wrappers (e.g., {"events": [...]})
    - Direct JSON arrays

    Returns:
        List of dicts, each with motif extraction data.
    """
    text = raw_text.strip()

    # Strip markdown code fences if present
    text = re.sub(r'^```(?:json)?\s*\n?', '', text)
    text = re.sub(r'\n?```\s*$', '', text)
    text = text.strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Failed to parse LLM response as JSON: {e}\n"
            f"First 200 chars: {text[:200]}"
        )

    # If it's already a list of event dicts, return directly
    if isinstance(parsed, list):
        unwrapped = _find_motif_list(parsed)
        return unwrapped if unwrapped is not None else parsed

    # If it's a dict, try to find the event list inside
    if isinstance(parsed, dict):
        unwrapped = _find_motif_list(parsed)
        if unwrapped is not None:
            return unwrapped
        # Last resort: look for any list value
        for v in parsed.values():
            if isinstance(v, list):
                return v

    return parsed if isinstance(parsed, list) else [parsed]


def _call_gemini(text: str, system_prompt: str, model: str = "gemini-2.5-pro",
                 cached_content: str = None, temperature: float = 0.0) -> list[dict]:
    """
    Send text to a Gemini model and return parsed extraction events.

    Parameters:
        text:            The user-facing content (narrative chunk + instructions)
        system_prompt:   The system instruction. Ignored if cached_content is set
                         (system prompt was baked into the cache at creation time).
        model:           Gemini model identifier
        cached_content:  Name of an existing Gemini context cache (optional)
        temperature:     Generation temperature (default 0.0 for deterministic output)
    """
    load_dotenv()
    client = genai.Client()

    config_kwargs = {
        "response_mime_type": "application/json",
        "temperature": temperature,
    }

    if cached_content:
        # System prompt is already inside the cache — just send the text
        config_kwargs["cached_content"] = cached_content
    elif system_prompt:
        # No cache — pass system prompt as system_instruction
        config_kwargs["system_instruction"] = system_prompt

    response = client.models.generate_content(
        model=model,
        contents=text,
        config=types.GenerateContentConfig(**config_kwargs),
    )

    return parse_extraction_response(response.text)


def _call_claude(text: str, system_prompt: str, model: str = "claude-opus-4-6",
                 temperature: float = 0.0) -> list[dict]:
    """
    Send text to a Claude model and return parsed extraction events.

    Uses Anthropic's prompt caching to cache the system prompt (which contains
    the motif dictionary, Vol 1 context, and prompt library rules). The 1-hour
    TTL ensures cache hits across batch runs with pauses between cases.

    Parameters:
        text:           The user-facing content (narrative chunk + instructions)
        system_prompt:  The full system instruction (will be cached)
        model:          Claude model identifier
        temperature:    Generation temperature (default 0.0)
    """
    load_dotenv(override=True)
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    response = client.messages.create(
        model=model,
        max_tokens=16000,
        temperature=temperature,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral", "ttl": "1h"}
            }
        ],
        messages=[
            {"role": "user", "content": text}
        ],
    )

    # Log cache performance
    usage = response.usage
    print(f"  Cache write: {getattr(usage, 'cache_creation_input_tokens', 0)} tokens")
    print(f"  Cache read:  {getattr(usage, 'cache_read_input_tokens', 0)} tokens")
    print(f"  Uncached:    {usage.input_tokens} tokens")

    raw_text = response.content[0].text
    return parse_extraction_response(raw_text)


def call_model(text: str, system_prompt: str, model: str = "gemini-2.5-pro",
               cached_content: str = None, temperature: float = 0.0) -> list[dict]:
    """
    Low-level model dispatcher. Routes to Gemini or Claude based on model name.

    Use this when you build your own prompt and just need the API routing.
    For scripts that use prompt_library.json profiles, use run_extraction() instead.

    Parameters:
        text:           The user-facing content to send to the model
        system_prompt:  The system instruction (empty string if baked into cache)
        model:          Model identifier (must start with 'gemini' or 'claude')
        cached_content: Gemini cache name (optional, Gemini-only)
        temperature:    Generation temperature
    """
    if model.startswith("gemini"):
        return _call_gemini(text, system_prompt, model,
                            cached_content=cached_content, temperature=temperature)
    elif model.startswith("claude"):
        return _call_claude(text, system_prompt, model, temperature=temperature)
    else:
        raise ValueError(f"Unsupported model: {model}")


def run_extraction(text: str, profile: dict, model: str = "gemini-2.5-pro",
                   cached_content: str = None, temperature: float = 0.0) -> list[dict]:
    """
    High-level extraction interface. Assembles the prompt from a profile dict
    and sends text to the specified model.

    This is the primary public API for model-agnostic extraction. Changing the
    extraction model requires changing only the model argument.

    Parameters:
        text:           The raw narrative text to extract from (one chunk)
        profile:        Profile dict from prompt_library.json
        model:          Which LLM to use ('gemini-2.5-pro', 'gemini-3.1-pro-preview',
                        'claude-opus-4-6')
        cached_content: Gemini cache name (optional, Gemini-only)
        temperature:    Generation temperature

    Returns:
        List of dicts, each representing one extracted event with keys:
        sequence, motif_code, citation, reasoning, memory_state, chunk
    """
    system_prompt = assemble_prompt(profile)
    return call_model(text, system_prompt, model,
                      cached_content=cached_content, temperature=temperature)
