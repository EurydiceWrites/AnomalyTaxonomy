import sqlite3
import argparse
import sys

def get_db_connection():
    try:
        conn = sqlite3.connect('ufo_matrix.db')
        return conn
    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
        sys.exit(1)

def print_case_narrative(case_number):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Fetch the Encounter Metadata
    cursor.execute('''
        SELECT s.Pseudonym, s.Age, e.Date_of_Encounter, e.Location_Type
        FROM Encounters e
        JOIN Subjects s ON e.Subject_ID = s.Subject_ID
        WHERE e.Case_Number = ?
    ''', (case_number,))
    
    metadata = cursor.fetchone()
    if not metadata:
        print(f"Error: Could not find Case {case_number} in the database.")
        conn.close()
        return

    name, age, date, location = metadata
    
    print("=" * 60)
    print(f"CASE {case_number}: {name}")
    print(f"Age: {age} | Date: {date} | Location: {location}")
    print("-" * 60)
    
    # 2. Fetch the chronological Motif Sequence for this encounter
    cursor.execute('''
        SELECT ev.Sequence_Order, ev.Motif_Code, m.current_family, m.motif_description, ev.Source_Citation
        FROM Encounter_Events ev
        JOIN Motif_Dictionary m ON ev.Motif_Code = m.motif_number
        JOIN Encounters e ON ev.Encounter_ID = e.Encounter_ID
        WHERE e.Case_Number = ?
        ORDER BY ev.Sequence_Order ASC
    ''', (case_number,))
    
    events = cursor.fetchall()
    
    if not events:
        print("No motif sequences logged for this case.")
    else:
        print("CHRONOLOGICAL NARRATIVE SEQUENCE:")
        print("-" * 60)
        for seq, code, family, desc, quote in events:
            # We pad the strings so they align like a beautiful matrix / table
            print(f"{seq:2d}. [{code:4s}] {family:15s} | {desc}")
            if quote:
                print(f"          ...\"{quote}\"")

    print("=" * 60)
    conn.close()

if __name__ == "__main__":
    # Set up command line arguments
    parser = argparse.ArgumentParser(description="Query the UFO Matrix database for a specific case.")
    parser.add_argument("case", type=str, help="The Case Number string (e.g., '001', '180a') to query.")
    
    args = parser.parse_args()
    
    # Format the case num to be 3 digits if the user just typed '1' or '62'
    formatted_case = args.case
    if formatted_case.isdigit() and len(formatted_case) < 3:
        formatted_case = formatted_case.zfill(3)
        
    print_case_narrative(formatted_case)
