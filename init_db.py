import sqlite3
import json
import os

# 1. Connect to the Database
# This creates the file 'ufo_matrix.db' in the current folder if it doesn't exist,
# and connects to it so we can run SQL commands.
db_path = 'ufo_matrix.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print(f"Connected to database: {db_path}")

# 2. Build the Tables using our Schema
# We read the schema.sql file we just created and run it against the database.
# This creates the Subjects, Encounters, Motif_Dictionary, and Encounter_Events tables.
schema_path = 'schema.sql'
with open(schema_path, 'r', encoding='utf-8') as f:
    schema_sql = f.read()

cursor.executescript(schema_sql)
print("Database schema created successfully.")

# 3. Load the Motif Data from JSON
# We open the motif_key.json file that we generated in Phase 1 and load it into a Python dictionary.
json_path = 'motif_key.json'
with open(json_path, 'r', encoding='utf-8') as f:
    motif_data = json.load(f)

print("motif_key.json loaded successfully.")

# 4. Insert Data into the Motif_Dictionary Table
# We loop through the nested dictionary to extract each piece of data.
inserted_count = 0

# loop through the top level: Family Headers (e.g., "E--EFFECTS.")
for family_header, families in motif_data.items():
    
    # loop through the second level: Families (e.g., "E100-199")
    for family, subfamilies in families.items():
        
        # loop through the third level: Subfamilies (e.g., "E100-109")
        for subfamily, motifs in subfamilies.items():
            
            # loop through the fourth level: Individual Motifs (e.g., "E100") and their descriptions
            for motif_number, motif_description in motifs.items():
                
                # We use parameterized queries (?) to safely insert the data into the SQL table.
                # 'INSERT OR REPLACE' ensures that if we run the script twice, it just updates existing rows instead of crashing.
                cursor.execute('''
                    INSERT OR REPLACE INTO Motif_Dictionary (
                        motif_number, 
                        current_family_header, 
                        current_family, 
                        current_subfamily, 
                        motif_description
                    ) 
                    VALUES (?, ?, ?, ?, ?)
                ''', (motif_number, family_header, family, subfamily, motif_description))
                
                inserted_count += 1

# 5. Save the Changes and Close Connection
# After inserting all rows, we must 'commit' the changes to save them permanently to the file.
conn.commit()
conn.close()

print(f"Successfully inserted {inserted_count} motifs into the Motif_Dictionary table.")
print("Database initialization complete!")
