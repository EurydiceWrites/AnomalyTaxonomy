from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3

app = Flask(__name__)
CORS(app)

def get_db():
    conn = sqlite3.connect('ufo_matrix.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/api/stats', methods=['GET'])
def get_stats():
    conn = get_db()
    total_encounters = conn.execute('SELECT COUNT(*) FROM Encounters').fetchone()[0]
    total_events = conn.execute('SELECT COUNT(*) FROM Encounter_Events').fetchone()[0]
    conn.close()
    return jsonify({
        "total_encounters": total_encounters,
        "total_events": total_events
    })

@app.route('/api/architecture', methods=['GET'])
def get_architecture():
    conn = get_db()
    query = """
        SELECT SUBSTR(m.current_family_header, 1, 1) as category, 
               m.current_family_header as full_category,
               COUNT(e.Motif_Code) as count
        FROM Encounter_Events e
        JOIN Motif_Dictionary m ON e.Motif_Code = m.motif_number
        GROUP BY category, full_category
        ORDER BY count DESC
    """
    results = [dict(row) for row in conn.execute(query).fetchall()]
    conn.close()
    return jsonify(results)

@app.route('/api/cases', methods=['GET'])
def get_cases():
    conn = get_db()
    query = """
        SELECT 
            e.Encounter_ID, 
            s.Pseudonym as subject, 
            e.Date_of_Encounter as date, 
            e.Location_Type as location, 
            e.Case_Number as case_num, 
            s.Hypnosis_Utilized as hypnosis,
            e.Source_Material as source
        FROM Encounters e
        JOIN Subjects s ON e.Subject_ID = s.Subject_ID
    """
    
    # We also want to know which motifs this case has, so we can filter by Motif in the UI
    motifs_query = """
        SELECT e.Encounter_ID, m.current_family_header, e.Motif_Code
        FROM Encounter_Events e
        JOIN Motif_Dictionary m ON e.Motif_Code = m.motif_number
    """
    
    cases_raw = [dict(row) for row in conn.execute(query).fetchall()]
    motifs_raw = conn.execute(motifs_query).fetchall()
    
    # Get all cases that have a 'hypnosis' memory state
    hyp_query = "SELECT DISTINCT Encounter_ID FROM Encounter_Events WHERE memory_state='hypnosis'"
    hypnosis_cases = {r['Encounter_ID'] for r in conn.execute(hyp_query).fetchall()}

    # Group motifs by encounter
    encounter_motifs = {}
    encounter_motif_codes = {}
    for r in motifs_raw:
        eid = r['Encounter_ID']
        cat = r['current_family_header']
        code = r['Motif_Code']
        
        if eid not in encounter_motifs:
            encounter_motifs[eid] = set()
            encounter_motif_codes[eid] = set()
            
        encounter_motifs[eid].add(cat)
        encounter_motif_codes[eid].add(code)
        
    for c in cases_raw:
        pseudo = str(c['subject']).lower()
        # Heuristic for multiple experiencers
        c['num_subjects'] = 1 + pseudo.count(' and ') + pseudo.count(',') + pseudo.count(' & ')
        
        eid = c['Encounter_ID']
        # Override empty Hypnosis_Utilized from phase 1 with our Phase 11 LLM context
        c['hypnosis'] = 1 if eid in hypnosis_cases else 0
        
        # Attach list of motif categories present in this case
        c['motifs_present'] = list(encounter_motifs.get(eid, []))
        c['motifs_present_codes'] = list(encounter_motif_codes.get(eid, []))
        
        # Ensure 'source' defaults to Unknown if missing
        if not c.get('source'):
            c['source'] = 'Unknown'

    conn.close()
    return jsonify(cases_raw)

@app.route('/api/motifs', methods=['GET'])
def get_motifs():
    conn = get_db()
    query = """
        SELECT motif_number, motif_description, current_family_header
        FROM Motif_Dictionary
    """
    motifs = [dict(row) for row in conn.execute(query).fetchall()]
    conn.close()
    return jsonify(motifs)

