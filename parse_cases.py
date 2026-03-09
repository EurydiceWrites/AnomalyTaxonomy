import pdfplumber
import sqlite3
import re
import os

# Connect to the database
conn = sqlite3.connect('ufo_matrix.db')
cursor = conn.cursor()

pdf_path = "Sources/Bullard, Thomas - UFO Abductions, The Measure of a Mystery - Volume 2.pdf"

print("Starting Pass 1: Parsing Bullard Vol 2 case metadata...")

# Clear out any old data from previous runs (but leave Motif_Dictionary alone)
cursor.execute("DELETE FROM Encounter_Events")
cursor.execute("DELETE FROM Encounters")
cursor.execute("DELETE FROM Subjects")
# Reset the AUTOINCREMENT counters back to 1
cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('Encounter_Events', 'Encounters', 'Subjects')")
conn.commit()

# We will read from page 20 to the end of the document
raw_text = ""
print("Extracting text from PDF (this might take a minute)...")
with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages[20:]: # Pages 21 onwards
        text = page.extract_text()
        if text:
            # We add a newline to preserve the visual structure
            raw_text += text + "\n"

print("Text extracted. Parsing cases...")

# Variables to keep track of our state as we read line-by-line
current_subject_id = None
current_encounter_id = None

# Regex patterns
# We keep this strict to avoid false positives (like body text that happens to start with 3 digits)
# We add an optional [a-z] to handle multi-part cases like 180a, 180b, etc.
case_start_pattern = re.compile(r'^(\d{3}[a-z]?)\.\s+(.*)')

lines = raw_text.split('\n')
parsed_count = 0

for line in lines:
    line = line.strip()
    if not line:
        continue

    # Initialize variables to see if we found a case header
    case_num = None
    raw_header = None

    # Handle the two specific OCR catastrophic failures first: Case 51 and Case 62
    if line.startswith('O.Sl. '):
        case_num = '051'
        raw_header = line[6:].strip()
    elif line.startswith('OG2. '):
        case_num = '062'
        raw_header = line[5:].strip()
    elif line.startswith('62. JiM'):
        case_num = '062'
        raw_header = line[4:].strip()
    elif line.startswith('061. Carlos'):
        case_num = '051'
        raw_header = line[4:].strip()
    else:
        # Standard regex check for everyone else
        case_match = case_start_pattern.match(line)
        if case_match:
            case_num = case_match.group(1)
            raw_header = case_match.group(2).strip()

    if case_num and raw_header:
        # The header is split by the 'I' or '|' or 'l' or '1' character surrounded by spaces
        # e.g., "001. Dr. Geis I age 7, 16 I 1950, ct959 I Brooklyn, Wurtsboro, N.Y."
        parts = re.split(r'\s+[I\|l1]\s+', raw_header)
        
        subject_name = parts[0].strip()
        
        # Apply specific OCR fixes to the subject name based on user feedback
        subject_name = subject_name.replace('or. 6eis', 'Dr. Geis')
        subject_name = subject_name.replace('6e', 'Ge')
        subject_name = subject_name.replace('6ermany', 'Germany')
        
        age = None
        date = None
        location = None
        
        # Basic heuristic to distribute Age, Date, Location based on the number of 'parts'
        if len(parts) >= 4:
            age = parts[1].strip()
            date = parts[2].strip()
            location = " ".join(parts[3:]).strip()
        elif len(parts) == 3:
            location = parts[2].strip()
            middle = parts[1].strip()
            # Try to guess if the middle part is an age or a date
            if 'age' in middle.lower() or '<' in middle or '(' in middle:
                age = middle
            else:
                date = middle
        elif len(parts) == 2:
            location = parts[1].strip()
        # 1. Insert into Subjects table
        cursor.execute("INSERT INTO Subjects (Pseudonym, Age) VALUES (?, ?)", (subject_name, age))
        current_subject_id = cursor.lastrowid
        
        # Add the expected Case_Number column if it doesn't already exist from the old schema
        try:
             cursor.execute("ALTER TABLE Encounters ADD COLUMN Case_Number VARCHAR")
        except sqlite3.OperationalError:
             pass # Column already exists
             
        # 2. Insert into Encounters table
        cursor.execute("INSERT INTO Encounters (Subject_ID, Case_Number, Date_of_Encounter, Location_Type) VALUES (?, ?, ?, ?)", (current_subject_id, case_num, date, location))
        current_encounter_id = cursor.lastrowid
        
        parsed_count += 1
        
        # Stop at exactly 270 cases as per the blueprint
        if parsed_count == 270:
            break

# Commit the database changes
conn.commit()

# --- DEMONSTRATION OF DATABASE RESULTS ---
print("\n========================================")
print(f"DATABASE PARSING RESULTS ({parsed_count} CASES)")
print("========================================")

cursor.execute('''
    SELECT e.Encounter_ID, s.Pseudonym, s.Age, e.Date_of_Encounter, e.Location_Type
    FROM Subjects s
    JOIN Encounters e ON s.Subject_ID = e.Subject_ID
    ORDER BY e.Encounter_ID
    LIMIT 20
''')

rows = cursor.fetchall()
for r in rows:
    print(f"[{r[0]}] Name: {r[1]} | Age: {r[2]} | Date: {r[3]} | Loc: {r[4]}")
print(f"... and {parsed_count - 20} more.")

conn.close()
