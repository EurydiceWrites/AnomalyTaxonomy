import sqlite3

conn = sqlite3.connect('ufo_matrix.db')
cur = conn.cursor()
cur.execute("""
    SELECT Event_ID, Sequence_Order, Motif_Code, source_citation, memory_state
    FROM Encounter_Events
    WHERE Encounter_ID = 94
    ORDER BY Sequence_Order
""")
rows = cur.fetchall()
print("Case 093 (enc 94): " + str(len(rows)) + " events")
print()
for r in rows:
    cite = (r[3] or "")[:60]
    print("  Seq " + str(r[1]).rjust(3) + ": " + str(r[2]).ljust(10) + " | " + cite + " | mem=" + str(r[4]))
conn.close()
