import pdfplumber
import sqlite3
import json
import time
from google import genai
from google.genai import types
from google.genai.errors import APIError
from dotenv import load_dotenv

load_dotenv()
client = genai.Client()
conn = sqlite3.connect('ufo_matrix.db')
cursor = conn.cursor()

# Clear existing regex motifs so we don't duplicate
cursor.execute("DELETE FROM Encounter_Events")
cursor.execute("UPDATE sqlite_sequence SET seq = 0 WHERE name = 'Encounter_Events'")
conn.commit()

pdf_path = "Sources/Bullard, Thomas - UFO Abductions, The Measure of a Mystery - Volume 2.pdf"

print("Loading PDF for LLM Motif extraction with Memory States...")
START_PAGE = 20
END_PAGE = 258

pages_text = []
with pdfplumber.open(pdf_path) as pdf:
    for i in range(START_PAGE, END_PAGE):
        ptxt = pdf.pages[i].extract_text()
        if ptxt:
            pages_text.append(f"[--- START PAGE {i} ---]\n" + ptxt)

all_events = []
CHUNK_SIZE = 2
CONTEXT_SIZE = 1

for i in range(0, len(pages_text), CHUNK_SIZE):
    start_context = max(0, i - CONTEXT_SIZE)
    context_text = "\n".join(pages_text[start_context:i])
    extraction_text = "\n".join(pages_text[i:i + CHUNK_SIZE])
    
    print(f"Processing pages {i+START_PAGE} to {i+START_PAGE+CHUNK_SIZE} ...")
    
    prompt = f"""You are a precise data extraction engine processing a horribly OCR-corrupted encyclopedia of UFO abduction cases.
    
The motifs appear on the left margin, e.g. 'E200', 'B350'. They are sometimes corrupted (e.g. '8200' -> 'B200', 'S00' -> '500'). Apply logical fixes.
Some lines have multiple motifs separated by commas like 'E315,U501'. Extract EACH as a separate JSON object.

CRITICAL INSTRUCTIONS:
1. Extract ALL motifs presented in the 'TEXT TO EXTRACT FROM' block in exact chronological order.
2. Link every motif to its correct 'case_number'.
3. DO NOT extract motifs that ONLY appear in the 'PREVIOUS CONTEXT' block.
4. If a quote is missing or unclear, provide the surrounding sentence text verbatim as the source_citation.
5. YOU MUST RETURN ONLY A VALID JSON ARRAY OF OBJECTS containing keys: "case_number", "motif_code", "source_citation", "source_page", "memory_state", "ai_justification".
6. For "memory_state", extensively analyze the context and classify the recall as "conscious", "hypnosis", "dream", or "unknown". Look for words like "Under hypnosis", "dreamt", or normal narrative.
7. For "ai_justification", provide a brief, logical explanation of why this specific Motif Code was chosen based on the text.

=== PREVIOUS CONTEXT (READ-ONLY FOR CASE HEADER MATCHING) ===
{context_text}

=== TEXT TO EXTRACT FROM ===
{extraction_text}
"""
    
    success = False
    retries = 3
    while not success and retries > 0:
        try:
            response = client.models.generate_content(
                model='gemini-2.5-pro',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0
                )
            )
            data = json.loads(response.text)
            motifs = data if isinstance(data, list) else data.get('motifs', [])
            all_events.extend(motifs)
            print(f"-> Extracted {len(motifs)} motifs. memory_state correctly analyzed.")
            success = True
            time.sleep(4) # 15 RPM = 1 request every 4 seconds standard
            
        except APIError as e:
            if hasattr(e, 'code') and e.code == 429:
                print(f"Rate capacity hit. Sleeping for 45s to clear standard quota... ({retries} retries left)")
                time.sleep(45)
                retries -= 1
            elif '429' in str(e):
                print(f"Rate limit hit. Sleeping for 45 seconds... ({retries} retries left)")
                time.sleep(45)
                retries -= 1
            else:
                print(f"API Error processing chunk: {e}")
                break
        except Exception as e:
            if '429' in str(e):
                print(f"Rate limit Exception hit. Sleeping for 45 seconds... ({retries} retries left)")
                time.sleep(45)
                retries -= 1
            else:
                print(f"Error processing chunk: {e}")
                break

print(f"Successfully extracted {len(all_events)} total motifs. Injecting into Database...")

sequence_dict = {}
cursor.execute("SELECT motif_number FROM Motif_Dictionary")
valid_motifs = {row[0] for row in cursor.fetchall()}

motifs_logged = 0
for m in all_events:
    c_num = m.get('case_number')
    m_code = m.get('motif_code')
    
    if not m_code or m_code not in valid_motifs: 
        continue

    cursor.execute("SELECT Encounter_ID FROM Encounters WHERE Case_Number COLLATE NOCASE = ?", (c_num,))
    result = cursor.fetchone()
    if not result:
        continue
    eid = result[0]
    
    if eid not in sequence_dict:
        sequence_dict[eid] = 1
    seq = sequence_dict[eid]
    sequence_dict[eid] += 1
    
    cursor.execute('''
        INSERT INTO Encounter_Events (Encounter_ID, Motif_Code, Sequence_Order, Source_Citation, source_page, memory_state, ai_justification)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (eid, m_code, seq, m.get('source_citation'), str(m.get('source_page')), m.get('memory_state'), m.get('ai_justification', 'LLM Structured Extraction')))
    motifs_logged += 1

conn.commit()
conn.close()
print(f"Phase 2 LLM Ingestion Complete. {motifs_logged} motifs logged with full memory_state context.")
