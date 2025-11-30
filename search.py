from db import collection
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ---------------- TF-IDF Index Builder ---------------- #
def build_search_index(documents):
    """
    Build TF-IDF index from all meaningful document fields for keyword search.
    """
    corpus = []
    for doc in documents:
        # Extract text-based fields safely
        title = doc.get("title", "")
        abstract = doc.get("abstract", "")
        keywords = doc.get("keywords", [])
        if isinstance(keywords, list):
            keywords = " ".join(keywords)
        authors = doc.get("authors", [])
        if isinstance(authors, list):
            authors = " ".join(authors)
        category = doc.get("category", "")

        # Merge all fields into one searchable text
        combined_text = " ".join([title, abstract, keywords, authors, category]).strip()
        corpus.append(combined_text)

    # Configure TF-IDF with better phrase and weighting support
    vectorizer = TfidfVectorizer(
        stop_words="english",
        lowercase=True,
        ngram_range=(1, 2),       # include unigrams + bigrams
        sublinear_tf=True,
        max_features=10000        # keeps model efficient
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
        doc["similarity"] = round(score, 3)
        results.append(doc)
        if len(results) >= top_n:
            break

    return results


# ---------------- Main Search Function ---------------- #
def search_docs(keyword=None, author=None, year=None, category=None, limit=20):
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

    projection = {"_id": 0}
    mongo_results = list(collection.find(query, projection).limit(limit))

    if not mongo_results:
        return []

    # 2️⃣ Keyword Search (TF-IDF Ranking)
    if keyword:
        vectorizer, tfidf_matrix = build_search_index(mongo_results)
        results = search_documents(keyword, mongo_results, vectorizer, tfidf_matrix, top_n=limit)
    else:
        results = mongo_results

    return results

