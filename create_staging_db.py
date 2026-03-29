"""
create_staging_db.py — Creates an empty staging database for the generalized extraction pipeline.

Reads the schema from ufo_matrix.db (production) and creates ufo_matrix_staging.db with:
  - Identical table structure for Subjects, Encounters, Encounter_Events, Motif_Dictionary
  - Motif_Dictionary populated with all rows (the engine needs it for code validation)
  - All other tables empty (no Bullard data copied)

Usage:
    python create_staging_db.py
"""

import os
import sqlite3

# --- Configuration ---
PRODUCTION_DB = "ufo_matrix.db"
STAGING_DB = "ufo_matrix_staging.db"

# These are the four tables the pipeline uses
TABLES_TO_COPY = ["Subjects", "Encounters", "Encounter_Events", "Motif_Dictionary"]

# This table gets its data copied too (the engine needs motif codes for validation)
TABLES_WITH_DATA = ["Motif_Dictionary"]


def main():
    # Step 1: Check that production database exists
    if not os.path.exists(PRODUCTION_DB):
        print(f"ERROR: Production database '{PRODUCTION_DB}' not found.")
        print("Make sure you're running this script from the project root directory.")
        return

    # Step 2: If staging DB already exists, remove it so we get a fresh copy
    if os.path.exists(STAGING_DB):
        print(f"[*] Removing existing '{STAGING_DB}' to create a fresh copy...")
        os.remove(STAGING_DB)

    # Step 3: Read schemas and data from production database
    print(f"[*] Reading schema from '{PRODUCTION_DB}'...")

    prod_conn = sqlite3.connect(PRODUCTION_DB)
    prod_cursor = prod_conn.cursor()

    # Grab the CREATE TABLE SQL for each table
    table_schemas = {}
    for table_name in TABLES_TO_COPY:
        prod_cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        result = prod_cursor.fetchone()
        if result:
            table_schemas[table_name] = result[0]
            print(f"    Found schema for '{table_name}'")
        else:
            print(f"    WARNING: Table '{table_name}' not found in production database!")

    # Grab all rows from tables that need their data copied
    table_data = {}
    for table_name in TABLES_WITH_DATA:
        prod_cursor.execute(f"SELECT * FROM {table_name}")
        rows = prod_cursor.fetchall()
        table_data[table_name] = rows
        print(f"    Read {len(rows)} rows from '{table_name}'")

    prod_conn.close()

    # Step 4: Create the staging database
    print(f"\n[*] Creating '{STAGING_DB}'...")

    staging_conn = sqlite3.connect(STAGING_DB)
    staging_cursor = staging_conn.cursor()

    # Create each table using the exact SQL from production
    for table_name, create_sql in table_schemas.items():
        staging_cursor.execute(create_sql)
        print(f"    Created table '{table_name}'")

    # Copy data for tables that need it
    for table_name, rows in table_data.items():
        if not rows:
            continue

        # Build a parameterized INSERT with the right number of placeholders
        num_columns = len(rows[0])
        placeholders = ", ".join(["?"] * num_columns)
        insert_sql = f"INSERT INTO {table_name} VALUES ({placeholders})"

        staging_cursor.executemany(insert_sql, rows)
        print(f"    Inserted {len(rows)} rows into '{table_name}'")

    staging_conn.commit()

    # Step 5: Verify the result
    print(f"\n[*] Verifying '{STAGING_DB}'...")
    for table_name in TABLES_TO_COPY:
        staging_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = staging_cursor.fetchone()[0]
        print(f"    {table_name}: {count} rows")

    staging_conn.close()

    print(f"\nSUCCESS: Staging database '{STAGING_DB}' created.")
    print("  - Motif_Dictionary: populated (engine needs it for code validation)")
    print("  - All other tables: empty (ready for AI-extracted data)")


if __name__ == "__main__":
    main()
