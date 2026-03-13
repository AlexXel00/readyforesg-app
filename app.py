import streamlit as st
import pandas as pd
import altair as alt
from supabase import create_client
from fpdf import FPDF
from openai import OpenAI
import time
import uuid
import plotly.graph_objects as go

# --- DAS ZENTRALE ESRS GEHIRN (Mapping für Tags & Einheiten) ---
ESRS_MAP = {
    # Environment
    "Grid Mix (National Average)": {"tag": "ESRS-E1-M-01", "unit": "kWh"},
    "Green Electricity (Renewable)": {"tag": "ESRS-E1-M-02", "unit": "kWh"},
    "District Heating (Standard Mix)": {"tag": "ESRS-E1-M-03", "unit": "kWh"},
    "Diesel (B7)": {"tag": "ESRS-E1-S1-Fleet", "unit": "liters"},
    "Petrol / Gasoline (E10)": {"tag": "ESRS-E1-S1-Fleet", "unit": "liters"},
    "General Waste (Residual)": {"tag": "ESRS-E5-5", "unit": "kg"},
    "Paper / Cardboard": {"tag": "ESRS-E5-5", "unit": "kg"},
    
    # Social
    "S1: Workforce Data": {"tag": "ESRS-S1-6", "unit": "count"},
    "S1.2: Health & Safety": {"tag": "ESRS-S1-14", "unit": "count"},
    "S1.3: Wages & Gender Pay Gap": {"tag": "ESRS-S1-16", "unit": "percent"},
    "S1.4: Training & Skills": {"tag": "ESRS-S1-13", "unit": "hours"},
    "S2: Workers in the Value Chain": {"tag": "ESRS-S2", "unit": "text"},
    "S3: Affected Communities": {"tag": "ESRS-S3", "unit": "text"},
    "S4: Consumers & End-users": {"tag": "ESRS-S4", "unit": "text"},
    
    # Governance
    "G1: Business Conduct": {"tag": "ESRS-G1", "unit": "text"},
    "G2: Management & Strategy": {"tag": "ESRS-G2", "unit": "text"},
    "G3: Supplier Relations": {"tag": "ESRS-G1-6", "unit": "text"}
}
MONTHLY_CATEGORIES = {
    "Electricity (kWh)": {
        "esrs_tag": "ESRS-E1-M-01",
        "unit": "kWh",
        "co2_factor": 0.40,
        "scope": "Scope 2"
    },
    "Gas / Heating (kWh)": {
        "esrs_tag": "ESRS-E1-M-03",
        "unit": "kWh",
        "co2_factor": 0.20,
        "scope": "Scope 1"
    },
    "Water (m3)": {
        "esrs_tag": "ESRS-E3-1",
        "unit": "m3",
        "co2_factor": 1.052,
        "scope": "Scope 3"
    },
    "Diesel / Fuel (Liters)": {
        "esrs_tag": "ESRS-E1-S1-Fleet",
        "unit": "liters",
        "co2_factor": 2.68,
        "scope": "Scope 1"
    },
    "General Waste (kg)": {
        "esrs_tag": "ESRS-E5-5",
        "unit": "kg",
        "co2_factor": 0.50,
        "scope": "Scope 3"
    },
    "Recycling (kg)": {
        "esrs_tag": "ESRS-E5-5",
        "unit": "kg",
        "co2_factor": 0.02,
        "scope": "Scope 3"
    },
    "District Heating (kWh)": {
        "esrs_tag": "ESRS-E1-M-03",
        "unit": "kWh",
        "co2_factor": 0.28,
        "scope": "Scope 2"
    },
    "Other / Custom": {
        "esrs_tag": "ESRS-GENERIC",
        "unit": "units",
        "co2_factor": 0.0,
        "scope": "Scope 3"
    }
}
GRID_FACTORS = {
    "Austria": 0.13,
    "Germany": 0.38,
    "Switzerland": 0.03,
    "France": 0.06,
    "Italy": 0.23,
    "Spain": 0.19,
    "Netherlands": 0.37,
    "Belgium": 0.17,
    "Sweden": 0.02,
    "Denmark": 0.16,
    "Poland": 0.70,
    "Ireland": 0.33,
    "United Kingdom": 0.23,
    "Singapore": 0.41,
    "Philippines": 0.51,
    "USA": 0.39,
    "Other / Unknown": 0.40
}
MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

LOCATION_TYPES = [
    "Office / Headquarters",
    "Production Hall / Factory",
    "Warehouse / Logistics",
    "Retail / Shop",
    "Data Center",
    "Construction Site",
    "Other"
]

# --- CONFIGURATION ---
st.set_page_config(
    page_title="Ready for ESG", 
    layout="wide",
    page_icon="logo.png"  
)

# --- CUSTOM CSS: DER RAHMEN & STYLE & BUTTONS ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500;600&family=DM+Sans:wght@300;400;500&display=swap');

    /* 1. Globale Schriften & Hintergrund */
    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
        background-color: #fdfef9;
        color: #1a1a1a;
    }

    /* 2. Hauptbereich weiss */
    [data-testid="stAppViewContainer"] {
        background-color: #fdfef9;
        border: 20px solid #023425;
    }

    [data-testid="stHeader"] {
        background-color: transparent;
    }

    /* 3. Sidebar dunkelgruen */
    section[data-testid="stSidebar"] {
        background-color: #023425 !important;
        border-right: none;
    }

    section[data-testid="stSidebar"] * {
        color: #fdfef9 !important;
    }

    section[data-testid="stSidebar"] .stTextInput input {
        background-color: #416852 !important;
        border: 1px solid #8a9a93 !important;
        color: #fdfef9 !important;
        border-radius: 4px;
    }

    section[data-testid="stSidebar"] .stTextInput input::placeholder {
        color: #8a9a93 !important;
    }

    section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] {
        background-color: #416852 !important;
        border: 1px solid #8a9a93 !important;
        border-radius: 4px;
    }

    section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] * {
        color: #fdfef9 !important;
    }

    section[data-testid="stSidebar"] hr {
        border-color: #416852 !important;
    }

    /* 4. Radio Buttons in Sidebar */
    section[data-testid="stSidebar"] div[role="radiogroup"] label {
        color: #fdfef9 !important;
    }

    section[data-testid="stSidebar"] div[role="radiogroup"] div[data-testid="stMarkdownContainer"] p {
        color: #fdfef9 !important;
    }

    /* 5. Alle Primary Buttons */
    div.stButton > button[kind="primary"] {
        background-color: #023425 !important;
        border: 1px solid #023425 !important;
        color: #fdfef9 !important;
        border-radius: 2px !important;
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 500 !important;
        letter-spacing: 0.05em !important;
        padding: 0.5rem 1.5rem !important;
        transition: background-color 0.2s ease !important;
    }

    div.stButton > button[kind="primary"]:hover {
        background-color: #416852 !important;
        border-color: #416852 !important;
    }

    /* 6. Secondary Buttons */
    div.stButton > button[kind="secondary"] {
        background-color: transparent !important;
        border: 1px solid #023425 !important;
        color: #023425 !important;
        border-radius: 2px !important;
        font-family: 'DM Sans', sans-serif !important;
    }

    div.stButton > button[kind="secondary"]:hover {
        background-color: #dfe1d6 !important;
    }

    /* 7. Ueberschriften */
    h1, h2, h3 {
        font-family: 'Cormorant Garamond', serif !important;
        font-weight: 500 !important;
        color: #023425 !important;
        letter-spacing: 0.02em !important;
    }

    h1 { font-size: 2.8rem !important; }
    h2 { font-size: 2rem !important; }
    h3 { font-size: 1.5rem !important; }

    /* 8. Container / Cards */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border: 1px solid #dfe1d6 !important;
        border-radius: 4px !important;
        background-color: #ffffff !important;
    }

    /* 9. Tabs */
    div[data-baseweb="tab-list"] {
        border-bottom: 2px solid #dfe1d6 !important;
        background-color: transparent !important;
    }

    div[data-baseweb="tab"] {
        font-family: 'DM Sans', sans-serif !important;
        color: #8a9a93 !important;
    }

    div[data-baseweb="tab"][aria-selected="true"] {
        color: #023425 !important;
        border-bottom: 2px solid #023425 !important;
    }

    /* 10. Input Felder */
    div.stTextInput input, div.stNumberInput input, div.stTextArea textarea {
        border: 1px solid #dfe1d6 !important;
        border-radius: 2px !important;
        background-color: #ffffff !important;
        font-family: 'DM Sans', sans-serif !important;
    }

    div.stTextInput input:focus, div.stNumberInput input:focus, div.stTextArea textarea:focus {
        border-color: #023425 !important;
        box-shadow: 0 0 0 1px #023425 !important;
    }

    /* 11. Selectbox */
    div[data-baseweb="select"] {
        border-radius: 2px !important;
    }

    /* 12. Metriken */
    div[data-testid="stMetric"] {
        background-color: #ffffff !important;
        border: 1px solid #dfe1d6 !important;
        border-radius: 4px !important;
        padding: 1rem !important;
    }

    div[data-testid="stMetricValue"] {
        color: #023425 !important;
        font-family: 'Cormorant Garamond', serif !important;
        font-size: 2rem !important;
    }

    /* 13. Info / Warning / Success Boxen */
    div[data-testid="stAlert"] {
        border-radius: 2px !important;
        border-left: 3px solid #023425 !important;
    }

    /* 14. Dataframe */
    div[data-testid="stDataFrame"] {
        border: 1px solid #dfe1d6 !important;
        border-radius: 4px !important;
    }

    /* 15. Sidebar Logo Bereich */
    [data-testid="stSidebarUserContent"] {
        padding-top: 1rem !important;
    }

    </style>
