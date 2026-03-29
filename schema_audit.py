"""
schema_audit.py — Compares the database schema against the Pydantic models and
INSERT statements in llm_bridge.py to identify any mismatches.

Usage:
    python schema_audit.py

Checks performed:
  1. DB columns that nothing currently writes to
  2. Pydantic fields that have no matching DB column
  3. INSERT columns that don't exist in the DB (should be none after recent fixes)
"""

import sqlite3
import re

DB_PATH = "ufo_matrix.db"
BRIDGE_PATH = "llm_bridge.py"

# ---------------------------------------------------------------------------
# Step 1: Read actual column names from the database
# ---------------------------------------------------------------------------

def get_db_columns(db_path):
    """Returns {table_name: [column_name, ...]} for the three tables we care about."""
    tables = ["Subjects", "Encounters", "Encounter_Events"]
    result = {}
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        for table in tables:
            cursor.execute(f"PRAGMA table_info({table})")
            rows = cursor.fetchall()
            # PRAGMA table_info returns: (cid, name, type, notnull, dflt_value, pk)
            result[table] = [row[1] for row in rows]
    return result

# ---------------------------------------------------------------------------
# Step 2: Parse Pydantic field names from llm_bridge.py
# ---------------------------------------------------------------------------

def get_pydantic_fields(bridge_path):
    """
    Reads llm_bridge.py and extracts field names from EncounterProfile,
    EncounterEvent, and CaseMetadata by scanning for lines like:
        field_name: Type = Field(...)
    inside each class block.
    """
    with open(bridge_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    models = {}
    current_class = None

    for line in lines:
        # Detect class definition
        class_match = re.match(r'^class (\w+)\(BaseModel\):', line)
        if class_match:
            current_class = class_match.group(1)
            models[current_class] = []
            continue

        # Stop collecting when we exit the class body (hit a non-indented line
        # that isn't blank or a comment, after we've started a class)
        if current_class and line.strip() and not line.startswith(" ") and not line.startswith("\t"):
            current_class = None

        # Collect field definitions (indented lines with a type annotation)
        if current_class:
            field_match = re.match(r'\s{4}(\w+)\s*:', line)
            if field_match:
                field_name = field_match.group(1)
                # Skip dunder methods and 'pass'
                if field_name not in ("pass",) and not field_name.startswith("__"):
                    models[current_class].append(field_name)

    return models

# ---------------------------------------------------------------------------
# Step 3: Parse INSERT column names from load_to_database() in llm_bridge.py
# ---------------------------------------------------------------------------

def get_insert_columns(bridge_path):
    """
    Reads llm_bridge.py and extracts the column names used in each
    INSERT INTO <table> statement inside load_to_database().
    Returns {table_name: [column_name, ...]}
    """
    with open(bridge_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Find the load_to_database function body
    func_match = re.search(r'def load_to_database\(.*?(?=\ndef |\Z)', content, re.DOTALL)
    if not func_match:
        print("WARNING: Could not find load_to_database() in llm_bridge.py")
        return {}

    func_body = func_match.group(0)

    # Find all INSERT INTO statements: INSERT INTO TableName (col1, col2, ...)
    insert_pattern = re.compile(
        r'INSERT INTO (\w+)\s*\(([^)]+)\)',
        re.DOTALL
    )

    result = {}
    for match in insert_pattern.finditer(func_body):
        table_name = match.group(1)
        cols_raw = match.group(2)
        # Clean up: split on commas, strip whitespace and newlines
        cols = [c.strip() for c in cols_raw.split(",") if c.strip()]
        result[table_name] = cols

    return result

# ---------------------------------------------------------------------------
# Step 4: Compare and report
# ---------------------------------------------------------------------------

def run_audit():
    print("=" * 65)
    print("  UFO MATRIX SCHEMA AUDIT")
    print("  Comparing: ufo_matrix.db  vs  llm_bridge.py")
    print("=" * 65)

    db_cols = get_db_columns(DB_PATH)
    pydantic_models = get_pydantic_fields(BRIDGE_PATH)
    insert_cols = get_insert_columns(BRIDGE_PATH)

    # Map: which Pydantic model feeds which table
    # (based on what load_to_database() uses)
    model_to_table = {
        "EncounterProfile": "Encounters",   # profile fields → Encounters + Subjects
        "EncounterEvent":   "Encounter_Events",
        "CaseMetadata":     "Encounters",   # retrieval method → Encounters
    }

    # EncounterProfile also feeds Subjects (pseudonym, age, gender, narrative_summary)
    # We'll handle Subjects separately
    profile_to_subjects = ["pseudonym", "age", "narrative_summary"]   # fields written to Subjects

    print()

    # --- Table 1: Subjects ---
    print("-" * 65)
    print("TABLE: Subjects")
    print("-" * 65)
    subjects_db = set(db_cols.get("Subjects", []))
    subjects_insert = set(insert_cols.get("Subjects", []))
    subjects_from_profile = set(profile_to_subjects)
    # hypnosis_val is derived inline (not a Pydantic field), so add it manually
    subjects_written = subjects_insert  # what the INSERT actually writes

    unwritten = subjects_db - subjects_insert - {"Subject_ID"}  # PK is auto
    print(f"  DB columns:        {sorted(subjects_db)}")
    print(f"  INSERT writes:     {sorted(subjects_insert)}")
    print()
    if unwritten:
        print(f"  [!] DB columns nothing writes to: {sorted(unwritten)}")
    else:
        print("  [OK] All non-PK DB columns are written by the INSERT")

    # Subjects doesn't have its own Pydantic model — fields come from EncounterProfile
    profile_fields = set(pydantic_models.get("EncounterProfile", []))
    # Fields in EncounterProfile that map to Subjects columns
    profile_subjects_overlap = profile_fields & subjects_db
    print(f"  EncounterProfile fields that map to Subjects columns: {sorted(profile_subjects_overlap)}")

    print()

    # --- Table 2: Encounters ---
    print("-" * 65)
    print("TABLE: Encounters")
    print("-" * 65)
    enc_db = set(db_cols.get("Encounters", []))
    enc_insert = set(insert_cols.get("Encounters", []))
    profile_fields = set(pydantic_models.get("EncounterProfile", []))
    meta_fields = set(pydantic_models.get("CaseMetadata", []))
    all_pydantic_enc = profile_fields | meta_fields

    unwritten = enc_db - enc_insert - {"Encounter_ID"}   # PK is auto
    print(f"  DB columns:                {sorted(enc_db)}")
    print(f"  INSERT writes:             {sorted(enc_insert)}")
    print(f"  EncounterProfile fields:   {sorted(profile_fields)}")
    print(f"  CaseMetadata fields:       {sorted(meta_fields)}")
    print()

    if unwritten:
        print(f"  [!] DB columns nothing writes to: {sorted(unwritten)}")
    else:
        print("  [OK] All non-PK DB columns are written by the INSERT")

    # Pydantic fields that have no matching DB column.
    # Use case-insensitive comparison because Pydantic fields are lowercase
    # (e.g. 'date_of_encounter') while DB columns are mixed case ('Date_of_Encounter').
    # Also note: the Pydantic field 'location' maps to the DB column 'Location_Type' —
    # a deliberate name difference that the INSERT handles explicitly.
    enc_db_lower = {c.lower() for c in enc_db}
    skip = {"events", "narrative_summary", "pseudonym", "age", "gender",
            "location"}   # 'location' maps intentionally to 'Location_Type'
    no_db_col = {f for f in all_pydantic_enc if f.lower() not in enc_db_lower and f not in skip}
    if no_db_col:
        print(f"  [!] Pydantic fields with no matching Encounters column: {sorted(no_db_col)}")
    else:
        print("  [OK] No Pydantic fields are orphaned (no DB column to receive them)")

    # INSERT columns that don't exist in DB
    bad_insert = enc_insert - enc_db
    if bad_insert:
        print(f"  [!!] INSERT references columns NOT in DB: {sorted(bad_insert)}")
    else:
        print("  [OK] All INSERT columns exist in the DB")

    print()

    # --- Table 3: Encounter_Events ---
    print("-" * 65)
    print("TABLE: Encounter_Events")
    print("-" * 65)
    ev_db = set(db_cols.get("Encounter_Events", []))
    ev_insert = set(insert_cols.get("Encounter_Events", []))
    event_fields = set(pydantic_models.get("EncounterEvent", []))

    unwritten = ev_db - ev_insert - {"Event_ID"}   # PK is auto
    print(f"  DB columns:            {sorted(ev_db)}")
    print(f"  INSERT writes:         {sorted(ev_insert)}")
    print(f"  EncounterEvent fields: {sorted(event_fields)}")
    print()

    if unwritten:
        print(f"  [!] DB columns nothing writes to: {sorted(unwritten)}")
    else:
        print("  [OK] All non-PK DB columns are written by the INSERT")

    # Pydantic fields with no matching DB column
    # (sequence_order is written as Sequence_Order — case difference — handle that)
    ev_db_lower = {c.lower() for c in ev_db}
    orphaned = set()
    for field in event_fields:
        if field.lower() not in ev_db_lower:
            orphaned.add(field)
    if orphaned:
        print(f"  [!] EncounterEvent fields with no matching DB column: {sorted(orphaned)}")
    else:
        print("  [OK] All EncounterEvent fields have a matching DB column")

    # INSERT columns not in DB
    bad_insert = ev_insert - ev_db
    if bad_insert:
        print(f"  [!!] INSERT references columns NOT in DB: {sorted(bad_insert)}")
    else:
        print("  [OK] All INSERT columns exist in the DB")

    print()
    print("-" * 65)
    print("AUDIT COMPLETE")
    print("-" * 65)


if __name__ == "__main__":
    run_audit()
