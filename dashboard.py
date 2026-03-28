import streamlit as st 
import json
from db import collection, db
from bson import ObjectId
from search import render_search_module
from enrich import enrich_and_update, enrich_pdf_metadata
from pdf_extractor import process_pdf
from ml.recommender import get_similar_papers
from admin.user_management import show_user_management
from admin.paper_management import show_paper_management
from admin.admin_analytics import show_admin_analytics
from admin.logger import log_auth, log_search, log_admin, log_perf
from summarizer import render_summary_card
from qa import render_qa_panel
import time
import pandas as pd
from collections import Counter
import logging
from datetime import datetime, timezone, timedelta
import re
from io import BytesIO
import plotly.express as px
import plotly.graph_objects as go

from file_storage import save_pdf_to_gridfs, download_pdf_from_gridfs
from auth.login_view import render_auth_page, users_collection

logging.getLogger("streamlit.runtime.media_file_handler").setLevel(logging.ERROR)

st.set_page_config(
    page_title="MetaScan",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🔬"
)

# ============================================================
# GLOBAL CSS — Premium Research Terminal Aesthetic
# ============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;700;800&family=Inter:wght@300;400;500&display=swap');

/* ── Root Variables ── */
:root {
    --bg:        #070B0F;
    --surface:   #0D1117;
    --surface2:  #131920;
    --border:    rgba(255,255,255,0.06);
    --border-hi: rgba(0,224,255,0.25);
    --accent:    #00E0FF;
    --accent2:   #00FF94;
    --accent3:   #FF6B35;
    --text:      #E8EDF2;
    --muted:     #5A6472;
    --font-head: 'Syne', sans-serif;
    --font-mono: 'Space Mono', monospace;
    --font-body: 'Inter', sans-serif;
}

/* ── Base ── */
.stApp {
    background: var(--bg) !important;
    font-family: var(--font-body) !important;
    color: var(--text) !important;
}

/* Scanline overlay */
.stApp::before {
    content: '';
    position: fixed;
    inset: 0;
    background: repeating-linear-gradient(
        0deg,
        transparent,
        transparent 2px,
        rgba(0,224,255,0.012) 2px,
        rgba(0,224,255,0.012) 4px
    );
    pointer-events: none;
    z-index: 0;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: var(--surface) !important;
    border-right: 1px solid var(--border) !important;
}

[data-testid="stSidebar"]::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
}

/* ── Sidebar Buttons ── */
[data-testid="stSidebar"] .stButton button {
    background: transparent !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
    color: var(--text) !important;
    font-family: var(--font-mono) !important;
    font-size: 11px !important;
    letter-spacing: 0.5px !important;
    padding: 10px 14px !important;
    width: 100% !important;
    text-align: left !important;
    transition: all 0.15s ease !important;
    margin-bottom: 2px !important;
}

[data-testid="stSidebar"] .stButton button:hover {
    background: rgba(0,224,255,0.06) !important;
    border-color: var(--accent) !important;
    color: var(--accent) !important;
    transform: translateX(4px) !important;
}

/* ── Main Buttons ── */
.stButton button {
    background: transparent !important;
    border: 1px solid var(--border-hi) !important;
    border-radius: 6px !important;
    color: var(--accent) !important;
    font-family: var(--font-mono) !important;
    font-size: 12px !important;
    letter-spacing: 0.5px !important;
    transition: all 0.15s ease !important;
}

.stButton button:hover {
    background: rgba(0,224,255,0.08) !important;
    border-color: var(--accent) !important;
    box-shadow: 0 0 20px rgba(0,224,255,0.15) !important;
}

/* Primary buttons */
.stButton button[kind="primary"] {
    background: linear-gradient(135deg, rgba(0,224,255,0.15), rgba(0,255,148,0.1)) !important;
    border-color: var(--accent) !important;
}

/* ── Inputs ── */
.stTextInput input, .stSelectbox select {
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
    color: var(--text) !important;
    font-family: var(--font-mono) !important;
    font-size: 12px !important;
}

.stTextInput input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px rgba(0,224,255,0.1) !important;
}

/* ── Expanders ── */
[data-testid="stExpander"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    margin-bottom: 8px !important;
    overflow: hidden !important;
}

[data-testid="stExpander"]:hover {
    border-color: rgba(0,224,255,0.2) !important;
}

[data-testid="stExpander"] summary {
    font-family: var(--font-head) !important;
    font-weight: 600 !important;
    color: var(--text) !important;
    padding: 14px 18px !important;
}

/* ── Metrics ── */
[data-testid="stMetric"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    padding: 16px !important;
}

/* ── Dataframes ── */
[data-testid="stDataFrame"] {
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    overflow: hidden !important;
}

