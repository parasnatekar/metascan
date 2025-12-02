import streamlit as st
import json
from db import collection
from search import search_docs
from enrich import enrich_and_update, enrich_pdf_metadata
from pdf_extractor import process_pdf
import pandas as pd
from collections import Counter
import logging

# NEW IMPORTS FOR GRIDFS
from file_storage import save_pdf_to_gridfs, download_pdf_from_gridfs

# ---------------- Streamlit UI Config ----------------
st.set_page_config(page_title="MetaScan Dashboard", layout="wide")
st.markdown("""
    <style>
        .stApp { background: linear-gradient(to bottom right, #0E1117, #1E2025); color: white; }
        .big-title { text-align:center; font-size:36px; color:#00BFFF; font-weight:bold; margin-top:10px; }
        .sub-title { text-align:center; color:#CCCCCC; font-size:18px; margin-bottom:30px; }
    </style>
""", unsafe_allow_html=True)
st.markdown("<div class='big-title'>MetaScan Dashboard</div><div class='sub-title'>AI-Powered Research Metadata Indexing</div>", unsafe_allow_html=True)

# ---------------- Logger ----------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ---------------- Sidebar Upload ----------------
st.sidebar.header("📤 Upload Documents")
uploaded_file = st.sidebar.file_uploader("Upload JSON or PDF", type=["json", "pdf"])

if uploaded_file:
    # ---------------- JSON Upload ----------------
    if uploaded_file.name.endswith(".json"):
        try:
            data = json.load(uploaded_file)
            if isinstance(data, list):
                inserted = 0
                for doc in data:
                    if not collection.find_one({"title": doc.get("title")}):
                        collection.insert_one(doc)
                        inserted += 1
                st.sidebar.success(f"✅ {inserted} new document(s) added.")
                enrich_and_update()
            else:
                st.sidebar.error("❌ JSON file must contain a list of documents.")
        except Exception as e:
            st.sidebar.error(f"Error: {e}")

    # ---------------- PDF Upload ----------------
    elif uploaded_file.name.endswith(".pdf"):

        # ✅ SAVE PDF INTO GRIDFS
        file_id = save_pdf_to_gridfs(uploaded_file)

        # Reset pointer so extractor can read PDF
        uploaded_file.seek(0)

        try:
            paper_data = process_pdf(uploaded_file)
        except Exception as e:
            st.error(f"❌ Failed to process PDF: {e}")
            paper_data = None

        # --- If extraction fails, fallback to minimal record ---
        if not paper_data:
            st.warning("⚠️ Could not extract metadata. Using fallback document.")
            paper_data = {
                "title": uploaded_file.name.replace(".pdf", ""),
                "abstract": "",
                "keywords": [],
                "authors": [],
                "year": "",
                "category": "Uncategorized",
                "source": "PDF upload (fallback)",
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

# ---------------- Search Filters ----------------
st.sidebar.header("🔍 Search Filters")
keyword = st.sidebar.text_input("Keyword")
author = st.sidebar.text_input("Author")
year = st.sidebar.text_input("Year")
category = st.sidebar.text_input("Category")

if st.sidebar.button("Search"):
    results = search_docs(keyword=keyword, author=author, year=year, category=category)
    st.subheader(f"🔎 {len(results)} result(s) found")

    if results:
        for i, doc in enumerate(results, 1):
            with st.expander(f"{i}. {doc.get('title', 'Untitled')}"):
                st.markdown(f"**Authors:** {', '.join(doc.get('authors', []))}")
                st.markdown(f"**Year:** {doc.get('year', 'Unknown')}")
                st.markdown(f"**Category:** {doc.get('category', 'Other')}")
                st.markdown(f"**Keywords:** {', '.join(doc.get('keywords', []))}")
                st.markdown(f"**Abstract:** {doc.get('abstract', '')}")

                # ⭐ DOWNLOAD PDF BUTTON (NEW)
                if "file_id" in doc:
                    pdf_bytes = download_pdf_from_gridfs(doc["file_id"])
                    if pdf_bytes:
                        st.download_button(
                            label="📥 Download PDF",
                            data=pdf_bytes,
                            file_name=f"{doc.get('title','document')}.pdf",
                            mime="application/pdf",
                        )

                if 'similarity' in doc:
                    st.markdown(f"**Relevance Score:** {doc['similarity']}")
    else:
        st.info("No documents match your search criteria.")

# ---------------- Analytics ----------------
st.subheader("📊 Document Analytics")
docs = list(collection.find())

if docs:
    for doc in docs:
        if not isinstance(doc.get('keywords'), list):
            doc['keywords'] = []

    df = pd.DataFrame(docs)

    # --- Category Distribution ---
    if "category" in df.columns:
        st.markdown("### 📂 Category Distribution")
        category_counts = df['category'].value_counts()
        st.bar_chart(category_counts)

    # --- Keyword Frequency ---
    if "keywords" in df.columns:
        st.markdown("### 🔑 Keyword Frequency")
        all_keywords = [kw for sublist in df['keywords'] if isinstance(sublist, (list, tuple)) for kw in sublist]
        if all_keywords:
            keyword_counts = Counter(all_keywords)
            keyword_df = pd.DataFrame(keyword_counts.items(), columns=["Keyword", "Count"]).sort_values("Count", ascending=False)
            st.dataframe(keyword_df.head(15))
else:
    st.info("No documents found in database.")
