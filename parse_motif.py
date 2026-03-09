import pdfplumber
import json
import re

# Step 1: Extract raw text from motif key pages
raw_text = ""

with pdfplumber.open("Sources/Bullard, Thomas - UFO Abductions, The Measure of a Mystery - Volume 2.pdf") as pdf:
    for i in range(3, 20):
        page = pdf.pages[i]
        text = page.extract_text()
        if text:
            raw_text += text + "\n"

# Step 2: Split into lines and look at them
lines = raw_text.split("\n")
print(f"Total lines extracted: {len(lines)}")
print("First 10 lines:")
for line in lines[:10]:
    print(repr(line))

# Step 3: Build a Nested Dictionary
motif_structure = {}
current_family_header=None
current_family=None
current_subfamily=None

for line in lines: 
    line=line.strip()
    
    if not line:
        continue
        
    # Generic OCR fixes for motif codes at the start of the line
    # 1. Start with 8 -> B, and 5 -> S
    if re.match(r'^8(?=[0-9lIOSZB\-=\_])', line):
        line = 'B' + line[1:]
    elif re.match(r'^5(?=[0-9lIOSZB\-=\_])', line):
        line = 'S' + line[1:]
        
    # 2. Spaces around 'l' or missing spaces for 1s
    line = re.sub(r'^([A-Z])\s*l\s*(\d)', r'\g<1>1\2', line)
    line = re.sub(r'^([A-Z])\s+(\d)', r'\1\2', line)
    
    # 3. Clean up the actual code token
    # Match the prefix block before the first space or dot
    m = re.match(r'^([A-Z])([0-9lIOSZBt\-\=\_\~]{1,10})(?=[.\s]|$)(.*)', line)
    if m:
        first = m.group(1)
        rest_code = m.group(2)
        rest_line = m.group(3)
        rest_code = rest_code.translate(str.maketrans('lIOSZBt', '1105281')).replace('=', '-').replace('_', '-').replace('~', '-')
        line = first + rest_code + rest_line

    # Determine hierarchy
    if re.match(r'^[A-Z]--', line):
        current_family_header = line
        current_family = None
        current_subfamily = None
        if current_family_header not in motif_structure:
            motif_structure[current_family_header] = {}

    elif re.match(r'^[A-Z]\d+00-\d+99', line):
        current_family = line
        current_subfamily = None
        if current_family not in motif_structure[current_family_header]:
            motif_structure[current_family_header][current_family] = {}

    elif re.match(r'^[A-Z]\d{3}-\d+', line):
        if line == current_family:
            continue
        current_subfamily = line
        if current_family_header and current_family:
            if current_subfamily not in motif_structure[current_family_header][current_family]:
                motif_structure[current_family_header][current_family][current_subfamily] = {}
        else:
            print(f"SKIPPED subfamily: {current_subfamily} - no family header")

    elif re.match(r'^[A-Z]\d{3}\.', line):
        parts = line.split('.', 1)
        if len(parts) == 2:
            motif_number = parts[0].strip()
            motif_description = parts[1].strip()
            if current_family_header and current_family and current_subfamily:
                motif_structure[current_family_header][current_family][current_subfamily][motif_number] = motif_description
            else:
                print(f"SKIPPED: {motif_number} - missing container")

# Step 4: Save to JSON
print(f"Saving motif hierarchy to motif_key.json...")
with open("motif_key.json", "w", encoding="utf-8") as f:
    json.dump(motif_structure, f, indent=4, ensure_ascii=False)
