-- schema.sql
-- This file defines the exact structure of the UFO Matrix database based on the automation blueprint.

-- 1. Subjects Table
CREATE TABLE IF NOT EXISTS Subjects (
    Subject_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Pseudonym VARCHAR,
    Age VARCHAR,
    Baseline_Psychology TEXT,
    Hypnosis_Utilized BOOLEAN
);

-- 2. Encounters Table
CREATE TABLE IF NOT EXISTS Encounters (
    Encounter_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Subject_ID INTEGER NOT NULL,
    Case_Number VARCHAR,
    Date_of_Encounter DATE,
    Location_Type VARCHAR,
    Conscious_Recall BOOLEAN,
    Investigator_Credibility VARCHAR,
    Witness_Credibility VARCHAR,
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
    FOREIGN KEY (Encounter_ID) REFERENCES Encounters(Encounter_ID),
    FOREIGN KEY (Motif_Code) REFERENCES Motif_Dictionary(Motif_Code)
);
