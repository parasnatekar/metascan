from db import collection
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def build_search_index(documents):
    corpus = []

    for doc in documents:
        title = doc.get("title", "")
        abstract = doc.get("abstract", "")
        cleaned_text = doc.get("cleaned_text", "")

        keywords = doc.get("keywords", [])
        if isinstance(keywords, list):
            keywords = " ".join(keywords)

        topics = doc.get("topics", [])
        if isinstance(topics, list):
            topics = " ".join(topics)

        entities = doc.get("entities", [])
        if isinstance(entities, list):
            entities = " ".join(entities)

        authors = doc.get("authors", [])
        if isinstance(authors, list):
            authors = " ".join(authors)

        category = doc.get("category", "")

        combined_text = " ".join([
            title,
            abstract,
            cleaned_text,
            keywords,
            topics,
            entities,
            authors,
            category
        ]).strip()

        corpus.append(combined_text)

    vectorizer = TfidfVectorizer(
        stop_words="english",
        lowercase=True,
        ngram_range=(1, 2),
        sublinear_tf=True,
        max_features=12000
    )

    tfidf_matrix = vectorizer.fit_transform(corpus)
    return vectorizer, tfidf_matrix   

# ---------------- TF-IDF Search ---------------- #
def search_documents(keyword, documents, vectorizer, tfidf_matrix, top_n=20):
    """
    Rank documents by cosine similarity to the given keyword.
    """
    if not keyword:
        return documents

    query_vec = vectorizer.transform([keyword.lower()])
    similarities = cosine_similarity(query_vec, tfidf_matrix).flatten()

    # Sort documents by similarity score (highest first)
    ranked_indices = similarities.argsort()[::-1]

    results = []
    for idx in ranked_indices:
        score = float(similarities[idx])
        if score <= 0:  # skip irrelevant results
            continue
        doc = documents[idx].copy()
        # 🔥 CRITICAL: preserve MongoDB _id
        doc["_id"] = documents[idx]["_id"]
        
        doc["similarity"] = round(score, 3)
        results.append(doc)
        if len(results) >= top_n:
            break

    return results


# ---------------- Main Search Function ---------------- #
def search_docs(keyword=None, author=None, year=None, category=None, limit=1000):
    """
    Search MongoDB documents by author, year, category, and keyword (TF-IDF).
    """
    # 1️⃣ MongoDB Filters
    query = {}
    if author:
        query["authors"] = {"$regex": f".*{author}.*", "$options": "i"}
    if year:
        query["year"] = str(year)
    if category:
        query["category"] = {"$regex": f".*{category}.*", "$options": "i"}

    projection = {}  # DO NOT REMOVE _id
    mongo_results = list(collection.find(query).limit(limit))


    if not mongo_results:
        return []

    # 2️⃣ Keyword Search (TF-IDF Ranking)
    if keyword:
        vectorizer, tfidf_matrix = build_search_index(mongo_results)
        results = search_documents(keyword, mongo_results, vectorizer, tfidf_matrix, top_n=limit)
    else:
        results = mongo_results

    return results


# ================= STREAMLIT SEARCH UI (MOVED FROM DASHBOARD) =================
import streamlit as st
import time
from ml.recommender import get_similar_papers
from admin.logger import log_search, log_perf

def render_search_module(
    safe_filename,
    get_pdf_bytes_cached,
    add_bookmark,
    remove_bookmark,
    get_user_bookmarks
):
    # ---------------- Search ----------------
    st.subheader("🔍 Search Research Papers")

    keyword = st.text_input("Keyword")
    author = st.text_input("Author")
    year = st.text_input("Year")
    category = st.text_input("Category")

    if st.button("Search"):
        st.session_state.results = search_docs(keyword, author, year, category)

        q = " ".join([
            str(keyword or "").strip(),
            str(author or "").strip(),
            str(year or "").strip(),
            str(category or "").strip()
        ]).strip()

        results_count = len(st.session_state.results or [])

        log_search(
            st.session_state.user["email"],
            q if q else "(empty)",
            results_count,
            filters={"keyword": keyword, "author": author, "year": year, "category": category}
        )


    # Always initialize results
    if "results" not in st.session_state:
        st.session_state.results = []

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

            t_rec = time.perf_counter()
            similar = get_similar_papers(doc.get("abstract", ""), top_n=5)
            log_perf(
                "recommend",
                int((time.perf_counter() - t_rec) * 1000),
                meta={"user": st.session_state.user["email"], "paper_id": str(paper_id)}
            )

            for sp in similar:
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
