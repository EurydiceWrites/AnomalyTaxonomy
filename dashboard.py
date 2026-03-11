import streamlit as st
import sqlite3
import pandas as pd
import altair as alt
import re

st.set_page_config(page_title="UAP Sequence Explorer", page_icon="🛸", layout="wide")

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
        background: linear-gradient(135deg, #00f2fe 0%, #8a2be2 50%, #4facfe 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: -15px;
        text-shadow: 0px 0px 25px rgba(138, 43, 226, 0.5);
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
        box-shadow: 0 8px 40px rgba(0, 242, 254, 0.25);
        border: 1px solid rgba(138, 43, 226, 0.5);
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

st.markdown('<div class="title-glow">UAP Sequence Explorer</div>', unsafe_allow_html=True)
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
            ee.memory_state,
            m.current_family_header AS General_Category,
            m.motif_description AS Motif_Description
        FROM Encounter_Events ee
        LEFT JOIN Motif_Dictionary m ON ee.Motif_Code = m.motif_number
    """, conn)
    
    encounters_df['Date_of_Encounter'] = encounters_df['Date_of_Encounter'].astype(str)
    
    # Format category names to avoid long strings
    events_df['General_Category'] = events_df['General_Category'].apply(lambda x: str(x).split('--')[-1].replace('.', '').strip() if pd.notnull(x) else 'Unknown')
    
    # Heuristics for advanced filtering
    encounters_df['Pseudonym_str'] = encounters_df['Pseudonym'].astype(str).str.lower()
    encounters_df['num_subjects'] = 1 + encounters_df['Pseudonym_str'].str.count(' and ') + encounters_df['Pseudonym_str'].str.count(',') + encounters_df['Pseudonym_str'].str.count(' & ')
    
    hypnosis_cases = events_df[events_df['memory_state'] == 'hypnosis']['Encounter_ID'].unique()
    encounters_df['has_hypnosis'] = encounters_df['Encounter_ID'].isin(hypnosis_cases)

    conn.close()
    return encounters_df, events_df

encounters_df, events_df = load_data()

st.sidebar.header("Global Matrix Filters")
multi_experiencer = st.sidebar.checkbox("👨‍👩‍👧‍👦 Multiple Experiencers Only", value=False)
require_hypnosis = st.sidebar.checkbox("🌀 Requires Hypnosis Recall", value=False)

all_categories = sorted(events_df['General_Category'].dropna().unique())
selected_motif_cat = st.sidebar.selectbox("Filter by Motif Category", ["All"] + list(all_categories))

st.sidebar.divider()
st.sidebar.header("Source & Credibility")
selected_source = st.sidebar.selectbox("Filter by Source Material", ["All"] + list(encounters_df['Source_Material'].dropna().unique()))

inv_creds = [c for c in encounters_df['Investigator_Credibility'].dropna().unique()]
selected_inv_cred = []
if inv_creds:
    selected_inv_cred = st.sidebar.multiselect("Investigator Credibility", inv_creds, default=inv_creds)

wit_creds = [c for c in encounters_df['Witness_Credibility'].dropna().unique()]
selected_wit_cred = []
if wit_creds:
    selected_wit_cred = st.sidebar.multiselect("Witness Credibility", wit_creds, default=wit_creds)

filtered_encounters = encounters_df.copy()

if selected_source != "All":
    filtered_encounters = filtered_encounters[filtered_encounters['Source_Material'] == selected_source]

if multi_experiencer:
    filtered_encounters = filtered_encounters[filtered_encounters['num_subjects'] > 1]

if require_hypnosis:
    filtered_encounters = filtered_encounters[filtered_encounters['has_hypnosis'] == True]

if selected_motif_cat != "All":
    cases_with_motif = events_df[events_df['General_Category'] == selected_motif_cat]['Encounter_ID'].unique()
    filtered_encounters = filtered_encounters[filtered_encounters['Encounter_ID'].isin(cases_with_motif)]

if selected_inv_cred:
    filtered_encounters = filtered_encounters[filtered_encounters['Investigator_Credibility'].isin(selected_inv_cred) | filtered_encounters['Investigator_Credibility'].isna()]
    
if selected_wit_cred:
    filtered_encounters = filtered_encounters[filtered_encounters['Witness_Credibility'].isin(selected_wit_cred) | filtered_encounters['Witness_Credibility'].isna()]

st.metric("Total Encounters Matching Criteria", len(filtered_encounters))

display_cols = ['Case_Number', 'Pseudonym', 'Date_of_Encounter', 'Location_Type', 'Source_Material']
st.dataframe(filtered_encounters[display_cols], use_container_width=True, hide_index=True)

st.divider()

st.header("Case File Explorer")

if not filtered_encounters.empty:
    selected_case = st.selectbox("Select an Encounter Case to render its full sequence telemetry:", filtered_encounters['Encounter_ID'].astype(str) + " - " + filtered_encounters['Case_Number'])
    
    case_id = int(selected_case.split(" - ")[0])
    
    case_events = events_df[events_df['Encounter_ID'] == case_id].sort_values('Sequence_Order')
    
    st.subheader(f"Motif Sequence Architecture for Case #{case_id}")
    
    case_info = filtered_encounters[filtered_encounters['Encounter_ID'] == case_id].iloc[0]
    
    if case_info.get('num_subjects', 1) > 1:
        st.warning(f"⚠️ Multi-Experiencer Entity Encounter ({int(case_info['num_subjects'])} Subjects)")
        
    if case_info.get('has_hypnosis'):
        st.info("🌀 This sequence contains memories retrieved via Hypnosis.", icon="🧠")
    
    colA, colB, colC = st.columns(3)
    colA.markdown(f"**Subject:** {case_info.get('Pseudonym', 'Unknown')}")
    colA.markdown(f"**Source:** {case_info.get('Source_Material', 'Unknown')}")
    colB.markdown(f"**Date:** {case_info.get('Date_of_Encounter', 'Unknown')}")
    colB.markdown(f"**Location:** {case_info.get('Location_Type', 'Unknown')}")
    creds = f"Inv: {case_info.get('Investigator_Credibility', 'N/A')} | Wit: {case_info.get('Witness_Credibility', 'N/A')}"
    colC.markdown(f"**Ratings:** {creds}")
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.dataframe(case_events[['Sequence_Order', 'General_Category', 'Motif_Code', 'Motif_Description', 'Emotional_Marker', 'memory_state', 'Source_Citation']], use_container_width=True, hide_index=True)
else:
    st.info("No cases match the current Matrix filters.")

st.divider()

# --- ANALYTICS SECTION ---
st.header("Relational Analytics")

# 1. Heatmap
st.subheader("1. Chronological Motif Heatmap")
def get_decade(date_str):
    years = re.findall(r'(19\d{2}|20\d{2})', str(date_str))
    if years:
        return f"{(int(years[0]) // 10) * 10}s"
    return None

events_with_dates = events_df.merge(encounters_df[['Encounter_ID', 'Date_of_Encounter']], on='Encounter_ID')
events_with_dates['Decade'] = events_with_dates['Date_of_Encounter'].apply(get_decade)
valid_heatmap = events_with_dates[events_with_dates['Decade'].notna()]

if not valid_heatmap.empty:
    heatmap_data = valid_heatmap.groupby(['Decade', 'General_Category']).size().reset_index(name='Count')
    heatmap_chart = alt.Chart(heatmap_data).mark_rect(cornerRadius=4).encode(
        x=alt.X('Decade:O', title='Decade'),
        y=alt.Y('General_Category:N', title='Motif Category'),
        color=alt.Color('Count:Q', scale=alt.Scale(scheme='tealblues'), legend=alt.Legend(title="Motif Count")),
        tooltip=['Decade', 'General_Category', 'Count']
    ).properties(height=500).configure_view(strokeOpacity=0)
    st.altair_chart(heatmap_chart, use_container_width=True)
else:
    st.info("Not enough chronological data for a heatmap.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("2. Emotional Motif Correlation")
    available_emotions = events_df['Emotional_Marker'].dropna().unique()
    
    if len(available_emotions) > 0:
        target_emotion = st.selectbox("Select an Emotion:", available_emotions)
        emotion_events = events_df[events_df['Emotional_Marker'] == target_emotion]
        top_motifs = emotion_events['General_Category'].value_counts().reset_index()
        top_motifs.columns = ['Category', 'Count']
        
        st.write(f"When Subjects feel **{target_emotion}**, they are typically experiencing:")
        
        chart = alt.Chart(top_motifs.head(5)).mark_bar(color='#8a2be2', cornerRadiusEnd=4).encode(
            x=alt.X('Count:Q', title='Number of Occurrences'),
            y=alt.Y('Category:N', sort='-x', title=''),
            tooltip=['Category', 'Count']
        ).properties(height=250)
        st.altair_chart(chart, use_container_width=True)

with col2:
    st.subheader("3. Most Common Granular Motifs")
    if not events_df.empty:
        top_codes = events_df['Motif_Code'].value_counts().reset_index()
        top_codes.columns = ['Motif_Code', 'Count']
        
        query = "SELECT motif_number AS Motif_Code, motif_description AS Motif_Description FROM Motif_Dictionary"
        conn = sqlite3.connect('ufo_matrix.db')
        dict_df = pd.read_sql_query(query, conn)
        conn.close()
        
        top_codes = top_codes.merge(dict_df, on='Motif_Code', how='left')
        
        chart2 = alt.Chart(top_codes.head(7)).mark_bar(color='#00d2ff', cornerRadiusEnd=4).encode(
            x=alt.X('Count:Q', title='Number of Occurrences'),
            y=alt.Y('Motif_Code:N', sort='-x', title='Code'),
            tooltip=['Motif_Description', 'Count']
        ).properties(height=250)
        st.altair_chart(chart2, use_container_width=True)
