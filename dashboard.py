import streamlit as st
import sqlite3
import pandas as pd
import altair as alt

st.set_page_config(page_title="UFO Matrix Explorer", page_icon="🛸", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap');
    
    html, body, [class*="css"]  {
        font-family: 'Inter', sans-serif !important;
    }

    /* Glowing Gradient Title */
    .title-glow {
        font-size: 3rem;
        font-weight: 800;
        background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: -15px;
        text-shadow: 0px 0px 20px rgba(79, 172, 254, 0.4);
    }
    
    .subtitle {
        color: #A0AEC0;
        font-weight: 300;
        letter-spacing: 1px;
    }

    /* Glassmorphism Metric Cards */
    div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 40px rgba(0, 242, 254, 0.15);
        border: 1px solid rgba(0, 242, 254, 0.2);
    }

    /* Customizing DataFrames */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid rgba(255, 255, 255, 0.08);
    }

    /* Top padding adjustment */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="title-glow">The Anomaly Taxonomy</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">DECODING ENCOUNTERS USING THE BULLARD MOTIF TAXONOMY</div><br>', unsafe_allow_html=True)

st.info("**Academic Framework & Methodology Disclaimer**  \n"
        "This relational database is actively powered by the foundational Motif Taxonomy developed by **Dr. Thomas E. Bullard**, "
        "and is heavily expanded through the psychiatric framework of **Dr. John E. Mack**.")

@st.cache_data
def load_data():
    conn = sqlite3.connect('ufo_matrix.db')
    
    # Load Encounters with Subject Data
    encounters_df = pd.read_sql_query("""
        SELECT 
            e.Encounter_ID, 
            s.Pseudonym, 
            e.Date_of_Encounter, 
            e.Location_Type, 
            e.Case_Number, 
            e.Source_Material,
            e.Investigator_Credibility,
            e.Witness_Credibility,
            s.Hypnosis_Utilized
        FROM Encounters e
        JOIN Subjects s ON e.Subject_ID = s.Subject_ID
    """, conn)
    
    # Load Events
    events_df = pd.read_sql_query("""
        SELECT 
            ee.Encounter_ID, 
            ee.Sequence_Order, 
            ee.Motif_Code, 
            ee.Source_Citation, 
            ee.Emotional_Marker,
            m.current_family_header AS General_Category
        FROM Encounter_Events ee
        LEFT JOIN Motif_Dictionary m ON ee.Motif_Code = m.motif_number
    """, conn)
    
    conn.close()
    return encounters_df, events_df

encounters_df, events_df = load_data()

st.sidebar.header("Data Purity Filters")
exclude_hypnosis = st.sidebar.checkbox("Exclude Hypnosis Cases", value=False)

inv_creds = [c for c in encounters_df['Investigator_Credibility'].dropna().unique()]
if inv_creds:
    selected_inv_cred = st.sidebar.multiselect("Investigator Credibility", inv_creds, default=inv_creds)

wit_creds = [c for c in encounters_df['Witness_Credibility'].dropna().unique()]
if wit_creds:
    selected_wit_cred = st.sidebar.multiselect("Witness Credibility", wit_creds, default=wit_creds)

st.sidebar.divider()
st.sidebar.header("Filter Database")
selected_source = st.sidebar.selectbox("Filter by Source Material", ["All"] + list(encounters_df['Source_Material'].dropna().unique()))

filtered_encounters = encounters_df.copy()

if selected_source != "All":
    filtered_encounters = filtered_encounters[filtered_encounters['Source_Material'] == selected_source]

if exclude_hypnosis:
    filtered_encounters = filtered_encounters[filtered_encounters['Hypnosis_Utilized'] != 1]

if inv_creds:
    filtered_encounters = filtered_encounters[filtered_encounters['Investigator_Credibility'].isin(selected_inv_cred) | filtered_encounters['Investigator_Credibility'].isna()]
    
if wit_creds:
    filtered_encounters = filtered_encounters[filtered_encounters['Witness_Credibility'].isin(selected_wit_cred) | filtered_encounters['Witness_Credibility'].isna()]

st.metric("Total Encounters in Matrix", len(filtered_encounters))

st.dataframe(filtered_encounters, use_container_width=True, hide_index=True)

st.divider()

st.header("Deep Dive: Case Files")

if not filtered_encounters.empty:
    selected_case = st.selectbox("Select an Encounter ID to view its full Motif Sequence:", filtered_encounters['Encounter_ID'].astype(str) + " - " + filtered_encounters['Case_Number'])
    
    case_id = int(selected_case.split(" - ")[0])
    
    case_events = events_df[events_df['Encounter_ID'] == case_id].sort_values('Sequence_Order')
    
    st.subheader(f"Motif Sequence for Encounter #{case_id}")
    st.dataframe(case_events[['Sequence_Order', 'General_Category', 'Motif_Code', 'Emotional_Marker', 'Source_Citation']], use_container_width=True, hide_index=True)
else:
    st.info("No cases match the current filters.")

st.divider()

# --- ANALYTICS SECTION ---
st.header("Relational Analytics")
st.markdown("Discover thematic and emotional patterns using SQL-driven cross-referencing.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Emotional Motif Correlation")
    available_emotions = events_df['Emotional_Marker'].dropna().unique()
    
    if len(available_emotions) > 0:
        target_emotion = st.selectbox("Select an Emotion:", available_emotions)
        
        # Filter events by this emotion and get the most common motifs
        emotion_events = events_df[events_df['Emotional_Marker'] == target_emotion]
        top_motifs = emotion_events['General_Category'].value_counts().reset_index()
        top_motifs.columns = ['Category', 'Count']
        
        st.write(f"When Abductees feel **{target_emotion}**, they are usually experiencing:")
        
        chart = alt.Chart(top_motifs.head(5)).mark_bar(color='#00f2fe').encode(
            x=alt.X('Count:Q', title='Number of Occurrences'),
            y=alt.Y('Category:N', sort='-x', title=''),
        ).properties(height=200)
        
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No emotional data has been ingested yet.")

with col2:
    st.subheader("2. What are the most common Motifs?")
    if not events_df.empty:
        top_codes = events_df['Motif_Code'].value_counts().reset_index()
        top_codes.columns = ['Motif_Code', 'Count']
        
        # Merge descriptions
        query = "SELECT motif_number AS Motif_Code, motif_description AS Motif_Description FROM Motif_Dictionary"
        conn = sqlite3.connect('ufo_matrix.db')
        dict_df = pd.read_sql_query(query, conn)
        conn.close()
        
        top_codes = top_codes.merge(dict_df, on='Motif_Code', how='left')
        
        chart2 = alt.Chart(top_codes.head(6)).mark_bar(color='#4facfe').encode(
            x=alt.X('Count:Q', title='Number of Occurrences'),
            y=alt.Y('Motif_Code:N', sort='-x', title='Code'),
            tooltip=['Motif_Description', 'Count']
        ).properties(height=200)
        
        st.altair_chart(chart2, use_container_width=True)
