import streamlit as st
import json
from db import collection, db
from bson import ObjectId
from search import search_docs
from enrich import enrich_and_update, enrich_pdf_metadata
from pdf_extractor import process_pdf
from ml.recommender import get_similar_papers
import pandas as pd
from collections import Counter
import logging
import bcrypt
from datetime import datetime, timezone
import re
from io import BytesIO
import plotly.express as px
logging.getLogger("streamlit.runtime.media_file_handler").setLevel(logging.ERROR)



st.set_page_config(page_title="MetaScan", layout="wide")

def safe_filename(name):
    if not name:
        return "paper.pdf"
    # Remove newlines, tabs, and illegal header characters
    name = re.sub(r'[\r\n\t]', ' ', str(name))
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    return name.strip() + ".pdf"

def get_pdf_stream(file_id):
    if not file_id:
        return None

    file_id_str = str(file_id)
    cache_key = f"pdf_stream_{file_id_str}"

    if cache_key not in st.session_state:
        pdf_bytes = download_pdf_from_gridfs(file_id)
        if not pdf_bytes:
            return None
        st.session_state[cache_key] = BytesIO(pdf_bytes)

    st.session_state[cache_key].seek(0)
    return st.session_state[cache_key]

def get_pdf_bytes_cached(file_id):
    if not file_id:
        return None

    # Ensure file_id is a string to prevent BSON/Object mismatch in keys
    file_id_str = str(file_id)
    cache_key = f"pdf_blob_{file_id_str}" # Change pdf_data_ to pdf_blob_

    if cache_key not in st.session_state:
        pdf_bytes = download_pdf_from_gridfs(file_id)
        if not pdf_bytes:
            return None
        # Store as bytes directly
        st.session_state[cache_key] = pdf_bytes

    return st.session_state[cache_key]


# NEW IMPORTS FOR GRIDFS
from file_storage import save_pdf_to_gridfs, download_pdf_from_gridfs

# ================= AUTH SETUP =================
users_collection = db["users"]

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed)

# Session defaults
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None

# ================= LOGIN / REGISTER UI =================
if not st.session_state.logged_in:
    st.markdown("## 🔐 MetaScan Authentication")

    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            user = users_collection.find_one({"email": email})
            if user and verify_password(password, user["password"]):
                st.session_state.logged_in = True
                st.session_state.user = {
                    "username": user["username"],
                    "email": user["email"],
                    "role": user["role"]
                }
                st.success("✅ Login successful")
                st.rerun()
            else:
                st.error("❌ Invalid credentials")

    with tab2:
        username = st.text_input("Username")
        reg_email = st.text_input("Register Email")
        reg_password = st.text_input("Register Password", type="password")
        confirm = st.text_input("Confirm Password", type="password")

        if st.button("Create Account"):
            if reg_password != confirm:
                st.error("❌ Passwords do not match")
            elif users_collection.find_one({"email": reg_email}):
                st.error("❌ User already exists")
            else:
                users_collection.insert_one({
                    "username": username,
                    "email": reg_email,
                    "password": hash_password(reg_password),
                    "role": "researcher",
                    "created_at": datetime.utcnow()
                })
                st.success("✅ Account created. Please login.")

    st.stop()

    # Sidebar navigation state
if "active_module" not in st.session_state:
    st.session_state.active_module = "Dashboard"

# ================= BOOKMARK HELPERS =================
def add_bookmark(user_email, paper_id):
    users_collection.update_one(
        {"email": user_email},
        {"$addToSet": {"bookmarks": ObjectId(paper_id)}}
    )

def remove_bookmark(user_email, paper_id):
    users_collection.update_one(
        {"email": user_email},
        {"$pull": {"bookmarks": ObjectId(paper_id)}}
    )

def get_user_bookmarks(user_email):
    user = users_collection.find_one({"email": user_email})
    return user.get("bookmarks", []) if user else []


