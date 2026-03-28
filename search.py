from db import collection
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def build_search_index(documents):
    corpus = []
    for doc in documents:
        keywords = doc.get("keywords", [])
        if isinstance(keywords, list): keywords = " ".join(keywords)
        topics = doc.get("topics", [])
        if isinstance(topics, list): topics = " ".join(topics)
        entities = doc.get("entities", [])
        if isinstance(entities, list): entities = " ".join(entities)
        authors = doc.get("authors", [])
        if isinstance(authors, list): authors = " ".join(authors)
        combined_text = " ".join([
            doc.get("title", ""), doc.get("abstract", ""),
            doc.get("cleaned_text", ""), keywords, topics,
            entities, authors, doc.get("category", "")
        ]).strip()
        corpus.append(combined_text)

    vectorizer = TfidfVectorizer(
        stop_words="english", lowercase=True,
        ngram_range=(1, 2), sublinear_tf=True, max_features=12000
    )
    tfidf_matrix = vectorizer.fit_transform(corpus)
    return vectorizer, tfidf_matrix


def search_documents(keyword, documents, vectorizer, tfidf_matrix, top_n=20):
    if not keyword:
        return documents
    query_vec = vectorizer.transform([keyword.lower()])
    similarities = cosine_similarity(query_vec, tfidf_matrix).flatten()
    ranked_indices = similarities.argsort()[::-1]
    results = []
    for idx in ranked_indices:
        score = float(similarities[idx])
        if score <= 0:
            continue
        doc = documents[idx].copy()
        doc["_id"] = documents[idx]["_id"]
        doc["similarity"] = round(score, 3)
        results.append(doc)
        if len(results) >= top_n:
            break
    return results


def search_docs(keyword=None, author=None, year=None, category=None, limit=1000):
    query = {}
    if author:   query["authors"]  = {"$regex": f".*{author}.*",   "$options": "i"}
    if year:     query["year"]     = str(year)
    if category: query["category"] = {"$regex": f".*{category}.*", "$options": "i"}
    mongo_results = list(collection.find(query).limit(limit))
    if not mongo_results:
        return []
    if keyword:
        vectorizer, tfidf_matrix = build_search_index(mongo_results)
        return search_documents(keyword, mongo_results, vectorizer, tfidf_matrix, top_n=limit)
    return mongo_results


# ================= STREAMLIT SEARCH UI =================
import streamlit as st
import time
from ml.recommender import get_similar_papers
from admin.logger import log_search, log_perf
from summarizer import render_summary_card
from qa import render_qa_panel