@app.route('/api/heatmap', methods=['GET'])
def get_heatmap():
    conn = get_db()
    query = """
        SELECT 
            e.Date_of_Encounter as full_date, 
            m.current_family_header as category
        FROM Encounter_Events ee
        JOIN Encounters e ON ee.Encounter_ID = e.Encounter_ID
        JOIN Motif_Dictionary m ON ee.Motif_Code = m.motif_number
        WHERE e.Date_of_Encounter IS NOT NULL AND e.Date_of_Encounter != 'nan'
    """
    raw_data = conn.execute(query).fetchall()
    conn.close()
    
    heatmap = {}
    for r in raw_data:
        date_str = str(r['full_date'])
        cat = str(r['category']).split('--')[-1].replace('.', '').strip()
        
        # Extract Decade
        import re
        years = re.findall(r'19\d{2}|20\d{2}', date_str)
        if years:
            year = int(years[0])
            decade = f"{(year // 10) * 10}s"
            
            if decade not in heatmap:
                heatmap[decade] = {}
            if cat not in heatmap[decade]:
                heatmap[decade][cat] = 0
            heatmap[decade][cat] += 1
            
    # Format for charting
    formatted = []
    for dec, cats in heatmap.items():
        for c, count in cats.items():
            formatted.append({"decade": dec, "category": c, "count": count})
            
    return jsonify(formatted)

@app.route('/api/sequence/<int:encounter_id>', methods=['GET'])
def get_sequence(encounter_id):
    conn = get_db()
    query = """
        SELECT 
            ee.Sequence_Order as seq, 
            ee.Motif_Code as code, 
            ee.Source_Citation as citation, 
            ee.memory_state as memory,
            m.current_family_header as category,
            m.motif_description as description
        FROM Encounter_Events ee
        JOIN Motif_Dictionary m ON ee.Motif_Code = m.motif_number
        WHERE ee.Encounter_ID = ?
        ORDER BY ee.Sequence_Order
    """
    events = [dict(row) for row in conn.execute(query, (encounter_id,)).fetchall()]
    conn.close()
    return jsonify(events)

@app.route('/api/network', methods=['GET'])
def get_network():
    conn = get_db()
    query = """
        SELECT ee.Encounter_ID, ee.Motif_Code, m.current_family_header, m.motif_description
        FROM Encounter_Events ee
        JOIN Motif_Dictionary m ON ee.Motif_Code = m.motif_number
    """
    raw_data = [dict(row) for row in conn.execute(query).fetchall()]
    conn.close()
    
    import itertools
    from collections import Counter
    
    encounters = {}
    motif_meta = {}
    
    for r in raw_data:
        eid = r['Encounter_ID']
        mcode = r['Motif_Code']
        cat = str(r['current_family_header']).split('--')[-1].replace('.', '').strip()
        desc = r['motif_description']
        
        if eid not in encounters:
            encounters[eid] = set()
        encounters[eid].add(mcode)
            
        if mcode not in motif_meta:
            motif_meta[mcode] = {'category': cat, 'description': desc}
            
    pair_counter = Counter()
    for eid, motifs in encounters.items():
        sorted_motifs = sorted(list(motifs))
        for pair in itertools.combinations(sorted_motifs, 2):
            pair_counter[pair] += 1
            
    nodes = []
    for mcode, meta in motif_meta.items():
        nodes.append({
            "id": mcode,
            "group": meta['category'],
            "name": f"{mcode}: {meta['description']}"
        })
        
    links = []
    for (m1, m2), count in pair_counter.items():
        links.append({
            "source": m1,
            "target": m2,
            "value": count
        })
        
    return jsonify({"nodes": nodes, "links": links})

if __name__ == '__main__':
    print("UFO Matrix API Server running on port 5000")
    app.run(port=5000, debug=False)
