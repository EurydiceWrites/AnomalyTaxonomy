import sqlite3

print("Injecting the 'ANOMALY' safety valve into the database taxonomy...")

with sqlite3.connect('ufo_matrix.db') as conn:
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO Motif_Dictionary (motif_number, current_family_header, current_family, current_subfamily, motif_description)
            VALUES (?, ?, ?, ?, ?)
        """, ('ANOMALY', 'ANOMALY', 'ANOMALY', 'ANOMALY', 'Novel psychological concept not covered by Bullard'))
        print("Successfully injected 'ANOMALY' into the Motif Dictionary.")
    except sqlite3.IntegrityError:
        print("'ANOMALY' already exists in the dictionary.")

    conn.commit()