/* ── Alerts ── */
.stSuccess, .stInfo, .stWarning, .stError {
    border-radius: 8px !important;
    font-family: var(--font-mono) !important;
    font-size: 12px !important;
}

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    background: var(--surface) !important;
    border: 1px dashed rgba(0,224,255,0.2) !important;
    border-radius: 10px !important;
}

/* ── Dividers ── */
hr {
    border-color: var(--border) !important;
    margin: 20px 0 !important;
}

/* ── Headings ── */
h1, h2, h3 {
    font-family: var(--font-head) !important;
    letter-spacing: -0.3px !important;
}

/* ── Captions ── */
.stCaption, caption {
    font-family: var(--font-mono) !important;
    font-size: 11px !important;
    color: var(--muted) !important;
}

/* ── Tabs ── */
[data-testid="stTabs"] [data-baseweb="tab"] {
    font-family: var(--font-mono) !important;
    font-size: 12px !important;
    letter-spacing: 0.5px !important;
}

/* ── Spinner ── */
[data-testid="stSpinner"] {
    color: var(--accent) !important;
}

/* ── Custom scrollbar ── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--muted); border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: var(--accent); }
</style>
""", unsafe_allow_html=True)


# ============================================================
# HELPERS
# ============================================================
def safe_filename(name):
    if not name:
        return "paper.pdf"
    name = re.sub(r"[\r\n\t]", " ", str(name))
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    return name.strip() + ".pdf"

def normalize_for_duplicate_check(text):
    if not text:
        return ""
    text = str(text).lower().strip()
    text = re.sub(r"https?://(dx\.)?doi\.org/", "", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s./-]", "", text)
    return text.strip()

def get_pdf_bytes_cached(file_id):
    if not file_id:
        return None
    cache_key = f"pdf_blob_{str(file_id)}"
    if cache_key not in st.session_state:
        pdf_bytes = download_pdf_from_gridfs(file_id)
        if not pdf_bytes:
            return None
        st.session_state[cache_key] = pdf_bytes
    return st.session_state[cache_key]

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None

def is_admin():
    return st.session_state.get("user") is not None and st.session_state.user.get("role") == "admin"

def admin_only():
    if not is_admin():
        st.error("⛔ Unauthorized access")
        st.stop()

if not st.session_state.logged_in:
    render_auth_page()

if "active_module" not in st.session_state:
    st.session_state.active_module = "Dashboard"


# ============================================================
# BOOKMARK HELPERS
# ============================================================
def add_bookmark(user_email, paper_id):
    users_collection.update_one({"email": user_email}, {"$addToSet": {"bookmarks": ObjectId(paper_id)}})

def remove_bookmark(user_email, paper_id):
    users_collection.update_one({"email": user_email}, {"$pull": {"bookmarks": ObjectId(paper_id)}})

def get_user_bookmarks(user_email):
    user = users_collection.find_one({"email": user_email})
    return user.get("bookmarks", []) if user else []


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    # Logo block
    st.markdown("""
    <div style="padding: 20px 4px 16px; border-bottom: 1px solid rgba(255,255,255,0.06); margin-bottom: 16px;">
        <div style="font-family:'Syne',sans-serif; font-size:22px; font-weight:800; letter-spacing:-0.5px;">
            <span style="color:#00E0FF;">META</span><span style="color:#E8EDF2;">SCAN</span>
        </div>
        <div style="font-family:'Space Mono',monospace; font-size:10px; color:#5A6472; margin-top:3px; letter-spacing:1px;">
            RESEARCH INTELLIGENCE v2.0
        </div>
    </div>
    """, unsafe_allow_html=True)

    # User badge
    if st.session_state.get("user"):
        u = st.session_state.user
        role_color = "#FF6B35" if u.get("role") == "admin" else "#00FF94"
        st.markdown(f"""
        <div style="
            background: rgba(0,224,255,0.05);
            border: 1px solid rgba(0,224,255,0.12);
            border-radius: 8px;
            padding: 10px 12px;
            margin-bottom: 16px;
            font-family: 'Space Mono', monospace;
        ">
            <div style="font-size:10px; color:#5A6472; letter-spacing:1px;">SIGNED IN AS</div>
            <div style="font-size:13px; color:#E8EDF2; font-weight:600; margin-top:2px;">{u['username']}</div>
            <div style="display:inline-block; margin-top:4px; padding:2px 8px; background:rgba(0,0,0,0.3); border-radius:4px; font-size:10px; color:{role_color}; letter-spacing:1px;">{u.get('role','user').upper()}</div>
        </div>
        """, unsafe_allow_html=True)

    def navigate(module_name, clear_results=True):
        for k in list(st.session_state.keys()):
            if k.startswith("pdf_blob_"):
                del st.session_state[k]
        st.session_state.active_module = module_name
        if clear_results:
            st.session_state.results = []
        st.rerun()

    st.markdown('<div style="font-family:\'Space Mono\',monospace; font-size:10px; color:#5A6472; letter-spacing:2px; margin-bottom:8px;">NAVIGATE</div>', unsafe_allow_html=True)

    nav_items = [
        ("🏠", "Dashboard", "Dashboard"),
        ("📤", "Upload", "Upload Documents"),
        ("🔍", "Search", "Search Papers"),
        ("⭐", "Bookmarks", "Bookmarks"),
        ("📁", "My Uploads", "My Uploads"),
        ("📊", "Analytics", "Analytics"),
    ]

    for icon, module, label in nav_items:
        active = st.session_state.active_module == module
        if st.button(f"{icon}  {label}", key=f"nav_{module}", use_container_width=True):
            navigate(module, clear_results=(module != "Search"))

    if is_admin():
        st.markdown('<div style="font-family:\'Space Mono\',monospace; font-size:10px; color:#FF6B35; letter-spacing:2px; margin: 16px 0 8px;">ADMIN</div>', unsafe_allow_html=True)
        admin_items = [
            ("👥", "UserManagement", "User Management"),
            ("🗂️", "PaperManagement", "Paper Management"),
            ("📊", "AdminAnalytics", "Admin Analytics"),
        ]
        for icon, module, label in admin_items:
            if st.button(f"{icon}  {label}", key=f"nav_{module}", use_container_width=True):
                navigate(module)

    st.markdown("---")
    if st.button("⏻  Logout", key="nav_logout", use_container_width=True):
        for k in list(st.session_state.keys()):
            if k.startswith("pdf_bytes_"):
                del st.session_state[k]
        st.session_state.logged_in = False
        st.session_state.user = None
        st.session_state.active_module = "Dashboard"
        st.session_state.results = []
        st.rerun()


# ============================================================
# PAGE HEADER COMPONENT
# ============================================================
def page_header(title: str, subtitle: str = "", accent: str = "#00E0FF"):
    st.markdown(f"""
    <div style="
        padding: 28px 0 20px;
        border-bottom: 1px solid rgba(255,255,255,0.06);
        margin-bottom: 28px;
    ">
        <div style="
            font-family: 'Space Mono', monospace;
            font-size: 10px;
            color: {accent};
            letter-spacing: 3px;
            margin-bottom: 8px;
            opacity: 0.8;
        ">METASCAN // {title.upper()}</div>
        <div style="
            font-family: 'Syne', sans-serif;
            font-size: 32px;
            font-weight: 800;
            color: #E8EDF2;
            line-height: 1.1;
            letter-spacing: -0.5px;
        ">{title}</div>
        {f'<div style="font-family:Inter,sans-serif; font-size:14px; color:#5A6472; margin-top:6px;">{subtitle}</div>' if subtitle else ''}
    </div>
    """, unsafe_allow_html=True)


def stat_card(icon, value, label, color="#00E0FF"):
    return f"""
    <div style="
        background: #0D1117;
        border: 1px solid rgba(255,255,255,0.06);
        border-top: 2px solid {color};
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        transition: all 0.2s ease;
    ">
        <div style="font-size:28px; margin-bottom:8px;">{icon}</div>
        <div style="font-family:'Space Mono',monospace; font-size:28px; font-weight:700; color:{color}; line-height:1;">{value}</div>
        <div style="font-family:'Space Mono',monospace; font-size:10px; color:#5A6472; margin-top:6px; letter-spacing:1px;">{label.upper()}</div>
    </div>
    """


# ============================================================
# DASHBOARD
# ============================================================
if st.session_state.active_module == "Dashboard":
    total_papers = collection.count_documents({})
    total_categories = len(collection.distinct("category"))
    total_authors = len(collection.distinct("authors"))
    latest_docs = list(collection.find({}, {"title": 1, "category": 1, "year": 1}).sort("_id", -1).limit(6))

    page_header("Dashboard", "Real-time overview of your research intelligence system")

    # HERO SECTION
    st.markdown(f"""
    <div style="
        position: relative;
        overflow: hidden;
        background: #0D1117;
        border: 1px solid rgba(0,224,255,0.12);
        border-radius: 16px;
        padding: 48px 48px 44px;
        margin-bottom: 28px;
    ">
        <div style="position:absolute; top:-80px; left:-60px; width:400px; height:400px;
            background: radial-gradient(circle, rgba(0,224,255,0.07) 0%, transparent 70%);
            pointer-events:none;"></div>
        <div style="position:absolute; bottom:-100px; right:-40px; width:350px; height:350px;
            background: radial-gradient(circle, rgba(0,255,148,0.06) 0%, transparent 70%);
            pointer-events:none;"></div>
        <div style="position:absolute; inset:0; opacity:0.25;
            background-image: radial-gradient(rgba(0,224,255,0.35) 1px, transparent 1px);
            background-size: 28px 28px; pointer-events:none;"></div>
        <div style="position:relative; z-index:1;">
            <div style="font-family:'Space Mono',monospace; font-size:10px; color:#00E0FF;
                letter-spacing:4px; margin-bottom:14px; opacity:0.75;">[ RESEARCH INTELLIGENCE SYSTEM ]</div>
            <div style="font-family:'Syne',sans-serif; font-size:clamp(32px,4vw,52px); font-weight:800;
                line-height:1.05; letter-spacing:-1px; margin-bottom:16px;">
                <span style="color:#E8EDF2;">Discover.</span>
                <span style="background:linear-gradient(90deg,#00E0FF,#00FF94);-webkit-background-clip:text;-webkit-text-fill-color:transparent;"> Analyze.</span>
                <span style="color:#E8EDF2;"> Index.</span>
            </div>
            <div style="font-family:'Inter',sans-serif; font-size:15px; color:#5A6472;
                max-width:580px; line-height:1.7; margin-bottom:28px;">
                MetaScan automatically extracts, enriches, and indexes academic research using
                NLP pipelines, ML classification, and AI-powered summarization.
            </div>
            <div style="display:flex; flex-wrap:wrap; gap:8px;">
                <span style="font-family:'Space Mono',monospace; font-size:10px; padding:5px 12px;
                    border:1px solid rgba(0,224,255,0.2); border-radius:20px; color:#00E0FF;
                    background:rgba(0,224,255,0.06);">⚡ NLP Enrichment</span>
                <span style="font-family:'Space Mono',monospace; font-size:10px; padding:5px 12px;
                    border:1px solid rgba(0,255,148,0.2); border-radius:20px; color:#00FF94;
                    background:rgba(0,255,148,0.06);">🧠 AI Summarization</span>
                <span style="font-family:'Space Mono',monospace; font-size:10px; padding:5px 12px;
                    border:1px solid rgba(167,139,250,0.2); border-radius:20px; color:#A78BFA;
                    background:rgba(167,139,250,0.06);">🔍 Semantic Search</span>
                <span style="font-family:'Space Mono',monospace; font-size:10px; padding:5px 12px;
                    border:1px solid rgba(255,107,53,0.2); border-radius:20px; color:#FF6B35;
                    background:rgba(255,107,53,0.06);">📊 ML Classification</span>
                <span style="font-family:'Space Mono',monospace; font-size:10px; padding:5px 12px;
                    border:1px solid rgba(90,100,114,0.3); border-radius:20px; color:#5A6472;
                    background:rgba(255,255,255,0.03);">☁️ MongoDB GridFS</span>
                <span style="font-family:'Space Mono',monospace; font-size:10px; padding:5px 12px;
                    border:1px solid rgba(0,224,255,0.2); border-radius:20px; color:#00E0FF;
                    background:rgba(0,224,255,0.06);">💬 Paper Q&A</span>
            </div>
        </div>
        <div style="position:absolute; top:20px; right:24px; display:flex; align-items:center;
            gap:7px; font-family:'Space Mono',monospace; font-size:10px; color:#00FF94;">
            <span style="display:inline-block; width:7px; height:7px; background:#00FF94;
                border-radius:50%; box-shadow:0 0 8px #00FF94;"></span>
            SYSTEM ONLINE
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Stats row
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(stat_card("📄", total_papers, "Papers Indexed", "#00E0FF"), unsafe_allow_html=True)
    with c2:
        st.markdown(stat_card("🏷️", total_categories, "Categories", "#00FF94"), unsafe_allow_html=True)
    with c3:
        st.markdown(stat_card("✍️", total_authors, "Unique Authors", "#FF6B35"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Pipeline visualization
    st.markdown("""
    <div style="
        background: #0D1117;
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 24px;
    ">
        <div style="font-family:'Space Mono',monospace; font-size:10px; color:#5A6472; letter-spacing:2px; margin-bottom:16px;">PROCESSING PIPELINE</div>
        <div style="display:flex; align-items:center; gap:0; overflow-x:auto;">
            <div style="flex:1; text-align:center; padding:12px; background:rgba(0,224,255,0.06); border:1px solid rgba(0,224,255,0.15); border-radius:8px 0 0 8px;">
                <div style="font-size:20px; margin-bottom:4px;">📤</div>
                <div style="font-family:'Space Mono',monospace; font-size:10px; color:#00E0FF;">UPLOAD</div>
            </div>
            <div style="color:#5A6472; padding:0 4px; font-size:18px;">→</div>
            <div style="flex:1; text-align:center; padding:12px; background:rgba(0,255,148,0.04); border:1px solid rgba(0,255,148,0.12); border-radius:0;">
                <div style="font-size:20px; margin-bottom:4px;">📄</div>
                <div style="font-family:'Space Mono',monospace; font-size:10px; color:#00FF94;">EXTRACT</div>
            </div>
            <div style="color:#5A6472; padding:0 4px; font-size:18px;">→</div>
            <div style="flex:1; text-align:center; padding:12px; background:rgba(255,107,53,0.04); border:1px solid rgba(255,107,53,0.12); border-radius:0;">
                <div style="font-size:20px; margin-bottom:4px;">🧠</div>
                <div style="font-family:'Space Mono',monospace; font-size:10px; color:#FF6B35;">ENRICH</div>
            </div>
            <div style="color:#5A6472; padding:0 4px; font-size:18px;">→</div>
            <div style="flex:1; text-align:center; padding:12px; background:rgba(167,139,250,0.04); border:1px solid rgba(167,139,250,0.12); border-radius:0;">
                <div style="font-size:20px; margin-bottom:4px;">🏷️</div>
                <div style="font-family:'Space Mono',monospace; font-size:10px; color:#A78BFA;">INDEX</div>
            </div>
            <div style="color:#5A6472; padding:0 4px; font-size:18px;">→</div>
            <div style="flex:1; text-align:center; padding:12px; background:rgba(0,224,255,0.06); border:1px solid rgba(0,224,255,0.15); border-radius:0 8px 8px 0;">
                <div style="font-size:20px; margin-bottom:4px;">🔎</div>
                <div style="font-family:'Space Mono',monospace; font-size:10px; color:#00E0FF;">SEARCH</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Recent papers
    st.markdown("""
    <div style="font-family:'Space Mono',monospace; font-size:10px; color:#5A6472; letter-spacing:2px; margin-bottom:12px;">
        RECENTLY INDEXED
    </div>
    """, unsafe_allow_html=True)

    if latest_docs:
        for doc in latest_docs:
            cat = doc.get("category", "Unassigned")
            year = doc.get("year", "")
            cat_colors = {
                "AI / Machine Learning": "#00E0FF",
                "Data Management": "#00FF94",
                "Healthcare / Bioinformatics": "#FF6B35",
                "Natural Language Processing": "#A78BFA",
            }
            c = cat_colors.get(cat, "#5A6472")
            st.markdown(f"""
            <div style="
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 12px 16px;
                background: #0D1117;
                border: 1px solid rgba(255,255,255,0.05);
                border-left: 3px solid {c};
                border-radius: 0 8px 8px 0;
                margin-bottom: 6px;
            ">
                <div style="flex:1; font-family:'Syne',sans-serif; font-size:14px; font-weight:600; color:#E8EDF2;">{doc.get('title','Untitled')}</div>
                <div style="font-family:'Space Mono',monospace; font-size:10px; color:{c}; white-space:nowrap; padding:3px 8px; background:rgba(0,0,0,0.4); border-radius:4px;">{cat}</div>
                {f'<div style="font-family:Space Mono,monospace; font-size:10px; color:#5A6472;">{year}</div>' if year else ''}
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="text-align:center; padding:48px; color:#5A6472; font-family:'Space Mono',monospace; font-size:12px; border:1px dashed rgba(255,255,255,0.06); border-radius:10px;">
            NO DOCUMENTS INDEXED YET<br>
            <span style="font-size:10px; opacity:0.6;">Upload a PDF to activate the system</span>
        </div>
        """, unsafe_allow_html=True)


# ============================================================
# UPLOAD
# ============================================================
uploaded_file = None
if st.session_state.active_module == "Upload":
    page_header("Upload Documents", "Ingest PDF or JSON research papers into the knowledge base", "#00FF94")
    uploaded_file = st.file_uploader("Drop a PDF or JSON file", type=["json", "pdf"])

if st.session_state.active_module == "Upload" and uploaded_file:
    if uploaded_file.name.endswith(".json"):
        data = json.load(uploaded_file)
        if isinstance(data, list):
            for doc in data:
                if not collection.find_one({"title": doc.get("title")}):
                    collection.insert_one(doc)
            enrich_and_update()
            st.success("✅ JSON uploaded & enriched")

    elif uploaded_file.name.endswith(".pdf"):
        file_id = save_pdf_to_gridfs(uploaded_file)
        uploaded_file.seek(0)
        user_email = st.session_state.user["email"]
        filename = uploaded_file.name

        t0 = time.perf_counter()
        paper_data = process_pdf(uploaded_file) or {
            "title": uploaded_file.name.replace(".pdf", ""),
            "abstract": "", "keywords": [], "authors": [],
            "year": "", "category": "Uncategorized", "source": "PDF upload"
        }
        log_perf("pdf_extract", int((time.perf_counter() - t0) * 1000),
                 meta={"user": user_email, "filename": filename, "file_id": str(file_id)})

        try:
            t1 = time.perf_counter()
            enriched_data = enrich_pdf_metadata(paper_data)
            log_perf("metadata_enrich", int((time.perf_counter() - t1) * 1000),
                     meta={"user": user_email, "filename": filename, "file_id": str(file_id)})
        except Exception as e:
            st.warning(f"⚠️ Enrichment failed: {e}")
            enriched_data = paper_data

        enriched_data.pop("raw_text", None)
        enriched_data["file_id"] = file_id

        st.markdown("#### 🧾 Extracted Metadata")
        st.json(enriched_data)

        doi = enriched_data.get("doi")
        title = enriched_data.get("title", "").strip()
        norm_doi = normalize_for_duplicate_check(doi)
        norm_title = normalize_for_duplicate_check(title)
        existing = None

        if norm_doi:
            for doc in collection.find({}, {"doi": 1, "title": 1}):
                if normalize_for_duplicate_check(doc.get("doi", "")) == norm_doi:
                    existing = doc; break
        if not existing and norm_title:
            for doc in collection.find({}, {"title": 1, "doi": 1}):
                if normalize_for_duplicate_check(doc.get("title", "")) == norm_title:
                    existing = doc; break

        if existing:
            st.warning(f"⚠️ Duplicate detected: {existing.get('title', 'Untitled')}")
        else:
            try:
                enriched_data["uploaded_by"] = user_email
                enriched_data["uploaded_at"] = datetime.now(timezone.utc)
                collection.insert_one(enriched_data)
                st.success("✅ PDF stored and indexed successfully!")
            except Exception as e:
                st.error(f"❌ Database insert failed: {e}")


# ============================================================
# SEARCH
# ============================================================
if st.session_state.active_module == "Search":
    render_search_module(
        safe_filename=safe_filename,
        get_pdf_bytes_cached=get_pdf_bytes_cached,
        add_bookmark=add_bookmark,
        remove_bookmark=remove_bookmark,
        get_user_bookmarks=get_user_bookmarks
    )


# ============================================================
# BOOKMARKS
# ============================================================
if st.session_state.active_module == "Bookmarks":
    page_header("Bookmarks", "Your saved research papers", "#A78BFA")

    user_bookmark_ids = [
        ObjectId(pid) if isinstance(pid, str) else pid
        for pid in get_user_bookmarks(st.session_state.user["email"])
    ]

    if user_bookmark_ids:
        bookmarked_docs = collection.find({"_id": {"$in": user_bookmark_ids}})
        for doc in bookmarked_docs:
            paper_id = doc["_id"]
            with st.expander(doc.get("title", "Untitled")):
                st.markdown(f"**Category:** `{doc.get('category', '—')}`")
                st.markdown(f"**Abstract:** {doc.get('abstract', 'N/A')}")
                st.markdown("### ✨ AI Summary")
                render_summary_card(doc, key_prefix=f"bm_{paper_id}")
                st.divider()                                         
                st.markdown("### 💬 Ask This Paper")                
                render_qa_panel(doc, key_prefix=f"bm_{paper_id}") 
            if "file_id" in doc:
                if st.button("🔗 Generate Download Link", key=f"prep_{paper_id}"):
                    pdf_data = get_pdf_bytes_cached(doc["file_id"])
                    if pdf_data:
                        st.download_button("📥 Download PDF", data=pdf_data,
                            file_name=safe_filename(doc.get("title")), mime="application/pdf",
                            key=f"dl_btn_{paper_id}")
                    else:
                        st.error("Could not retrieve PDF.")
    else:
        st.markdown("""
        <div style="text-align:center; padding:64px 24px; color:#5A6472; font-family:'Space Mono',monospace; font-size:12px; border:1px dashed rgba(255,255,255,0.06); border-radius:10px;">
            NO BOOKMARKS YET<br>
            <span style="font-size:10px; opacity:0.6;">Star papers in Search to save them here</span>
        </div>
        """, unsafe_allow_html=True)


# ============================================================
# MY UPLOADS
# ============================================================
if st.session_state.active_module == "My Uploads":
    page_header("My Uploads", "Papers you have contributed to the knowledge base", "#FF6B35")

    user_email = st.session_state.user["email"]
    my_uploads = list(collection.find({"uploaded_by": user_email}))

    if not my_uploads:
        st.markdown("""
        <div style="text-align:center; padding:64px 24px; color:#5A6472; font-family:'Space Mono',monospace; font-size:12px; border:1px dashed rgba(255,255,255,0.06); border-radius:10px;">
            NO UPLOADS YET
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="font-family:'Space Mono',monospace; font-size:11px; color:#5A6472; margin-bottom:16px;">
            {len(my_uploads)} DOCUMENT{'S' if len(my_uploads) != 1 else ''} INDEXED
        </div>
        """, unsafe_allow_html=True)

        for i, doc in enumerate(my_uploads, 1):
            paper_id = doc["_id"]
            with st.expander(f"{i}. {doc.get('title', 'Untitled')}"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown("**Authors**")
                    authors = doc.get("authors", [])
                    st.write(", ".join(authors) if authors else "Not available")
                with col2:
                    st.markdown("**Year**")
                    st.write(doc.get("year", "Not available"))
                with col3:
                    st.markdown("**Category**")
                    st.write(doc.get("category", "Not available"))

                st.divider()
                st.markdown("### 🧠 Abstract")
                st.write(doc.get("abstract", "Abstract not available"))

                st.markdown("### ✨ AI Summary")
                render_summary_card(doc, key_prefix=f"upload_{paper_id}")
                st.divider()                                             
                st.markdown("### 💬 Ask This Paper")                   
                render_qa_panel(doc, key_prefix=f"upload_{paper_id}")

                keywords = doc.get("keywords", [])
                if isinstance(keywords, list) and keywords:
                    st.markdown("### 🏷️ Keywords")
                    st.write(", ".join(keywords))

                entities = doc.get("entities") or doc.get("topics", [])
                if isinstance(entities, list) and entities:
                    st.markdown("### 🧩 Entities")
                    st.write(", ".join(entities))

                st.divider()
                uploaded_at = doc.get("uploaded_at")
                if uploaded_at:
                    st.caption(f"📅 {uploaded_at.strftime('%Y-%m-%d %H:%M')}")

            if "file_id" in doc:
                if st.button("🔗 Generate Download Link", key=f"prep_{paper_id}"):
                    pdf_data = get_pdf_bytes_cached(doc["file_id"])
                    if pdf_data:
                        st.download_button("📥 Download PDF", data=pdf_data,
                            file_name=safe_filename(doc.get("title")), mime="application/pdf",
                            key=f"dl_btn_{paper_id}")
                    else:
                        st.error("Could not retrieve PDF.")


# ============================================================
# ADMIN
# ============================================================
if st.session_state.active_module == "UserManagement":
    admin_only(); show_user_management()

if st.session_state.active_module == "PaperManagement":
    admin_only(); show_paper_management()

if st.session_state.active_module == "AdminAnalytics":
    admin_only(); show_admin_analytics()


# ============================================================
# ANALYTICS
# ============================================================
if st.session_state.active_module == "Analytics":
    page_header("Analytics", "Research corpus intelligence and usage patterns", "#A78BFA")

    docs = list(collection.find())
    if not docs:
        st.info("No documents available yet.")
    else:
        df = pd.DataFrame(docs)

        m1, m2, m3 = st.columns(3)
        with m1:
            st.markdown(stat_card("📄", len(df), "Total Papers", "#00E0FF"), unsafe_allow_html=True)
        with m2:
            st.markdown(stat_card("📚", df['category'].nunique() if 'category' in df else 0, "Categories", "#00FF94"), unsafe_allow_html=True)
        with m3:
            total_bookmarks = sum(len(u.get("bookmarks", [])) for u in users_collection.find())
            st.markdown(stat_card("⭐", total_bookmarks, "Total Bookmarks", "#FF6B35"), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        col_left, col_right = st.columns(2)

        with col_left:
            if "category" in df:
                st.markdown("""<div style="font-family:'Space Mono',monospace; font-size:10px; color:#5A6472; letter-spacing:2px; margin-bottom:12px;">CATEGORY DISTRIBUTION</div>""", unsafe_allow_html=True)
                cat_df = df["category"].value_counts().reset_index()
                cat_df.columns = ["Category", "Count"]
                fig_cat = go.Figure(go.Pie(
                    labels=cat_df["Category"], values=cat_df["Count"],
                    hole=0.65,
                    marker=dict(colors=["#00E0FF","#00FF94","#FF6B35","#A78BFA","#F59E0B","#EF4444","#06B6D4","#84CC16"]),
                    textinfo="percent",
                    hovertemplate="<b>%{label}</b><br>%{value} papers<extra></extra>"
                ))
                fig_cat.update_layout(
                    height=320, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=0,r=0,t=0,b=0),
                    legend=dict(font=dict(family="Space Mono", size=10, color="#5A6472"), bgcolor="rgba(0,0,0,0)"),
                    showlegend=True,
                )
                st.plotly_chart(fig_cat, use_container_width=True, key="cat_donut")

        with col_right:
            if "year" in df:
                st.markdown("""<div style="font-family:'Space Mono',monospace; font-size:10px; color:#5A6472; letter-spacing:2px; margin-bottom:12px;">PAPERS BY YEAR</div>""", unsafe_allow_html=True)
                year_df = (df["year"].dropna().astype(str).str.extract(r"(\d{4})")[0]
                           .dropna().value_counts().sort_index().reset_index())
                year_df.columns = ["Year", "Papers"]
                fig_year = go.Figure(go.Bar(
                    x=year_df["Year"], y=year_df["Papers"],
                    marker=dict(color="#00E0FF", opacity=0.8),
                    hovertemplate="<b>%{x}</b><br>%{y} papers<extra></extra>"
                ))
                fig_year.update_layout(
                    height=320, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=0,r=0,t=0,b=0),
                    xaxis=dict(showgrid=False, color="#5A6472", tickfont=dict(family="Space Mono", size=10)),
                    yaxis=dict(gridcolor="rgba(255,255,255,0.04)", color="#5A6472", tickfont=dict(family="Space Mono", size=10)),
                    bargap=0.3,
                )
                st.plotly_chart(fig_year, use_container_width=True, key="year_bar")

        st.markdown("---")

        # Keyword analytics
        st.markdown("""<div style="font-family:'Space Mono',monospace; font-size:10px; color:#5A6472; letter-spacing:2px; margin-bottom:12px;">TOP KEYWORDS</div>""", unsafe_allow_html=True)

        if "keywords" in df:
            all_keywords = []
            for kws in df["keywords"]:
                if isinstance(kws, list):
                    all_keywords.extend(kws)

            if all_keywords:
                kw_counter = Counter(all_keywords)
                kw_df = pd.DataFrame(kw_counter.most_common(15), columns=["Keyword", "Count"])

                fig_kw = go.Figure(go.Bar(
                    x=kw_df["Count"][::-1], y=kw_df["Keyword"][::-1],
                    orientation="h",
                    marker=dict(
                        color=kw_df["Count"][::-1],
                        colorscale=[[0, "#0D3340"], [1, "#00E0FF"]],
                    ),
                    hovertemplate="<b>%{y}</b><br>%{x} papers<extra></extra>"
                ))
                fig_kw.update_layout(
                    height=400, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=0,r=0,t=0,b=0),
                    xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.04)", color="#5A6472", tickfont=dict(family="Space Mono", size=10)),
                    yaxis=dict(showgrid=False, color="#E8EDF2", tickfont=dict(family="Space Mono", size=11)),
                )
                st.plotly_chart(fig_kw, use_container_width=True, key="kw_bar")

                selected_keyword = st.selectbox("Drill into keyword", ["— select —"] + kw_df["Keyword"].tolist())
                if selected_keyword != "— select —":
                    matched = collection.find({"keywords": selected_keyword})
                    for doc in matched:
                        with st.expander(doc.get("title", "Untitled")):
                            st.write(doc.get("abstract", "Not available"))
            else:
                st.info("No keywords available.")

        st.markdown("---")
        st.markdown("""<div style="font-family:'Space Mono',monospace; font-size:10px; color:#5A6472; letter-spacing:2px; margin-bottom:12px;">MOST BOOKMARKED</div>""", unsafe_allow_html=True)

        bookmark_counts = Counter()
        for user in users_collection.find():
            for pid in user.get("bookmarks", []):
                bookmark_counts[str(pid)] += 1

        if bookmark_counts:
            for pid, count in bookmark_counts.most_common(5):
                paper = collection.find_one({"_id": ObjectId(pid)})
                if paper:
                    st.markdown(f"""
                    <div style="display:flex; justify-content:space-between; align-items:center; padding:10px 14px; background:#0D1117; border:1px solid rgba(255,255,255,0.05); border-radius:8px; margin-bottom:6px;">
                        <div style="font-family:'Syne',sans-serif; font-size:13px; font-weight:600;">{paper.get('title','Untitled')}</div>
                        <div style="font-family:'Space Mono',monospace; font-size:11px; color:#FF6B35;">⭐ {count}</div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("No bookmarks yet.")