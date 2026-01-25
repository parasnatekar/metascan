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

