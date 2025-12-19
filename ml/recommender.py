# ml/recommender.py

import os
import sys
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Add project root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(PROJECT_ROOT)

from db import collection


def get_similar_papers(input_abstract, top_n=5):
    """
    Returns top N similar papers based on abstract similarity
    """

    if not input_abstract:
        return []

    # Fetch documents from DB
    docs = list(collection.find({"abstract": {"$exists": True, "$ne": ""}}))

    if len(docs) < 2:
        return []

    abstracts = [doc["abstract"] for doc in docs]

    # Vectorize abstracts
    vectorizer = TfidfVectorizer(
        stop_words="english",
        max_features=5000
    )

    tfidf_matrix = vectorizer.fit_transform(abstracts)
    input_vector = vectorizer.transform([input_abstract])

    # Compute similarity
    similarities = cosine_similarity(input_vector, tfidf_matrix)[0]

    # Get top indices (excluding itself)
    top_indices = np.argsort(similarities)[::-1][1: top_n + 1]

    recommendations = []
    for idx in top_indices:
        recommendations.append({
            "title": docs[idx].get("title", "Untitled"),
            "category": docs[idx].get("category", "Unknown"),
            "similarity_score": round(float(similarities[idx]), 3)
        })

    return recommendations
