import streamlit as st
import json
from db import collection, db
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

if st.sidebar.button("Search"):
    results = search_docs(keyword, author, year, category)
    st.subheader(f"🔎 {len(results)} result(s) found")

    for i, doc in enumerate(results, 1):
        with st.expander(f"{i}. {doc.get('title')}"):
            st.markdown(f"**Category:** {doc.get('category')}")
            st.markdown(f"**Abstract:** {doc.get('abstract')}")

            st.markdown("### 🔁 Similar Papers")
            for sp in get_similar_papers(doc.get("abstract", ""), top_n=5):
                st.markdown(
                    f"- **{sp['title']}** ({sp['category']}) "
                    f"— {round(sp['similarity_score'],3)}"
                )

            if "file_id" in doc:
                pdf = download_pdf_from_gridfs(doc["file_id"])
                if pdf:
                    st.download_button(
                        "📥 Download PDF",
                        pdf,
                        file_name=f"{doc['title']}.pdf",
                        key=f"dl_{i}"
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
