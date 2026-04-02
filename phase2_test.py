"""
Phase 2: Blind Calibration Test
Strips Bullard's margin codes from raw encounter text, sends the prose
to Gemini using the baseline profile, and compares against ground truth.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import os
import json
import sqlite3
import re
import time
import argparse
from datetime import datetime, timezone
from dotenv import load_dotenv

from llm_bridge import assemble_prompt, call_model

load_dotenv()

# ── Args ──
parser = argparse.ArgumentParser(description="Phase 2 Blind Calibration Test")
parser.add_argument("case_number", help="Case number (e.g., 093)")
parser.add_argument("encounter_id", type=int, help="Encounter_ID for ground truth")
parser.add_argument("line_start", type=int, help="Start line in bullard_vol2_raw.txt")
parser.add_argument("line_end", type=int, help="End line in bullard_vol2_raw.txt")
parser.add_argument("--profile", default="baseline_test", help="Profile name from prompt_library.json")
parser.add_argument("--model", default="gemini-2.5-pro",
                    choices=["gemini-2.5-pro", "gemini-3.1-pro-preview", "claude-opus-4-6"],
                    help="Which LLM to use for extraction")
args = parser.parse_args()

print(f"{'=' * 70}")
print(f"PHASE 2 BLIND CALIBRATION — Case {args.case_number} (profile: {args.profile}, model: {args.model})")
print(f"{'=' * 70}")

# ── Step 1: Strip margin codes from raw text ──
print("\n[Step 1] Stripping margin codes from raw text...")

with open('Sources/bullard_vol2_raw.txt', encoding='utf-8') as f:
    all_lines = f.readlines()

raw_text = ''.join(all_lines[args.line_start - 1 : args.line_end])

# Patterns to remove:
# 1. Margin codes at start of lines: E411, B625, U101, 8295, etc.
#    These appear as codes like E411, B291, U133,W400. at line starts
MARGIN_CODE_PAT = re.compile(
    r'^\s*'                    # leading whitespace
    r'(?:[A-Z0-9][A-Za-z0-9\.\-]{2,8}'  # a code
    r'(?:\s*,\s*[A-Z0-9][A-Za-z0-9\.\-]{2,8})*'  # more comma-separated codes
    r'[\.\s]*)'                # trailing dot/space
)

# 2. Page markers: [--- START PAGE 67 ---]
PAGE_MARKER_PAT = re.compile(r'\[--- START PAGE \d+ ---\]')

# 3. Bullard page labels: C-47
BULLARD_PAGE_PAT = re.compile(r'^C-\d+\s*$')

# 4. Section numbers at line start: IA., II., VII., VIII.
# Keep the text after the section label
SECTION_PAT = re.compile(r'^(I{1,3}[A-Z]?\.|VII?\.|VIII?\.) ')

# 5. Bibliography refs: lines starting with 1), 2), etc.
BIBLIO_PAT = re.compile(r'^\d\s*[\)\>]')

stripped_lines = []
for line in raw_text.split('\n'):
    # Skip page markers
    if PAGE_MARKER_PAT.search(line):
        continue
    # Skip Bullard page labels
    if BULLARD_PAGE_PAT.match(line.strip()):
        continue
    # Skip blank lines
    if not line.strip():
        continue
    # Skip bibliography
    if BIBLIO_PAT.match(line.strip()):
        continue
    
    # Remove margin codes from the beginning of lines
    cleaned = MARGIN_CODE_PAT.sub('', line)
    
    # Remove section labels but keep text after
    cleaned = SECTION_PAT.sub('', cleaned)
    
    # Only keep lines with actual text
    if cleaned.strip():
        stripped_lines.append(cleaned.rstrip())

stripped_text = '\n'.join(stripped_lines)

print(f"  Original: {len(raw_text)} chars")
print(f"  Stripped: {len(stripped_text)} chars")
print(f"\n  --- STRIPPED TEXT ---")
for line in stripped_lines:
    print(f"  {line}")
print(f"  --- END ---\n")

# ── Step 2: Build prompt and set up model context ──
print(f"[Step 2] Building prompt for model: {args.model}...")

with open('prompt_library.json', 'r', encoding='utf-8') as f:
    prompt_lib = json.load(f)

profile = prompt_lib['profiles'][args.profile]
print(f"  Profile: {args.profile}")

# assemble_prompt() is the single source of truth — prints key counts automatically
system_prompt = assemble_prompt(profile)

# Volume 1 removed from pipeline — dictionary-only mode performs equivalently
# at 40x lower token cost. See TEST-007 vs no-vol1 comparison (88.2% match both).
cached_content_name = None

# ── Split text into chunks of ≤3000 chars at paragraph boundaries ──
CHUNK_SIZE = 3000
chunks = []
current_chunk = ""
for line in stripped_text.split('\n'):
    if len(current_chunk) + len(line) + 1 > CHUNK_SIZE and current_chunk:
        chunks.append(current_chunk.strip())
        current_chunk = line
    else:
        current_chunk += '\n' + line if current_chunk else line
if current_chunk.strip():
    chunks.append(current_chunk.strip())

print(f"  Split into {len(chunks)} chunks:")
for i, ch in enumerate(chunks):
    print(f"    Chunk {i+1}: {len(ch)} chars")

# ── Step 3: Send each chunk to the model via llm_bridge ──
print(f"\n[Step 3] Sending {len(chunks)} chunks to {args.model} (temperature=0.0)...")

ai_events = []
global_seq = 1

for i, chunk in enumerate(chunks):
    print(f"\n  Chunk {i+1}/{len(chunks)} ({len(chunk)} chars)...")

    user_prompt = f"""Analyze the following UFO encounter narrative CHUNK and extract all Motif Codes in chronological order.