def render_search_module(
    safe_filename,
    get_pdf_bytes_cached,
    add_bookmark,
    remove_bookmark,
    get_user_bookmarks
):
    st.markdown("""
    <div style="padding:28px 0 20px; border-bottom:1px solid rgba(255,255,255,0.06); margin-bottom:28px;">
        <div style="font-family:'Space Mono',monospace; font-size:10px; color:#00E0FF;
            letter-spacing:3px; margin-bottom:8px;">METASCAN // SEARCH</div>
        <div style="font-family:'Syne',sans-serif; font-size:32px; font-weight:800;
            color:#E8EDF2; letter-spacing:-0.5px;">Search Papers</div>
        <div style="font-family:'Inter',sans-serif; font-size:14px; color:#5A6472; margin-top:6px;">
            TF-IDF semantic search across the full research corpus</div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns([4, 1])
    with c1:
        keyword = st.text_input("", placeholder="🔍  Keyword, topic, or concept...",
                                label_visibility="collapsed", key="search_keyword")
    with c2:
        search_clicked = st.button("Search →", use_container_width=True, key="search_btn")

    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        author   = st.text_input("", placeholder="Author name",      label_visibility="collapsed", key="search_author")
    with fc2:
        year     = st.text_input("", placeholder="Year e.g. 2023",   label_visibility="collapsed", key="search_year")
    with fc3:
        category = st.text_input("", placeholder="Category",          label_visibility="collapsed", key="search_category")

    if search_clicked:
        with st.spinner("Searching..."):
            st.session_state.results = search_docs(keyword, author, year, category)
        q = " ".join([str(x or "").strip() for x in [keyword, author, year, category]]).strip()
        log_search(
            st.session_state.user["email"],
            q if q else "(empty)",
            len(st.session_state.results or []),
            filters={"keyword": keyword, "author": author, "year": year, "category": category}
        )

    if "results" not in st.session_state:
        st.session_state.results = []

    results = st.session_state.results

    if results:
        st.markdown(f"""
        <div style="font-family:'Space Mono',monospace; font-size:10px; color:#5A6472;
            letter-spacing:2px; margin:16px 0 12px;">
            {len(results)} RESULT{'S' if len(results)!=1 else ''} FOUND
        </div>""", unsafe_allow_html=True)

    user_email = st.session_state.user["email"]
    bookmarks  = get_user_bookmarks(user_email)

    for i, doc in enumerate(results, 1):
        paper_id = doc["_id"]
        if not paper_id:
            continue

        sim     = doc.get("similarity", None)
        sim_str = f"  ·  score {sim:.3f}" if sim else ""

        with st.expander(f"{i}.  {doc.get('title', 'Untitled')}{sim_str}"):

            # ── Bookmark ──
            bm_col, _ = st.columns([1, 11])
            with bm_col:
                if paper_id in bookmarks:
                    if st.button("⭐", key=f"rm_{paper_id}"):
                        remove_bookmark(user_email, paper_id); st.rerun()
                else:
                    if st.button("☆", key=f"bm_{paper_id}"):
                        add_bookmark(user_email, paper_id); st.rerun()

            # ── Metadata ──
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

            # ── Abstract ──
            st.markdown("### 🧠 Abstract")
            st.write(doc.get("abstract", "Abstract not available"))

            # ── AI Summary ──
            st.markdown("### ✨ AI Summary")
            render_summary_card(doc, key_prefix=str(paper_id))

            st.divider()

            # ── Paper Q&A  ◀ NEW ──
            st.markdown("### 💬 Ask This Paper")
            render_qa_panel(doc, key_prefix=f"search_{paper_id}")

            st.divider()

            # ── Keywords / Topics / Entities ──
            kws = doc.get("keywords", [])
            if isinstance(kws, list) and kws:
                st.markdown("### 🏷️ Keywords")
                st.write(", ".join(kws))

            topics = doc.get("topics", [])
            if isinstance(topics, list) and topics:
                st.markdown("### 🧠 Research Topics")
                st.write(", ".join(topics))

            entities = doc.get("entities")
            if isinstance(entities, list) and entities:
                st.markdown("### 🧩 Entities")
                st.write(", ".join(entities))

            # ── Similar Papers ──
            st.markdown("### 🔁 Similar Papers")
            t_rec   = time.perf_counter()
            similar = get_similar_papers(doc.get("abstract", ""), top_n=5)
            log_perf("recommend", int((time.perf_counter() - t_rec) * 1000),
                     meta={"user": st.session_state.user["email"], "paper_id": str(paper_id)})
            for sp in similar:
                st.markdown(f"- **{sp['title']}** ({sp['category']}) — {round(sp['similarity_score'], 3)}")

            # ── PDF Download ──
            if "file_id" in doc:
                if st.button("🔗 Generate Download Link", key=f"prep_{paper_id}"):
                    pdf_data = get_pdf_bytes_cached(doc["file_id"])
                    if pdf_data:
                        st.download_button("📥 Download PDF Now", data=pdf_data,
                            file_name=safe_filename(doc.get("title")),
                            mime="application/pdf", key=f"dl_btn_{paper_id}")
                    else:
                        st.error("Could not retrieve PDF from storage.")