# ================= MAIN DASHBOARD =================
if st.session_state.active_module == "Dashboard":

    # -------- LIVE DATA --------
    total_papers = collection.count_documents({})
    total_categories = len(collection.distinct("category"))
    total_authors = len(collection.distinct("authors"))

    latest_docs = list(
        collection.find({}, {"title": 1, "category": 1})
        .sort("_id", -1)
        .limit(5)
    )

    st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(135deg, #0E1117, #1E2025);
        color: white;
    }

    .hero-card {
        background: linear-gradient(135deg, #0F172A, #1F2937);
        padding: 40px;
        border-radius: 24px;
        box-shadow: 0 25px 60px rgba(0,0,0,0.7);
        margin-bottom: 40px;
        transform: perspective(1200px) rotateX(2deg);
    }

    .hero-title {
        font-size: 42px;
        font-weight: 800;
        text-align: center;
        background: linear-gradient(90deg, #38BDF8, #22C55E);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .hero-desc {
        text-align: center;
        color: #D1D5DB;
        font-size: 18px;
        max-width: 900px;
        margin: 14px auto 0;
        line-height: 1.6;
    }

    .glass-card {
        background: rgba(30,33,40,0.75);
        backdrop-filter: blur(14px);
        border-radius: 18px;
        padding: 22px;
        box-shadow: 0 14px 40px rgba(0,0,0,0.6);
        border: 1px solid rgba(255,255,255,0.08);
        transition: all 0.25s ease-in-out;
    }

    .glass-card:hover {
        transform: translateY(-6px) scale(1.02);
        box-shadow: 0 22px 55px rgba(0,0,0,0.75);
    }

    .metric-card {
        text-align: center;
        padding: 26px 18px;
    }

    .metric-icon {
        font-size: 34px;
        margin-bottom: 6px;
    }

    .metric-value {
        font-size: 34px;
        font-weight: 700;
        color: #38BDF8;
    }

    .metric-label {
        font-size: 14px;
        opacity: 0.75;
    }

    .section-title {
        font-size: 22px;
        font-weight: 600;
        margin-bottom: 16px;
    }

    .workflow {
        display: flex;
        gap: 16px;
        flex-wrap: wrap;
    }

    .workflow-step {
        flex: 1;
        min-width: 150px;
        text-align: center;
        padding: 18px;
    }

    .soft-divider {
        height: 1px;
        background: linear-gradient(to right, transparent, rgba(255,255,255,0.15), transparent);
        margin: 36px 0;
    }
    </style>
    """, unsafe_allow_html=True)

    # ===== HERO =====
    st.markdown("""
    <div class="hero-card">
        <div class="hero-title">MetaScan</div>
        <div class="hero-desc">
            MetaScan is an AI-powered research intelligence system that automatically extracts,
            indexes, categorizes, and enables intelligent search over academic documents using
            NLP-driven metadata enrichment and machine learning techniques.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ===== METRICS =====
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(f"""
        <div class="glass-card metric-card">
            <div class="metric-icon">📄</div>
            <div class="metric-value">{total_papers}</div>
            <div class="metric-label">Papers Indexed</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="glass-card metric-card">
            <div class="metric-icon">🏷️</div>
            <div class="metric-value">{total_categories}</div>
            <div class="metric-label">Categories</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="glass-card metric-card">
            <div class="metric-icon">✍️</div>
            <div class="metric-value">{total_authors}</div>
            <div class="metric-label">Unique Authors</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div class='soft-divider'></div>", unsafe_allow_html=True)

    # ===== PIPELINE =====
    st.markdown("<div class='section-title'>🔬 Research Processing Pipeline</div>", unsafe_allow_html=True)

    st.markdown("""
    <div class="workflow">
        <div class="glass-card workflow-step">📤 Upload PDF</div>
        <div class="glass-card workflow-step">📄 Text Extraction</div>
        <div class="glass-card workflow-step">🧠 Metadata Analysis</div>
        <div class="glass-card workflow-step">🏷️ Topic Indexing</div>
        <div class="glass-card workflow-step">🔎 Search & Insights</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div class='soft-divider'></div>", unsafe_allow_html=True)

    # ===== LIVE SNAPSHOT =====
    st.markdown("<div class='section-title'>📡 Live System Snapshot</div>", unsafe_allow_html=True)

    if latest_docs:
        for doc in latest_docs:
            st.markdown(
                f"""
                <div class="glass-card">
                    <b>{doc.get('title', 'Untitled')}</b><br>
                    <span style="color:#22C55E">Category:</span> {doc.get('category', 'Unassigned')}
                </div>
                """,
                unsafe_allow_html=True
            )
    else:
        st.markdown("""
        <div class="glass-card">
            No documents indexed yet.<br>
            Upload PDFs to activate the system.
        </div>
        """, unsafe_allow_html=True)


# Sidebar user info + logout
# ================= SIDEBAR NAVIGATION =================

st.sidebar.markdown("## 🧠 MetaScan")

if st.session_state.get("user"):
    st.sidebar.caption(f"👤 Logged in as **{st.session_state.user['username']}**")

st.sidebar.markdown("---")

def navigate(module_name, clear_results=True):
    # Clear PDF blobs to prevent MediaFileHandler mismatch and save RAM
    for k in list(st.session_state.keys()):
        if k.startswith("pdf_blob_"):
            del st.session_state[k]
            
    st.session_state.active_module = module_name
    if clear_results:
        st.session_state.results = []
    st.rerun()

if st.sidebar.button("🏠 Dashboard", use_container_width=True):
    navigate("Dashboard")

if st.sidebar.button("📤 Upload Documents", use_container_width=True):
    navigate("Upload")

if st.sidebar.button("🔍 Search Papers", use_container_width=True):
    navigate("Search", clear_results=False)

if st.sidebar.button("⭐ Bookmarks", use_container_width=True):
    navigate("Bookmarks")

if st.sidebar.button("📁 My Uploads", use_container_width=True):
    navigate("My Uploads")

if st.sidebar.button("📊 Analytics", use_container_width=True):
    navigate("Analytics")

st.sidebar.markdown("---")

if st.sidebar.button("🚪 Logout", use_container_width=True):
    # clear cached pdf bytes to avoid media.bin issues
    for k in list(st.session_state.keys()):
        if k.startswith("pdf_bytes_"):
            del st.session_state[k]

    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.active_module = "Dashboard"
    st.session_state.results = []
    st.rerun()

uploaded_file = None
if st.session_state.active_module == "Upload":
    st.subheader("📤 Upload Documents")

    uploaded_file = st.file_uploader(
        "Upload JSON or PDF",
        type=["json", "pdf"]
    )


if st.session_state.active_module == "Upload" and uploaded_file:
    if uploaded_file.name.endswith(".json"):
        data = json.load(uploaded_file)
        if isinstance(data, list):
            for doc in data:
                if not collection.find_one({"title": doc.get("title")}):
                    collection.insert_one(doc)
            enrich_and_update()
            st.sidebar.success("✅ JSON uploaded & enriched")

    elif uploaded_file.name.endswith(".pdf"):
        file_id = save_pdf_to_gridfs(uploaded_file)
        uploaded_file.seek(0)

        paper_data = process_pdf(uploaded_file) or {
            "title": uploaded_file.name.replace(".pdf", ""),
            "abstract": "",
            "keywords": [],
            "authors": [],
            "year": "",
            "category": "Uncategorized",
            "source": "PDF upload"
        }

# --- Attempt metadata enrichment ---
        try:
            enriched_data = enrich_pdf_metadata(paper_data)
        except Exception as e:
            st.warning(f"⚠️ Metadata enrichment failed: {e}")
            enriched_data = paper_data

        # 🔥 ADD THE FILE ID TO THE DOCUMENT
        enriched_data["file_id"] = file_id

        # --- Preview extracted metadata ---
        st.subheader("🧾 Extracted Metadata Preview")
        st.json(enriched_data)

        # --- Duplicate detection ---
        doi = enriched_data.get("doi")
        title = enriched_data.get("title", "").strip()

        existing = None
        if doi:
            existing = collection.find_one({"doi": doi})
        elif title:
            existing = collection.find_one({"title": {"$regex": f"^{title}$", "$options": "i"}})

        if existing:
            st.warning("⚠️ Duplicate detected — document already exists in the database.")
        else:
            try:
                enriched_data["uploaded_by"] = st.session_state.user["email"]
                enriched_data["uploaded_at"] = datetime.now(timezone.utc)
                collection.insert_one(enriched_data)
                st.success("✅ PDF stored successfully!")
                st.info("⚡ Metadata enriched (keywords, category, entities) completed.")
                logging.info(f"Inserted PDF: {title or 'Untitled'}")
            except Exception as e:
                st.error(f"❌ Database insert failed: {e}")


# ---------------- Search ----------------
if st.session_state.active_module == "Search":
    st.subheader("🔍 Search Research Papers")

    keyword = st.text_input("Keyword")
    author = st.text_input("Author")
    year = st.text_input("Year")
    category = st.text_input("Category")

    if st.button("Search"):
        st.session_state.results = search_docs(keyword, author, year, category)


# Always initialize results
if "results" not in st.session_state:
    st.session_state.results = []

if st.session_state.active_module == "Search":
    results = st.session_state.results

    if results:
        st.subheader(f"🔎 {len(results)} result(s) found")

    user_email = st.session_state.user["email"]
    bookmarks = get_user_bookmarks(user_email)

    for i, doc in enumerate(results, 1):
        paper_id = doc["_id"]
        if not paper_id:
            continue

        with st.expander(f"{i}. {doc.get('title', 'Untitled')}"):

            # ---------- HEADER ROW ----------
            h1, h2 = st.columns([12, 1])

            with h2:
                if paper_id in bookmarks:
                    if st.button("⭐", key=f"rm_{paper_id}"):
                        remove_bookmark(user_email, paper_id)
                        st.rerun()
                else:
                    if st.button("☆", key=f"bm_{paper_id}"):
                        add_bookmark(user_email, paper_id)
                        st.rerun()

            # ---------- METADATA GRID ----------
            m1, m2, m3 = st.columns(3)

            with m1:
                st.markdown("**Authors**")
                authors = doc.get("authors", [])
                st.write(", ".join(authors) if authors else "Not available")

            with m2:
                st.markdown("**Year**")
                st.write(doc.get("year", "Unknown"))

            with m3:
                st.markdown("**Category**")
                st.write(doc.get("category", "Uncategorized"))

            m4, m5 = st.columns(2)

            with m4:
                st.markdown("**DOI**")
                st.write(doc.get("doi", "Not available"))

            with m5:
                st.markdown("**Source**")
                st.write(doc.get("source", "Uploaded PDF"))

            st.divider()

            # ---------- ABSTRACT ----------
            st.markdown("### 🧠 Abstract")
            st.write(doc.get("abstract", "Abstract not available"))

            # ---------- KEYWORDS ----------
            keywords = doc.get("keywords", [])
            if isinstance(keywords, list) and keywords:
                st.markdown("### 🏷️ Keywords")
                st.write(", ".join(keywords))
            
            # ---------- TOPICS (MODEL-DERIVED) ----------
            topics = doc.get("topics", [])
            if isinstance(topics, list) and topics:
                st.markdown("### 🧠 Research Topics")
                st.write(", ".join(topics))

            # ---------- TOPICS / ENTITIES ----------
            entities = doc.get("entities")
            if isinstance(entities, list) and entities:
                st.markdown("### 🧩 Extracted Topics")
                st.write(", ".join(entities))

            # ---------- SIMILAR PAPERS ----------
            st.markdown("### 🔁 Similar Papers")
            for sp in get_similar_papers(doc.get("abstract", ""), top_n=5):
                st.markdown(
                    f"- **{sp['title']}** ({sp['category']}) — {round(sp['similarity_score'], 3)}"
                )

# ---------- PDF DOWNLOAD (LAZY LOADING) ----------
            if "file_id" in doc:
                # Use a toggle to avoid loading bytes until needed
                download_trigger = st.button("🔗 Generate Download Link", key=f"prep_{paper_id}")
                
                if download_trigger:
                    pdf_data = get_pdf_bytes_cached(doc["file_id"])
                    if pdf_data:
                        st.download_button(
                            "📥 Download PDF Now",
                            data=pdf_data,
                            file_name=safe_filename(doc.get("title")),
                            mime="application/pdf",
                            key=f"dl_btn_{paper_id}"
                        )
                    else:
                        st.error("Could not retrieve PDF from storage.")



# ================= BOOKMARKS SECTION =================
if st.session_state.active_module == "Bookmarks":
    user_bookmark_ids = [
    ObjectId(pid) if isinstance(pid, str) else pid
    for pid in get_user_bookmarks(st.session_state.user["email"])
]

    if user_bookmark_ids:
        bookmarked_docs = collection.find(
            {"_id": {"$in": user_bookmark_ids}}
        )

        for doc in bookmarked_docs:
            paper_id = doc["_id"] # <-- ADD THIS LINE
            with st.expander(doc.get("title", "Untitled")):
                st.markdown(f"**Category:** {doc.get('category')}")
                st.markdown(f"**Abstract:** {doc.get('abstract', 'N/A')}")

# ---------- PDF DOWNLOAD (LAZY LOADING) ----------
            if "file_id" in doc:
                # Use a toggle to avoid loading bytes until needed
                download_trigger = st.button("🔗 Generate Download Link", key=f"prep_{paper_id}")
                
                if download_trigger:
                    pdf_data = get_pdf_bytes_cached(doc["file_id"])
                    if pdf_data:
                        st.download_button(
                            "📥 Download PDF Now",
                            data=pdf_data,
                            file_name=safe_filename(doc.get("title")),
                            mime="application/pdf",
                            key=f"dl_btn_{paper_id}"
                        )
                    else:
                        st.error("Could not retrieve PDF from storage.")
    else:
        st.info("No bookmarks yet. Start saving papers ⭐")


# ================= MY UPLOADS SECTION =================
if st.session_state.active_module == "My Uploads":
    st.subheader("📁 My Uploaded Papers")

    user_email = st.session_state.user["email"]

    my_uploads = list(
        collection.find({"uploaded_by": user_email})
    )

    if not my_uploads:
        st.info("You haven’t uploaded any papers yet.")
    else:
        st.markdown(f"🧾 **Total uploads:** {len(my_uploads)}")

        for i, doc in enumerate(my_uploads, 1):
            paper_id = doc["_id"]  # <--- ADD THIS LINE HERE
            with st.expander(f"{i}. {doc.get('title', 'Untitled')}"):

                # ---------- METADATA GRID ----------
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

                # ---------- ABSTRACT ----------
                st.markdown("### 🧠 Abstract")
                st.write(doc.get("abstract", "Abstract not available"))

                # ---------- KEYWORDS ----------
                keywords = doc.get("keywords", [])
                if isinstance(keywords, list) and keywords:
                    st.markdown("### 🏷️ Keywords")
                    st.write(", ".join(keywords))

                # ---------- TOPICS / ENTITIES ----------
                entities = doc.get("entities") or doc.get("topics", [])
                if isinstance(entities, list) and entities:
                    st.markdown("### 🧩 Extracted Topics")
                    st.write(", ".join(entities))

                st.divider()

                # ---------- UPLOAD INFO ----------
                uploaded_at = doc.get("uploaded_at")
                if uploaded_at:
                    st.caption(
                        f"📅 Uploaded on: {uploaded_at.strftime('%Y-%m-%d %H:%M')} | 👤 Uploaded by you"
                    )
                else:
                    st.caption("👤 Uploaded by you")

# ---------- PDF DOWNLOAD (LAZY LOADING) ----------
            if "file_id" in doc:
                # Use a toggle to avoid loading bytes until needed
                download_trigger = st.button("🔗 Generate Download Link", key=f"prep_{paper_id}")
                
                if download_trigger:
                    pdf_data = get_pdf_bytes_cached(doc["file_id"])
                    if pdf_data:
                        st.download_button(
                            "📥 Download PDF Now",
                            data=pdf_data,
                            file_name=safe_filename(doc.get("title")),
                            mime="application/pdf",
                            key=f"dl_btn_{paper_id}"
                        )
                    else:
                        st.error("Could not retrieve PDF from storage.")
# ================= ANALYTICS DASHBOARD =================
if st.session_state.active_module == "Analytics":
    st.subheader("📊 Research Analytics Overview")

    docs = list(collection.find())

    if not docs:
        st.info("No documents available for analytics.")
    else:
        df = pd.DataFrame(docs)

        # ------------------ TOP METRICS (MINIMAL STYLE) ------------------
        m1, m2, m3 = st.columns(3)

        with m1:
            st.markdown(f"### 📄 {len(df)}")
            st.caption("Total Papers")

        with m2:
            st.markdown(f"### 📚 {df['category'].nunique() if 'category' in df else 0}")
            st.caption("Unique Categories")

        with m3:
            total_bookmarks = sum(len(u.get("bookmarks", [])) for u in users_collection.find())
            st.markdown(f"### ⭐ {total_bookmarks}")
            st.caption("Total Bookmarks")

        st.markdown("---")

        # ------------------ CATEGORY DISTRIBUTION (DONUT) ------------------
        if "category" in df:
            st.markdown("### 📂 Papers by Category")

            cat_df = df["category"].value_counts().reset_index()
            cat_df.columns = ["Category", "Count"]

            fig_cat = px.pie(
                cat_df,
                names="Category",
                values="Count",
                hole=0.55,
                color_discrete_sequence=px.colors.sequential.Teal
            )
            fig_cat.update_traces(textinfo="percent+label")
            fig_cat.update_layout(
                showlegend=True,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                transition_duration=800
            )

            st.plotly_chart(
                fig_cat,
                use_container_width=True,
                key="analytics_category_donut"
            )

        st.markdown("---")

        # ------------------ PAPERS PER YEAR (ANIMATED AREA) ------------------
        if "year" in df:
            st.markdown("### 📅 Papers by Year")

            year_df = (
                 df["year"]
                 .dropna()
                 .astype(str)
                 .str.extract(r"(\d{4})")[0]
                 .dropna()
                 .value_counts()
                 .sort_index()
                 .reset_index()
             )

            year_df.columns = ["Year", "Papers"]

            fig_year = px.area(
                year_df,
                x="Year",
                y="Papers",
                markers=True,
                line_shape="spline"
            )

            fig_year.update_layout(
                xaxis_title="Year",
                yaxis_title="Number of Papers",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                transition_duration=900
            )

            st.plotly_chart(
                fig_year,
                use_container_width=True,
                key="analytics_year_area"
            )


        st.markdown("---")

        # ------------------ KEYWORD ANALYTICS (UNCHANGED LOGIC) ------------------
        st.subheader("🏷️ Keyword Analytics")

        if "keywords" in df:
            all_keywords = []
            for kws in df["keywords"]:
                if isinstance(kws, list):
                    all_keywords.extend(kws)

            if all_keywords:
                kw_counter = Counter(all_keywords)
                kw_df = (
                    pd.DataFrame(kw_counter.items(), columns=["Keyword", "Count"])
                    .sort_values("Count", ascending=False)
                )

                st.markdown("### 🔝 Top Keywords")
                st.dataframe(kw_df.head(15).reset_index(drop=True))

                selected_keyword = st.selectbox(
                    "Select a keyword",
                    ["-- Select --"] + kw_df["Keyword"].tolist()
                )

                if selected_keyword != "-- Select --":
                    matched_docs = collection.find({"keywords": selected_keyword})

                    for doc in matched_docs:
                        with st.expander(doc.get("title", "Untitled")):
                            st.write(doc.get("abstract", "Not available"))
            else:
                st.info("No keywords available.")

        st.markdown("---")

        # ------------------ MOST BOOKMARKED PAPERS ------------------
        st.markdown("### ⭐ Most Bookmarked Papers")

        bookmark_counts = Counter()
        for user in users_collection.find():
            for pid in user.get("bookmarks", []):
                bookmark_counts[str(pid)] += 1

        if bookmark_counts:
            for pid, count in bookmark_counts.most_common(5):
                paper = collection.find_one({"_id": ObjectId(pid)})
                if paper:
                    st.write(f"**{paper.get('title')}** — ⭐ {count}")
        else:
            st.info("No bookmarks yet.")





