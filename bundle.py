import sqlite3
import json
import urllib.request
import re

# Fetch from our running Flask API to get the exact data payload
stats_raw = json.loads(urllib.request.urlopen('http://127.0.0.1:5000/api/stats').read())
arch_raw = json.loads(urllib.request.urlopen('http://127.0.0.1:5000/api/architecture').read())
cases_raw = json.loads(urllib.request.urlopen('http://127.0.0.1:5000/api/cases').read())
heat_raw = json.loads(urllib.request.urlopen('http://127.0.0.1:5000/api/heatmap').read())
motifs_raw = json.loads(urllib.request.urlopen('http://127.0.0.1:5000/api/motifs').read())

# Fetch all sequences
sequences = {}
for c in cases_raw:
    eid = c['Encounter_ID']
    seq_raw = json.loads(urllib.request.urlopen(f'http://127.0.0.1:5000/api/sequence/{eid}').read())
    sequences[eid] = seq_raw

# Output as a JS module so we bypass all CORS and backend requirements
js_content = "const UAP_DATA = {\n"
js_content += f"  stats: {json.dumps(stats_raw)},\n"
js_content += f"  architecture: {json.dumps(arch_raw)},\n"
js_content += f"  cases: {json.dumps(cases_raw)},\n"
js_content += f"  heatmap: {json.dumps(heat_raw)},\n"
js_content += f"  motifs: {json.dumps(motifs_raw)},\n"
js_content += f"  sequences: {json.dumps(sequences)}\n"
js_content += "};\n"

with open("data.js", "w", encoding='utf-8') as f:
    f.write(js_content)

print("Data successfully bundled into data.js!")
