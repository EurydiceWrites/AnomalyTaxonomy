import sqlite3

try:
    with sqlite3.connect("ufo_matrix.db") as conn:
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE Encounters ADD COLUMN Source_Material VARCHAR;")
        print("Successfully added 'Source_Material' column to the Encounters table.")
except sqlite3.OperationalError as e:
    print(f"OperationalError (might already exist): {e}")