This is chunk {i+1} of {len(chunks)} from the full narrative. Start sequence numbering at {global_seq}.

Return a JSON array where each element has:
- "sequence" (integer, chronological order starting at {global_seq})
- "motif_code" (string, from the dictionary)
- "citation" (string, the text passage justifying the code)
- "reasoning" (string, brief explanation of why this code fits)
- "memory_state" (string, the memory state during this event)

*** ENCOUNTER NARRATIVE (CHUNK {i+1} of {len(chunks)}) ***
{chunk}
"""

    chunk_events = call_model(
        text=user_prompt,
        system_prompt="" if cached_content_name else system_prompt,
        model=args.model,
        cached_content=cached_content_name,
        temperature=0.0,
    )

    print(f"    -> {len(chunk_events)} motifs extracted")

    # Re-number sequences globally
    for ev in chunk_events:
        ev['sequence'] = global_seq
        ev['chunk'] = i + 1
        global_seq += 1

    ai_events.extend(chunk_events)

print(f"  AI returned {len(ai_events)} motifs")

# ── Step 4: Get ground truth ──
print("\n[Step 4] Loading ground truth from database...")

conn = sqlite3.connect('ufo_matrix.db')
c = conn.cursor()
c.execute("SELECT Encounter_ID FROM Encounters WHERE Case_Number = ?", (args.case_number,))
enc_row = c.fetchone()
if enc_row:
    gt_encounter_id = enc_row[0]
else:
    gt_encounter_id = args.encounter_id
    print(f"  WARNING: Case '{args.case_number}' not found by Case_Number, falling back to encounter_id={args.encounter_id}")
c.execute("""
    SELECT Sequence_Order, Motif_Code, source_citation
    FROM Encounter_Events
    WHERE Encounter_ID = ?
    ORDER BY Sequence_Order