""", unsafe_allow_html=True)

# Initialisiere Session State
if 'entry_stage' not in st.session_state:
    st.session_state['entry_stage'] = 'main'

# State Lists & Flags
if 'e1_batch_list' not in st.session_state: st.session_state['e1_batch_list'] = []
if 'e1_step_complete' not in st.session_state: st.session_state['e1_step_complete'] = False

if 'e1_2_batch_list' not in st.session_state: st.session_state['e1_2_batch_list'] = []
if 'e1_2_step_complete' not in st.session_state: st.session_state['e1_2_step_complete'] = False

if 'e2_batch_list' not in st.session_state: st.session_state['e2_batch_list'] = []
if 'e2_step_complete' not in st.session_state: st.session_state['e2_step_complete'] = False

if 'e3_batch_list' not in st.session_state: st.session_state['e3_batch_list'] = [] 
if 'e3_step_complete' not in st.session_state: st.session_state['e3_step_complete'] = False

if 'e4_batch_list' not in st.session_state: st.session_state['e4_batch_list'] = [] 
if 'e4_step_complete' not in st.session_state: st.session_state['e4_step_complete'] = False

if 'e5_batch_list' not in st.session_state: st.session_state['e5_batch_list'] = [] 
if 'e5_step_complete' not in st.session_state: st.session_state['e5_step_complete'] = False

if 's1_batch_list' not in st.session_state: st.session_state['s1_batch_list'] = []
if 's1_step_complete' not in st.session_state: st.session_state['s1_step_complete'] = False

if 's1_2_batch_list' not in st.session_state: st.session_state['s1_2_batch_list'] = []
if 's1_2_step_complete' not in st.session_state: st.session_state['s1_2_step_complete'] = False

if 's1_3_batch_list' not in st.session_state: st.session_state['s1_3_batch_list'] = []
if 's1_3_step_complete' not in st.session_state: st.session_state['s1_3_step_complete'] = False

if 's1_4_batch_list' not in st.session_state: st.session_state['s1_4_batch_list'] = []
if 's1_4_step_complete' not in st.session_state: st.session_state['s1_4_step_complete'] = False

if 's2_batch_list' not in st.session_state: st.session_state['s2_batch_list'] = []
if 's2_step_complete' not in st.session_state: st.session_state['s2_step_complete'] = False

if 's3_batch_list' not in st.session_state: st.session_state['s3_batch_list'] = []
if 's3_step_complete' not in st.session_state: st.session_state['s3_step_complete'] = False

if 's4_batch_list' not in st.session_state: st.session_state['s4_batch_list'] = []
if 's4_step_complete' not in st.session_state: st.session_state['s4_step_complete'] = False

if 'e_water_batch_list' not in st.session_state: st.session_state['e_water_batch_list'] = []
if 'e_water_step_complete' not in st.session_state: st.session_state['e_water_step_complete'] = False

if 'e_bio_batch_list' not in st.session_state: st.session_state['e_bio_batch_list'] = []
if 'e_bio_step_complete' not in st.session_state: st.session_state['e_bio_step_complete'] = False

if 'e6_batch_list' not in st.session_state: st.session_state['e6_batch_list'] = [] 
if 'e6_step_complete' not in st.session_state: st.session_state['e6_step_complete'] = False

if 'g1_step_complete' not in st.session_state: st.session_state['g1_step_complete'] = False
if 'g2_step_complete' not in st.session_state: st.session_state['g2_step_complete'] = False
if 'g3_step_complete' not in st.session_state: st.session_state['g3_step_complete'] = False

if 'company_setup_complete' not in st.session_state: st.session_state['company_setup_complete'] = False
if 'company_description' not in st.session_state: st.session_state['company_description'] = ""
if 'company_industry' not in st.session_state: st.session_state['company_industry'] = "Services / Office"
if 'material_topics' not in st.session_state: st.session_state['material_topics'] = []

# Database Connection
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Supabase Connection Error: {e}")
        return None

supabase = init_connection()
def login(email, password):
    try:
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        if response.session:
            st.session_state['user'] = response.user
            st.session_state['access_token'] = response.session.access_token
            return "success"
        else:
            st.session_state['mfa_pending_email'] = email
            st.session_state['mfa_pending_password'] = password
            return "mfa_required"
    except Exception as e:
        st.error(f"Login failed: {e}")
        return "error"

st.session_state['last_activity'] = time.time()
def register(email, password, company):
    try:
        response = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": {"company_name": company}
            }
        })
        st.session_state['user'] = response.user
        return True
    except Exception as e:
        st.error(f"Registration failed: {e}")
        return False

def logout():
    supabase.auth.sign_out()
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

import time

if 'last_activity' not in st.session_state:
    st.session_state['last_activity'] = time.time()

if 'user' in st.session_state:
    if time.time() - st.session_state.get('last_activity', 0) > 3600:
        st.warning("Your session has expired. Please login again.")
        logout()

def setup_mfa():
    try:
        response = supabase.auth.mfa.enroll({
            "factor_type": "totp",
            "issuer": "Ready for ESG"
        })
        st.session_state['mfa_factor_id'] = response.id
        return response.totp.qr_code, response.totp.secret
    except Exception as e:
        st.error(f"MFA Setup failed: {e}")
        return None, None

def verify_mfa(code):
    try:
        factor_id = st.session_state.get('mfa_factor_id')
        challenge = supabase.auth.mfa.challenge({"factor_id": factor_id})
        verify = supabase.auth.mfa.verify({
            "factor_id": factor_id,
            "challenge_id": challenge.id,
            "code": code
        })
        st.session_state['user'] = verify.user
        st.session_state['access_token'] = verify.access_token
        return True
    except Exception as e:
        st.error(f"MFA verification failed: {e}")
        return False
    
# --- HELPER FUNCTIONS ---

# E1.1 Electricity Helpers
def add_exact_to_batch():
    source = st.session_state.get('widget_source', "Grid Mix (National Average)")
    kwh = st.session_state.get('widget_kwh', 0.0)
    notes = st.session_state.get('widget_notes_exact', "")
    
    # Den aktuellen dynamischen Key abrufen
    current_uploader_key = st.session_state.get('file_key_e1', 'fallback_key')
    uploaded_file = st.session_state.get(current_uploader_key)
    
    file_url = ""
    
    if uploaded_file is not None and supabase is not None:
        try:
                company = st.session_state.get('current_company_id', 'Unknown')
                year = st.session_state.get('current_year', '2024')
                file_ext = uploaded_file.name.split('.')[-1]
                file_name = f"{company}/{year}/{uuid.uuid4().hex[:8]}.{file_ext}"
                
                supabase.storage.from_("esg_evidence").upload(file_name, uploaded_file.getvalue())
                file_url = supabase.storage.from_("esg_evidence").get_public_url(file_name)
                notes = f"{notes} | Evidence: {file_url}"
                
                
        except Exception as e:
            st.toast(f"Upload failed: {e}")

    if kwh > 0:
        country = st.session_state.get('widget_e1_country', 'Other / Unknown')
        factors = {
            "Green Electricity (Renewable)": 0.0,
            "Nuclear Power": 0.01,
            "Coal / Fossil Mix": 0.80
        }
        if source == "Grid Mix (National Average)":
            co2_factor = GRID_FACTORS.get(country, 0.40)
        else:
            co2_factor = factors.get(source, 0.40)
        co2 = kwh * co2_factor
        st.session_state['e1_batch_list'].append({
            "type": "Exact",
            "source": source,
            "liters": kwh,
            "notes": f"{notes} | Country: {country} | Factor: {co2_factor} kg/kWh",
            "co2": co2
        })
        st.session_state['e1_batch_list'].append({"type": "Exact", "source": source, "liters": kwh, "notes": notes, "co2": co2})
        
        # Eingabefelder zurücksetzen
        st.session_state.widget_kwh = 0.0
        st.session_state.widget_notes_exact = ""
        
        # Den Uploader-Key erneuern, um ein leeres Feld zu erzwingen
        st.session_state['file_key_e1'] = str(uuid.uuid4())
            
    else: 
        st.toast("Value must be greater than 0.")

def add_estimate_to_batch():
    n_b = st.session_state.get('widget_n_buildings', 1)
    area = st.session_state.get('widget_area', 100.0)
    age = st.session_state.get('widget_age', "Standard (1980-2010)")
    use = st.session_state.get('widget_use', "Office")
    country = st.session_state.get('widget_e1_country_est', 'Other / Unknown')
    
    base = 180 if "Old" in age else (120 if "Standard" in age else 70)
    if "Warehouse" in use: base *= 0.5
    if "Production" in use: base *= 2.5
    
    est_kwh = n_b * area * base
    co2_factor = GRID_FACTORS.get(country, 0.40)
    est_co2 = est_kwh * co2_factor
    
    st.session_state['e1_batch_list'].append({
        "type": "Estimate",
        "source": f"ESTIMATE: {use} ({age})",
        "liters": est_kwh,
        "notes": f"{n_b}x {area}m2 | Country: {country} | Factor: {co2_factor} kg/kWh",
        "co2": est_co2
    })

def upload_batch():
    current_company = st.session_state.get('current_company_id', '')
    if current_company and st.session_state['e1_batch_list']:
        entries = []
        for item in st.session_state['e1_batch_list']:
            meta = ESRS_MAP.get(item['source'], {"tag": "ESRS-GENERIC", "unit": "unit"})
            entries.append({
                "company": current_company,
                "fuel_type": item['source'],
                "value_raw": item['liters'],
                "co2_kg": item['co2'],
                "type": item['type'],
                "esrs_tag": meta['tag'],
                "description": item.get('notes', ''), 
                "methodology": f"Calculated via Boku-Factor ({meta['unit']})",
                "date_of_service": f"{st.session_state.get('current_year', '2024')}-12-31" 
            })
        if supabase is not None:
            try:
                supabase.table("esg_data_entries").insert(entries).execute()
                st.toast(f"Uploaded {len(entries)} records successfully.")
            except Exception as e:
                st.error(f"Error during upload: {e}")
        else:
            st.warning("No database connection detected. Simulating upload...")
            
        st.session_state['e1_batch_list'] = []      
        st.session_state['e1_step_complete'] = True 

def remove_last_e1():
    if st.session_state['e1_batch_list']: st.session_state['e1_batch_list'].pop()

def remove_last_s2():
    if 's2_batch_list' in st.session_state and st.session_state['s2_batch_list']:
        st.session_state['s2_batch_list'].pop()

def remove_last_s3():
    if 's3_batch_list' in st.session_state and st.session_state['s3_batch_list']:
        st.session_state['s3_batch_list'].pop()

def remove_last_s4():
    if 's4_batch_list' in st.session_state and st.session_state['s4_batch_list']:
        st.session_state['s4_batch_list'].pop()

def add_heating_exact_to_batch():
    source = st.session_state.get('widget_h_source', "District Heating (Standard Mix)")
    kwh = st.session_state.get('widget_h_kwh', 0.0)
    notes = st.session_state.get('widget_h_notes', "")
    
    # --- Datei-Upload Logik für Heizkostenbelege ---
    current_uploader_key = st.session_state.get('file_key_heat_exact', 'fallback_key_h')
    uploaded_file = st.session_state.get(current_uploader_key)
    
    if uploaded_file is not None and supabase is not None:
        try:
            company = st.session_state.get('current_company_id', 'Unknown')
            year = st.session_state.get('current_year', '2024')
            file_ext = uploaded_file.name.split('.')[-1]
            file_name = f"{company}/{year}/{uuid.uuid4().hex[:8]}.{file_ext}"
            
            supabase.storage.from_("esg_evidence").upload(file_name, uploaded_file.getvalue())
            file_url = supabase.storage.from_("esg_evidence").get_public_url(file_name)
            notes = f"{notes} | Evidence: {file_url}"
        except Exception as e:
            st.toast(f"Upload failed: {e}")
    # -----------------------------------------------

    if kwh > 0:
        factors = {"District Heating (Standard Mix)": 0.28, "District Heating (Green/Geothermal)": 0.05, "District Cooling": 0.40, "Steam (Purchased)": 0.30}
        co2 = kwh * factors.get(source, 0.28)
        st.session_state['e1_2_batch_list'].append({"type": "Exact", "source": source, "liters": kwh, "notes": notes, "co2": co2})
        
        # Felder zurücksetzen
        st.session_state.widget_h_kwh = 0.0
        st.session_state.widget_h_notes = ""
        
        # Key erneuern, um das Upload-Feld zu leeren
        st.session_state['file_key_heat_exact'] = str(uuid.uuid4())
    else: 
        st.toast("Value must be greater than 0.")

def add_heating_estimate_to_batch():
    n_b = st.session_state.get('widget_h_n', 1)
    area = st.session_state.get('widget_h_area', 100.0)
    insulation = st.session_state.get('widget_h_insulation', "Standard Insulation (1980-2015)")
    demand_map = {"Poor Insulation (Pre-1980)": 160, "Standard Insulation (1980-2015)": 100, "High Efficiency (Post-2015/Renovated)": 40}
    base = demand_map.get(insulation, 100)
    est_kwh = n_b * area * base
    est_co2 = est_kwh * 0.28
    st.session_state['e1_2_batch_list'].append({"type": "Estimate", "source": f"ESTIMATE: Heating ({insulation})", "liters": est_kwh, "notes": f"{n_b}x {area}m2", "co2": est_co2})

def upload_heating_batch():
    current_company = st.session_state.get('current_company_id', '')
    if current_company and st.session_state['e1_2_batch_list']:
        entries = []
        for item in st.session_state['e1_2_batch_list']:
            meta = ESRS_MAP.get(item['source'], {"tag": "ESRS-E1-M-03", "unit": "kWh"})
            entries.append({
                "company": current_company,
                "fuel_type": item['source'],
                "value_raw": item['liters'],
                "co2_kg": item['co2'],
                "type": item['type'],
                "esrs_tag": meta['tag'],
                "description": item.get('notes', ''),
                "methodology": f"Boku-Standard-Factor ({meta['unit']})",
                "date_of_service": f"{st.session_state.get('current_year', '2024')}-12-31"
            })
        if supabase:
            try:
                supabase.table("esg_data_entries").insert(entries).execute()
                st.toast(f"Uploaded {len(entries)} records successfully.")
                st.session_state['e1_2_batch_list'] = []
                st.session_state['e1_2_step_complete'] = True
            except Exception as e:
                st.error(f"Upload failed: {e}")

def remove_last_heating():
    if st.session_state['e1_2_batch_list']: st.session_state['e1_2_batch_list'].pop()

def add_fuel_exact_to_batch():
    fuel = st.session_state.get('widget_m_fuel', "Diesel (B7)")
    amount = st.session_state.get('widget_m_liters', 0.0) 
    notes = st.session_state.get('widget_m_notes', "")
    
    # --- NEU: Datei-Upload Logik für Tankbelege ---
    current_uploader_key = st.session_state.get('file_key_m_exact', 'fallback_key_m')
    uploaded_file = st.session_state.get(current_uploader_key)
    
    if uploaded_file is not None and supabase is not None:
        try:
            company = st.session_state.get('current_company_id', 'Unknown')
            year = st.session_state.get('current_year', '2024')
            file_ext = uploaded_file.name.split('.')[-1]
            file_name = f"{company}/{year}/{uuid.uuid4().hex[:8]}.{file_ext}"
            
            supabase.storage.from_("esg_evidence").upload(file_name, uploaded_file.getvalue())
            file_url = supabase.storage.from_("esg_evidence").get_public_url(file_name)
            notes = f"{notes} | Evidence: {file_url}"
        except Exception as e:
            st.toast(f"Upload failed: {e}")
    # ----------------------------------------------

    if amount > 0:
        factors = {"Diesel (B7)": 2.68, "Petrol / Gasoline (E10)": 2.31, "Natural Gas (Heating / Boiler)": 0.20, "Heating Oil (Light)": 2.66, "LPG (Forklift/Car)": 1.61}
        co2 = amount * factors.get(fuel, 2.5)
        st.session_state['e2_batch_list'].append({"type": "Exact", "source": f"Scope 1: {fuel}", "liters": amount, "notes": notes, "co2": co2})
        
        # Felder zurücksetzen
        st.session_state.widget_m_liters = 0.0
        st.session_state.widget_m_notes = ""
        
        # Key erneuern, um das Upload-Feld zu leeren
        st.session_state['file_key_m_exact'] = str(uuid.uuid4())
    else: 
        st.toast("Value must be greater than 0.")
        
def add_distance_estimate_to_batch():
    vehicle = st.session_state.get('widget_m_vehicle_2', "Passenger Car (Diesel)")
    km = st.session_state.get('widget_m_km_2', 0.0)
    if km > 0:
        consumption_map = {"Passenger Car (Diesel)": 6.0, "Passenger Car (Petrol)": 7.5, "Van / Light Truck (Diesel)": 9.5, "Heavy Truck (Diesel)": 28.0}
        fuel_map = {"Passenger Car (Diesel)": "Diesel (B7)", "Passenger Car (Petrol)": "Petrol / Gasoline (E10)", "Van / Light Truck (Diesel)": "Diesel (B7)", "Heavy Truck (Diesel)": "Diesel (B7)"}
        fuel_type = fuel_map.get(vehicle, "Diesel (B7)")
        l_per_100 = consumption_map.get(vehicle, 7.0)
        liters_calc = (km / 100) * l_per_100
        factors = {"Diesel (B7)": 2.68, "Petrol / Gasoline (E10)": 2.31}
        est_co2 = liters_calc * factors.get(fuel_type, 2.68)
        st.session_state['e2_batch_list'].append({"type": "Estimate", "source": f"ESTIMATE: {vehicle}", "liters": liters_calc, "notes": f"Driven: {km:,.0f} km", "co2": est_co2})
        st.session_state.widget_m_km_2 = 0.0  # <--- HIER WAR NOCH DIE ALTE VARIABLE
    else: st.toast("Distance must be greater than 0.")

def upload_mobility_batch():
    current_company = st.session_state.get('current_company_id', '')
    if current_company and st.session_state['e2_batch_list']:
        entries = []
        for item in st.session_state['e2_batch_list']:
            meta = ESRS_MAP.get(item['source'], {"tag": "ESRS-E1-S1-Fleet", "unit": "liters"})
            entries.append({
                "company": current_company,
                "fuel_type": item['source'],
                "value_raw": item['liters'],
                "co2_kg": item['co2'],
                "type": item['type'],
                "esrs_tag": meta['tag'],
                "description": item.get('notes', ''),
                "methodology": f"Boku-Calculation ({meta['unit']})",
                "date_of_service": f"{st.session_state.get('current_year', '2024')}-12-31"
            })
        if supabase:
            supabase.table("esg_data_entries").insert(entries).execute()
            st.toast(f"Uploaded {len(entries)} records successfully.")
            st.session_state['e2_batch_list'] = []
            st.session_state['e2_step_complete'] = True
            
def remove_last_e2():
    if st.session_state['e2_batch_list']: st.session_state['e2_batch_list'].pop()

def add_travel_to_batch():
    travel_type = st.session_state.get('widget_t_type', "Flight: Short Haul (< 500 km)")
    amount = st.session_state.get('widget_t_amount', 0.0)
    notes = st.session_state.get('widget_t_notes', "")
    
    # --- Datei-Upload Logik für Reisebelege ---
    current_uploader_key = st.session_state.get('file_key_travel', 'fallback_key_t')
    uploaded_file = st.session_state.get(current_uploader_key)
    
    file_url = ""
    if uploaded_file is not None and supabase is not None:
        try:
            company = st.session_state.get('current_company_id', 'Unknown')
            year = st.session_state.get('current_year', '2024')
            file_ext = uploaded_file.name.split('.')[-1]
            file_name = f"{company}/{year}/{uuid.uuid4().hex[:8]}.{file_ext}"
            
            supabase.storage.from_("esg_evidence").upload(file_name, uploaded_file.getvalue())
            file_url = supabase.storage.from_("esg_evidence").get_public_url(file_name)
        except Exception as e:
            st.toast(f"Upload failed: {e}")
    # ------------------------------------------

    if amount > 0:
        co2 = 0.0
        unit_label = "units"
        
        if "Flight" in travel_type:
            unit_label = "Flights"
            flight_factors = {
                "Flight: Short Haul (< 500 km)": 75.0,
                "Flight: Medium Haul (500-1500 km)": 200.0,
                "Flight: Long Haul (1500-3700 km)": 450.0,
                "Flight: Intercontinental (3700-5000 km)": 645.0,
                "Flight: Ultra Long Haul (> 5000 km)": 1200.0
            }
            co2 = amount * flight_factors.get(travel_type, 200.0)
            
        elif "Hotel" in travel_type:
            unit_label = "Nights"
            co2 = amount * 25.0 
            
        else:
            unit_label = "km"
            km_factors = {
                "Train (National/Regional)": 0.06,
                "Train (Long Distance/High Speed)": 0.01,
                "Private Car (Reimbursement)": 0.18
            }
            co2 = amount * km_factors.get(travel_type, 0.1)
        
        # Notizen und Upload-Link zusammenfügen
        final_notes = f"{notes} ({unit_label})"
        if file_url:
            final_notes += f" | Evidence: {file_url}"
        
        st.session_state['e3_batch_list'].append({
            "type": "Travel", 
            "source": travel_type, 
            "liters": amount, 
            "notes": final_notes, 
            "co2": co2
        })
        
        # Felder zurücksetzen
        st.session_state.widget_t_amount = 0.0
        st.session_state.widget_t_notes = ""
        
        # Key erneuern, um das Upload-Feld zu leeren
        st.session_state['file_key_travel'] = str(uuid.uuid4())
        
    else:
        st.toast("Amount must be greater than 0.")

def show_materiality_badge(esrs_code):
    topics = st.session_state.get('material_topics', [])
    is_material = any(esrs_code in t for t in topics)
    
    if is_material:
        st.success("**Highly Relevant (Material Topic)**\n\nBased on your company profile and industry, this module is considered mandatory. We strongly recommend completing this section to ensure compliance.")
    else:
        st.info("**Optional (Non-Material Topic)**\n\nThis module was not flagged as highly relevant for your operations. You can skip it, but providing extra data provides more credibility to your report and is recommended.")

def upload_travel_batch():
    current_company = st.session_state.get('current_company_id', '')
    if current_company and st.session_state['e3_batch_list']:
        entries = []
        for item in st.session_state['e3_batch_list']:
            meta = ESRS_MAP.get(item['source'], {"tag": "ESRS-E1-S3-Travel", "unit": "unit"})
            entries.append({
                "company": current_company,
                "fuel_type": item['source'],
                "value_raw": item['liters'],
                "co2_kg": item['co2'],
                "type": "Travel Record",
                "esrs_tag": meta['tag'],
                "description": item.get('notes', ''),
                "methodology": f"Boku-Travel-Factor ({meta['unit']})",
                "date_of_service": f"{st.session_state.get('current_year', '2024')}-12-31"
            })
        
        if supabase is not None:
            try:
                supabase.table("esg_data_entries").insert(entries).execute()
                st.toast(f"Uploaded {len(entries)} records successfully.")
                st.session_state['e3_batch_list'] = []
                st.session_state['e3_step_complete'] = True
            except Exception as e:
                st.error(f"Datenbank-Fehler beim Upload: {e}")

            
def remove_last_e3():
    if st.session_state['e3_batch_list']: st.session_state['e3_batch_list'].pop()

def add_commute_to_batch():
    mode = st.session_state.get('widget_c_mode', "Car (Petrol/Diesel)")
    dist_cat = st.session_state.get('widget_c_dist_cat', "Short (< 10 km)")
    days_week = st.session_state.get('widget_c_days', 5)
    employees = st.session_state.get('widget_c_emp', 1)
    
    if employees > 0:
        distance_map = {
            "Short (< 10 km)": 5.0,         
            "Medium (10 - 30 km)": 20.0,    
            "Long (30 - 60 km)": 45.0,      
            "Very Long (> 60 km)": 80.0     
        }
        km_one_way = distance_map.get(dist_cat, 10.0)

        factors = {
            "Car (Petrol/Diesel)": 0.18,
            "Car (Electric)": 0.0,
            "Public Transport (Bus/Train)": 0.04,
            "Motorbike": 0.10,
            "Bicycle / Walk": 0.0
        }
        
        annual_km = km_one_way * 2 * days_week * 46 * employees
        co2 = annual_km * factors.get(mode, 0.15)
        
        note = f"{employees} Pers. ({dist_cat})"
        
        st.session_state['e4_batch_list'].append({
            "type": "Commuting", 
            "source": f"Commute: {mode}", 
            "liters": annual_km, 
            "notes": note, 
            "co2": co2
        })
        
        st.toast("Record added to list.")
    else:
        st.toast("Number of Employees must be greater than 0.")

def upload_commute_batch():
    current_company = st.session_state.get('current_company_id', '')
    if current_company and st.session_state['e4_batch_list']:
        entries = []
        for item in st.session_state['e4_batch_list']:
            entries.append({
                "company": current_company,
                "fuel_type": item['source'],
                "value_raw": item['liters'],
                "co2_kg": item['co2'],
                "type": "Commuting Group",
                "esrs_tag": "ESRS-E1-S3-Commuting",
                "description": item.get('notes', ''),
                "methodology": "Boku-Employee-Commuting-Model",
                "date_of_service": f"{st.session_state.get('current_year', '2024')}-12-31"
            })
        if supabase:
            supabase.table("esg_data_entries").insert(entries).execute()
            st.toast(f"Uploaded {len(entries)} records successfully.")
            st.session_state['e4_batch_list'] = []
            st.session_state['e4_step_complete'] = True
            
def remove_last_e4():
    if st.session_state['e4_batch_list']: st.session_state['e4_batch_list'].pop()

def add_waste_volume_to_batch():
    waste_type = st.session_state.get('widget_w_type', "General Waste (Residual)")
    container_size = st.session_state.get('widget_w_size', 240)
    quantity = st.session_state.get('widget_w_qty', 1)
    frequency = st.session_state.get('widget_w_freq', "Weekly")
    provider = st.session_state.get('widget_w_provider', "Municipal / City")
    
    if quantity > 0:
        freq_factor = 52 if "Weekly" in frequency else (12 if "Monthly" in frequency else 1)
        total_liters = container_size * quantity * freq_factor
        
        density_map = {
            "General Waste (Residual)": 0.15,
            "Paper / Cardboard": 0.06,
            "Plastic / Packaging": 0.05,
            "Glass": 0.35,
            "Organic / Bio": 0.40,
            "Electronic Waste": 0.25
        }
        est_weight_kg = total_liters * density_map.get(waste_type, 0.15)
        
        co2_factors = {
            "General Waste (Residual)": 0.5,
            "Paper / Cardboard": 0.02,
            "Plastic / Packaging": 0.05,
            "Glass": 0.02,
            "Organic / Bio": 0.1,
            "Electronic Waste": 0.05
        }
        
        co2 = est_weight_kg * co2_factors.get(waste_type, 0.5)
        note = f"{quantity}x {container_size}L ({frequency}) | {provider}"
        
        st.session_state['e5_batch_list'].append({
            "type": "Waste", 
            "source": f"Waste: {waste_type}", 
            "liters": est_weight_kg, 
            "notes": note, 
            "co2": co2
        })
        st.toast("Record added to list.")

def upload_waste_batch():
    current_company = st.session_state.get('current_company_id', '')
    if current_company and st.session_state['e5_batch_list']:
        entries = []
        for item in st.session_state['e5_batch_list']:
            meta = ESRS_MAP.get(item['source'], {"tag": "ESRS-E5-5", "unit": "kg"})
            entries.append({
                "company": current_company,
                "fuel_type": item['source'],
                "value_raw": item['liters'], 
                "co2_kg": item['co2'],
                "type": "Waste Record",
                "esrs_tag": meta['tag'],
                "description": item.get('notes', ''),
                "methodology": "Boku-Waste-Factor",
                "date_of_service": f"{st.session_state.get('current_year', '2024')}-12-31"
            })
        if supabase:
            supabase.table("esg_data_entries").insert(entries).execute()
            st.toast(f"Uploaded {len(entries)} records successfully.")
            st.session_state['e5_batch_list'] = []
            st.session_state['e5_step_complete'] = True
            
def remove_last_e5():
    if st.session_state['e5_batch_list']: st.session_state['e5_batch_list'].pop()

def add_water_to_batch():
    source = st.session_state.get('widget_wat_source', "Mains Water (Municipal)")
    m3 = st.session_state.get('widget_wat_m3', 0.0)
    
    if m3 > 0:
        co2_factor = 1.052 if "Municipal" in source else 0.0
        co2 = m3 * co2_factor
        
        st.session_state['e_water_batch_list'].append({
            "type": "Water",
            "source": f"Water: {source}", 
            "liters": m3, 
            "notes": f"{m3} m3 consumed", 
            "co2": co2
        })
        st.toast("Record added to list.")

def add_water_estimate_to_batch():
    b_type = st.session_state.get('widget_wat_est_type', "Office")
    occupants = st.session_state.get('widget_wat_est_ppl', 1)
    days = st.session_state.get('widget_wat_est_days', 250) 
    toilets = st.session_state.get('widget_wat_est_wc', 1) 
    
    if occupants > 0:
        base_lpd = 25.0
        if "Warehouse" in b_type: base_lpd = 15.0
        if "Retail" in b_type: base_lpd = 10.0
        
        total_liters = occupants * days * base_lpd
        m3_calc = total_liters / 1000.0 
        co2 = m3_calc * 1.052
        
        note = f"ESTIMATE: {b_type} ({occupants} People, {toilets} WCs)"
        
        st.session_state['e_water_batch_list'].append({
            "type": "Water",
            "source": "Mains Water (Estimated)", 
            "liters": m3_calc, 
            "notes": note, 
            "co2": co2
        })
        st.toast("Record added to list.")
        st.session_state['e_water_step_complete'] = True 

    else:
        st.toast("Occupants must be greater than 0.")        

def remove_last_water():
    if st.session_state['e_water_batch_list']: st.session_state['e_water_batch_list'].pop()

def add_bio_check_to_batch():
    pollutants = st.session_state.get('widget_bio_poll', "None")
    area_type = st.session_state.get('widget_bio_area', "Urban / Industrial Zone")
    
    st.session_state['e_bio_batch_list'].append({
        "type": "Pollution",
        "source": "ESRS E2: Pollution Check",
        "liters": 0,
        "notes": f"Hazardous Substances: {pollutants}",
        "co2": 0
    })
    
    st.session_state['e_bio_batch_list'].append({
        "type": "Biodiversity",
        "source": "ESRS E4: Biodiversity",
        "liters": 0,
        "notes": f"Site Location: {area_type}",
        "co2": 0
    })
    
    st.toast("Record added to list.")
    st.session_state['e_bio_step_complete'] = True

def remove_last_bio():
    if st.session_state['e_bio_batch_list']: st.session_state['e_bio_batch_list'].pop()

def save_policies_to_batch():
    has_policy = st.session_state.get('widget_p_policy', "No")
    
    st.session_state['e6_batch_list'].append({
        "type": "Policy", 
        "source": "Governance: Environmental Policy", 
        "liters": 0, 
        "notes": f"Status: {has_policy}", 
        "co2": 0
    })
    
    target_type = st.session_state.get('widget_p_targets', "No defined targets")
    target_note = target_type 
    
    if "Reduce" in target_type:
        pct = st.session_state.get('widget_p_target_pct', 20)
        year = st.session_state.get('widget_p_target_year', 2030)
        target_note = f"Target: Reduce Emissions by {pct}% (Target Year: {year})"
        
    elif "Net Zero" in target_type:
        year = st.session_state.get('widget_p_target_year', 2050)
        target_note = f"Target: Net Zero Emissions (Target Year: {year})"
    
    if target_type != "No defined targets":
        st.session_state['e6_batch_list'].append({
            "type": "Policy", 
            "source": "Strategy: Emission Targets", 
            "liters": 0, 
            "notes": target_note, 
            "co2": 0
        })
        
    circular_strat = st.session_state.get('widget_p_circular', "")
    if circular_strat:
        st.session_state['e6_batch_list'].append({
            "type": "Policy", 
            "source": "Circular Economy: Strategy", 
            "liters": 0, 
            "notes": circular_strat, 
            "co2": 0
        })
    
    st.toast("Record added to list.")
    st.session_state['e6_step_complete'] = True

def upload_policies_batch():
    current_company = st.session_state.get('current_company_id', '')
    if current_company and st.session_state['e6_batch_list']:
        entries = []
        for item in st.session_state['e6_batch_list']:
            entries.append({
                "company": current_company,
                "fuel_type": item['source'], 
                "value_raw": 0, 
                "co2_kg": 0, 
                "type": "Policy/Strategy", 
                "esrs_tag": "ESRS-E1-2", 
                "description": item['notes'], 
                "methodology": "Management Disclosure",
                "date_of_service": f"{st.session_state.get('current_year', '2024')}-12-31"
            })
        
        if supabase:
            try:
                supabase.table("esg_data_entries").insert(entries).execute()
                st.toast(f"Uploaded {len(entries)} records successfully.")
                st.session_state['e6_batch_list'] = []
                st.session_state['e6_step_complete'] = True
            except Exception as e:
                st.error(f"Error: {e}")

def save_s1_basic_direct():
    hc = st.session_state.get('widget_s1_headcount', 0)
    women_count = st.session_state.get('widget_s1_women_count', 0)
    age_u30 = st.session_state.get('widget_s1_age_u30', 0)
    age_mid = st.session_state.get('widget_s1_age_mid', 0)
    age_o50 = hc - age_u30 - age_mid

    if age_o50 < 0:
        st.toast("Error: Age groups exceed total headcount.")
        return 

    women_pct = (women_count / hc * 100) if hc > 0 else 0
    st.session_state['s1_total_headcount'] = hc
    note = f"Women: {women_count} ({women_pct:.1f}%) | Age: <30 ({age_u30}), 30-50 ({age_mid}), >50 ({age_o50})"
    current_company = st.session_state.get('current_company_id', '')
    
    if current_company:
        entry = {
            "company": current_company,
            "fuel_type": "S1: Workforce Data",
            "value_raw": hc, 
            "co2_kg": 0, 
            "type": "Exact",
            "esrs_tag": "ESRS-S1-6", 
            "description": note,
            "methodology": "HR Record Export",
            "date_of_service": f"{st.session_state.get('current_year', '2024')}-12-31"
        }
        supabase.table("esg_data_entries").insert([entry]).execute()
        st.session_state['s1_step_complete'] = True
        st.toast("Data uploaded successfully.")

def save_s1_health_direct():
    accidents = st.session_state.get('widget_s1_accidents', 0)
    sick_rate = st.session_state.get('widget_s1_sick', 0.0)
    fatalities = st.session_state.get('widget_s1_fatalities', 0)
    
    note = f"Sick Rate: {sick_rate}% | Fatalities: {fatalities}"
    current_company = st.session_state.get('current_company_id', '')
    
    if current_company:
        entry = {
            "company": current_company,
            "fuel_type": "S1.2: Health & Safety",
            "value_raw": accidents, 
            "co2_kg": 0,
            "type": "Social",
            "esrs_tag": "ESRS-S1-14", 
            "description": note,
            "methodology": "Accident Log / Insurance Data",
            "date_of_service": f"{st.session_state.get('current_year', '2024')}-12-31"
        }
        supabase.table("esg_data_entries").insert([entry]).execute()
        st.session_state['s1_2_step_complete'] = True
        st.toast("Data uploaded successfully.")

def save_s1_wages_direct():
    sal_men = st.session_state.get('widget_s1_sal_men', 0.0)
    sal_women = st.session_state.get('widget_s1_sal_women', 0.0)
    gap_pct = ((sal_men - sal_women) / sal_men * 100) if sal_men > 0 else 0.0
    
    ceo_ratio = st.session_state.get('widget_s1_ceo', 'Unknown / Confidential')
    living_wage = st.session_state.get('widget_s1_living_wage', "Yes")
    note = f"Ø Salary M/F: {int(sal_men)}EUR / {int(sal_women)}EUR | Pay Disparity: {ceo_ratio} | Living Wage: {living_wage}"
    
    current_company = st.session_state.get('current_company_id', '')
    
    if current_company:
        entry = {
            "company": current_company,
            "fuel_type": "S1.3: Wages & Gender Pay Gap",
            "value_raw": gap_pct, 
            "co2_kg": 0,
            "type": "Calculated",
            "esrs_tag": "ESRS-S1-16", 
            "description": note,
            "methodology": "Payroll Analysis",
            "date_of_service": f"{st.session_state.get('current_year', '2024')}-12-31"
        }
        if supabase is not None:
            supabase.table("esg_data_entries").insert([entry]).execute()
            st.session_state['s1_3_step_complete'] = True
            st.toast(f"Data uploaded successfully. Calculated Pay Gap: {gap_pct:.1f}%")

def save_s1_training_direct():
    total_h = st.session_state.get('widget_s1_hours_total', 0)
    hc = st.session_state.get('s1_total_headcount', 1)
    avg = total_h / hc if hc > 0 else 0
    note = f"Total Hours: {total_h} | Average: {avg:.1f}h per employee"
    current_company = st.session_state.get('current_company_id', '')
    
    if current_company:
        entry = {
            "company": current_company,
            "fuel_type": "S1.4: Training & Skills",
            "value_raw": total_h,
            "co2_kg": 0,
            "type": "Social",
            "esrs_tag": "ESRS-S1-13", 
            "description": note,
            "methodology": "Training Management System",
            "date_of_service": f"{st.session_state.get('current_year', '2024')}-12-31"
        }
        supabase.table("esg_data_entries").insert([entry]).execute()
        st.session_state['s1_4_step_complete'] = True
        st.toast("Data uploaded successfully.")

def add_s2_to_batch():
    coc_status = st.session_state.get('widget_s2_coc', "No")
    risk_check = st.session_state.get('widget_s2_risk', "None")
    audit_status = st.session_state.get('widget_s2_audit', "None")
    
    note = f"CoC: {coc_status} | Risk Check: {risk_check} | Audits: {audit_status}"
    
    st.session_state['s2_batch_list'].append({
        "type": "Qualitative", 
        "source": "S2: Workers in the Value Chain", 
        "liters": 0, 
        "notes": note, 
        "co2": 0
    })
    st.session_state['s2_step_complete'] = True
    st.toast("Record added to list.")

def upload_s2_batch():
    current_company = st.session_state.get('current_company_id', '')
    if current_company and st.session_state['s2_batch_list']:
        entries = []
        for item in st.session_state['s2_batch_list']:
            entries.append({
                "company": current_company,
                "fuel_type": item['source'],
                "value_raw": 0,
                "co2_kg": 0,
                "type": "Social",
                "esrs_tag": "ESRS-S2",
                "description": item['notes'],
                "methodology": "Management Disclosure",
                "date_of_service": f"{st.session_state.get('current_year', '2024')}-12-31"
            })
        if supabase:
            supabase.table("esg_data_entries").insert(entries).execute()
            st.toast("Uploaded records successfully.")
            st.session_state['s2_batch_list'] = []
            
def add_s3_to_batch():
    impact = st.session_state.get('widget_s3_impact', "None")
    engagement = st.session_state.get('widget_s3_engage', "None")
    desc = st.session_state.get('widget_s3_desc', "")
    note = f"Impact: {impact} | Engagement: {engagement} | Details: {desc}"
    
    st.session_state['s3_batch_list'].append({
        "type": "Qualitative", 
        "source": "S3: Affected Communities", 
        "liters": 0, 
        "notes": note, 
        "co2": 0
    })
    st.session_state['s3_step_complete'] = True
    st.toast("Record added to list.")

def upload_s3_batch():
    current_company = st.session_state.get('current_company_id', '')
    if current_company and st.session_state['s3_batch_list']:
        entries = []
        for item in st.session_state['s3_batch_list']:
            entries.append({
                "company": current_company,
                "fuel_type": item['source'],
                "value_raw": 0,
                "co2_kg": 0,
                "type": "Social",
                "esrs_tag": "ESRS-S3",
                "description": item['notes'],
                "methodology": "Management Disclosure",
                "date_of_service": f"{st.session_state.get('current_year', '2024')}-12-31"
            })
        if supabase:
            supabase.table("esg_data_entries").insert(entries).execute()
            st.toast("Uploaded records successfully.")
            st.session_state['s3_batch_list'] = []
            
def add_s4_to_batch():
    privacy = st.session_state.get('widget_s4_privacy', "Standard GDPR Compliance")
    safety = st.session_state.get('widget_s4_safety', "Legal Standard (CE)")
    marketing = st.session_state.get('widget_s4_marketing', "No formal policy")
    note = f"Privacy: {privacy} | Safety: {safety} | Marketing: {marketing}"
    
    st.session_state['s4_batch_list'].append({
        "type": "Qualitative", 
        "source": "S4: Consumers & End-users", 
        "liters": 0, 
        "notes": note, 
        "co2": 0
    })
    st.session_state['s4_step_complete'] = True
    st.toast("Record added to list.")

def upload_s4_batch():
    current_company = st.session_state.get('current_company_id', '')
    if current_company and st.session_state['s4_batch_list']:
        entries = []
        for item in st.session_state['s4_batch_list']:
            entries.append({
                "company": current_company,
                "fuel_type": item['source'],
                "value_raw": 0,
                "co2_kg": 0,
                "type": "Social",
                "esrs_tag": "ESRS-S4",
                "description": item['notes'],
                "methodology": "Management Disclosure",
                "date_of_service": f"{st.session_state.get('current_year', '2024')}-12-31"
            })
        if supabase:
            supabase.table("esg_data_entries").insert(entries).execute()
            st.toast("Uploaded records successfully.")
            st.session_state['s4_batch_list'] = []
            
def save_g1_direct():
    code = st.session_state.get('widget_g1_corruption', 'No formal policy') 
    whistle = st.session_state.get('widget_g1_whistle', 'None')
    lobby = st.session_state.get('widget_g1_lobby', 'No political contributions')
    
    note = f"Corruption Policy: {code} | Whistleblowing: {whistle} | Lobbying: {lobby}"
    current_company = st.session_state.get('current_company_id', '')
    
    if current_company:
        entry = {
            "company": current_company,
            "fuel_type": "G1: Business Conduct",
            "value_raw": 0,
            "co2_kg": 0,
            "type": "Governance",
            "esrs_tag": "ESRS-G1",
            "description": note,
            "methodology": "Management Disclosure",
            "date_of_service": f"{st.session_state.get('current_year', '2024')}-12-31"
        }
        if supabase:
            supabase.table("esg_data_entries").insert([entry]).execute()
            st.session_state['g1_step_complete'] = True
            st.toast("Data uploaded successfully.")
            
def save_g2_direct():
    resp = st.session_state.get('widget_g2_resp', 'None')
    risk = st.session_state.get('widget_g2_risk', 'No')
    
    note = f"ESG Responsibility: {resp} | Risk Mgmt Integration: {risk}"
    current_company = st.session_state.get('current_company_id', '')
    
    if current_company:
        entry = {
            "company": current_company,
            "fuel_type": "G2: Management & Strategy",
            "value_raw": 0,
            "co2_kg": 0,
            "type": "Governance",
            "esrs_tag": "ESRS-G2",
            "description": note,
            "methodology": "Management Disclosure",
            "date_of_service": f"{st.session_state.get('current_year', '2024')}-12-31"
        }
        if supabase:
            supabase.table("esg_data_entries").insert([entry]).execute()
            st.session_state['g2_step_complete'] = True
            st.toast("Data uploaded successfully.")
            
def save_g3_direct():
    pay_terms = st.session_state.get('widget_g3_pay', 'None')
    local_suppliers = st.session_state.get('widget_g3_local', '0%')
    
    note = f"Standard Payment Terms: {pay_terms} | Local Sourcing: {local_suppliers}"
    current_company = st.session_state.get('current_company_id', '')
    
    if current_company:
        entry = {
            "company": current_company,
            "fuel_type": "G3: Supplier Relations",
            "value_raw": 0,
            "co2_kg": 0,
            "type": "Governance",
            "esrs_tag": "ESRS-G1-6", 
            "description": note,
            "methodology": "Management Disclosure",
            "date_of_service": f"{st.session_state.get('current_year', '2024')}-12-31"
        }
        if supabase:
            supabase.table("esg_data_entries").insert([entry]).execute()
            st.session_state['g3_step_complete'] = True
            st.toast("Data uploaded successfully.")
            
# --- PDF GENERATOR ---
from fpdf import FPDF

# Kleine Hilfsklasse für automatische Seitenzahlen
class ESG_PDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

def generate_audit_pdf(company, year, report_text, df, country="Austria", gauge_img=None, bar_img=None, risk_img=None, star_rating=0.0):
    from datetime import datetime
    import os
    current_date = datetime.now().strftime("%d.%m.%Y")
    
    # Wir rufen jetzt unsere neue Klasse (ESG_PDF) auf
    pdf = ESG_PDF(orientation='P')
    pdf.set_margins(left=20, top=20, right=20)
    pdf.add_page()
    
    def clean(text):
        if not isinstance(text, str):
            text = str(text)
        
        # Waehrungen und Bullets
        text = text.replace('€', 'EUR').replace('•', '-').replace('–', '-')
        # Markdown Markierungen
        text = text.replace('**', '') 
        
        # NEU: Typografische Apostrophe und Anfuehrungszeichen in Standard-Zeichen umwandeln
        text = text.replace('’', "'").replace('‘', "'").replace('´', "'").replace('`', "'")
        text = text.replace('“', '"').replace('”', '"')
        
        return text.encode('latin-1', 'replace').decode('latin-1')

    # --- ABCo Style Header ---
    pdf.set_font("Arial", '', 20)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(100, 10, "CSRD Audit Report:", ln=False, align='L')
    
    pdf.set_font("Arial", 'B', 24)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 10, clean(company), ln=True, align='R')
    
    pdf.set_font("Arial", '', 10)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(100, 8, clean(f"Reporting Year: {year}  |  Country: {country}"), ln=False, align='L')
    pdf.cell(0, 8, clean(f"Generated on: {current_date}"), ln=True, align='R')
    pdf.ln(4)
    
    # --- Faktenbasiertes 5-Punkte-Rating ---
    pdf.set_font("Arial", 'B', 12)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(0, 8, "Corporate Sustainability Rating", ln=True)
    
    y_pos = pdf.get_y() + 2
    for i in range(1, 6):
        if i <= round(star_rating):
            pdf.set_fill_color(2, 52, 37)
            pdf.rect(20 + (i-1)*9, y_pos, 7, 7, 'F')
        else:
            pdf.set_draw_color(200, 200, 200)
            pdf.set_fill_color(245, 245, 245)
            pdf.rect(20 + (i-1)*9, y_pos, 7, 7, 'FD')
            
    pdf.set_xy(70, y_pos)
    pdf.set_font("Arial", 'B', 14)
    pdf.set_text_color(2, 52, 37)
    pdf.cell(25, 7, f"{star_rating:.1f} / 5.0", ln=False)
    
    pdf.set_font("Arial", 'I', 9)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 7, "Derived from Industry Benchmark, Policies & Data Readiness", ln=True)
    pdf.ln(6)
    
    pdf.set_draw_color(220, 220, 220)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(6)
    
    # --- Grafiken & Neues 3-Spalten Erklärungs-Layout ---
    if gauge_img and risk_img and bar_img and os.path.exists(gauge_img):
        y_pos = pdf.get_y() + 5
        pdf.image(gauge_img, x=15, y=y_pos, w=85)
        pdf.image(risk_img, x=15, y=y_pos + 45, w=85)
        pdf.image(bar_img, x=105, y=y_pos, w=90)
        pdf.ln(95) 
        
        # 3 Spalten Überschriften
        pdf.set_font("Arial", 'B', 10)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(56, 6, "CS Rating:", ln=False)
        pdf.cell(56, 6, "ESG Risk Score:", ln=False)
        pdf.cell(56, 6, "Carbon Footprint:", ln=True)
        
        # 3 Spalten Texte
        pdf.set_font("Arial", '', 9)
        pdf.set_text_color(100, 100, 100)
        x_start = pdf.get_x()
        y_start = pdf.get_y()
        
        pdf.multi_cell(52, 5, "A composite 5-point score reflecting overall ESG maturity, integrating your risk profile and data quality.", align='L')
        pdf.set_xy(x_start + 56, y_start)
        pdf.multi_cell(52, 5, "Compares your firm to the industry average (vertical line). Lower values indicate better risk management.", align='L')
        pdf.set_xy(x_start + 112, y_start)
        pdf.multi_cell(52, 5, "Emissions categorized by Scopes: Direct (1), Energy (2), and Value Chain (3).", align='L')
        
        pdf.ln(6)
        pdf.set_draw_color(220, 220, 220)
        pdf.line(20, pdf.get_y(), 190, pdf.get_y())
        pdf.ln(6)
    else:
        pdf.ln(5)
        
    pdf.set_text_color(0, 0, 0)
        
    # Text Parsen
    for line in report_text.split('\n'):
        line = line.strip()
        if not line:
            pdf.ln(4)
            continue
            
        if line.startswith('## '):
            heading_text = line.replace('## 0.', '').replace('## 1.', '').replace('## 2.', '').replace('## 3.', '').replace('## ', '').strip()
            
            # --- NEU: Zwingt jede Hauptüberschrift auf eine neue Seite! ---
            pdf.add_page()
            
            pdf.set_font("Arial", 'B', 16)
            pdf.set_text_color(2, 52, 37)
            pdf.cell(0, 10, clean(heading_text), ln=True)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(4)
            
        elif line.startswith('#') or (line.startswith('**') and line.endswith('**')):
            subheading_text = line.replace('#', '').replace('**', '').strip()
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 8, clean(subheading_text), ln=True)
            pdf.set_font("Arial", '', 11)
            pdf.ln(2)
            
        else:
            pdf.set_font("Arial", '', 11)
            pdf.multi_cell(0, 6, txt=clean(line))
    
    # Auditor Index
    pdf.add_page(orientation='L')
    pdf.set_font("Arial", 'B', 14)
    pdf.set_text_color(2, 52, 37)
    pdf.cell(0, 10, "Auditor Index: Certified ESG Data & Evidence", ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)
    
    pdf.set_font("Arial", 'B', 9)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(25, 8, "ESRS Tag", 1, 0, 'L', 1)
    pdf.cell(55, 8, "Category / Source", 1, 0, 'L', 1)
    pdf.cell(20, 8, "Value", 1, 0, 'R', 1)
    pdf.cell(20, 8, "CO2 (kg)", 1, 0, 'R', 1)
    pdf.cell(115, 8, "Context / Notes", 1, 0, 'L', 1) 
    pdf.cell(22, 8, "Evidence", 1, 1, 'C', 1)
    
    total_val = 0.0
    total_co2 = 0.0
    
    pdf.set_font("Arial", size=8)
    for index, row in df.iterrows():
        tag = clean(str(row.get('esrs_tag', ''))[:15])
        cat = clean(str(row.get('fuel_type', ''))[:35])
        
        try:
            raw_val = float(row.get('value_raw', 0))
            raw_co2 = float(row.get('co2_kg', 0))
        except:
            raw_val = 0.0
            raw_co2 = 0.0
            
        total_val += raw_val
        total_co2 += raw_co2
        
        val = clean(f"{raw_val:.1f}")
        co2 = clean(f"{raw_co2:.1f}")
        
        desc_val = str(row.get('description', ''))
        url = ""
        note_text = desc_val
        if " | Evidence: " in desc_val:
            parts = desc_val.split(" | Evidence: ")
            note_text = parts[0]
            if len(parts) > 1:
                url = parts[1].strip()
        elif "Evidence: " in desc_val:
            parts = desc_val.split("Evidence: ")
            note_text = parts[0]
            if len(parts) > 1:
                url = parts[1].strip()

        note_text = clean(note_text[:85]) 
        
        pdf.cell(25, 8, tag, 1)
        pdf.cell(55, 8, cat, 1)
        pdf.cell(20, 8, val, 1, 0, 'R')
        pdf.cell(20, 8, co2, 1, 0, 'R')
        pdf.cell(115, 8, note_text, 1, 0, 'L')
        
        if url:
            pdf.set_text_color(0, 0, 255) 
            pdf.cell(22, 8, "View Doc", 1, 1, 'C', link=url)
            pdf.set_text_color(0, 0, 0)   
        else:
            pdf.cell(22, 8, "N/A", 1, 1, 'C')
            
    pdf.set_font("Arial", 'B', 9)
    pdf.set_fill_color(2, 52, 37)
    pdf.set_text_color(255, 255, 255)
    
    pdf.cell(80, 8, "SUMMARY (TOTALS)", 1, 0, 'R', 1) 
    pdf.cell(20, 8, f"{total_val:.1f}", 1, 0, 'R', 1)
    pdf.cell(20, 8, f"{total_co2:.1f}", 1, 0, 'R', 1)
    pdf.cell(137, 8, "", 1, 1, 'L', 1) 
    
    pdf.set_text_color(0, 0, 0)
    
    return pdf.output(dest='S').encode('latin-1')
if 'user' not in st.session_state:
    st.markdown("# Ready for ESG")
    st.markdown("### Your expert tool for simplified ESG reporting.")
    st.markdown("---")

    tab_login, tab_register = st.tabs(["Login", "Register"])

    with tab_login:
        with st.form("login_form"):
            st.markdown("**Login to your account**")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", type="primary", use_container_width=True)
            if submitted:
                result = login(email, password)
                if result == "success":
                    st.rerun()
                elif result == "mfa_required":
                    st.session_state['show_mfa'] = True
                    st.rerun()

    if st.session_state.get('show_mfa'):
        with st.form("mfa_form"):
            st.markdown("**Two-Factor Authentication**")
            st.caption("Enter the 6-digit code from your authenticator app.")
            totp_code = st.text_input("Authentication Code", max_chars=6, placeholder="123456")
            submitted_mfa = st.form_submit_button("Verify", type="primary", use_container_width=True)
            if submitted_mfa:
                if verify_mfa(totp_code):
                    st.session_state.pop('show_mfa', None)
                    st.rerun()

    with tab_register:
        with st.form("register_form"):
            st.markdown("**Create a new account**")
            reg_email = st.text_input("Email")
            reg_password = st.text_input("Password", type="password")
            reg_password2 = st.text_input("Confirm Password", type="password")
            reg_company = st.text_input("Company Name", placeholder="e.g. Muster GmbH")
            submitted = st.form_submit_button("Create Account", type="primary", use_container_width=True)
            if submitted:
                if reg_password != reg_password2:
                    st.error("Passwords do not match.")
                elif len(reg_password) < 6:
                    st.error("Password must be at least 6 characters.")
                elif not reg_company:
                    st.error("Please enter your company name.")
                else:
                    if register(reg_email, reg_password, reg_company):
                        st.success("Account created! Please check your email to confirm.")
    st.stop()
# --- SUBSCRIPTION CHECK ---
# Dieser Block kommt direkt nach dem st.stop() beim Login,
# also nach der Zeile: st.stop()
# und VOR der Sidebar (# --- SIDEBAR ---)

def check_subscription(user_id: str) -> dict | None:
    """Gibt die Subscription zurueck wenn aktiv, sonst None."""
    try:
        from datetime import datetime, timezone
        response = supabase.table("subscriptions").select("*").eq("user_id", user_id).execute()
        subs = response.data
        if not subs:
            return None
        for sub in subs:
            if sub.get("status") == "active":
                expires = sub.get("expires_at")
                if expires:
                    expires_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                    if expires_dt > datetime.now(timezone.utc):
                        return sub
                else:
                    # Kein Ablaufdatum = dauerhaft aktiv
                    return sub
        return None
    except Exception as e:
        st.error(f"Subscription check failed: {e}")
        return None

# Subscription pruefen
user_id = st.session_state['user'].id
subscription = check_subscription(user_id)

if subscription is None:
    # --- KEIN ZUGANG: Request Access Seite ---
    st.markdown("# Ready for ESG")
    st.markdown("---")

    col1, col2 = st.columns([3, 2])

    with col1:
        st.markdown("### Ihr Zugang ist noch nicht aktiv.")
        st.markdown("""
        Vielen Dank fuer Ihre Registrierung!
        
        Um die App nutzen zu koennen, benoetigen Sie eine aktive Lizenz.
        Bitte kontaktieren Sie uns um Ihren Zugang freizuschalten.
        """)

        with st.container(border=True):
            st.markdown("**Pakete & Preise**")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("**ESG Ready**")
                st.markdown("1.099 EUR / Jahr")
                st.caption("Software + KI-Bericht")
            with c2:
                st.markdown("**ESG Certified**")
                st.markdown("1.799 EUR / Jahr")
                st.caption("+ Beratung & Bestaetigung")
            with c3:
                st.markdown("**ESG Partner**")
                st.markdown("3.299 EUR / Jahr")
                st.caption("+ Strategie & Begleitung")

        st.markdown("---")
        st.markdown("**Kontakt aufnehmen:**")
        st.markdown("info@readyforesg.com")
        st.markdown("[Zur Website](https://readyforesg.com)")

    with col2:
        with st.container(border=True):
            st.markdown("**Zugang anfragen**")
            with st.form("request_access_form"):
                req_name = st.text_input("Ihr Name")
                req_company = st.text_input("Unternehmen")
                req_plan = st.selectbox("Gewuenschtes Paket", [
                    "ESG Ready (1.099 EUR)",
                    "ESG Certified (1.799 EUR)",
                    "ESG Partner (3.299 EUR)",
                    "Erstgespraech (kostenlos)"
                ])
                req_message = st.text_area("Nachricht (optional)", height=100)
                submitted = st.form_submit_button("Anfrage senden", type="primary", use_container_width=True)

                if submitted:
                    if not req_name or not req_company:
                        st.error("Bitte Name und Unternehmen angeben.")
                    else:
                        try:
                            user_email = st.session_state['user'].email
                            supabase.table("subscriptions").insert({
                                "user_id": user_id,
                                "email": user_email,
                                "status": "pending",
                                "plan": req_plan,
                            }).execute()
                            st.success("Anfrage gesendet! Wir melden uns innerhalb von 24 Stunden.")
                        except Exception as e:
                            st.error(f"Fehler: {e}")

    if st.button("Logout", key="logout_no_sub"):
        logout()

    st.stop()

# Ab hier laeuft die normale App (Subscription ist aktiv)
# --- SIDEBAR ---
# --- SIDEBAR ---
with st.sidebar:
    st.markdown("""
        <style>
        [data-testid="stSidebarHeader"] {
            display: none !important;
        }
        
        [data-testid="stSidebarUserContent"] {
            padding-top: 0rem !important;
        }

        [data-testid="stSidebar"] [data-testid="stImage"] {
            display: flex;
            justify-content: flex-start !important;
            margin-top: -5px !important;  
            margin-left: -65px !important; 
            margin-bottom: 10px !important; 
        }

        </style>
    """, unsafe_allow_html=True)
    
    st.image("logo2.svg", width=200)
    st.caption(f"{st.session_state['user'].email}")
    if st.button("Logout"):
        logout()

    st.header("Ready for ESG")
    st.markdown("### Client Mandate")
    
    st.markdown("**Start Here**")
    with st.container(border=True):
       if 'current_company_id' not in st.session_state:
        user_meta = st.session_state['user'].user_metadata or {}
        default_company = user_meta.get('company_name', '')
        st.session_state['current_company_id'] = default_company

        company_name = st.text_input("Company Name / ID", placeholder="Enter Name...", key="current_company_id")

        # NEU: Das Reporting-Jahr
        reporting_year = st.selectbox("Reporting Year", ["2023", "2024", "2025", "2026"], index=1, key="current_year")

        from datetime import datetime
        current_year = str(datetime.now().year)
        if reporting_year != current_year:
            st.warning(f"Achtung: Sie berichten fuer {reporting_year}, das aktuelle Jahr ist {current_year}.")
        
        # --- NEU: Profil aus Datenbank laden ---
        if company_name:
            if st.session_state.get('loaded_company') != company_name or st.session_state.get('loaded_year') != reporting_year:
                import json
                if supabase:
                    try:
                        resp = supabase.table("esg_data_entries").select("*").eq("company", company_name).eq("type", "Company Setup").execute()
                        profiles = resp.data
                        if profiles:
                            current_year_profile = next((p for p in profiles if str(reporting_year) in str(p.get('date_of_service', ''))), None)
                            if current_year_profile:
                                prof = json.loads(current_year_profile['description'])
                                st.session_state['company_industry'] = prof.get('industry', 'Services / Office')
                                st.session_state['company_size'] = prof.get('size', 'Medium (50 - 249 employees)')
                                st.session_state['setup_footprint'] = prof.get('footprint', 'Office / Remote only')
                                st.session_state['hq_country'] = prof.get('hq_country', 'Austria')
                                st.session_state['other_countries'] = prof.get('other_countries', [])
                                st.session_state['company_description_raw'] = prof.get('description', '')
                                st.session_state['company_description'] = f"{prof.get('description', '')} (Operations Type: {prof.get('footprint', '')})"
                                st.session_state['material_topics'] = prof.get('material_topics', [])
                                st.session_state['company_setup_complete'] = True
                                st.session_state['setup_needs_review'] = False
                            else:
                                latest_profile = sorted(profiles, key=lambda x: x['date_of_service'], reverse=True)[0]
                                prof = json.loads(latest_profile['description'])
                                st.session_state['company_industry'] = prof.get('industry', 'Services / Office')
                                st.session_state['company_size'] = prof.get('size', 'Medium (50 - 249 employees)')
                                st.session_state['setup_footprint'] = prof.get('footprint', 'Office / Remote only')
                                st.session_state['hq_country'] = prof.get('hq_country', 'Austria')
                                st.session_state['other_countries'] = prof.get('other_countries', [])
                                st.session_state['company_description_raw'] = prof.get('description', '')
                                st.session_state['company_description'] = f"{prof.get('description', '')} (Operations Type: {prof.get('footprint', '')})"
                                st.session_state['material_topics'] = prof.get('material_topics', [])
                                st.session_state['company_setup_complete'] = False
                                st.session_state['setup_needs_review'] = True
                        else:
                            st.session_state['company_setup_complete'] = False
                            st.session_state['setup_needs_review'] = False
                    except Exception as e:
                        pass
                st.session_state['loaded_company'] = company_name
                st.session_state['loaded_year'] = reporting_year
        # --------------------------------------

    st.markdown("---")
    
    menu = st.radio("Main Menu", ["Dashboard", "Data Entry Center", "Document Portal", "Reports", "Settings"])
    
    if menu == "Data Entry Center":
        st.markdown("---")
        if st.button("Reset Wizard"):
            st.session_state['entry_stage'] = 'main'
            
            st.session_state['e1_batch_list'] = []
            st.session_state['e1_2_batch_list'] = []
            st.session_state['e2_batch_list'] = []
            st.session_state['e3_batch_list'] = []
            st.session_state['e4_batch_list'] = []
            st.session_state['e5_batch_list'] = []
            st.session_state['e6_batch_list'] = []        
            st.session_state['e_water_batch_list'] = []
            st.session_state['e_bio_batch_list'] = []
            st.session_state['s1_batch_list'] = []
            st.session_state['s1_2_batch_list'] = []
            st.session_state['s1_3_batch_list'] = []
            st.session_state['s1_4_batch_list'] = []
            st.session_state['s2_batch_list'] = []
            st.session_state['s3_batch_list'] = []
            st.session_state['s4_batch_list'] = []
            
            st.session_state['e1_step_complete'] = False
            st.session_state['e1_2_step_complete'] = False
            st.session_state['e2_step_complete'] = False
            st.session_state['e3_step_complete'] = False
            st.session_state['e4_step_complete'] = False
            st.session_state['e5_step_complete'] = False
            st.session_state['e6_step_complete'] = False 
            st.session_state['e_water_step_complete'] = False
            st.session_state['e_bio_step_complete'] = False
            st.session_state['s1_step_complete'] = False
            st.session_state['s1_2_step_complete'] = False
            st.session_state['s1_3_step_complete'] = False
            st.session_state['s1_4_step_complete'] = False
            st.session_state['s2_step_complete'] = False
            st.session_state['s3_step_complete'] = False
            st.session_state['s4_step_complete'] = False

            st.rerun()

# --- MAIN APP ---

if not company_name:
    
    st.markdown("<br>", unsafe_allow_html=True) 
    st.markdown("# Welcome to 'Ready for ESG'")
    st.markdown("### Your expert tool for simplified ESG reporting.")
    
    st.markdown("""
    This software is designed to help you generate your **Environment, Social, and Governance (ESG)** report 
    with ease and precision.
    """)
    
    c1, c2 = st.columns(2)
    with c1:
        st.container(border=True).markdown("""
        **Expert Verification** Developed with the help of environmental management experts to ensure data accuracy.
        """, unsafe_allow_html=True)
    with c2:
        st.container(border=True).markdown("""
        **EU Compliance** Follows highest industry standards and EU directives (CSRD / ESRS).
        """, unsafe_allow_html=True)
        
    st.info("To proceed, please enter your Organization Name in the sidebar.")
    st.stop()

if menu == "Dashboard":
    st.subheader(f"Executive ESG Scorecard: {company_name}")
    st.markdown("High-level overview of your corporate sustainability performance.")
    
    rows = [] 
    
    if supabase is not None:
        try:
            response = supabase.table("esg_data_entries").select("*").eq("company", company_name).order('id', desc=True).execute()
            rows = response.data
        except Exception as e:
            st.error(f"Database error: {e}")
    else:
        st.warning("No database connection.")

    if rows:
        df = pd.DataFrame(rows)
        
        # --- DATEN-ANALYSE FÜR DIE SCORECARD ---
        total_co2_kg = df['co2_kg'].sum()
        total_co2_t = total_co2_kg / 1000
        
        # ESG Readiness Score berechnen (Echte Daten vs. Schätzungen)
        est_mask = df['fuel_type'].str.contains("ESTIMATE", case=False, na=False) | (df['type'] == 'Estimate')
        est_count = est_mask.sum()
        exact_count = len(df) - est_count
        quality_score = int((exact_count / len(df)) * 100) if len(df) > 0 else 0
        
        # Scopes berechnen (1, 2, 3)
        def get_scope(name):
            n = str(name).lower()
            if "scope 1" in n or "diesel" in n or "petrol" in n or "natural gas" in n: return "Scope 1"
            if "electricity" in n or "grid mix" in n or "heating (" in n or "district" in n: return "Scope 2"
            if "flight" in n or "train" in n or "hotel" in n or "commute" in n or "waste" in n or "water" in n: return "Scope 3"
            return "Other"

        df['Scope'] = df['fuel_type'].apply(get_scope)
        s1_co2 = df[df['Scope'] == 'Scope 1']['co2_kg'].sum() / 1000
        s2_co2 = df[df['Scope'] == 'Scope 2']['co2_kg'].sum() / 1000
        s3_co2 = df[df['Scope'] == 'Scope 3']['co2_kg'].sum() / 1000
        
        # --- 1. TOP LEVEL METRICS ---
        st.markdown("### 1. Overall ESG Performance")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Carbon Footprint", f"{total_co2_t:,.1f} t CO2e")
        c2.metric("Total Records Tracked", len(df))
        
        # Rote/Grüne Pfeile bei der Datenqualität
        score_color = "normal" if quality_score >= 80 else "inverse"
        c3.metric("Data Quality Score", f"{quality_score} / 100", "High Precision" if quality_score >= 80 else "Needs Exact Data", delta_color=score_color)
        
        esrs_tags_used = len(df['esrs_tag'].unique())
        c4.metric("ESRS Modules Active", f"{esrs_tags_used} Tags")
        
        st.markdown("---")
        
        # --- 2. VISUAL SCORECARDS (TACHOMETER & BALKEN) ---
        st.markdown("### 2. Carbon Risk & Data Coverage")
        col_g1, col_g2 = st.columns(2)

        with col_g1:
            with st.container(border=True):
                st.markdown("**Data Readiness (ESG Score)**")
                # Plotly Tachometer (Gauge) für den Score
                fig1 = go.Figure(go.Indicator(
                    mode = "gauge+number",
                    value = quality_score,
                    domain = {'x': [0, 1], 'y': [0, 1]},
                    title = {'text': "% Measured Data vs. Estimates", 'font': {'size': 14}},
                    gauge = {
                        'axis': {'range': [0, 100]},
                        'bar': {'color': "#023425"},
                        'steps': [
                            {'range': [0, 50], 'color': "#fca5a5"},   # Rot
                            {'range': [50, 80], 'color': "#fde047"},  # Gelb
                            {'range': [80, 100], 'color': "#86efac"}  # Grün
                        ]
                    }
                ))
                fig1.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=10))
                st.plotly_chart(fig1, use_container_width=True)

        with col_g2:
            with st.container(border=True):
                st.markdown("**Carbon Footprint by Scope (t CO2e)**")
                # Gestapeltes Balkendiagramm für die Scopes
                fig2 = go.Figure(data=[
                    go.Bar(name='Scope 1 (Direct)', x=['Scopes'], y=[s1_co2], marker_color='#023425'),
                    go.Bar(name='Scope 2 (Energy)', x=['Scopes'], y=[s2_co2], marker_color='#416852'),
                    go.Bar(name='Scope 3 (Value Chain)', x=['Scopes'], y=[s3_co2], marker_color='#86efac')
                ])
                fig2.update_layout(barmode='stack', height=250, margin=dict(l=20, r=20, t=40, b=10))
                st.plotly_chart(fig2, use_container_width=True)

        st.markdown("---")
        
        # --- 3. TARGETS & PROGRESS ---
        st.markdown("### 3. Corporate Sustainability Targets")
        with st.container(border=True):
            # Wir suchen, ob in Modul E6 ein Ziel definiert wurde
            targets = df[df['fuel_type'] == 'Strategy: Emission Targets']
            if not targets.empty:
                target_desc = targets.iloc[0]['description']
                st.markdown(f"**Current Active Target:** {target_desc}")
                # Visueller Fortschrittsbalken
                st.progress(15, text="Target Completion Progress (Estimated based on current vs baseline)")
            else:
                st.info("No emission targets defined yet. Go to Module E6 in the Data Entry Center to set your corporate targets.")

        st.markdown("---")
        
        # --- 4. AUDITOR INDEX & DATA TABLE (Eingeklappt) ---
        st.markdown("### 4. Data Management & Auditor Index")
        with st.expander("Click to View & Manage Raw Data Records"):
            st.markdown("Review your submitted records, verify ESRS tags, and remove incorrect entries.")
            
            if 'id' in df.columns:
                display_df = df[['id', 'esrs_tag', 'fuel_type', 'value_raw', 'co2_kg', 'type', 'description']].copy()
                display_df.columns = ['ID', 'ESRS Tag', 'Category / Source', 'Value', 'CO2 (kg)', 'Data Type', 'Description']
            else:
                display_df = df.copy() 
                
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # Delete Function
            st.markdown("#### Delete a Record")
            if 'id' in df.columns:
                c_del1, c_del2 = st.columns([3, 1])
                with c_del1:
                    record_options = {f"ID {row['id']} - {row['fuel_type']} (Value: {row['value_raw']})": row['id'] for index, row in df.iterrows()}
                    selected_record_display = st.selectbox("Select record to delete", options=list(record_options.keys()))
                
                with c_del2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("Delete Record", type="primary", use_container_width=True):
                        record_id_to_delete = record_options[selected_record_display]
                        try:
                            supabase.table("esg_data_entries").delete().eq("id", record_id_to_delete).execute()
                            st.success(f"Record ID {record_id_to_delete} deleted successfully.")
                            time.sleep(1)
                            st.rerun()  
                        except Exception as e:
                            st.error(f"Failed to delete record: {e}")
            else:
                st.info("Delete function requires an 'id' column in the database.")
    else:
        st.info("No data found. Please enter data in the 'Data Entry Center'.")

elif menu == "Data Entry Center":
    
    # Zwangs-Weiterleitung zum Setup
    if not st.session_state.get('company_setup_complete', False) and st.session_state.get('entry_stage', 'main') == 'main':
        if st.session_state.get('setup_needs_review', False):
            st.session_state['entry_stage'] = 'review_setup'
        else:
            st.session_state['entry_stage'] = 'company_setup'

    if st.session_state['entry_stage'] == 'review_setup':
        st.header(f"Welcome back! Setting up {st.session_state.get('current_year')}")
        st.info("We found your company profile from a previous reporting year. Do you want to reuse it, or has your company structure changed?")
        
        with st.container(border=True):
            st.markdown(f"**Current Profile:** {st.session_state.get('company_industry')} | {st.session_state.get('company_size')} | HQ: {st.session_state.get('hq_country')}")
            
            c1, c2 = st.columns(2)
            if c1.button("No changes, use existing profile", type="primary", use_container_width=True):
                import json
                prof = {
                    "industry": st.session_state.get('company_industry'),
                    "size": st.session_state.get('company_size'),
                    "footprint": st.session_state.get('setup_footprint'),
                    "hq_country": st.session_state.get('hq_country'),
                    "other_countries": st.session_state.get('other_countries'),
                    "description": st.session_state.get('company_description_raw'),
                    "material_topics": st.session_state.get('material_topics')
                }
                entry = {
                    "company": st.session_state.get('current_company_id'),
                    "fuel_type": "Profile Data",
                    "value_raw": 0, "co2_kg": 0,
                    "type": "Company Setup",
                    "esrs_tag": "SETUP",
                    "description": json.dumps(prof),
                    "methodology": "System",
                    "date_of_service": f"{st.session_state.get('current_year')}-01-01"
                }
                if supabase:
                    supabase.table("esg_data_entries").insert([entry]).execute()
                
                st.session_state['company_setup_complete'] = True
                st.session_state['setup_needs_review'] = False
                st.session_state['entry_stage'] = 'main'
                st.rerun()
                
            if c2.button("Yes, let me update my profile", use_container_width=True):
                st.session_state['entry_stage'] = 'company_setup'
                st.rerun()

    elif st.session_state['entry_stage'] == 'company_setup':
        st.header("Step 1: Company Profile & Materiality Assessment")
        st.markdown("Describe your business. We use this to determine your material ESG topics and generate the 'Business Model' chapter.")
        
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                ind_opts = ["Services / Office", "IT / Software", "Manufacturing / Production", "Logistics / Transport", "Retail / Wholesale", "Construction / Real Estate", "Agriculture / Food", "Other"]
                def_ind = st.session_state.get('company_industry', "Services / Office")
                ind = st.selectbox("Primary Industry", ind_opts, index=ind_opts.index(def_ind) if def_ind in ind_opts else 0)
            with c2:
                size_opts = ["Micro (< 10 employees)", "Small (10 - 49 employees)", "Medium (50 - 249 employees)", "Large (250+ employees)"]
                def_size = st.session_state.get('company_size', "Medium (50 - 249 employees)")
                size = st.selectbox("Company Size", size_opts, index=size_opts.index(def_size) if def_size in size_opts else 2)
            with c3:
                foot_opts = ["Office / Remote only", "Includes Warehouses / Light Facilities", "Heavy Industry / Factories / Construction Sites"]
                def_foot = st.session_state.get('setup_footprint', "Office / Remote only")
                footprint = st.selectbox("Physical Footprint (Operations)", foot_opts, index=foot_opts.index(def_foot) if def_foot in foot_opts else 0)
            
            st.markdown("---")
            st.markdown("**Locations & Operations Setup**")
            
            hq_opts = ["Germany", "Austria", "Switzerland", "France", "Italy", "Spain", "Netherlands", "Belgium", "Sweden", "Denmark", "Poland", "Ireland", "Other EU Member State", "United Kingdom", "USA", "Canada", "Singapore", "Japan", "Hong Kong", "Australia", "Other"]
            def_hq = st.session_state.get('hq_country', "Austria")
            hq_country = st.selectbox("Headquarters (Main Country)", hq_opts, index=hq_opts.index(def_hq) if def_hq in hq_opts else 1, key="setup_hq")
            
            st.markdown("**Secondary Locations / Supply Chain (Optional)**")
            is_global = st.checkbox("Global / Worldwide Operations", key="setup_global")
            
            # Die neuen, spezifischen Regionen
            regions = {
                "Europe": ["Germany", "Austria", "Switzerland", "France", "Italy", "Spain", "Netherlands", "Poland", "UK", "Sweden", "Denmark", "Ireland", "Czechia", "Hungary"],
                "South East Asia": ["Singapore", "Vietnam", "Indonesia", "Malaysia", "Thailand", "Philippines"],
                "Northern & East Asia": ["China", "Japan", "South Korea", "Taiwan", "Hong Kong"],
                "Middle East": ["UAE", "Saudi Arabia", "Qatar", "Israel", "Turkey"],
                "North & Middle America": ["USA", "Canada", "Mexico", "Costa Rica", "Panama"],
                "South America": ["Brazil", "Argentina", "Chile", "Colombia"],
                "Africa": ["South Africa", "Nigeria", "Egypt", "Kenya", "Morocco"]
            }
            
            other_countries = []
            
            if is_global:
                st.caption("All regions are selected by default. Uncheck a region or remove individual countries by clicking the 'x'.")
                c_reg1, c_reg2 = st.columns(2) 
                
                for i, (region, countries) in enumerate(regions.items()):
                    col = c_reg1 if i % 2 == 0 else c_reg2
                    with col:
                        # Bei Global ist standardmäßig alles angehakt
                        if st.checkbox(f"All of {region}", value=True, key=f"chk_glob_{region}"):
                            selected = st.multiselect(f"Countries in {region}", options=countries, default=countries, key=f"ms_glob_{region}", label_visibility="collapsed")
                            other_countries.extend(selected)
            else:
                st.caption("Select specific regions to add their respective countries:")
                c_reg1, c_reg2 = st.columns(2)
                
                for i, (region, countries) in enumerate(regions.items()):
                    col = c_reg1 if i % 2 == 0 else c_reg2
                    with col:
                        # Hier ist standardmäßig NICHTS angehakt
                        if st.checkbox(region, value=False, key=f"chk_{region}"):
                            # Wenn angehakt, klappt das Feld auf (Länder sind vorausgewählt, können aber per 'x' gelöscht werden)
                            selected = st.multiselect(f"Countries in {region}", options=countries, default=countries, key=f"ms_{region}", label_visibility="collapsed")
                            other_countries.extend(selected)
            
            st.markdown("---")
            # --- ENDE DER NEUEN LÄNDER-LOGIK ---
            
            desc = st.text_area("Brief Company Description (Value Chain, Products, Services)", value=st.session_state.get('company_description_raw', ''), placeholder="e.g. We are a mid-sized software company developing B2B SaaS solutions...", height=100)
            
            st.markdown("---")
            st.markdown("**Double Materiality Assessment (Doppelte Wesentlichkeit)**")
            
            defaults = ["E1: Climate Change (Energy & Fleet)", "S1: Own Workforce", "G1-G3: Governance & Conduct"]
            if ind == "Manufacturing / Production":
                defaults.extend(["E2: Pollution", "E5: Waste & Circular Economy", "S2: Value Chain Workers"])
            elif ind == "Construction / Real Estate":
                defaults.extend(["E2: Pollution", "E3: Water", "E4: Biodiversity", "E5: Waste & Circular Economy", "S2: Value Chain Workers"])
            elif ind == "Logistics / Transport":
                defaults.extend(["E2: Pollution", "S2: Value Chain Workers", "S3: Affected Communities"])
            elif ind == "Agriculture / Food":
                defaults.extend(["E2: Pollution", "E3: Water", "E4: Biodiversity", "S2: Value Chain Workers"])
            elif ind == "Retail / Wholesale":
                defaults.extend(["E5: Waste & Circular Economy", "S2: Value Chain Workers", "S4: Consumers"])
            elif ind == "IT / Software":
                defaults.extend(["S4: Consumers"])
                
            if footprint == "Heavy Industry / Factories / Construction Sites":
                if "E3: Water" not in defaults: defaults.append("E3: Water")
                if "E5: Waste & Circular Economy" not in defaults: defaults.append("E5: Waste & Circular Economy")
                if "S3: Affected Communities" not in defaults: defaults.append("S3: Affected Communities")
            
            defaults = list(dict.fromkeys(defaults))
            
            st.info("**Smart Setup:** Based on your Industry and Footprint, we have pre-selected the ESG topics that are highly likely to be material (wesentlich) for your business. You can add or remove topics manually.")
            
            # --- FIX: Verhindert, dass eine leere Liste die smarten Vorschläge blockiert ---
            saved_topics = st.session_state.get('material_topics', [])
            active_defaults = saved_topics if len(saved_topics) > 0 else defaults
            
            mat_topics = st.multiselect(
                "Material ESG Topics",
                ["E1: Climate Change (Energy & Fleet)", "E2: Pollution", "E3: Water", "E4: Biodiversity", "E5: Waste & Circular Economy", "S1: Own Workforce", "S2: Value Chain Workers", "S3: Affected Communities", "S4: Consumers", "G1-G3: Governance & Conduct"],
                default=active_defaults
            )
            
            if st.button("Save Profile & Proceed to Data Entry", type="primary", use_container_width=True):
                if len(desc) < 20:
                    st.warning("Please provide a meaningful description of your company (at least 20 characters).")
                else:
                    st.session_state['company_industry'] = ind
                    st.session_state['company_size'] = size
                    st.session_state['setup_footprint'] = footprint
                    st.session_state['hq_country'] = hq_country
                    st.session_state['other_countries'] = other_countries
                    st.session_state['company_description_raw'] = desc
                    st.session_state['company_description'] = f"{desc} (Operations Type: {footprint})"
                    st.session_state['material_topics'] = mat_topics
                    st.session_state['company_setup_complete'] = True
                    st.session_state['setup_needs_review'] = False
                    
                    import json
                    prof = {
                        "industry": ind,
                        "size": size,
                        "footprint": footprint,
                        "hq_country": hq_country,
                        "other_countries": other_countries,
                        "description": desc,
                        "material_topics": mat_topics
                    }
                    entry = {
                        "company": st.session_state.get('current_company_id'),
                        "fuel_type": "Profile Data",
                        "value_raw": 0, "co2_kg": 0,
                        "type": "Company Setup",
                        "esrs_tag": "SETUP",
                        "description": json.dumps(prof),
                        "methodology": "System",
                        "date_of_service": f"{st.session_state.get('current_year')}-01-01"
                    }
                    if supabase:
                        supabase.table("esg_data_entries").delete().eq("company", st.session_state.get('current_company_id')).eq("type", "Company Setup").eq("date_of_service", f"{st.session_state.get('current_year')}-01-01").execute()
                        supabase.table("esg_data_entries").insert([entry]).execute()

                    st.session_state['entry_stage'] = 'main'
                    st.rerun()

    elif st.session_state['entry_stage'] == 'main':
        st.header("Data Collection Center")
        st.markdown("Sustainable reporting relies on three fundamental pillars. Select a pillar below to start.")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.container(border=True)
            st.success("### Environment")
            st.markdown("Climate change, energy, pollution. (Modules E1-E5)")
            if st.button("Select Environment"): 
                st.session_state['entry_stage'] = 'env_intro'
                st.rerun()
        with col2:
            st.container(border=True)
            st.warning("### Social")
            st.markdown("Employees, Workers, Communities. (Modules S1-S4)")
            if st.button("Select Social"): 
                st.session_state['entry_stage'] = 'soc_intro'
                st.rerun()
        with col3:
            st.container(border=True)
            st.info("### Governance") 
            st.markdown("Business Ethics, Management, Suppliers. (Modules G1-G3)")
            if st.button("Select Governance"): 
                st.session_state['entry_stage'] = 'gov_intro'
                st.rerun()

    elif st.session_state['entry_stage'] == 'env_intro':
        st.header("The Environmental Pillar")
        st.markdown("The environmental pillar focuses on how your company performs as a steward of nature.")
        
        with st.container(border=True):
            st.markdown("""
            **The 5 European Sustainability Reporting Standards (Environmental):**
            
            * **E1 Climate Change** (Energy, CO2 Emissions - Scope 1, 2, 3)
            * **E2 Pollution** (Air, Water, Soil micro-particles)
            * **E3 Water & Marine Resources** (Consumption, Grey water)
            * **E4 Biodiversity & Ecosystems** (Land use, invasive species)
            * **E5 Resource Use & Circular Economy** (Waste, Recycling, Plastic)
            """)
            
        st.divider()
        c1, c2 = st.columns([1,4])
        if c1.button("Back"): st.session_state['entry_stage'] = 'main'; st.rerun()
        if c2.button("Start Module E1: Energy Use", type="primary"): st.session_state['entry_stage'] = 'e1_intro'; st.rerun()

    elif st.session_state['entry_stage'] == 'e1_intro':
        st.header("Module E1: Purchased Energy (Scope 2)")
        
        # --- HIER WIRD DER BADGE ANGEZEIGT ---
        show_materiality_badge("E1")
        # -------------------------------------
        
        with st.container(border=True):
            st.markdown("""
            **Focus: Energy generated ELSEWHERE.**
            This module only covers energy products that you **purchase** from external utility providers.
            * **Electricity** (from the grid)
            * **District Heating / Cooling**
            *If you burn fuel yourself (e.g. Gas Boiler), add it to Module E2.*
            """, unsafe_allow_html=True)
        st.divider()
        c1, c2 = st.columns([1,4])
        if c1.button("Back"): st.session_state['entry_stage'] = 'env_intro'; st.rerun()
        if c2.button("Next: Module E1.1 (Electricity)", type="primary"): st.session_state['entry_stage'] = 'e1_form'; st.rerun()

    elif st.session_state['entry_stage'] == 'e1_form':
        st.subheader("E1.1 Electricity Consumption")
        st.markdown("Add all your buildings/meters to the list below. **Review and upload in batch.**")
        
        tab_exact, tab_estimate = st.tabs(["Exact Records (Bills)", "Estimation Calculator"])
        with tab_exact:
            with st.container(border=True):
                st.markdown("**Add Record**")
                c1, c2 = st.columns(2)
                with c1:
                    if 'widget_source' not in st.session_state: st.session_state['widget_source'] = "Grid Mix (National Average)"
                    st.selectbox("Energy Source", ["Grid Mix (National Average)", "Green Electricity (Renewable)", "Nuclear Power", "Coal / Fossil Mix"], key="widget_source")
                with c2:
                    if 'widget_kwh' not in st.session_state: st.session_state['widget_kwh'] = 0.0
                    st.number_input("Consumption (kWh)", min_value=0.0, step=100.0, key="widget_kwh")
                st.selectbox(
                    "Country / Grid Zone",
                    options=list(GRID_FACTORS.keys()),
                    key="widget_e1_country"
                )

                # Dynamischen Key initialisieren, falls noch nicht vorhanden
                if 'file_key_e1' not in st.session_state:
                    st.session_state['file_key_e1'] = str(uuid.uuid4())
                
                # Der Uploader verwendet nun den dynamischen Key
                st.file_uploader("Upload Invoice / Proof (PDF, JPG)", type=["pdf", "jpg", "png", "jpeg"], key=st.session_state['file_key_e1'])
                
                if 'widget_notes_exact' not in st.session_state: st.session_state['widget_notes_exact'] = ""
                st.text_input("Reference / Note", placeholder="e.g. Meter A", key="widget_notes_exact")
                
                st.button("Add to List", on_click=add_exact_to_batch, key="btn_add_e1", type="primary")
        with tab_estimate:
            st.warning("Only use this method if actual data is unavailable (Bills/Meters).")
            with st.container(border=True):
                st.markdown("**Add Estimate**")
                c1, c2 = st.columns(2)
                with c1:
                    if 'widget_n_buildings' not in st.session_state: st.session_state['widget_n_buildings'] = 1
                    st.number_input("Number of Buildings", min_value=1, key="widget_n_buildings")
                    if 'widget_area' not in st.session_state: st.session_state['widget_area'] = 100.0
                    st.number_input("Avg Area (sqm)", min_value=10.0, key="widget_area")
                with c2:
                    if 'widget_age' not in st.session_state: st.session_state['widget_age'] = "Standard (1980-2010)"
                    st.selectbox("Building Age", ["Old (Pre-1980)", "Standard (1980-2010)", "New (Post-2010)"], key="widget_age")
                    if 'widget_use' not in st.session_state: st.session_state['widget_use'] = "Office"
                    st.selectbox("Usage", ["Office", "Warehouse", "Production"], key="widget_use")
                st.selectbox(
                    "Country / Grid Zone",
                    options=list(GRID_FACTORS.keys()),
                    key="widget_e1_country_est"
                )    
                st.button("Calculate & Add to List", on_click=add_estimate_to_batch, key="btn_est_e1", type="primary")
        
        st.markdown("---")
        if st.session_state['e1_batch_list']:
            st.subheader("Review Data")
            df_batch = pd.DataFrame(st.session_state['e1_batch_list'])
            st.dataframe(df_batch[["source", "liters", "co2"]], use_container_width=True)
            c1, c2 = st.columns(2)
            c1.button("Remove Last", on_click=remove_last_e1, key="rm_e1")
            c2.button("Confirm & Upload", type="primary", on_click=upload_batch, key="up_e1")
        
        st.markdown("---")
        c1, c2 = st.columns([1, 4])
        if c1.button("Back", key="back_e1"): st.session_state['entry_stage'] = 'e1_intro'; st.rerun()
        if st.session_state['e1_step_complete']:
            if c2.button("Next: Module E1.2 (Heating)", type="primary", key="next_e1"):
                st.session_state['entry_stage'] = 'e1_2_intro'
                st.rerun()
        else:
            if c2.button("Skip / Not Applicable", key="skip_e1"):
                st.session_state['entry_stage'] = 'e1_2_intro'
                st.rerun()

    elif st.session_state['entry_stage'] == 'e1_2_intro':
        st.header("Module E1.2: District Heating & Cooling")
        st.markdown("""
        **Purchased Thermal Energy (Scope 2).**
        This module tracks energy that you buy in the form of Heat (Steam/Hot Water) or Cold via a network.
        Please check your source before proceeding:
        """)
        col1, col2 = st.columns(2)
        with col1:
            with st.container(border=True):
                st.info("**Heating Check**")
                st.markdown("* District Heating -> **Enter here.**\n* Own Boiler (Gas/Oil) -> **Module E2.**")
        with col2:
            with st.container(border=True):
                st.info("**Cooling Check**")
                st.markdown("* District Cooling -> **Enter here.**\n* AC (Electricity) -> **Module E1.1.**")
        st.divider()
        c1, c2 = st.columns([1,4])
        if c1.button("Back"): st.session_state['entry_stage'] = 'e1_form'; st.rerun()
        if c2.button("Next: Module E1.2 (Heating Form)", type="primary"): st.session_state['entry_stage'] = 'e1_2_form'; st.rerun()

    elif st.session_state['entry_stage'] == 'e1_2_form':
        st.subheader("E1.2 District Heating & Cooling")
        st.markdown("Add your heating contracts or estimate based on building insulation.")
        tab_exact, tab_estimate = st.tabs(["Exact Records (Bills)", "Estimation Calculator"])
        with tab_exact:
            with st.container(border=True):
                st.markdown("**Add Heating Record**")
                c1, c2 = st.columns(2)
                
                with c1:
                    if 'widget_h_source' not in st.session_state: st.session_state['widget_h_source'] = "District Heating (Standard Mix)"
                    st.selectbox("Source", ["District Heating (Standard Mix)", "District Heating (Green/Geothermal)", "District Cooling", "Steam (Purchased)"], key="widget_h_source")
                
                with c2:
                    if 'widget_h_kwh' not in st.session_state: st.session_state['widget_h_kwh'] = 0.0
                    st.number_input("Consumption (kWh)", min_value=0.0, step=100.0, key="widget_h_kwh")
                
                # --- NEU: File Uploader für Heizkostenabrechnungen ---
                if 'file_key_heat_exact' not in st.session_state:
                    st.session_state['file_key_heat_exact'] = str(uuid.uuid4())
                
                st.file_uploader("Upload Heating Bill (PDF, JPG)", type=["pdf", "jpg", "png", "jpeg"], key=st.session_state['file_key_heat_exact'])
                # -----------------------------------------------------
                
                if 'widget_h_notes' not in st.session_state: st.session_state['widget_h_notes'] = ""
                st.text_input("Reference", placeholder="e.g. Headquarters Heating", key="widget_h_notes")
                
                st.button("Add to List", on_click=add_heating_exact_to_batch, key="btn_add_e12", type="primary")
        with tab_estimate:
            st.warning("Only use this method if actual data is unavailable.")
            with st.container(border=True):
                st.markdown("**Add Heating Estimate**")
                c1, c2 = st.columns(2)
                with c1:
                    if 'widget_h_n' not in st.session_state: st.session_state['widget_h_n'] = 1
                    st.number_input("Number of Buildings", min_value=1, key="widget_h_n")
                    if 'widget_h_area' not in st.session_state: st.session_state['widget_h_area'] = 100.0
                    st.number_input("Avg Area (sqm)", min_value=10.0, key="widget_h_area")
                with c2:
                    if 'widget_h_insulation' not in st.session_state: st.session_state['widget_h_insulation'] = "Standard Insulation (1980-2015)"
                    st.selectbox("Insulation Quality", ["Poor Insulation (Pre-1980)", "Standard Insulation (1980-2015)", "High Efficiency (Post-2015/Renovated)"], key="widget_h_insulation")
                st.button("Calculate & Add to List", on_click=add_heating_estimate_to_batch, key="btn_est_e12", type="primary")
        
        st.markdown("---")
        if st.session_state['e1_2_batch_list']:
            st.subheader("Review Data")
            df_batch = pd.DataFrame(st.session_state['e1_2_batch_list'])
            st.dataframe(df_batch[["source", "liters", "co2"]], use_container_width=True)
            c1, c2 = st.columns(2)
            c1.button("Remove Last", on_click=remove_last_heating, key="rm_e12")
            c2.button("Confirm & Upload", type="primary", on_click=upload_heating_batch, key="up_e12")
        st.markdown("---")
        c1, c2 = st.columns([1, 4])
        if c1.button("Back", key="back_e12"): st.session_state['entry_stage'] = 'e1_2_intro'; st.rerun()
        if st.session_state['e1_2_step_complete']:
            if c2.button("Next: Module E2 (Scope 1)", type="primary", key="next_e12"):
                st.session_state['entry_stage'] = 'e2_intro'
                st.rerun()
        else:
            if c2.button("Skip / Not Applicable", key="skip_e12"):
                st.session_state['entry_stage'] = 'e2_intro'
                st.rerun()

    elif st.session_state['entry_stage'] == 'e2_intro':
        st.header("Module E2: Direct Emissions (Scope 1)")
        show_materiality_badge("E2")
        with st.container(border=True):
            st.markdown("""
            **Focus: Emissions generated ON-SITE.**
            This module covers emissions that happen physically **at your location** or inside your assets.
            * **Company Fleet** (Burning Diesel/Petrol in engines)
            * **Stationary Combustion** (Burning Gas/Oil in your own boilers)
            """, unsafe_allow_html=True)
        st.divider()
        c1, c2 = st.columns([1,4])
        if c1.button("Back"): st.session_state['entry_stage'] = 'e1_2_form'; st.rerun()
        if c2.button("Next: Module E2 (Form)", type="primary"): st.session_state['entry_stage'] = 'e2_form'; st.rerun()

    elif st.session_state['entry_stage'] == 'e2_form':
        st.subheader("E2 Scope 1: Direct Emissions")
        st.markdown("Add your fleet and heating fuels. **Review and upload in batch.**")
        
        tab_exact, tab_estimate = st.tabs(["Receipts (Liters/kWh)", "Distance Calculator (km)"])
        
        with tab_exact:
            with st.container(border=True):
                st.markdown("**Add Fuel Record**")
                c1, c2 = st.columns(2)
                
                with c1:
                    if 'widget_m_fuel' not in st.session_state: st.session_state['widget_m_fuel'] = "Diesel (B7)"
                    st.selectbox("Fuel Type", ["Diesel (B7)", "Petrol / Gasoline (E10)", "Natural Gas (Heating / Boiler)", "Heating Oil (Light)"], key="widget_m_fuel")
                
                with c2:
                    if 'widget_m_liters' not in st.session_state: st.session_state['widget_m_liters'] = 0.0
                    st.number_input("Consumption (Liters or kWh for Gas)", min_value=0.0, step=10.0, key="widget_m_liters")
                
                if 'file_key_m_exact' not in st.session_state:
                    st.session_state['file_key_m_exact'] = str(uuid.uuid4())
                
                st.file_uploader("Upload Fuel Receipt (PDF, JPG)", type=["pdf", "jpg", "png", "jpeg"], key=st.session_state['file_key_m_exact'])
                
                if 'widget_m_notes' not in st.session_state: st.session_state['widget_m_notes'] = ""
                st.text_input("Ref (Plate / Boiler ID)", placeholder="e.g. Plate AB-123", key="widget_m_notes")
                
                st.button("Add to List", on_click=add_fuel_exact_to_batch, key="btn_add_e2", type="primary")

        with tab_estimate:
            st.warning("Only use this method if actual fuel data is unavailable.")
            with st.container(border=True):
                st.markdown("**Add Distance Estimate**")
                c1, c2 = st.columns(2)
                with c1:
                    if 'widget_m_vehicle_2' not in st.session_state: st.session_state['widget_m_vehicle_2'] = "Passenger Car (Diesel)"
                    st.selectbox("Vehicle Class", ["Passenger Car (Diesel)", "Passenger Car (Petrol)", "Van / Light Truck (Diesel)", "Heavy Truck (Diesel)"], key="widget_m_vehicle_2")
                with c2:
                    if 'widget_m_km_2' not in st.session_state: st.session_state['widget_m_km_2'] = 0.0
                    st.number_input("Distance Driven (km)", min_value=0.0, step=100.0, key="widget_m_km_2")
                st.button("Calculate & Add to List", on_click=add_distance_estimate_to_batch, key="btn_est_e2_unique", type="primary")

        st.markdown("---")
        if st.session_state['e2_batch_list']:
            st.subheader("Review Data")
            df_batch = pd.DataFrame(st.session_state['e2_batch_list'])
            st.dataframe(df_batch[["source", "liters", "co2"]], use_container_width=True)
            c1, c2 = st.columns(2)
            c1.button("Remove Last", on_click=remove_last_e2, key="rm_e2")
            c2.button("Confirm & Upload", type="primary", on_click=upload_mobility_batch, key="up_e2")
        
        st.markdown("---")
        c1, c2 = st.columns([1, 4])
        if c1.button("Back", key="back_e2"): st.session_state['entry_stage'] = 'e2_intro'; st.rerun()
        if st.session_state['e2_step_complete']:
            if c2.button("Next: Module E3 (Business Travel)", type="primary", key="next_e2"):
                st.session_state['entry_stage'] = 'e3_intro'
                st.rerun()
        else:
            if c2.button("Skip / Not Applicable", key="skip_e2"):
                st.session_state['entry_stage'] = 'e3_intro'
                st.rerun()

    elif st.session_state['entry_stage'] == 'e3_intro':
        st.header("Module E3: Business Travel (Scope 3)")
        with st.container(border=True):
            st.markdown("""
            **Focus: Indirect Emissions from Travel.**
            This module covers transportation for business-related activities in vehicles **not owned** by the company.
            * **Flights** (Short/Long Haul)
            * **Train Travel**
            * **Hotel Stays**
            * **Private Car Usage** (Reimbursed Kilometers)
            """, unsafe_allow_html=True)
        st.divider()
        c1, c2 = st.columns([1,4])
        if c1.button("Back"): st.session_state['entry_stage'] = 'e2_form'; st.rerun()
        if c2.button("Next: Module E3 (Form)", type="primary"): st.session_state['entry_stage'] = 'e3_form'; st.rerun()

    elif st.session_state['entry_stage'] == 'e3_form':
        st.subheader("E3 Business Travel")
        st.markdown("Record flights, trains, and hotel stays.")
        
        with st.container(border=True):
            st.markdown("**Add Travel Activity**")
            c1, c2 = st.columns(2)
            with c1:
                if 'widget_t_type' not in st.session_state: st.session_state['widget_t_type'] = "Flight: Short Haul (< 500 km)"
                travel_options = [
                    "Flight: Short Haul (< 500 km)",
                    "Flight: Medium Haul (500-1500 km)",
                    "Flight: Long Haul (1500-3700 km)",
                    "Flight: Intercontinental (3700-5000 km)",
                    "Flight: Ultra Long Haul (> 5000 km)",
                    "Train (National/Regional)",
                    "Train (Long Distance/High Speed)",
                    "Hotel Stay (per Night)",
                    "Private Car (Reimbursement)"
                ]
                st.selectbox("Activity Type", travel_options, key="widget_t_type")
            with c2:
                current_selection = st.session_state.widget_t_type
                label = "Distance (km)"
                if "Flight" in current_selection: label = "Number of Flights (One-way)"
                elif "Hotel" in current_selection: label = "Number of Nights"
                
                if 'widget_t_amount' not in st.session_state: st.session_state['widget_t_amount'] = 0.0
                st.number_input(label, min_value=0.0, step=1.0, key="widget_t_amount")
            
            # --- NEU: File Uploader für Tickets/Rechnungen ---
            if 'file_key_travel' not in st.session_state:
                st.session_state['file_key_travel'] = str(uuid.uuid4())
            
            st.file_uploader("Upload Ticket / Invoice (PDF, JPG)", type=["pdf", "jpg", "png", "jpeg"], key=st.session_state['file_key_travel'])
            # -------------------------------------------------
            
            if 'widget_t_notes' not in st.session_state: st.session_state['widget_t_notes'] = ""
            st.text_input("Trip Details / Route", placeholder="e.g. Sales Trip London", key="widget_t_notes")
            st.button("Add to List", on_click=add_travel_to_batch, key="btn_add_e3", type="primary")

        # --- REVIEW & UPLOAD BEREICH ---
        if st.session_state['e3_batch_list']:
            st.subheader("Review Data")
            df_batch = pd.DataFrame(st.session_state['e3_batch_list'])
            st.dataframe(df_batch[["source", "liters", "notes", "co2"]], use_container_width=True)
            
            c_rm, c_up = st.columns(2)
            c_rm.button("Remove Last", on_click=remove_last_e3, key="rm_e3_btn")
            c_up.button("Confirm & Upload", type="primary", on_click=upload_travel_batch, key="up_e3_btn")

        st.markdown("---")
        
        # --- NAVIGATIONS BEREICH ---
        c_back, c_next = st.columns([1, 4])
        
        if c_back.button("Back", key="nav_back_e3"): 
            st.session_state['entry_stage'] = 'e3_intro'
            st.rerun()
            
        # Logik: Next erscheint NUR, wenn Upload erfolgreich war (e3_step_complete == True)
        if st.session_state.get('e3_step_complete', False):
            if c_next.button("Next: Module E4 (Commuting)", type="primary", key="nav_next_e3"):
                st.session_state['entry_stage'] = 'e4_intro'
                st.rerun()
        else:
            if c_next.button("Skip / Not Applicable", key="nav_skip_e3"):
                st.session_state['entry_stage'] = 'e4_intro'
                st.rerun()

    elif st.session_state['entry_stage'] == 'e4_intro':
        st.header("Module E4: Employee Commuting (Scope 3)")
        
        with st.container(border=True):
            st.markdown("""
            **Focus: How your team gets to work.**
            
            This module estimates emissions from employees traveling between their homes and their worksites.
            
            * **Car / Motorbike**
            * **Public Transport** (Train, Bus, Tram)
            * **Active Travel** (Walking, Cycling - 0 Emissions but good to track!)
            """, unsafe_allow_html=True)
            
        st.divider()
        c1, c2 = st.columns([1,4])
        if c1.button("Back"): st.session_state['entry_stage'] = 'e3_form'; st.rerun()
        if c2.button("Next: Module E4 (Form)", type="primary"): st.session_state['entry_stage'] = 'e4_form'; st.rerun()

    elif st.session_state['entry_stage'] == 'e4_form':
        st.subheader("E4 Employee Commuting")
        st.markdown("Group your employees by their primary mode of transport.")
        
        with st.container(border=True):
            st.markdown("**Add Commuting Group**")
            c1, c2 = st.columns(2)
            with c1:
                st.selectbox("Transport Mode", [
                    "Car (Petrol/Diesel)", 
                    "Car (Electric)", 
                    "Public Transport (Bus/Train)", 
                    "Motorbike", 
                    "Bicycle / Walk"
                ], key="widget_c_mode")
                
                st.selectbox("Commute Distance (One-Way)", [
                    "Short (< 10 km)",
                    "Medium (10 - 30 km)",
                    "Long (30 - 60 km)",
                    "Very Long (> 60 km)"
                ], key="widget_c_dist_cat")
            
            with c2:
                st.number_input("Number of Employees in this group", min_value=1, step=1, key="widget_c_emp")
                st.slider("Days per week in office", 1, 7, 3, key="widget_c_days") 
            
            st.button("Add to List", on_click=add_commute_to_batch, key="btn_add_e4", type="primary")

        st.markdown("---")
        if st.session_state['e4_batch_list']:
            st.subheader("Review Data")
            df_batch = pd.DataFrame(st.session_state['e4_batch_list'])
            st.dataframe(df_batch[["source", "liters", "notes", "co2"]], use_container_width=True)
            
            c1, c2 = st.columns(2)
            c1.button("Remove Last", on_click=remove_last_e4, key="rm_e4")
            c2.button("Confirm & Upload", type="primary", on_click=upload_commute_batch, key="up_e4")

        st.markdown("---")
        c1, c2 = st.columns([1, 4])
        
        if c1.button("Back", key="back_e4"): 
            st.session_state['entry_stage'] = 'e4_intro'
            st.rerun()
            
        if st.session_state['e4_step_complete']:
            if c2.button("Next: Module E5 (Waste)", type="primary", key="next_e4"):
                st.session_state['entry_stage'] = 'e5_intro'
                st.rerun()
        else:
            if c2.button("Skip / Not Applicable", key="skip_e4"):
                st.session_state['entry_stage'] = 'e5_intro'
                st.rerun()

    elif st.session_state['entry_stage'] == 'e5_intro':
        st.header("Module E5: Waste & Circular Economy")
        show_materiality_badge("E5")
        
        with st.container(border=True):
            st.markdown("""
            **Focus: What you throw away (and how).**
            
            Tracking waste helps calculate Scope 3 emissions (End-of-Life treatment) and proves circular economy efforts.
            
            * **Residual Waste** (General trash, usually incinerated)
            * **Recyclables** (Paper, Glass, Plastic)
            * **Hazardous / E-Waste** (Electronics, Batteries)
            """, unsafe_allow_html=True)
            
        st.divider()
        c1, c2 = st.columns([1,4])
        if c1.button("Back"): st.session_state['entry_stage'] = 'e4_form'; st.rerun()
        if c2.button("Next: Module E5 (Form)", type="primary"): st.session_state['entry_stage'] = 'e5_form'; st.rerun()

    elif st.session_state['entry_stage'] == 'e5_form':
        st.subheader("E5 Waste Management")
        st.markdown("Enter your waste volume based on container size and pickup frequency.")
        
        with st.container(border=True):
            st.markdown("**Add Waste Stream**")
            c1, c2 = st.columns(2)
            with c1:
                st.selectbox("Waste Type", [
                    "General Waste (Residual)", 
                    "Paper / Cardboard", 
                    "Plastic / Packaging", 
                    "Glass",
                    "Organic / Bio",
                    "Electronic Waste"
                ], key="widget_w_type")
                
                st.selectbox("Collection Frequency", ["Weekly", "Monthly", "One-time (Yearly)"], key="widget_w_freq")
                
                st.selectbox("Service Provider", [
                    "Municipal / City Service", 
                    "Private Contractor", 
                    "Recycling Center (Self-drop)"
                ], key="widget_w_provider")
                
            with c2:
                st.select_slider("Container Size (Liters)", options=[60, 120, 240, 660, 1100, 5000], value=240, key="widget_w_size")
                st.number_input("Number of Containers", min_value=1, step=1, key="widget_w_qty")
            
            st.info("We calculate the estimated weight (kg) based on material density automatically.")
            st.button("Add to List", on_click=add_waste_volume_to_batch, key="btn_add_e5", type="primary")

        st.markdown("---")
        if st.session_state['e5_batch_list']:
            st.subheader("Review Data")
            df_batch = pd.DataFrame(st.session_state['e5_batch_list'])
            st.dataframe(df_batch[["source", "liters", "notes", "co2"]], use_container_width=True)
            
            c1, c2 = st.columns(2)
            c1.button("Remove Last", on_click=remove_last_e5, key="rm_e5")
            c2.button("Confirm & Upload", type="primary", on_click=upload_waste_batch, key="up_e5")

        st.markdown("---")
        c1, c2 = st.columns([1, 4])
        
        if c1.button("Back", key="back_e5"): 
            st.session_state['entry_stage'] = 'e5_intro'
            st.rerun()
            
        if st.session_state['e5_step_complete']:
            if c2.button("Next: Module E3 (Water)", type="primary", key="next_e5"):
                st.session_state['entry_stage'] = 'water_intro'
                st.rerun()
        else:
            if c2.button("Skip / Not Applicable", key="skip_e5"):
                st.session_state['entry_stage'] = 'water_intro'
                st.rerun()

    elif st.session_state['entry_stage'] == 'water_intro':
        st.header("Module E3: Water & Marine Resources")
        show_materiality_badge("E3")
        with st.container(border=True):
            st.markdown("""
            **Focus: Water Consumption.**
            Even if you are an office, water is a precious resource.
            * **Water Withdrawal** (Mains water, Groundwater)
            * **Water Discharge** (Sewage treatment)
            """, unsafe_allow_html=True)
        st.divider()
        c1, c2 = st.columns([1,4])
        if c1.button("Back"): st.session_state['entry_stage'] = 'e5_form'; st.rerun()
        if c2.button("Next: Module E3 (Form)", type="primary"): st.session_state['entry_stage'] = 'water_form'; st.rerun()

    elif st.session_state['entry_stage'] == 'water_form':
        st.subheader("E3 Water Consumption")
        st.markdown("Add your buildings via meter reading OR estimation.")
        
        tab_exact, tab_est = st.tabs(["Exact Meter (m³)", "Estimation Calculator"])
        
        with tab_exact:
            with st.container(border=True):
                st.markdown("**Add Meter Reading**")
                c1, c2 = st.columns(2)
                with c1:
                    st.selectbox("Water Source", ["Mains Water (Municipal)", "Groundwater (Own Well)", "Rainwater Harvesting"], key="widget_wat_source")
                with c2:
                    st.number_input("Consumption (m³)", min_value=0.0, step=10.0, key="widget_wat_m3")
                
                # --- NEU: Datei-Uploader und Notizen ---
                if 'file_key_e3' not in st.session_state:
                    st.session_state['file_key_e3'] = str(uuid.uuid4())
                
                st.file_uploader("Upload Water Bill (PDF, JPG)", type=["pdf", "jpg", "png", "jpeg"], key=st.session_state['file_key_e3'])
                
                if 'widget_notes_water' not in st.session_state: st.session_state['widget_notes_water'] = ""
                st.text_input("Reference / Note", placeholder="e.g. Main Building", key="widget_notes_water")
                # ---------------------------------------
                
                st.button("Add to List", on_click=add_water_to_batch, key="btn_add_water", type="primary")

        with tab_est:
            st.warning("Only use this method if you don't have a water bill (e.g. part of shared rent).")
            with st.container(border=True):
                st.markdown("**Add Building Estimate**")
                c1, c2 = st.columns(2)
                with c1:
                    st.selectbox("Building Type", ["Office Building", "Warehouse / Logistics", "Retail / Shop"], key="widget_wat_est_type")
                    st.number_input("Number of Toilets/Urinals", min_value=1, step=1, key="widget_wat_est_wc")
                    st.number_input("Days in use (per year)", min_value=1, max_value=365, value=250, key="widget_wat_est_days")
                with c2:
                    st.number_input("Regular Occupants (Staff)", min_value=1, step=1, key="widget_wat_est_ppl")
                    st.caption("Calculation based on avg. daily usage per person (Flush, Hygiene, Kitchen).")
                
                st.button("Calculate & Add to List", on_click=add_water_estimate_to_batch, key="btn_est_water", type="primary")

        st.markdown("---")
        
        if st.session_state['e_water_batch_list']:
            st.subheader("Review Data")
            # Zeigt die temporäre Liste an
            st.dataframe(pd.DataFrame(st.session_state['e_water_batch_list'])[["source", "liters", "notes", "co2"]], use_container_width=True)
            
            c_rm, c_up = st.columns(2)
            c_rm.button("Remove Last", on_click=remove_last_water, key="rm_wat")
            
            # --- Der finale Upload-Button in die Datenbank ---
            if c_up.button("Confirm & Upload Water Data", type="primary", use_container_width=True):
                try:
                    company = st.session_state.get('current_company_id', 'Unknown')
                    year = st.session_state.get('current_year', '2024')
                    
                    records_to_insert = []
                    for item in st.session_state['e_water_batch_list']:
                        records_to_insert.append({
                            "company": company,
                            "date_of_service": f"{year}-12-31",
                            "esrs_tag": "ESRS-E3-1",
                            "type": "Water Consumption",
                            "fuel_type": item["source"],
                            "value_raw": item["liters"],
                            "co2_kg": item["co2"],
                            "description": item["notes"]
                        })
                    
                    supabase.table("esg_data_entries").insert(records_to_insert).execute()
                    
                    # Warteschlange leeren
                    st.session_state['e_water_batch_list'] = []
                    
                    # HIER WAR DER FEHLER: Das System muss wissen, dass der Upload fertig ist!
                    st.session_state['e_water_step_complete'] = True
                    
                    st.success("Water data successfully saved to database!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Database error during upload: {e}")
            # ------------------------------------------------------
            
        st.markdown("---")
        
        c1, c2 = st.columns([1,4])
        
        if c1.button("Back", key="back_wat"): 
            st.session_state['entry_stage'] = 'water_intro'
            st.rerun()
            
        # Navigation: Next erscheint NUR, wenn der Upload erfolgreich abgeschlossen wurde
        if st.session_state.get('e_water_step_complete', False):
            if c2.button("Next: Modules E2 & E4 (Pollution & Bio)", type="primary", key="next_wat"):
                st.session_state['entry_stage'] = 'bio_intro'
                st.rerun()
        else:
            if c2.button("Skip / Not Applicable", key="skip_wat"):
                st.session_state['entry_stage'] = 'bio_intro'
                st.rerun()

    elif st.session_state['entry_stage'] == 'bio_intro':
        st.header("Module E2 & E4: Pollution & Biodiversity")
        show_materiality_badge("E4")
        with st.container(border=True):
            st.markdown("""
            **Focus: Ecosystem Impact.**
            Completing the Environmental picture.
            * **E2 Pollution:** Substances of concern (Microplastics, Chemicals)?
            * **E4 Biodiversity:** Impact on sensitive areas or soil sealing.
            """, unsafe_allow_html=True)
        st.divider()
        c1, c2 = st.columns([1,4])
        if c1.button("Back"): st.session_state['entry_stage'] = 'water_form'; st.rerun()
        if c2.button("Next: Modules E2 & E4 (Form)", type="primary"): st.session_state['entry_stage'] = 'bio_form'; st.rerun()

    elif st.session_state['entry_stage'] == 'bio_form':
        st.subheader("E2 & E4 Impact Check")
        st.markdown("Qualitative assessment for full compliance.")
        
        with st.container(border=True):
            st.markdown("**1. ESRS E2: Pollution**")
            st.selectbox("Do you handle or emit hazardous substances (Microplastics, SVHC)?", 
                         ["None (Office/Service standard)", "Yes, managed internally", "Yes, high impact"], key="widget_bio_poll")
            
            st.markdown("---")
            st.markdown("**2. ESRS E4: Biodiversity**")
            st.selectbox("Is your operational site located in or near a biodiversity sensitive area?",
                         ["Urban / Industrial Zone (No Impact)", "Near Protected Area (Natura 2000)", "In Protected Area"], key="widget_bio_area")
            
            st.button("Add to List", on_click=add_bio_check_to_batch, type="primary")

        st.markdown("---")
        if st.session_state['e_bio_step_complete']:
            st.success("Records saved successfully.")
            
        # Die Navigation ist jetzt immer sichtbar, genau wie in den anderen Modulen
        c1, c2 = st.columns([1, 4])
        
        if c1.button("Back", key="back_bio"): 
            st.session_state['entry_stage'] = 'bio_intro'
            st.rerun()
            
        if st.session_state['e_bio_step_complete'] or len(st.session_state['e_bio_batch_list']) > 0:
            if c2.button("Next: Module E6 (Strategy)", type="primary", key="next_bio"):
                st.session_state['entry_stage'] = 'e6_intro'
                st.rerun()
        else:
            if c2.button("Skip / Not Applicable", key="skip_bio"):
                st.session_state['entry_stage'] = 'e6_intro'
                st.rerun()

    elif st.session_state['entry_stage'] == 'e6_intro':
        st.header("Module E6: Strategy & Policies")
        
        with st.container(border=True):
            st.markdown("""
            **Focus: Governance & Ambition.**
            
            An ESG report needs more than just numbers. Investors want to know **how** you manage risks and what your future targets are.
            
            * **Environmental Policy** (Do you have a written commitment?)
            * **Reduction Targets** (e.g. Net Zero by 2030)
            * **Circular Economy** (Repair, Reuse, Recycle initiatives)
            """, unsafe_allow_html=True)
            
        st.divider()
        c1, c2 = st.columns([1,4])
        if c1.button("Back"): st.session_state['entry_stage'] = 'bio_form'; st.rerun()
        if c2.button("Next: Module E6 (Form)", type="primary"): st.session_state['entry_stage'] = 'e6_form'; st.rerun()

    elif st.session_state['entry_stage'] == 'e6_form':
        st.subheader("E6 Environmental Strategy")
        st.markdown("Define your qualitative commitments.")
        
        with st.container(border=True):
            st.markdown("**1. Governance Documents**")
            st.selectbox("Do you have a formal Environmental Policy signed by management?", 
                         ["No", "Yes, internal only", "Yes, published publicly"], key="widget_p_policy")
            
            st.markdown("---")
            st.markdown("**2. Ambition & Targets**")
            
            target_selection = st.selectbox("What are your Emission Reduction Targets?", 
                         ["No defined targets", "Reduce by X% (Short/Mid Term)", "Net Zero (Long Term / SBTi)"], 
                         key="widget_p_targets")
            
            if "Reduce" in target_selection:
                st.info("Please specify your reduction goal:")
                c1, c2 = st.columns(2)
                with c1:
                    st.number_input("Reduction Target (%)", min_value=1, max_value=100, value=20, step=1, key="widget_p_target_pct")
                with c2:
                    st.number_input("Target Year", min_value=2024, max_value=2060, value=2030, step=1, key="widget_p_target_year")
                    
            elif "Net Zero" in target_selection:
                st.info("Please specify your Net Zero target year:")
                st.number_input("Target Year for Net Zero", min_value=2030, max_value=2100, value=2050, step=5, key="widget_p_target_year")
            
            st.markdown("---")
            st.markdown("**3. Circular Economy Initiatives**")
            st.caption("Do you have measures to extend product life, use recycled materials, or reduce waste in design?")
            st.text_area("Describe your strategy (optional)", placeholder="e.g. We use 50% recycled packaging and offer a repair service.", key="widget_p_circular")
            
            st.button("Add to List", on_click=save_policies_to_batch, key="btn_add_e6", type="primary")

        st.markdown("---")
        
        if st.session_state['e6_batch_list']:
            st.subheader("Review Data")
            df_batch = pd.DataFrame(st.session_state['e6_batch_list'])
            st.dataframe(df_batch[["source", "notes"]], use_container_width=True)
            
            st.button("Confirm & Upload", on_click=upload_policies_batch, type="primary", use_container_width=True, key="up_e6")

        st.markdown("---")
        c1, c2 = st.columns([1, 4])
        
        if c1.button("Back", key="back_e6"): 
            st.session_state['entry_stage'] = 'e6_intro'
            st.rerun()
            
        if st.session_state.get('e6_step_complete', False) or len(st.session_state['e6_batch_list']) > 0:
            if c2.button("Next: Review Data", type="primary", key="next_e6"):
                st.session_state['entry_stage'] = 'env_review'
                st.rerun()
        else:
            if c2.button("Skip / Not Applicable", key="skip_e6"):
                st.session_state['entry_stage'] = 'env_review'
                st.rerun()

    elif st.session_state['entry_stage'] == 'env_review':
        st.header("Environmental Summary")
        st.markdown("Review your total carbon footprint (Data fetched from Database).")
        
        response = supabase.table("esg_data_entries").select("*").eq("company", company_name).execute()
        db_rows = response.data
        
        all_data = []

        def classify_entry(name):
            n = name.lower()
            if "electricity" in n or "grid mix" in n or "renewable" in n or "nuclear" in n:
                return "E1 Electricity", "Scope 2"
            elif "district heating" in n or "cooling" in n or "steam" in n:
                return "E1 Heating", "Scope 2"
            elif "scope 1" in n or "diesel" in n or "petrol" in n or "natural gas" in n:
                return "E2 Fleet/Heat", "Scope 1"
            elif "flight" in n or "train" in n or "hotel" in n or "private car" in n:
                return "E3 Travel", "Scope 3"
            elif "commute" in n:
                return "E4 Commuting", "Scope 3"
            elif "waste" in n:
                return "E5 Waste", "Scope 3"
            elif "water" in n:
                return "E3 Water", "Scope 3"
            return "Other", "Scope 3"

        def get_type_from_string(name):
            if "estimate" in name.lower() or "calc" in name.lower():
                return "Estimated"
            return "Measured"

        if db_rows:
            for row in db_rows:
                name = row['fuel_type']
                mod, scope = classify_entry(name)
                dtype = get_type_from_string(name)
                
                all_data.append({
                    'Module': mod,
                    'Scope': scope,
                    'CO2': row['co2_kg'],
                    'Data Type': dtype
                })
        
        if all_data:
            df_review = pd.DataFrame(all_data)
            total_co2 = df_review['CO2'].sum()
            
            c1, c2, c3 = st.columns(3)
            with c1:
                st.container(border=True).metric("Total Footprint", f"{total_co2/1000:.2f} t", "CO2e")
            with c2:
                if not df_review.empty:
                    top_driver = df_review.groupby("Module")['CO2'].sum().idxmax()
                    share = df_review.groupby("Module")['CO2'].sum().max() / total_co2 * 100
                else:
                    top_driver = "N/A"
                    share = 0
                st.container(border=True).metric("Top Driver", top_driver, f"{share:.1f}% of total")
            with c3:
                est_co2 = df_review[df_review['Data Type'] == 'Estimated']['CO2'].sum()
                est_share = est_co2 / total_co2 * 100 if total_co2 > 0 else 0
                st.container(border=True).metric("Data Accuracy", f"{100-est_share:.1f}%", help="% of measured data.")

            st.markdown("### Composition by Category")
            with st.container(border=True):
                base = alt.Chart(df_review).encode(
                    theta=alt.Theta("CO2", stack=True)
                )
                
                pie = base.mark_arc(outerRadius=120, innerRadius=80).encode(
                    color=alt.Color("Module"),
                    order=alt.Order("CO2", sort="descending"),
                    tooltip=["Module", "CO2", "Scope"]
                )
                
                text = base.mark_text(radius=140).encode(
                    text=alt.Text("CO2", format=".0f"),
                    order=alt.Order("CO2", sort="descending"),
                    color=alt.value("black")
                )
                
                st.altair_chart(pie + text, use_container_width=True)

            c_left, c_right = st.columns(2)
            
            with c_left:
                with st.container(border=True):
                    st.markdown("**By Scope (1, 2, 3)**")
                    chart_data = df_review.groupby("Scope")['CO2'].sum().reset_index()
                    c = alt.Chart(chart_data).mark_bar(color='#023425').encode(
                        x='Scope',
                        y='CO2'
                    )
                    st.altair_chart(c, use_container_width=True)
            
            with c_right:
                with st.container(border=True):
                    st.markdown("**Data Quality (Measured vs. Estimated)**")
                    c = alt.Chart(df_review).mark_bar().encode(
                        x='Module',
                        y='CO2',
                        color=alt.Color('Data Type', scale=alt.Scale(domain=['Measured', 'Estimated'], range=['#023425', '#86efac']))
                    )
                    st.altair_chart(c, use_container_width=True)

            with st.expander("View Qualitative Policy Check"):
                policy_rows = [r for r in db_rows if r['co2_kg'] == 0]
                if policy_rows:
                    for p in policy_rows:
                        st.write(f"- {p['fuel_type']}")
                else:
                    st.info("No strategies uploaded yet.")

        else:
            st.info("No data found in Database. Please go back and ensure you clicked 'Upload' in the modules.")

        st.markdown("---")
        if st.button("Complete Pillar & Return to Main Menu", type="primary", use_container_width=True):
            st.session_state['entry_stage'] = 'main'
            st.rerun()

    # --- SOCIAL PILLAR START ---
    
    elif st.session_state['entry_stage'] == 'soc_intro':
        st.header("The Social Pillar")
        st.markdown("The social pillar focuses on your impact on people – your employees and society.")
        
        with st.container(border=True):
            st.markdown("""
            **The 4 European Sustainability Reporting Standards (Social):**
            
            * **S1 Own Workforce** (Employees, Wages, Diversity, Health & Safety)
            * **S2 Workers in the Value Chain** (Human rights in your supply chain)
            * **S3 Affected Communities** (Impact on local residents)
            * **S4 Consumers & End-users** (Product safety, Privacy)
            """)
            
        st.divider()
        c1, c2 = st.columns([1,4])
        if c1.button("Back"): st.session_state['entry_stage'] = 'main'; st.rerun()
        if c2.button("Next: Module S1 (Workforce)", type="primary"): st.session_state['entry_stage'] = 's1_intro'; st.rerun()

    elif st.session_state['entry_stage'] == 's1_intro':
        st.header("Module S1: Own Workforce")
        show_materiality_badge("S1")
        with st.container(border=True):
            st.markdown("""
            **Focus: Your Employees.**
            This is usually the most extensive part of the Social report. We will collect basic data first.
            
            * **Headcount** (Total number of employees)
            * **Gender Diversity** (% Women in workforce)
            * **Age Structure** (Demographic mix)
            """, unsafe_allow_html=True)
        st.divider()
        c1, c2 = st.columns([1,4])
        if c1.button("Back"): st.session_state['entry_stage'] = 'soc_intro'; st.rerun()
        if c2.button("Next: Module S1 (Form)", type="primary"): st.session_state['entry_stage'] = 's1_form'; st.rerun()

    elif st.session_state['entry_stage'] == 's1_form':
        st.subheader("S1.1 Basic Workforce Data")
        
        with st.container(border=True):
            hc = st.number_input("Total Headcount (Total number of employees)", min_value=0, step=1, key="widget_s1_headcount")
            
            st.markdown("---")
            
            c1, c2 = st.columns(2)
            with c1:
                women = st.number_input("Number of Women", min_value=0, max_value=hc, step=1, key="widget_s1_women_count")
            with c2:
                if hc > 0:
                    pct = (women / hc) * 100
                    st.metric("Female Share (Calculated)", f"{pct:.1f}%")
                else:
                    st.metric("Female Share", "0.0%")
            
            st.markdown("---")
            st.markdown("**Age Structure (Number of Employees)**")
            st.caption("Please enter employees under 30 and between 30-50. The rest is calculated automatically.")
            
            c1, c2, c3 = st.columns(3)
            with c1: 
                u30 = st.number_input("Under 30 years", min_value=0, max_value=hc, key="widget_s1_age_u30")
            with c2: 
                remaining = hc - u30
                mid = st.number_input("30 - 50 years", min_value=0, max_value=max(0, remaining), key="widget_s1_age_mid")
            with c3: 
                o50 = hc - u30 - mid
                st.metric("Over 50 years (Auto)", f"{o50}", help="Total Headcount minus (Under 30 + 30-50)")
            
            st.markdown("---")
            st.button("Confirm & Upload", on_click=save_s1_basic_direct, type="primary", use_container_width=True)

        st.markdown("---")
        c1, c2 = st.columns([1, 4])
        
        if c1.button("Back", key="back_s1_final"): 
            st.session_state['entry_stage'] = 's1_intro'
            st.rerun()
        
        if st.session_state.get('s1_step_complete', False):
             if c2.button("Next: S1.2 Health & Safety", type="primary", key="next_s1_final"):
                 st.session_state['entry_stage'] = 's1_2_form'
                 st.rerun()
        else:
             if c2.button("Skip / Not Applicable", key="skip_s1_final"):
                 st.session_state['entry_stage'] = 's1_2_form'
                 st.rerun()
                 
    elif st.session_state['entry_stage'] == 's1_2_form':
        st.subheader("S1.2 Health & Safety")
        
        with st.container(border=True):
            c1, c2 = st.columns(2)
            with c1:
                st.number_input("Number of Work Accidents", min_value=0, key="widget_s1_accidents", help="Recordable work-related accidents")
                st.number_input("Fatalities (Work-related)", min_value=0, key="widget_s1_fatalities")
            with c2:
                st.number_input("Sickness Rate (%)", min_value=0.0, max_value=100.0, step=0.1, key="widget_s1_sick", help="Average sick leave percentage")

            st.markdown("---")
            st.button("Confirm & Upload", on_click=save_s1_health_direct, type="primary", use_container_width=True)

        st.markdown("---")
        c1, c2 = st.columns([1, 4])
        
        if c1.button("Back", key="back_s1_2"): 
            st.session_state['entry_stage'] = 's1_form'
            st.rerun()
        
        if st.session_state.get('s1_2_step_complete', False):
             if c2.button("Next: S1.3 Wages", type="primary", key="fin_s1_2"):
                 st.session_state['entry_stage'] = 's1_3_form'
                 st.rerun()
        else:
             if c2.button("Skip / Not Applicable", key="skip_s1_2"):
                 st.session_state['entry_stage'] = 's1_3_form'
                 st.rerun()

    elif st.session_state['entry_stage'] == 's1_3_form':
        st.subheader("S1.3 Wages & Equality")
        
        st.info("**Data Privacy Note:** Salary data is sensitive. Your inputs are stored securely and only used to calculate the required ESG ratios (e.g., Pay Gap). No individual names are recorded.")
        
        with st.container(border=True):
            st.markdown("**1. Gender Pay Gap (Average Gross Yearly Salary)**")
            st.caption("Please enter the average gross salary (including bonuses) for men and women. We calculate the gap for you.")
            
            c1, c2 = st.columns(2)
            with c1:
                men = st.number_input("Ø Salary Men (€)", min_value=0.0, step=1000.0, key="widget_s1_sal_men")
            with c2:
                women = st.number_input("Ø Salary Women (€)", min_value=0.0, step=1000.0, key="widget_s1_sal_women")
            
            if men > 0 and women > 0:
                gap = ((men - women) / men) * 100
                color = "normal" if gap < 5 else "off" 
                st.metric("Calculated Pay Gap", f"{gap:.1f}%", delta_color=color, help="Difference between male and female average earnings.")
            
            st.markdown("---")
            st.markdown("**2. Fair Remuneration**")
            st.caption("Check if wages are fair compared to the highest earner and the cost of living.")
            
            c1, c2 = st.columns(2)
            with c1:
                st.selectbox("Top Management vs. Average Worker Pay",
                             ["Fair / Standard (< 1:10)", "High Disparity (> 1:10)", "Unknown / Confidential"],
                             key="widget_s1_ceo",
                             help="Rough estimate: Does the highest earner make more than 10 times the average worker?")
            with c2:
                st.selectbox("Do you pay a 'Living Wage'?", ["Yes, all above minimum standard", "No / Unsure", "Partially"], key="widget_s1_living_wage",
                             help="Does the lowest salary cover basic living costs (food, housing, transport) in your region?")

            st.markdown("---")
            st.button("Confirm & Upload", on_click=save_s1_wages_direct, type="primary", use_container_width=True)

        st.markdown("---")
        c1, c2 = st.columns([1, 4])
        
        if c1.button("Back", key="back_s1_3"): 
            st.session_state['entry_stage'] = 's1_2_form'
            st.rerun()
            
        if st.session_state.get('s1_3_step_complete', False):
             if c2.button("Next: S1.4 Training", type="primary", key="fin_s1_3"):
                 st.session_state['entry_stage'] = 's1_4_form'
                 st.rerun()
        else:
             if c2.button("Skip / Not Applicable", key="skip_s1_3"):
                 st.session_state['entry_stage'] = 's1_4_form'
                 st.rerun()

    elif st.session_state['entry_stage'] == 's1_4_form':
        st.subheader("S1.4 Training & Skills")
        
        with st.container(border=True):
            last_total = st.session_state.get('s1_total_headcount', 0)
            ref_text = f"(Calculating for {last_total} employees)" if last_total > 0 else "(Fallback: No headcount data)"
            
            st.markdown(f"**Total Training Hours** {ref_text}")
            c1, c2 = st.columns(2)
            with c1:
                total_h = st.number_input("Total Hours (All Staff)", min_value=0, step=10, key="widget_s1_hours_total")
            with c2:
                if last_total > 0:
                    st.metric("Average per Employee", f"{(total_h/last_total):.1f} h")
            
            st.markdown("---")
            st.button("Confirm & Upload", on_click=save_s1_training_direct, type="primary", use_container_width=True)

        st.markdown("---")
        c1, c2 = st.columns([1, 4])
        
        if c1.button("Back", key="back_s1_4"): 
            st.session_state['entry_stage'] = 's1_3_form'
            st.rerun()
            
        if st.session_state.get('s1_4_step_complete', False):
             if c2.button("Next: S2 Value Chain", type="primary", key="fin_s1_4"):
                 st.session_state['entry_stage'] = 's2_intro'
                 st.rerun()
        else:
             if c2.button("Skip / Not Applicable", key="skip_s1_4"):
                 st.session_state['entry_stage'] = 's2_intro'
                 st.rerun()
                 
    elif st.session_state['entry_stage'] == 's2_intro':
        st.header("Module S2: Workers in the Value Chain")
        show_materiality_badge("S2")
        
        with st.container(border=True):
            st.markdown("""
            **Focus: The people behind your value chain.**
            While S1 looked at your *own* employees, **S2** looks at the workers in your supply chain.
            
            <div style="background-color: #e8f5e9; padding: 15px; border-radius: 5px; margin-top: 10px; margin-bottom: 20px; border-left: 5px solid #023425;">
            <strong>Note:</strong> This applies to <u>ALL suppliers</u>, including <strong>Software providers (SaaS)</strong>, 
            <strong>Office Supplies</strong>, <strong>Cleaners</strong>, and <strong>Consultants</strong>.
            </div>
            
            * **Human Rights** (Risks of child labor or forced labor)
            * **Safety** (Safe working conditions at suppliers)
            * **Fairness** (Fair payment enabling living wages)
            """, unsafe_allow_html=True)
            
        st.divider()
        c1, c2 = st.columns([1,4])
        
        if c1.button("Back", key="back_s2_intro"): 
            st.session_state['entry_stage'] = 's1_4_form'
            st.rerun()
            
        if c2.button("Next: Module S2 (Form)", type="primary", key="start_s2"): 
            st.session_state['entry_stage'] = 's2_form'
            st.rerun()

    elif st.session_state['entry_stage'] == 's2_form':
        st.subheader("S2 Supply Chain Assessment")
        st.markdown("Please evaluate your management of supply chain risks.")
        
        with st.container(border=True):
            st.markdown("**1. Supplier Code of Conduct (CoC)**")
            st.caption("Do you have a document that sets out requirements for your suppliers regarding human rights and working conditions?")
            
            st.selectbox("Status of Code of Conduct", 
                         [
                             "No Code of Conduct", 
                             "Internal Guidelines exist (not shared)", 
                             "Yes, sent to suppliers", 
                             "Yes, signed bindingly by key suppliers"
                         ], key="widget_s2_coc")
            
            st.markdown("---")
            st.markdown("**2. Risk Analysis**")
            st.caption("Do you know where your products come from and if those regions/sectors are risky?")
            
            st.selectbox("Risk Management Approach",
                         [
                             "No formal analysis",
                             "Ad-hoc checks (Google/News)",
                             "Systematic screening of key suppliers",
                             "Full supply chain mapping (Tier 1 & Tier 2)"
                         ], key="widget_s2_risk")

            st.markdown("---")
            st.markdown("**3. Audits & Checks**")
            st.caption("Do you check if suppliers actually follow the rules?")
            
            st.selectbox("Audit Mechanism",
                         [
                             "None",
                             "Self-Assessment Questionnaires (Suppliers fill out form)",
                             "On-site Visits by our team",
                             "Third-party Audits (e.g. SMETA, SA8000)"
                         ], key="widget_s2_audit")
            
            st.button("Add to List", on_click=add_s2_to_batch, type="primary")

        st.markdown("---")
        
        if st.session_state['s2_batch_list']:
            st.subheader("Review Data")
            st.dataframe(pd.DataFrame(st.session_state['s2_batch_list'])[["source", "notes"]], use_container_width=True)
            c1, c2 = st.columns(2)
            c1.button("Remove Last", on_click=remove_last_s2, key="rm_s2")
            c2.button("Confirm & Upload", on_click=upload_s2_batch, key="up_s2")

        st.markdown("---")
        c1, c2 = st.columns([1, 4])
        
        if c1.button("Back", key="back_s2"): 
            st.session_state['entry_stage'] = 's2_intro'
            st.rerun()
        
        has_data = st.session_state['s2_step_complete'] or len(st.session_state['s2_batch_list']) > 0
        
        if has_data:
             if c2.button("Next: S3 Communities", type="primary", key="fin_s2"):
                 st.session_state['entry_stage'] = 's3_intro' 
                 st.rerun()
        else:
             if c2.button("Skip / Not Applicable", key="skip_s2"):
                 st.session_state['entry_stage'] = 's3_intro' 
                 st.rerun()

    elif st.session_state['entry_stage'] == 's3_intro':
        st.header("Module S3: Affected Communities")
        show_materiality_badge("S3")
        with st.container(border=True):
            st.markdown("""
            **Focus: Your Neighbors & Society.**
            How does your business affect the people living around you?
            
            * **Impact** (Noise, Traffic, Odor vs. Creating Jobs)
            * **Engagement** (Donations, Volunteering, Sponsorships)
            * **Dialogue** (Do you listen to complaints?)
            """, unsafe_allow_html=True)
            
        st.divider()
        c1, c2 = st.columns([1,4])
        
        if c1.button("Back", key="back_s3_intro"): 
            st.session_state['entry_stage'] = 's2_form'
            st.rerun()
            
        if c2.button("Next: Module S3 (Form)", type="primary", key="start_s3"): 
            st.session_state['entry_stage'] = 's3_form'
            st.rerun()

    elif st.session_state['entry_stage'] == 's3_form':
        st.subheader("S3 Community Impact")
        st.markdown("Evaluate your relationship with the local community.")
        
        with st.container(border=True):
            st.markdown("**1. Operational Impact (Negative)**")
            st.caption("Do your operations disturb the local neighborhood?")
            
            st.selectbox("Impact Level", 
                         [
                             "None (Office / Remote Work)", 
                             "Low (Some delivery traffic)", 
                             "Medium (Regular noise / Shift work)", 
                             "High (Industrial noise / Emissions)"
                         ], key="widget_s3_impact")
            
            st.markdown("---")
            st.markdown("**2. Social Engagement (Positive)**")
            st.caption("Do you actively support social causes?")
            
            st.selectbox("Type of Engagement",
                         [
                             "None",
                             "Occasional Donations (Christmas etc.)",
                             "Regular Sponsorship (Sports/Culture)",
                             "Corporate Volunteering (Time off for social work)"
                         ], key="widget_s3_engage")

            st.text_input("Optional: Description of activities", placeholder="e.g. Donated 5 laptops to local school...", key="widget_s3_desc")
            
            st.button("Add to List", on_click=add_s3_to_batch, type="primary")

        st.markdown("---")
        
        if st.session_state['s3_batch_list']:
            st.subheader("Review Data")
            st.dataframe(pd.DataFrame(st.session_state['s3_batch_list'])[["source", "notes"]], use_container_width=True)
            c1, c2 = st.columns(2)
            c1.button("Remove Last", on_click=remove_last_s3, key="rm_s3")
            c2.button("Confirm & Upload", on_click=upload_s3_batch, key="up_s3")

        st.markdown("---")
        c1, c2 = st.columns([1, 4])
        
        if c1.button("Back", key="back_s3_fix"): 
            st.session_state['entry_stage'] = 's3_intro'
            st.rerun()
        
        has_data = st.session_state['s3_step_complete'] or len(st.session_state['s3_batch_list']) > 0
        
        if has_data:
             if c2.button("Next: S4 Consumers", type="primary", key="fin_s3_fix"):
                 st.session_state['entry_stage'] = 's4_intro' 
                 st.rerun()
        else:
             if c2.button("Skip / Not Applicable", key="skip_s3_fix"):
                 st.session_state['entry_stage'] = 's4_intro'
                 st.rerun()

    elif st.session_state['entry_stage'] == 's4_intro':
        st.header("Module S4: Consumers & End-users")
        show_materiality_badge("S4")
        with st.container(border=True):
            st.markdown("""
            **Focus: Your Customers.**
            Ensuring safety, privacy, and honesty for the people using your products.
            
            * **Product Safety** (Quality controls, CE markings, Recalls)
            * **Data Privacy** (GDPR/DSGVO compliance, protecting customer data)
            * **Responsible Marketing** (No greenwashing, protection of minors)
            """, unsafe_allow_html=True)
            
        st.divider()
        c1, c2 = st.columns([1,4])
        
        if c1.button("Back", key="back_s4_intro"): 
            st.session_state['entry_stage'] = 's3_form'
            st.rerun()
            
        if c2.button("Next: Module S4 (Form)", type="primary", key="start_s4"): 
            st.session_state['entry_stage'] = 's4_form'
            st.rerun()

    elif st.session_state['entry_stage'] == 's4_form':
        st.subheader("S4 Consumer Protection")
        st.markdown("Assess risks regarding your customers.")
        
        with st.container(border=True):
            st.markdown("**1. Data Privacy (GDPR / DSGVO)**")
            st.caption("How do you handle personal data of customers?")
            
            st.selectbox("Privacy Standard", 
                         [
                             "Basic Compliance (Privacy Policy on Website)", 
                             "Advanced (Cookie Consent Manager & regular deletion)", 
                             "High Security (ISO 27001 certified)", 
                             "Not Applicable (B2B / No personal data)"
                         ], key="widget_s4_privacy")
            
            st.markdown("---")
            st.markdown("**2. Product Safety & Quality**")
            st.caption("Do your products pose any risks to users?")
            
            st.selectbox("Safety Measures",
                         [
                             "Legal Standard (CE Marking / Local Law)",
                             "Quality Management System (ISO 9001)",
                             "Extended Warranty & Support",
                             "Not Applicable (Service only)"
                         ], key="widget_s4_safety")

            st.markdown("---")
            st.markdown("**3. Responsible Marketing**")
            st.caption("Do you have ethical guidelines for advertising?")
            
            st.selectbox("Marketing Policy",
                         [
                             "No formal policy",
                             "Internal Code of Ethics (Honesty, Fairness)",
                             "Strict Anti-Greenwashing Guidelines",
                             "Protection of Minors / Vulnerable Groups"
                         ], key="widget_s4_marketing")
            
            st.button("Add to List", on_click=add_s4_to_batch, type="primary")

        st.markdown("---")
        
        if st.session_state['s4_batch_list']:
            st.subheader("Review Data")
            st.dataframe(pd.DataFrame(st.session_state['s4_batch_list'])[["source", "notes"]], use_container_width=True)
            c1, c2 = st.columns(2)
            c1.button("Remove Last", on_click=remove_last_s4, key="rm_s4")
            c2.button("Confirm & Upload", on_click=upload_s4_batch, key="up_s4")

        st.markdown("---")
        c1, c2 = st.columns([1, 4])
        
        if c1.button("Back", key="back_s4"): 
            st.session_state['entry_stage'] = 's4_intro'
            st.rerun()
        
        has_data = st.session_state['s4_step_complete'] or len(st.session_state['s4_batch_list']) > 0
        
        if has_data:
             if c2.button("Next: Review Data", type="primary", key="fin_s4"):
                 st.session_state['entry_stage'] = 'soc_review'
                 st.rerun()
        else:
             if c2.button("Skip / Not Applicable", key="skip_s4"):
                 st.session_state['entry_stage'] = 'soc_review'
                 st.rerun()          

    elif st.session_state['entry_stage'] == 'soc_review':
        st.header("Social Pillar Summary")
        st.markdown("Overview of your Social performance (S1 - S4).")
        
        try:
            response = supabase.table("esg_data_entries").select("*").eq("company", company_name).execute()
            rows = response.data
        except Exception as e:
            st.error(f"Connection Error: {e}")
            rows = []
        
        if rows:
            social_rows = []
            for r in rows:
                name = str(r.get('fuel_type', ''))
                if any(k in name for k in ["S1:", "S1.", "S2:", "S3:", "S4:"]):
                    social_rows.append(r)
            
            if social_rows:
                s1_data = [r for r in social_rows if "S1" in r.get('fuel_type', '')]
                
                if s1_data:
                    st.subheader("S1 Own Workforce (Metrics)")
                    clean_s1 = []
                    for item in s1_data:
                        raw_name = item.get('fuel_type', '')
                        display_name = raw_name.split('(')[0].replace("S1:", "").replace("S1.1", "").replace("S1.2", "").replace("S1.3", "").replace("S1.4", "").strip()
                        
                        clean_s1.append({
                            "Indicator": display_name,
                            "Value": item.get('value_raw', 0), 
                            "Details": raw_name 
                        })
                    st.dataframe(pd.DataFrame(clean_s1)[["Indicator", "Value", "Details"]], use_container_width=True)
                else:
                    st.info("No S1 data found yet.")

                st.markdown("---")

                other_data = [r for r in social_rows if "S1" not in r.get('fuel_type', '')]
                
                if other_data:
                    st.subheader("External Stakeholders (Qualitative)")
                    for item in other_data:
                        name = item.get('fuel_type', 'Unknown')
                        title = name.split('(')[0].strip()
                        with st.expander(title):
                            st.write(name)
                else:
                    st.info("No qualitative checks (S2-S4) found.")
            else:
                st.info("No Social data recorded yet in Database.")
        else:
            st.info("No data found in Database.")

        st.markdown("---")
        
        if st.button("Complete Pillar & Return to Main Menu", type="primary", use_container_width=True):
            st.session_state['entry_stage'] = 'main'
            st.rerun()

    # --- GOVERNANCE PILLAR START ---

    elif st.session_state['entry_stage'] == 'gov_intro':
        st.header("The Governance Pillar")
        st.markdown("Governance defines **how** your company is managed. It's about trust, transparency, and rules.")
        
        with st.container(border=True):
            st.markdown("""
            **The 3 Focus Areas for SMEs:**
            
            * **G1 Business Conduct** (Anti-corruption, Whistleblowing, Lobbying)
            * **G2 Management & Strategy** (Who is responsible? How do you manage risks?)
            * **G3 Supplier Relations** (Payment practices – do you pay fair and fast?)
            """, unsafe_allow_html=True)
            
        st.divider()
        c1, c2 = st.columns([1,4])
        if c1.button("Back"): st.session_state['entry_stage'] = 'main'; st.rerun()
        if c2.button("Next: Module G1 (Ethics)", type="primary"): 
            st.session_state['entry_stage'] = 'g1_form'
            st.rerun()

    elif st.session_state['entry_stage'] == 'g1_form':
        st.subheader("G1 Business Conduct & Ethics")
        st.markdown("Do you have the right rules in place to prevent misconduct?")
        show_materiality_badge("G1")
        with st.container(border=True):
            st.markdown("**1. Anti-Corruption & Bribery**")
            st.caption("Do you have guidelines preventing employees from accepting gifts or bribes?")
            st.selectbox("Policy Status", 
                         ["No formal policy", "Internal guidelines (verbal/written)", "Strict Anti-Corruption Policy signed by all staff"], 
                         key="widget_g1_corruption")
            
            st.markdown("---")
            st.markdown("**2. Whistleblower Protection**")
            st.caption("Can employees report illegal activities anonymously without fear of punishment?")
            st.selectbox("Reporting Channel",
                         ["None", "Direct supervisor only", "Anonymous Mailbox / Digital Channel (EU Compliant)"],
                         key="widget_g1_whistle",
                         help="Required by EU law for companies > 50 employees.")

            st.markdown("---")
            st.markdown("**3. Political Influence (Lobbying)**")
            st.selectbox("Political Contributions",
                         ["No political contributions", "Transparent donations (Publicly disclosed)", "Undisclosed lobbying activities"],
                         key="widget_g1_lobby")
            
            st.markdown("---")
            st.button("Confirm & Upload", on_click=save_g1_direct, type="primary", use_container_width=True)

        st.markdown("---")
        c1, c2 = st.columns([1, 4])
        
        if c1.button("Back", key="back_g1"): 
            st.session_state['entry_stage'] = 'gov_intro'
            st.rerun()
            
        if st.session_state.get('g1_step_complete', False):
             if c2.button("Next: G2 Management", type="primary", key="next_g1"):
                 st.session_state['entry_stage'] = 'g2_form' 
                 st.rerun()
        else:
             c2.button("Next: G2 Management (Upload first)", type="primary", disabled=True, key="skip_g1")

    elif st.session_state['entry_stage'] == 'g2_form':
        st.subheader("G2 Management & Strategy")
        st.markdown("Who is steering the ship? Investors and banks want to know who is accountable for ESG.")
        show_materiality_badge("G2")
        with st.container(border=True):
            st.markdown("**1. ESG Responsibility**")
            st.caption("Who holds the ultimate responsibility for sustainability matters in your company?")
            st.selectbox("Accountability", 
                         ["No dedicated person", "Shared among regular staff", "Dedicated ESG Officer / Manager", "Executive Board / CEO"], 
                         key="widget_g2_resp")
            
            st.markdown("---")
            st.markdown("**2. Risk Management**")
            st.caption("Are climate and social risks (e.g., supply chain disruptions, extreme weather) part of your regular risk management?")
            st.selectbox("Risk Integration",
                         ["No, not tracked", "Tracked informally", "Yes, fully integrated into company risk management"],
                         key="widget_g2_risk")

            st.markdown("---")
            st.button("Confirm & Upload", on_click=save_g2_direct, type="primary", use_container_width=True)

        st.markdown("---")
        c1, c2 = st.columns([1, 4])
        
        if c1.button("Back", key="back_g2"): 
            st.session_state['entry_stage'] = 'g1_form'
            st.rerun()
            
        if st.session_state.get('g2_step_complete', False):
             if c2.button("Next: G3 Suppliers", type="primary", key="next_g2"):
                 st.session_state['entry_stage'] = 'g3_form' 
                 st.rerun()
        else:
             c2.button("Next: G3 Suppliers (Upload first)", type="primary", disabled=True, key="skip_g2")

    elif st.session_state['entry_stage'] == 'g3_form':
        st.subheader("G3 Supplier Relations")
        st.markdown("How do you treat your partners? Fair payment practices and local sourcing are key indicators of good governance.")
        show_materiality_badge("G3")
        with st.container(border=True):
            st.markdown("**1. Payment Practices**")
            st.caption("What are your standard payment terms for suppliers? (Paying on time is a major ESG metric!)")
            st.selectbox("Standard Payment Terms",
                         ["0-30 days", "31-60 days", "61-90 days", "More than 90 days"],
                         key="widget_g3_pay")

            st.markdown("---")
            st.markdown("**2. Local Sourcing**")
            st.caption("Roughly what percentage of your procurement budget is spent on local/regional suppliers?")
            st.selectbox("Local Supplier Spend",
                         ["Less than 10%", "10% - 25%", "26% - 50%", "Over 50%"],
                         key="widget_g3_local")

            st.markdown("---")
            st.button("Confirm & Upload", on_click=save_g3_direct, type="primary", use_container_width=True)

        st.markdown("---")
        c1, c2 = st.columns([1, 4])
        
        if c1.button("Back", key="back_g3"): 
            st.session_state['entry_stage'] = 'g2_form'
            st.rerun()
            
        if st.session_state.get('g3_step_complete', False):
             if c2.button("Next: Review Data", type="primary", key="finish_g3"):
                 st.session_state['entry_stage'] = 'gov_overview' 
                 st.rerun()
        else:
             c2.button("Next: Review Data (Upload first)", type="primary", disabled=True, key="skip_g3")            

    elif st.session_state['entry_stage'] == 'gov_overview':
        st.header("Governance Pillar Summary")
        st.success("Governance data entry completed successfully.")
        st.markdown("Here is a quick overview of your submitted Governance profile:")
        
        c1, c2, c3 = st.columns(3)
        
        with c1:
            with st.container(border=True):
                st.markdown("### G1: Conduct")
                code_of_conduct = st.session_state.get('widget_g1_code', 'Not provided')
                st.caption("Code of Conduct:")
                st.write(f"**{code_of_conduct}**")
                
        with c2:
            with st.container(border=True):
                st.markdown("### G2: Management")
                accountability = st.session_state.get('widget_g2_resp', 'Not provided')
                risk = st.session_state.get('widget_g2_risk', 'Not provided')
                st.caption("ESG Responsibility:")
                st.write(f"**{accountability}**")
                st.caption("Risk Integration:")
                st.write(f"**{risk}**")

        with c3:
            with st.container(border=True):
                st.markdown("### G3: Suppliers")
                pay = st.session_state.get('widget_g3_pay', 'Not provided')
                local = st.session_state.get('widget_g3_local', 'Not provided')
                st.caption("Payment Terms:")
                st.write(f"**{pay}**")
                st.caption("Local Sourcing:")
                st.write(f"**{local}**")

        st.markdown("---")
        
        if st.button("Complete Pillar & Return to Main Menu", type="primary", use_container_width=True):
            st.session_state['g_pillar_complete'] = True 
            st.session_state['entry_stage'] = 'main'
            st.rerun()

elif menu == "Reports":
    st.subheader("Full CSRD Audit Report Generator")
    st.markdown("Generate a comprehensive, multi-page compliance report. The AI will write the report chapter by chapter to ensure maximum depth and accuracy.")
    
    # 1. Daten aus der Datenbank holen
    try:
        company = st.session_state.get('current_company_id', 'Unknown')
        year = st.session_state.get('current_year', '2024')
        response = supabase.table("esg_data_entries").select("*").eq("company", company).execute()
        raw_data = response.data
    except Exception as e:
        st.error(f"Database error: {e}")
        raw_data = []

    if raw_data:
        # 2. KI-Generierung per Knopfdruck
        if st.button("Generate Full Audit Report", type="primary", use_container_width=True):
            
            client = OpenAI(api_key=st.secrets["openai"]["api_key"])
            
        # Wir füttern die KI nun zusätzlich mit der Beschreibung und der Materialitäts-Auswahl
            desc = st.session_state.get('company_description', 'No description provided.')
            ind = st.session_state.get('company_industry', 'Unknown')
            size_val = st.session_state.get('company_size', 'Unknown')
            hq = st.session_state.get('hq_country', 'Unknown')
            other_locs = st.session_state.get('other_countries', [])
            mat = st.session_state.get('material_topics', [])
            
            filtered_raw_data = [r for r in raw_data if r.get('type') != 'Company Setup']
            user_data = f"Company: {company}\nReporting Year: {year}\nIndustry: {ind}\nCompany Size: {size_val}\nHeadquarters: {hq}\nSecondary Locations: {other_locs}\nDescription/Value Chain: {desc}\nMaterial Topics Identified: {mat}\n\nHere is the raw ESG data collected:\n{filtered_raw_data}"
            full_report = ""
            
            progress_text = "Generation in progress. Please wait."
            my_bar = st.progress(0, text=progress_text)
            
            try:
                # --- Kapitel 0: Introduction & Business Model ---
                my_bar.progress(5, text="Writing Company Overview & Materiality Assessment...")
                prompt_intro = """
                You are a senior ESG auditor. Write the 'Introduction & Business Model' chapter of a CSRD report.
                Use the provided Company Description and Industry to explain their value chain.
                Then, add a sub-chapter about their 'Double Materiality Assessment' listing their material topics.
                Be highly formal, analytical, and objective. Do not use any emojis.
                Format the main heading as '## 0. Business Model & Materiality'.
                """
                completion_intro = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": prompt_intro},
                        {"role": "user", "content": user_data}
                    ],
                    temperature=0.2
                )
                full_report += completion_intro.choices[0].message.content + "\n\n"

            
            
                # --- Kapitel 1: Environment ---
                my_bar.progress(10, text="Analyzing Environmental Data (ESRS E1-E5)...")
                prompt_env = """
                You are a senior ESG auditor. Write the 'Environment' chapter of a CSRD report based on the provided data. 
                Focus ONLY on environmental metrics (CO2 emissions, energy, waste, water). 
                Cite the exact ESRS tags in the text where applicable. 
                IMPORTANT: Incorporate the specific context and notes provided in the 'description' field of the data to make the report highly specific and personalized to the company's actual operations.
                Be highly formal, analytical, and objective. Do not use any emojis.
                """
                completion_env = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": prompt_env},
                        {"role": "user", "content": user_data}
                    ],
                    temperature=0.2
                )
                full_report += "## 1. Environmental Performance\n\n" + completion_env.choices[0].message.content + "\n\n"
                
                # --- Kapitel 2: Social ---
                my_bar.progress(50, text="Analyzing Social Data (ESRS S1-S4)...")
                prompt_soc = """
                You are a senior ESG auditor. Write the 'Social' chapter of a CSRD report based on the provided data. 
                Focus ONLY on social metrics (workforce, health & safety, gender pay gap, training). 
                Cite the exact ESRS tags in the text where applicable. 
                IMPORTANT: Incorporate the specific context and notes provided in the 'description' field of the data to make the report highly specific and personalized to the company's actual operations.
                Be highly formal, analytical, and objective. Do not use any emojis.
                """
                completion_soc = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": prompt_soc},
                        {"role": "user", "content": user_data}
                    ],
                    temperature=0.2
                )
                full_report += "## 2. Social Performance\n\n" + completion_soc.choices[0].message.content + "\n\n"
                
                # --- Kapitel 3: Governance ---
                my_bar.progress(80, text="Analyzing Governance Data (ESRS G1)...")
                prompt_gov = """
                You are a senior ESG auditor. Write the 'Governance' chapter of a CSRD report based on the provided data. 
                Focus ONLY on governance metrics (policies, risk management, anti-corruption, supplier relations). 
                Cite the exact ESRS tags in the text where applicable. 
                IMPORTANT: Incorporate the specific context and notes provided in the 'description' field of the data to make the report highly specific and personalized to the company's actual operations.
                Be highly formal, analytical, and objective. Do not use any emojis.
                """
                completion_gov = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": prompt_gov},
                        {"role": "user", "content": user_data}
                    ],
                    temperature=0.2
                )
                full_report += "## 3. Governance & Conduct\n\n" + completion_gov.choices[0].message.content + "\n\n"
                
                # Abschluss
                my_bar.progress(100, text="Report compiled successfully.")
                st.success("Full Audit Report generated successfully.")
                st.markdown("---")
                
                # Report in einem editierbaren Textfeld anzeigen
                st.markdown("### Review and Edit")
                st.markdown("You can make final adjustments to the generated report here before downloading.")
                edited_report = st.text_area("Final Report Output", value=full_report, height=600, label_visibility="collapsed")
                
                st.markdown("---")
                
                # Wir konvertieren die raw_data in einen Pandas DataFrame
                df_for_pdf = pd.DataFrame(filtered_raw_data)
                
                # PDF generieren
                hq = st.session_state.get('hq_country', 'Unknown')
                # --- NEU: Diagramme für das PDF generieren und speichern ---
                # --- NEU: 3 Diagramme (inkl. ESG Risk Score) ---
                my_bar.progress(90, text="Generating ESG Charts for PDF...")
                import plotly.graph_objects as go
                
                est_mask = df_for_pdf['fuel_type'].str.contains("ESTIMATE", case=False, na=False) | (df_for_pdf['type'] == 'Estimate')
                quality_score = int(((len(df_for_pdf) - est_mask.sum()) / len(df_for_pdf)) * 100) if len(df_for_pdf) > 0 else 0
                
                def get_scope(n):
                    n = str(n).lower()
                    if any(x in n for x in ["scope 1", "diesel", "petrol", "natural gas"]): return "Scope 1"
                    if any(x in n for x in ["electricity", "grid mix", "heating", "district"]): return "Scope 2"
                    return "Scope 3"
                
                df_for_pdf['Scope'] = df_for_pdf['fuel_type'].apply(get_scope)
                s1_co2 = df_for_pdf[df_for_pdf['Scope'] == 'Scope 1']['co2_kg'].sum() / 1000
                s2_co2 = df_for_pdf[df_for_pdf['Scope'] == 'Scope 2']['co2_kg'].sum() / 1000
                s3_co2 = df_for_pdf[df_for_pdf['Scope'] == 'Scope 3']['co2_kg'].sum() / 1000
                
                industry = st.session_state.get('company_industry', 'Services / Office')
                base_risk = {"IT / Software": 15, "Services / Office": 18, "Retail / Wholesale": 25, "Logistics / Transport": 35, "Manufacturing / Production": 38, "Construction / Real Estate": 40, "Agriculture / Food": 35}.get(industry, 25)
                
                has_targets = not df_for_pdf[df_for_pdf['fuel_type'] == 'Strategy: Emission Targets'].empty
                has_coc = not df_for_pdf[df_for_pdf['fuel_type'] == 'G1: Business Conduct'].empty
                
                user_risk = base_risk
                if has_targets: user_risk -= 4
                if has_coc: user_risk -= 3
                if quality_score > 80: user_risk -= 2
                if quality_score < 40: user_risk += 4
                user_risk = max(0, min(50, user_risk))
                
                sustainability_score = 100 - (user_risk * 2)
                calculated_star_rating = max(1.0, min(5.0, sustainability_score / 20))
                
                # 1. Data Readiness (Mit sichtbarer Skala und schmalerem Balken)
                fig1 = go.Figure(go.Indicator(
                    mode = "number+gauge", value = quality_score, 
                    number = {'font': {'size': 28, 'color': '#333333', 'family': 'Arial'}, 'suffix': "%"},
                    title = {'text': "Data<br>Quality", 'font': {'size': 13, 'color': '#777777', 'family': 'Arial'}},
                    gauge = {
                        'shape': "bullet",
                        # NEU: Skala ist jetzt sichtbar (0%, 50%, 100%)
                        'axis': {'range': [0, 100], 'tickvals': [0, 50, 100], 'ticktext': ['0%', '50%', '100%'], 'showticklabels': True, 'tickfont': dict(color='#777777', size=11)},
                        'bar': {'color': "#023425", 'thickness': 0.35},
                        'bgcolor': "rgba(0,0,0,0)",
                        'borderwidth': 0
                    }
                ))
                # NEU: Mehr Top/Bottom Margin (t=50, b=40) drückt den Balken stark zusammen, er wird filigraner!
                fig1.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=80, r=20, t=50, b=40), height=180)
                
                # --- Perfekter 50-Schritte Farbverlauf (Gradient) für den Risk Score ---
                risk_steps = []
                for i in range(50):
                    if i < 25: 
                        r = int(134 + (253 - 134) * (i / 25))
                        g = int(239 + (224 - 239) * (i / 25))
                        b = int(172 + (71 - 172) * (i / 25))
                    else:      
                        r = int(253 + (248 - 253) * ((i - 25) / 25))
                        g = int(224 + (113 - 224) * ((i - 25) / 25))
                        b = int(71 + (113 - 71) * ((i - 25) / 25))
                    risk_steps.append({'range': [i, i+1], 'color': f'rgb({r},{g},{b})'})

                # 2. ESG Risk Score (Ebenfalls schmaler gemacht)
                fig_risk = go.Figure(go.Indicator(
                    mode = "number+gauge", value = user_risk, 
                    number = {'font': {'size': 28, 'color': '#333333', 'family': 'Arial'}},
                    title = {'text': "ESG Risk<br>Score", 'font': {'size': 13, 'color': '#777777', 'family': 'Arial'}},
                    gauge = {
                        'shape': "bullet",
                        'axis': {'range': [0, 50], 'tickvals': [0, 25, 50], 'ticktext': ['Low', 'Med', 'Severe'], 'tickfont': dict(color='#777777', size=11)},
                        'bar': {'color': "#333333", 'thickness': 0.15}, 
                        'bgcolor': "rgba(0,0,0,0)",
                        'borderwidth': 0,
                        'steps': risk_steps,
                        'threshold': { 
                            'line': {'color': "#333333", 'width': 2},
                            'thickness': 0.8,
                            'value': base_risk
                        }
                    }
                ))
                # Gleiche Margins wie bei fig1 für absolute Symmetrie
                fig_risk.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=80, r=20, t=50, b=40), height=180)
                
                # 3. Bar Chart
                fig2 = go.Figure()
                fig2.add_trace(go.Bar(
                    y=['Scope 3', 'Scope 2', 'Scope 1'], 
                    x=[s3_co2, s2_co2, s1_co2], 
                    orientation='h', 
                    marker_color=['#86efac', '#416852', '#023425'],
                    width=0.4 
                ))
                fig2.update_layout(
                    title={'text': "Carbon Footprint (t CO2e)", 'font': {'size': 14, 'color': '#777777', 'family': 'Arial'}},
                    paper_bgcolor='rgba(0,0,0,0)', 
                    plot_bgcolor='rgba(0,0,0,0)',
                    margin=dict(l=70, r=20, t=40, b=30),
                    height=360, 
                    showlegend=False,
                    xaxis=dict(showgrid=True, gridcolor='#eeeeee', zeroline=False, tickfont=dict(color='#777777', size=11)),
                    yaxis=dict(showgrid=False, tickfont=dict(color='#555555', size=12))
                )
                
                try:
                    fig1.write_image("temp_gauge.png", width=500, height=200, scale=2)
                    fig_risk.write_image("temp_risk.png", width=500, height=200, scale=2)
                    fig2.write_image("temp_bar.png", width=500, height=450, scale=2)
                    gauge_path = "temp_gauge.png"
                    risk_path = "temp_risk.png"
                    bar_path = "temp_bar.png"
                except Exception as e:
                    gauge_path = None
                    risk_path = None
                    bar_path = None

                my_bar.progress(95, text="Compiling final PDF Document...")
                
                # --- BUGFIX: Land wird jetzt garantiert gefunden ---
                hq = st.session_state.get('setup_hq', st.session_state.get('hq_country', 'Austria'))
                
                pdf_bytes = generate_audit_pdf(
                    company, year, edited_report, df_for_pdf, 
                    country=hq, gauge_img=gauge_path, bar_img=bar_path, risk_img=risk_path,
                    star_rating=calculated_star_rating
                )
                
                st.download_button(
                    label="Download Official Audit Report (PDF)",
                    data=pdf_bytes,
                    file_name=f"CSRD_Audit_Report_{company}_{year}.pdf",
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True
                )
                
            except Exception as e:
                st.error(f"AI Generation failed: {e}")
                my_bar.empty()
                
    else:
        st.info("No data found. Please enter data in the 'Data Entry Center' first.")
elif menu == "Document Portal":
    import uuid as _uuid

    st.header("Document Portal")
    st.markdown("Manage your locations and upload monthly utility bills, invoices, and evidence documents.")

    if not company_name:
        st.warning("Please enter a Company Name in the sidebar first.")
        st.stop()

    tab_locations, tab_upload, tab_overview = st.tabs([
        "Manage Locations",
        "Monthly Upload",
        "Overview & History"
    ])

    # ============================================================
    # TAB 1: LOCATIONS
    # ============================================================
    with tab_locations:
        st.subheader("Your Locations")
        st.markdown("Add all your operational sites here. You can then upload monthly data per location.")

        existing_locations = []
        try:
            loc_response = supabase.table("esg_locations").select("*").eq("company", company_name).order("location_name").execute()
            existing_locations = loc_response.data or []
        except Exception as e:
            st.error(f"Could not load locations: {e}")

        with st.expander("Add New Location", expanded=(len(existing_locations) == 0)):
            with st.form("new_location_form"):
                st.markdown("**Location Details**")
                c1, c2 = st.columns(2)
                with c1:
                    new_loc_name = st.text_input(
                        "Location Name *",
                        placeholder="e.g. Vienna Headquarters, Warehouse Graz..."
                    )
                    new_loc_type = st.selectbox("Location Type", LOCATION_TYPES)
                with c2:
                    new_loc_address = st.text_input(
                        "Address (optional)",
                        placeholder="e.g. Mariahilfer Str. 1, 1060 Vienna"
                    )
                    new_loc_country = st.selectbox("Country", [
                        "Austria", "Germany", "Switzerland", "France", "Italy",
                        "Spain", "Netherlands", "Belgium", "Sweden", "Denmark",
                        "Poland", "Ireland", "Singapore", "Philippines",
                        "United Kingdom", "USA", "Other"
                    ])

                submitted = st.form_submit_button("Save Location", type="primary", use_container_width=True)
                if submitted:
                    if not new_loc_name.strip():
                        st.error("Please enter a location name.")
                    else:
                        try:
                            supabase.table("esg_locations").insert({
                                "company": company_name,
                                "location_name": new_loc_name.strip(),
                                "location_type": new_loc_type,
                                "address": new_loc_address.strip(),
                                "country": new_loc_country
                            }).execute()
                            st.success(f"Location '{new_loc_name}' added successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to save location: {e}")

        st.markdown("---")

        if existing_locations:
            st.markdown(f"**{len(existing_locations)} Location(s) registered:**")
            for loc in existing_locations:
                col_info, col_del = st.columns([5, 1])
                with col_info:
                    with st.container(border=True):
                        c1, c2, c3 = st.columns(3)
                        c1.markdown(f"**{loc['location_name']}**")
                        c2.caption(f"{loc.get('location_type', 'Office')}")
                        c3.caption(f"{loc.get('country', 'N/A')}")
                        if loc.get('address'):
                            st.caption(f"Address: {loc['address']}")
                with col_del:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("Delete", key=f"del_loc_{loc['id']}"):
                        try:
                            supabase.table("esg_locations").delete().eq("id", loc['id']).execute()
                            st.success("Location deleted.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
        else:
            st.info("No locations registered yet. Add your first location above.")

    # ============================================================
    # TAB 2: MONTHLY UPLOAD
    # ============================================================
    with tab_upload:
        st.subheader("Monthly Document Upload")
        st.markdown("Select a location and month, then upload your utility bills and enter the values.")

        locations_for_upload = []
        try:
            loc_resp = supabase.table("esg_locations").select("*").eq("company", company_name).order("location_name").execute()
            locations_for_upload = loc_resp.data or []
        except Exception as e:
            st.error(f"Could not load locations: {e}")

        if not locations_for_upload:
            st.warning("Please add at least one location in the 'Manage Locations' tab first.")
        else:
            with st.container(border=True):
                st.markdown("**1. Select Period & Location**")
                c1, c2, c3 = st.columns(3)
                loc_options = {loc['location_name']: loc for loc in locations_for_upload}
                with c1:
                    selected_loc_name = st.selectbox("Location", options=list(loc_options.keys()), key="portal_loc_select")
                with c2:
                    selected_year = st.selectbox("Year", ["2023", "2024", "2025", "2026"], index=1, key="portal_year_select")
                with c3:
                    selected_month = st.selectbox("Month", MONTHS, key="portal_month_select")

            selected_loc = loc_options.get(selected_loc_name)

            already_uploaded = []
            try:
                existing_resp = supabase.table("esg_monthly_uploads").select("category").eq(
                    "company", company_name
                ).eq("location_id", selected_loc['id']).eq("year", selected_year).eq("month", selected_month).execute()
                already_uploaded = [r['category'] for r in (existing_resp.data or [])]
            except Exception:
                pass

            if already_uploaded:
                st.info(f"Already uploaded for {selected_month} {selected_year} at {selected_loc_name}: {', '.join(already_uploaded)}")

            st.markdown("---")
            st.markdown(f"**2. Enter Data for {selected_loc_name} — {selected_month} {selected_year}**")

            with st.form("monthly_upload_form"):
                for cat_name, cat_info in MONTHLY_CATEGORIES.items():
                    already_done = cat_name in already_uploaded
                    label_suffix = " (already uploaded)" if already_done else ""

                    with st.container(border=True):
                        col_cat, col_val, col_file = st.columns([2, 1, 2])
                        with col_cat:
                            st.markdown(f"**{cat_name}**{label_suffix}")
                            st.caption(f"{cat_info['esrs_tag']} | {cat_info['scope']}")
                        with col_val:
                            val = st.number_input(
                                f"Value ({cat_info['unit']})",
                                min_value=0.0,
                                step=1.0,
                                key=f"val_{cat_name}",
                                disabled=already_done,
                                label_visibility="collapsed"
                            )
                            if val > 0:
                                co2 = val * cat_info['co2_factor']
                                st.caption(f"approx. {co2:.1f} kg CO2")
                        with col_file:
                            file_key = f"file_{cat_name}_{selected_loc['id']}_{selected_year}_{selected_month}"
                            st.file_uploader(
                                "Upload Bill",
                                type=["pdf", "jpg", "png", "jpeg"],
                                key=file_key,
                                disabled=already_done,
                                label_visibility="collapsed"
                            )
                        st.text_input(
                            "Note (optional)",
                            placeholder="e.g. Invoice #123, Meter ID...",
                            key=f"note_{cat_name}",
                            disabled=already_done,
                            label_visibility="collapsed"
                        )

                submit_all = st.form_submit_button(
                    f"Save All Entries for {selected_month} {selected_year}",
                    type="primary",
                    use_container_width=True
                )

                if submit_all:
                    saved_count = 0
                    error_count = 0

                    for cat_name, cat_info in MONTHLY_CATEGORIES.items():
                        if cat_name in already_uploaded:
                            continue
                        val = st.session_state.get(f"val_{cat_name}", 0.0)
                        if val <= 0:
                            continue

                        file_key = f"file_{cat_name}_{selected_loc['id']}_{selected_year}_{selected_month}"
                        uploaded_file = st.session_state.get(file_key)
                        file_url = ""

                        if uploaded_file is not None and supabase is not None:
                            try:
                                file_ext = uploaded_file.name.split('.')[-1]
                                storage_path = f"{company_name}/{selected_year}/{selected_month}/{selected_loc_name}/{_uuid.uuid4().hex[:8]}.{file_ext}"
                                supabase.storage.from_("esg_evidence").upload(storage_path, uploaded_file.getvalue())
                                file_url = supabase.storage.from_("esg_evidence").get_public_url(storage_path)
                            except Exception as e:
                                st.warning(f"File upload failed for {cat_name}: {e}")

                        note = st.session_state.get(f"note_{cat_name}", "")
                        co2 = val * cat_info['co2_factor']

                        try:
                            supabase.table("esg_monthly_uploads").insert({
                                "company": company_name,
                                "location_id": selected_loc['id'],
                                "location_name": selected_loc_name,
                                "year": selected_year,
                                "month": selected_month,
                                "category": cat_name,
                                "value_raw": val,
                                "unit": cat_info['unit'],
                                "co2_kg": co2,
                                "esrs_tag": cat_info['esrs_tag'],
                                "notes": f"{note} | Scope: {cat_info['scope']}",
                                "file_url": file_url
                            }).execute()
                            saved_count += 1
                        except Exception as e:
                            st.error(f"Failed to save {cat_name}: {e}")
                            error_count += 1

                    if saved_count > 0:
                        st.success(f"Saved {saved_count} records for {selected_loc_name} — {selected_month} {selected_year}!")
                        st.rerun()
                    elif error_count == 0:
                        st.warning("No values entered (all 0 or already uploaded).")

    # ============================================================
    # TAB 3: OVERVIEW & HISTORY
    # ============================================================
    with tab_overview:
        st.subheader("Upload History & Overview")

        all_uploads = []
        try:
            overview_resp = supabase.table("esg_monthly_uploads").select("*").eq(
                "company", company_name
            ).order("year", desc=True).execute()
            all_uploads = overview_resp.data or []
        except Exception as e:
            st.error(f"Could not load data: {e}")

        if not all_uploads:
            st.info("No monthly data uploaded yet. Use the 'Monthly Upload' tab to get started.")
        else:
            df_uploads = pd.DataFrame(all_uploads)

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Records", len(df_uploads))
            col2.metric("Total CO2 (kg)", f"{df_uploads['co2_kg'].sum():,.1f}")
            col3.metric("Locations Active", df_uploads['location_name'].nunique())
            docs_with_file = df_uploads[df_uploads['file_url'].str.len() > 0] if 'file_url' in df_uploads.columns else pd.DataFrame()
            col4.metric("Evidence Coverage", f"{len(docs_with_file) / len(df_uploads) * 100:.0f}%")

            st.markdown("---")

            with st.container(border=True):
                st.markdown("**Filter**")
                fc1, fc2, fc3 = st.columns(3)
                with fc1:
                    filter_loc = st.multiselect("Location", options=sorted(df_uploads['location_name'].unique()), default=sorted(df_uploads['location_name'].unique()))
                with fc2:
                    filter_year = st.multiselect("Year", options=sorted(df_uploads['year'].unique(), reverse=True), default=sorted(df_uploads['year'].unique(), reverse=True))
                with fc3:
                    filter_cat = st.multiselect("Category", options=sorted(df_uploads['category'].unique()), default=sorted(df_uploads['category'].unique()))

            df_filtered = df_uploads[
                df_uploads['location_name'].isin(filter_loc) &
                df_uploads['year'].isin(filter_year) &
                df_uploads['category'].isin(filter_cat)
            ]

            if not df_filtered.empty:
                st.markdown("### CO2 by Location & Category")
                chart_data = df_filtered.groupby(['location_name', 'category'])['co2_kg'].sum().reset_index()
                chart = alt.Chart(chart_data).mark_bar().encode(
                    x=alt.X('location_name:N', title='Location'),
                    y=alt.Y('co2_kg:Q', title='CO2 (kg)'),
                    color=alt.Color('category:N'),
                    tooltip=['location_name', 'category', 'co2_kg']
                ).properties(height=300)
                st.altair_chart(chart, use_container_width=True)

            st.markdown("---")
            st.markdown("### All Records")
            display_cols = ['location_name', 'year', 'month', 'category', 'value_raw', 'unit', 'co2_kg', 'notes']
            df_display = df_filtered[display_cols].copy()
            df_display.columns = ['Location', 'Year', 'Month', 'Category', 'Value', 'Unit', 'CO2 (kg)', 'Notes']
            st.dataframe(df_display, use_container_width=True, hide_index=True)

            st.markdown("### Uploaded Documents")
            if 'file_url' in df_filtered.columns:
                docs = df_filtered[df_filtered['file_url'].str.len() > 0][['location_name', 'year', 'month', 'category', 'file_url']]
                if not docs.empty:
                    for _, row in docs.iterrows():
                        with st.container(border=True):
                            dc1, dc2, dc3 = st.columns([2, 2, 1])
                            dc1.markdown(f"**{row['location_name']}** — {row['month']} {row['year']}")
                            dc2.caption(row['category'])
                            dc3.markdown(f"[View Document]({row['file_url']})")
                else:
                    st.info("No documents uploaded yet.")

            st.markdown("---")
            with st.expander("Delete a Record"):
                if 'id' in df_filtered.columns:
                    del_options = {
                        f"ID {r['id']} — {r['location_name']} | {r['month']} {r['year']} | {r['category']}": r['id']
                        for _, r in df_filtered.iterrows()
                    }
                    selected_del = st.selectbox("Select record to delete", list(del_options.keys()))
                    if st.button("Delete Selected Record", type="primary"):
                        try:
                            supabase.table("esg_monthly_uploads").delete().eq("id", del_options[selected_del]).execute()
                            st.success("Record deleted.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

elif menu == "Settings":
    st.header("Settings")
    st.info("Settings coming soon.")
    st.markdown("### Two-Factor Authentication")
    if st.button("Setup Authenticator App"):
        qr_code, secret = setup_mfa()
        if qr_code:
            st.image(qr_code, caption="Scan this with Google Authenticator or Authy")
            st.code(secret, language=None)
            st.caption("Or enter the secret key manually in your app.")
            with st.form("confirm_mfa_form"):
                confirm_code = st.text_input("Confirm with a code from your app", max_chars=6)
                if st.form_submit_button("Confirm & Activate"):
                    if verify_mfa(confirm_code):
                        st.success("Two-factor authentication is now active.")
