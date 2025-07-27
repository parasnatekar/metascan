import streamlit as st
import json
from db import collection
from search import search_docs
from enrich import enrich_and_update, assign_category, clean_text, extract_keywords, extract_entities
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title="MetaScan Dashboard", layout="wide")
st.title("📚 MetaScan - Research Metadata Indexing Dashboard")

# --- FILE UPLOAD SECTION ---
st.sidebar.header("📤 Upload Documents")
uploaded_file = st.sidebar.file_uploader("Upload JSON file", type="json")

if uploaded_file:
    try:
        data = json.load(uploaded_file)
        if isinstance(data, list):
            result = collection.insert_many(data)
            st.sidebar.success(f"✅ {len(result.inserted_ids)} documents uploaded.")
            enrich_and_update()
            st.sidebar.info("✅ Documents enriched and categorized.")
        else:
            st.sidebar.error("❌ Uploaded file must be a list of JSON documents.")
    except Exception as e:
        st.sidebar.error(f"❌ Error processing file: {e}")

# --- SEARCH FILTERS ---
st.sidebar.header("🔍 Search Filters")
keyword = st.sidebar.text_input("Keyword")
author = st.sidebar.text_input("Author")
year = st.sidebar.text_input("Year")
category = st.sidebar.text_input("Category")

if st.sidebar.button("Search"):
    results = search_docs(keyword, author, year, category)
    st.subheader(f"🔎 Search Results: {len(results)} document(s) found")
    for i, doc in enumerate(results, 1):
        with st.expander(f"{i}. {doc.get('title', 'Untitled')}"):
            st.write(doc)

# --- ANALYTICS SECTION ---
st.subheader("📊 Document Analytics")

# Load all documents
docs = list(collection.find())

if docs:
    df = pd.DataFrame(docs)

    # --- Category Distribution ---
    if "category" in df.columns:
        st.markdown("### 📂 Category Distribution")
        category_counts = df['category'].value_counts()
        st.bar_chart(category_counts)

    # --- Documents per Year ---
    if "publication_date" in df.columns:
        st.markdown("### 📅 Documents per Year")
        df['year'] = df['publication_date'].str[:4]
        year_counts = df['year'].value_counts().sort_index()
        st.line_chart(year_counts)

    # --- Keyword Frequency ---
    if "keywords" in df.columns:
        st.markdown("### 🔑 Keyword Frequency")
        from collections import Counter
        all_keywords = [kw for sublist in df['keywords'] for kw in sublist]
        keyword_counts = Counter(all_keywords)
        keyword_df = pd.DataFrame(keyword_counts.items(), columns=["Keyword", "Count"])
        st.dataframe(keyword_df.sort_values("Count", ascending=False).head(15))
else:
    st.warning("No documents found in the database to analyze.")
