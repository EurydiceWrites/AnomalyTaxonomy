import sqlite3
import json

conn = sqlite3.connect('ufo_matrix.db')
cursor = conn.cursor()
cursor.execute("""
    SELECT Motif_Code, motif_description 
    FROM Motif_Dictionary 
    WHERE Motif_Code IS NOT NULL 
    ORDER BY Motif_Code
""")

motif_key = {}
for code, desc in cursor.fetchall():
    motif_key[code] = desc

conn.close()

with open('motif_key.json', 'w', encoding='utf-8') as f:
    json.dump(motif_key, f, indent=2, ensure_ascii=False)

print(f"motif_key.json written with {len(motif_key)} entries.")
