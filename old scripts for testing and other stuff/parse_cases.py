import pdfplumber
import sqlite3
import json
import os
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class BullardCase(BaseModel):
    case_number: str = Field(description="The 3-digit Case Number (e.g. '001', '049'). Include letters if present (e.g. '004a'). Fix OCR typos like '061' to '051' based on contextual logical sequence. NEVER skip a case.")
    pseudonym: str = Field(description="The name or pseudonym of the subject(s). Clean OCR typos ('1' or 'l' instead of 'I'). Remove ages or numbers in parentheses/brackets (e.g. '<22>').")
    age: Optional[str] = Field(description="The age of the subject at the time of the encounter. Extract numbers inside brackets/parentheses like '<22>' -> '22'. If it says 'age cl7', output '17'. Fix OCR 'O' to '0'.")
    date_of_encounter: Optional[str] = Field(description="The date of the encounter, e.g. '1950', 'Spring 1973', 'October 9, 1967'. Fix OCR like 'ct959' -> '1959', 'OeceMber' -> 'December'. DO NOT include locations here.")
    location: Optional[str] = Field(description="The geographic location of the encounter. DO NOT include dates here.")
    investigator_credibility: Optional[str] = Field(description="The first number in 'Rating: X(Y)'. It must be 1-5. Append '/5'. e.g. '5/5'. If missing, output null.")
    witness_credibility: Optional[str] = Field(description="The number in parentheses in 'Rating: X(Y)'. It must be 1-5. Append '/5'. e.g. '4/5'. If missing, output null.")

class CaseList(BaseModel):
    cases: list[BullardCase] = Field(description="List of all chronological cases extracted from the current text chunk.")

client = genai.Client()
conn = sqlite3.connect('ufo_matrix.db')
cursor = conn.cursor()

pdf_path = "Sources/Bullard, Thomas - UFO Abductions, The Measure of a Mystery - Volume 2.pdf"

print("Extracting structured Case Metadata from PDF using Gemini 3.0 Pro...")

# We know cases 1 to 270 span from page 20 to 258
START_PAGE = 20
END_PAGE = 258
CHUNK_SIZE = 40

# Get all target pages text into memory first
pages_text = []
with pdfplumber.open(pdf_path) as pdf:
    for i in range(START_PAGE, END_PAGE):
        ptxt = pdf.pages[i].extract_text()
        if ptxt:
            pages_text.append(f"[--- START PAGE {i} ---]\n" + ptxt)

all_cases = []

# Process in chunks to prevent token overflow while giving max context
for i in range(0, len(pages_text), CHUNK_SIZE):
    chunk_text = "\n".join(pages_text[i:i+CHUNK_SIZE])
    print(f"Processing chunk {(i // CHUNK_SIZE) + 1} of {(len(pages_text) // CHUNK_SIZE) + 1}...")
    
    prompt = f"""You are a precise data extraction engine processing a horribly OCR-corrupted encyclopedia of UFO abduction cases.
    
Extract EVERY SINGLE case header in this text.
The cases are numbered progressively (001, 002... up to 270). Some have subcases (004a, 004b).
Each case starts with a header following this schema:
[Case Number]. [Pseudonym] / [Age if present] / [Date] / [Location]

Followed later by an Investigation 'Rating: X(Y)' where X is Investigator Credibility and Y is Witness Credibility.

CRITICAL INSTRUCTIONS:
1. Extract ALL sequentially numbered cases. Do not stop early. Do not summarize.
2. Fix sequence numbering OCR typos contextually. If the previous case was 050, and this one says '061', it is actually 051.
3. If a value does not exist for a case, return null. Do not hallucinate or guess.

RAW TEXT CHUNK:
{chunk_text}
"""
    try:
        response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=CaseList,
                temperature=0.0
            )
        )
        data = json.loads(response.text)
        chunk_cases = data.get('cases', [])
        all_cases.extend(chunk_cases)
        for c in chunk_cases:
            print(f"[{c.get('case_number')}] Extracted: {c.get('pseudonym')} | {c.get('location')} | Creds: {c.get('investigator_credibility')}, {c.get('witness_credibility')}")
            
    except Exception as e:
        print(f"Error processing chunk: {e}")

# Database logic to insert cases
print(f"Successfully extracted {len(all_cases)} total cases. Injecting into Database...")

for data in all_cases:
    case_num = data.get('case_number')
    pseudonym = data.get('pseudonym')
    
    # Generic pseudonym check
    is_generic = False
    if pseudonym and any(term in pseudonym.lower() for term in ['anonymous', 'unknown', '----']):
        is_generic = True
        
    row = None
    if not is_generic:
        cursor.execute("SELECT Subject_ID FROM Subjects WHERE Pseudonym = ?", (pseudonym,))
        row = cursor.fetchone()
    
    if row:
        subject_id = row[0]
    else:
        cursor.execute("INSERT INTO Subjects (Pseudonym, Age) VALUES (?, ?)", 
                      (pseudonym, data.get('age')))
        subject_id = cursor.lastrowid
        
    try:
         cursor.execute("ALTER TABLE Encounters ADD COLUMN Source_Material VARCHAR")
    except sqlite3.OperationalError:
         pass
         
    cursor.execute('''
        INSERT INTO Encounters 
        (Subject_ID, Case_Number, Date_of_Encounter, Location_Type, Investigator_Credibility, Witness_Credibility, Source_Material, is_hypnosis_used) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (subject_id, case_num, data.get('date_of_encounter'), data.get('location'), 
          data.get('investigator_credibility'), data.get('witness_credibility'),
          "Bullard, Thomas - UFO Abductions, The Measure of a Mystery - Volume 2.pdf", None))
    conn.commit()

conn.close()
print("Phase 1 Metadata Ingestion Complete!")
