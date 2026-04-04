-- schema.sql
-- This file defines the exact structure of the UFO Matrix database based on the automation blueprint.

-- 1. Subjects Table
CREATE TABLE IF NOT EXISTS Subjects (
    Subject_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Pseudonym VARCHAR NOT NULL,
    Age INTEGER,
    Gender VARCHAR,
    Baseline_Psychology TEXT,
    Hypnosis_Utilized BOOLEAN
);

-- 2. Encounters Table
CREATE TABLE IF NOT EXISTS Encounters (
    Encounter_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Subject_ID INTEGER NOT NULL,
    Case_Number VARCHAR,
    Date_of_Encounter VARCHAR,
    Location_Type VARCHAR,
    Conscious_Recall BOOLEAN,
    Investigator_Credibility VARCHAR,
    AI_Investigator_Credibility_Justification TEXT,
    Witness_Credibility VARCHAR,
    AI_Witness_Credibility_Justification TEXT,
    Source_Material VARCHAR,
    is_hypnosis_used BOOLEAN,
    Number_of_Witnesses INTEGER,
    Entity_Type VARCHAR,
    case_type TEXT,
    FOREIGN KEY (Subject_ID) REFERENCES Subjects(Subject_ID)
);

-- 3. Motif_Dictionary (The Taxonomy Table)
CREATE TABLE IF NOT EXISTS Motif_Dictionary (
    motif_number VARCHAR PRIMARY KEY,
    current_family_header VARCHAR,
    current_family VARCHAR,        
    current_subfamily VARCHAR,
    motif_description TEXT     
);

-- 4. Encounter_Events (The Junction Table)
CREATE TABLE IF NOT EXISTS Encounter_Events (
    Event_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Encounter_ID INTEGER NOT NULL,
    Sequence_Order INTEGER NOT NULL,
    Motif_Code VARCHAR NOT NULL,
    Emotional_Marker VARCHAR,
    Source_Citation TEXT, 
    memory_state VARCHAR,
    source_page VARCHAR,
    pdf_page VARCHAR,
    AI_Justification TEXT,
    voice_speaker TEXT,
    voice_content_type TEXT,
    run_timestamp TEXT,
    FOREIGN KEY (Encounter_ID) REFERENCES Encounters(Encounter_ID),
    FOREIGN KEY (Motif_Code) REFERENCES Motif_Dictionary(Motif_Code)
);
