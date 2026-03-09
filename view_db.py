import sqlite3

print("--- UFO MATRIX DATABASE VIEWER ---\n")

with sqlite3.connect("ufo_matrix.db") as conn:
    cursor = conn.cursor()
    
    # 1. View Subjects
    print("SUBJECTS IN DATABASE:")
    cursor.execute("SELECT Subject_ID, Pseudonym, Age FROM Subjects")
    for row in cursor.fetchall():
        print(f"  [ID {row[0]}] {row[1]}, Age {row[2]}")
        
    print("\nENCOUNTERS IN DATABASE:")
    cursor.execute("""
        SELECT Encounter_ID, Case_Number, Date_of_Encounter, Source_Material 
        FROM Encounters
    """)
    for row in cursor.fetchall():
        enc_id, case_num, date, source = row
        print(f"  [Encounter {enc_id}] {case_num}")
        print(f"    Date: {date}")
        print(f"    Source: {source}")
        
        # Look up 3 of the events for this encounter just to prove it worked
        cursor.execute("""
            SELECT Sequence_Order, Motif_Code 
            FROM Encounter_Events 
            WHERE Encounter_ID = ?
            ORDER BY Sequence_Order
            LIMIT 3
        """, (enc_id,))
        
        events = cursor.fetchall()
        if events:
            print(f"    Includes Events: {', '.join([f'{e[0]}: {e[1]}' for e in events])}...")
    print("\n")
