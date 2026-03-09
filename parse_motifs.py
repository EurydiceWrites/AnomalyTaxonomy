import pdfplumber
import sqlite3
import re

# Connect to the database
conn = sqlite3.connect('ufo_matrix.db')
cursor = conn.cursor()

pdf_path = "Sources/Bullard, Thomas - UFO Abductions, The Measure of a Mystery - Volume 2.pdf"

print("Starting Pass 2: Parsing Bullard Vol 2 for Motif Sequences...")

# We will read from page 20 to the end of the document
raw_text = ""
print("Extracting text from PDF (this might take a minute)...")
with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages[20:]:
        text = page.extract_text()
        if text:
            # We add a newline to preserve the visual structure
            raw_text += text + "\n"

print("Text extracted. Linking Motif Codes to Encounters...")

# Variables to keep track of our state as we read line-by-line
current_encounter_id = None
sequence_counter = 1

# Regex patterns
# To know which case we are currently inside.
case_start_pattern = re.compile(r'^(\d{3}[a-z]?)\.\s+(.*)')

lines = raw_text.split('\n')
motifs_added = 0

for line in lines:
    line = line.strip()
    if not line:
        continue

    # Check if this line is the start of a new case
    case_num_str = None
    
    # Handle the two specific OCR catastrophic failures first: Case 51 and Case 62
    if line.startswith('O.Sl. '):
        case_num_str = '051'
    elif line.startswith('OG2. '):
        case_num_str = '062'
    else:
        case_match = case_start_pattern.match(line)
        if case_match:
            case_num_str = case_match.group(1)
            
    if case_num_str:
        # We found a case boundary! We need to look up its Encounter_ID
        # In our database, Encounter_ID is 1 to 270 matching the parsed order.
        # But to be safe, let's just query it based on the order it was inserted.
        pass

for line in lines:
    line = line.strip()
    if not line:
        continue

    # Check if this line is the start of a new case
    is_new_case = False
    parsed_case_num = None
    
    if line.startswith('O.Sl. '):
        is_new_case = True
        parsed_case_num = '051'
    elif line.startswith('OG2. '):
        is_new_case = True
        parsed_case_num = '062'
    elif line.startswith('62. JiM'):
        is_new_case = True
        parsed_case_num = '062'
    elif line.startswith('061. Carlos'):
        is_new_case = True
        parsed_case_num = '051'
    else:
        case_match = case_start_pattern.match(line)
        if case_match:
            is_new_case = True
            parsed_case_num = case_match.group(1)
            
    if is_new_case and parsed_case_num:
        # Instead of risking an offset with a simple index counter, we query the exact Case_Number from the database!
        cursor.execute("SELECT Encounter_ID FROM Encounters WHERE Case_Number = ?", (parsed_case_num,))
        result = cursor.fetchone()
        
        if result:
            current_encounter_id = result[0]
        else:
            print(f"WARNING: Found case '{parsed_case_num}' in PDF but not in Database!")
            current_encounter_id = None
            
        sequence_counter = 1
        continue

    # If we are currently inside a case, we scan for Motif Codes on the left margin
    if current_encounter_id:
        
        # Check for OCR spaces inside motifs like "Al 10" -> "A110"
        space_motif_match = re.match(r'^([A-Z][lIOSZB])\s+(\d{1,3})(.*)', line)
        if space_motif_match:
            line = space_motif_match.group(1) + space_motif_match.group(2) + " " + space_motif_match.group(3).strip()
            
        # Does the line start with something that looks like a motif code (Any capital letter, 8, or 5)?
        if len(line) > 4 and line[0] in "ABCDEFGHIJKLMNOPQRSTUVWXYZ85" and (" " in line or "-" in line):
            first_word = line.split(" ")[0].split("-")[0]
            # Clean up OCR: 8 -> B, 5 -> S
            clean_word = first_word.replace('8', 'B').replace('5', 'S')
            
            # Sometime multiple codes are listed together separated by commas: "B300,B340."
            individual_codes = clean_word.split(',')
            
            cleaned_codes = []
            for code in individual_codes:
                # Fix the OCR within the code like B36S -> B365 and E20S -> E205 and S0 -> 50
                m = re.match(r'^([A-Z])(.*)', code)
                if m:
                    first_letter = m.group(1)
                    rest = m.group(2)
                    rest = rest.split('.')[0] # Strip trailing words
                    rest = rest.translate(str.maketrans('lIOSZB', '110528'))
                    clean_code = first_letter + rest
                    
                    if re.match(r'^[A-Z]\d{1,3}', clean_code):
                        cleaned_codes.append(clean_code)
            
            if cleaned_codes:
                quote = line.split(" ", 1)
                quote = quote[1] if len(quote) > 1 else ""
                
                for code in cleaned_codes:
                        cursor.execute('''
                            INSERT INTO Encounter_Events (Encounter_ID, Motif_Code, Sequence_Order, Source_Citation)
                            VALUES (?, ?, ?, ?)
                        ''', (current_encounter_id, code, sequence_counter, quote))
                        sequence_counter += 1
                        motifs_added += 1

# Commit the database changes
conn.commit()

# --- DEMONSTRATION OF DATABASE RESULTS ---
print("\n========================================")
print(f"PASS 2 COMPLETE. LOGGED {motifs_added} MOTIF SEQUENCES ACROSS 270 ENCOUNTERS.")
print("========================================")

cursor.execute('''
    SELECT s.Pseudonym, ev.Sequence_Order, ev.Motif_Code
    FROM Subjects s
    JOIN Encounters e ON s.Subject_ID = e.Subject_ID
    JOIN Encounter_Events ev ON e.Encounter_ID = ev.Encounter_ID
    ORDER BY e.Encounter_ID, ev.Sequence_Order
    LIMIT 20
''')

rows = cursor.fetchall()
for r in rows:
    print(f"[{r[0]}] Sequence {r[1]}: {r[2]}")
print(f"... and {motifs_added - 20} more sequences.")

conn.close()