""", (gt_encounter_id,))
gt_events = [(seq, code, cite) for seq, code, cite in c.fetchall()]
conn.close()

print(f"  Ground truth: {len(gt_events)} motifs")

# ── Step 5: Compare ──
print(f"\n{'=' * 70}")
print("COMPARISON RESULTS")
print(f"{'=' * 70}")

gt_codes = [code for _, code, _ in gt_events]
ai_codes = [ev.get('motif_code', ev.get('code', '')) for ev in ai_events]

gt_set = set(gt_codes)
ai_set = set(ai_codes)

# Frequency-based matching (handles duplicates)
from collections import Counter
gt_freq = Counter(gt_codes)
ai_freq = Counter(ai_codes)

exact_matches = []
near_misses = []
ai_extras = []
ai_misses = []

# Check each ground truth code
gt_remaining = Counter(gt_codes)
ai_remaining = Counter(ai_codes)

for code in sorted(gt_freq.keys()):
    gt_count = gt_freq[code]
    ai_count = ai_freq.get(code, 0)
    matched = min(gt_count, ai_count)
    
    for _ in range(matched):
        exact_matches.append(code)
        gt_remaining[code] -= 1
        ai_remaining[code] -= 1

# Check remaining GT codes for near misses
for code, count in list(gt_remaining.items()):
    if count <= 0:
        continue
    for _ in range(count):
        # Check if AI has a sibling code (same prefix, within 10)
        prefix = code[0]
        try:
            num = int(re.sub(r'[^0-9]', '', code[1:]))
        except ValueError:
            ai_misses.append(code)
            continue
        
        found_near = False
        for ai_code, ai_count in list(ai_remaining.items()):
            if ai_count <= 0:
                continue
            ai_prefix = ai_code[0] if ai_code else ''
            try:
                ai_num = int(re.sub(r'[^0-9]', '', ai_code[1:]))
            except ValueError:
                continue
            
            if ai_prefix == prefix and abs(ai_num - num) <= 10 and abs(ai_num - num) > 0:
                near_misses.append((code, ai_code, abs(ai_num - num)))
                ai_remaining[ai_code] -= 1
                found_near = True
                break
        
        if not found_near:
            ai_misses.append(code)

# Remaining AI codes are extras
for code, count in ai_remaining.items():
    for _ in range(count):
        if count > 0:
            ai_extras.append(code)

# ── Summary ──
match_rate = len(exact_matches) / len(gt_codes) * 100 if gt_codes else 0
combined_rate = (len(exact_matches) + len(near_misses)) / len(gt_codes) * 100 if gt_codes else 0

print(f"\n  Ground Truth Count:  {len(gt_codes)}")
print(f"  AI Count:           {len(ai_codes)}")
print(f"  Exact Matches:      {len(exact_matches)} ({match_rate:.1f}%)")
print(f"  Near Misses:        {len(near_misses)} ({len(near_misses)/len(gt_codes)*100:.1f}%)")
print(f"  AI Extras:          {len(ai_extras)}")
print(f"  AI Misses:          {len(ai_misses)}")
print(f"  Combined Match Rate: {combined_rate:.1f}%")

# ── Detail sections ──
print(f"\n{'─' * 40}")
print("EXACT MATCHES:")
for code in exact_matches:
    print(f"  ✓ {code}")

if near_misses:
    print(f"\n{'─' * 40}")
    print("NEAR MISSES (sibling codes):")
    for gt_code, ai_code, dist in near_misses:
        print(f"  ~ Bullard: {gt_code} → AI: {ai_code} (distance: {dist})")

if ai_misses:
    print(f"\n{'─' * 40}")
    print("AI MISSES (Bullard had it, AI didn't):")
    gt_cite_map = {code: cite for _, code, cite in gt_events}
    for code in ai_misses:
        cite = gt_cite_map.get(code, '')
        print(f"  ✗ {code}: {(cite or '')[:60]}")

if ai_extras:
    print(f"\n{'─' * 40}")
    print("AI EXTRAS (AI had it, Bullard didn't):")
    for code in ai_extras:
        # Find the AI's reasoning
        for ev in ai_events:
            ec = ev.get('motif_code', ev.get('code', ''))
            if ec == code:
                reasoning = ev.get('reasoning', ev.get('ai_justification', ''))
                citation = ev.get('citation', ev.get('source_citation', ''))
                print(f"  + {code}: {citation[:50]}")
                print(f"    Reasoning: {reasoning[:60]}")
                break

# ── Full AI output ──
print(f"\n{'─' * 40}")
print("FULL AI EXTRACTION:")
for ev in ai_events:
    seq = ev.get('sequence', '?')
    code = ev.get('motif_code', ev.get('code', ''))
    cite = ev.get('citation', ev.get('source_citation', ''))
    marker = '✓' if code in gt_set else ('~' if any(nm[1] == code for nm in near_misses) else '+')
    print(f"  [{seq:>2}] {marker} {code}: {(cite or '')[:60]}")

# ── Save results ──
results = {
    'case_number': args.case_number,
    'model': args.model,
    'ground_truth_count': len(gt_codes),
    'ai_count': len(ai_codes),
    'exact_matches': len(exact_matches),
    'near_misses': len(near_misses),
    'ai_extras': len(ai_extras),
    'ai_misses': len(ai_misses),
    'match_rate': round(match_rate, 1),
    'combined_rate': round(combined_rate, 1),
    'exact_match_codes': exact_matches,
    'near_miss_details': [(gt, ai, d) for gt, ai, d in near_misses],
    'missed_codes': ai_misses,
    'extra_codes': ai_extras,
    'ai_events': ai_events,
    'stripped_text': stripped_text,
}

# Include model name in filename (strip slashes from model IDs like gemini-2.5-pro)
model_tag = args.model.replace("/", "_")
outfile = os.path.join('test_results', 'raw', f'phase2_results_{args.case_number}_{args.profile}_{model_tag}.json')
with open(outfile, 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"\nResults saved to {outfile}")
