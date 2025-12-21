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
from datetime import datetime


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
    st.set_page_config(page_title="MetaScan Login", layout="centered")

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
# ================= BOOKMARK HELPERS =================
def add_bookmark(user_email, paper_id):
    users_collection.update_one(
        {"email": user_email},
        {"$addToSet": {"bookmarks": paper_id}}
    )

def remove_bookmark(user_email, paper_id):
    users_collection.update_one(
        {"email": user_email},
        {"$pull": {"bookmarks": paper_id}}
    )

def get_user_bookmarks(user_email):
    user = users_collection.find_one({"email": user_email})
    return user.get("bookmarks", []) if user else []


# ================= MAIN DASHBOARD =================
st.set_page_config(page_title="MetaScan Dashboard", layout="wide")

st.markdown("""
<style>
.stApp { background: linear-gradient(to bottom right, #0E1117, #1E2025); color: white; }
.big-title { text-align:center; font-size:36px; color:#00BFFF; font-weight:bold; }
.sub-title { text-align:center; color:#CCCCCC; font-size:18px; margin-bottom:30px; }
</style>
""", unsafe_allow_html=True)

st.markdown(
    "<div class='big-title'>MetaScan Dashboard</div>"
    "<div class='sub-title'>AI-Powered Research Metadata Indexing</div>",
    unsafe_allow_html=True
)

# Logger
logging.basicConfig(level=logging.INFO)

# Sidebar user info + logout
st.sidebar.markdown(f"👤 **Logged in as:** {st.session_state.user['username']}")
st.sidebar.markdown("---")
if st.sidebar.button("🚪 Logout"):
    st.session_state.logged_in = False
    st.session_state.user = None
    st.rerun()

# ---------------- Sidebar Upload ----------------
st.sidebar.header("📤 Upload Documents")
uploaded_file = st.sidebar.file_uploader("Upload JSON or PDF", type=["json", "pdf"])

if uploaded_file:
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
                enriched_data["uploaded_at"] = datetime.utcnow()
                collection.insert_one(enriched_data)
                st.success("✅ PDF stored successfully!")
                st.info("⚡ Metadata enriched (keywords, category, entities) completed.")
                logging.info(f"Inserted PDF: {title or 'Untitled'}")
            except Exception as e:
                st.error(f"❌ Database insert failed: {e}")


# ---------------- Search ----------------
st.sidebar.header("🔍 Search Filters")
keyword = st.sidebar.text_input("Keyword")
author = st.sidebar.text_input("Author")
year = st.sidebar.text_input("Year")
category = st.sidebar.text_input("Category")

# Always initialize results
if "results" not in st.session_state:
    st.session_state.results = []

# Run search
if st.sidebar.button("Search"):
    st.session_state.results = search_docs(keyword, author, year, category)

results = st.session_state.results

if results:
    st.subheader(f"🔎 {len(results)} result(s) found")

    user_email = st.session_state.user["email"]
    bookmarks = get_user_bookmarks(user_email)

    for i, doc in enumerate(results, 1):
        paper_id = doc["_id"]

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

            # ---------- TOPICS / ENTITIES ----------
            entities = doc.get("entities") or doc.get("topics")
            if isinstance(entities, list) and entities:
                st.markdown("### 🧩 Extracted Topics")
                st.write(", ".join(entities))

            # ---------- SIMILAR PAPERS ----------
            st.markdown("### 🔁 Similar Papers")
            for sp in get_similar_papers(doc.get("abstract", ""), top_n=5):
                st.markdown(
                    f"- **{sp['title']}** ({sp['category']}) — {round(sp['similarity_score'], 3)}"
                )

            # ---------- PDF DOWNLOAD ----------
            if "file_id" in doc:
                pdf = download_pdf_from_gridfs(doc["file_id"])
                if pdf:
                    st.download_button(
                        "📥 Download PDF",
                        pdf,
                        file_name=f"{doc.get('title', 'paper')}.pdf",
                        key=f"dl_{paper_id}"
                    )


# ================= BOOKMARKS SECTION =================
st.subheader("⭐ My Bookmarked Papers")

user_bookmark_ids = get_user_bookmarks(st.session_state.user["email"])

if user_bookmark_ids:
    bookmarked_docs = collection.find(
        {"_id": {"$in": user_bookmark_ids}}
    )

    for doc in bookmarked_docs:
        with st.expander(doc.get("title", "Untitled")):
            st.markdown(f"**Category:** {doc.get('category')}")
            st.markdown(f"**Abstract:** {doc.get('abstract', 'N/A')}")

            if "file_id" in doc:
                pdf = download_pdf_from_gridfs(doc["file_id"])
                if pdf:
                    st.download_button(
                        "📥 Download PDF",
                        pdf,
                        file_name=f"{doc['title']}.pdf",
                        key=f"bm_dl_{doc['_id']}"
                    )
else:
    st.info("No bookmarks yet. Start saving papers ⭐")

# ================= MY UPLOADS SECTION =================
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
        with st.expander(f"{i}. {doc.get('title', 'Untitled')}"):

            # --- Metadata layout ---
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

            st.markdown("---")

            # Abstract
            st.markdown("### 🧠 Abstract")
            st.write(doc.get("abstract", "Abstract not available"))

            # Keywords
            keywords = doc.get("keywords", [])
            if isinstance(keywords, list) and keywords:
                st.markdown("### 🏷️ Keywords")
                st.write(", ".join(keywords))

            # Topics / Entities
            entities = doc.get("entities") or doc.get("topics")
            if isinstance(entities, list) and entities:
                st.markdown("### 🧩 Extracted Topics")
                st.write(", ".join(entities))

            # Upload metadata
            st.markdown("---")
            st.caption(
                f"📅 Uploaded on: {doc.get('uploaded_at', 'Unknown')} | "
                f"👤 Uploaded by you"
            )

            # PDF Download
            if "file_id" in doc:
                pdf = download_pdf_from_gridfs(doc["file_id"])
                if pdf:
                    st.download_button(
                        "📥 Download PDF",
                        pdf,
                        file_name=f"{doc.get('title','paper')}.pdf",
                        key=f"myup_dl_{doc['_id']}"
                    )

# ---------------- Analytics ----------------
st.subheader("📊 Document Analytics")
docs = list(collection.find())

if docs:
    df = pd.DataFrame(docs)
    if "category" in df:
        st.bar_chart(df["category"].value_counts())

    if "keywords" in df:
        all_keywords = [k for sub in df["keywords"] if isinstance(sub, list) for k in sub]
        kw_df = pd.DataFrame(Counter(all_keywords).items(), columns=["Keyword", "Count"])
        st.dataframe(kw_df.sort_values("Count", ascending=False).head(15))
