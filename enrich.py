# enrich.py

import os
import pickle
import subprocess
import sys
import re

from db import collection
import spacy
from sklearn.feature_extraction.text import TfidfVectorizer

# ---------------- Load ML Category Model ---------------- #
MODEL_PATH = os.path.join("ml", "ml_category_model.pkl")

ml_vectorizer = None
ml_model = None

if os.path.exists(MODEL_PATH):
    with open(MODEL_PATH, "rb") as f:
        saved = pickle.load(f)   # ✅ FIX: load dict correctly
        ml_vectorizer = saved.get("vectorizer")
        ml_model = saved.get("model")

    print("✅ ML category model loaded")
else:
    print("⚠️ ML category model not found")


# ---------------- Load spaCy Model ---------------- #
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")


# ---------------- ML Category Prediction ---------------- #
def predict_ml_category(abstract):
    """
    Predict category using trained ML model.
    Falls back safely if model is unavailable.
    """
    if not abstract or ml_model is None or ml_vectorizer is None:
        return None

    try:
        X = ml_vectorizer.transform([abstract])
        return ml_model.predict(X)[0]
    except Exception as e:
        print(f"⚠️ ML prediction error: {e}")
        return None


# ---------------- 1. Text Preprocessing ---------------- #
def clean_text(text):
    if not text:
        return ""
    doc = nlp(text.lower())
    tokens = [t.lemma_ for t in doc if t.is_alpha and not t.is_stop]
    return " ".join(tokens)


# ---------------- 2. Keyword Extraction ---------------- #
def extract_keywords(docs, top_n=5):
    abstracts = [doc.get("abstract", "") for doc in docs]
    if not abstracts:
        return [[] for _ in docs]

    try:
        tfidf_vectorizer = TfidfVectorizer(   # ✅ FIX: renamed
            stop_words="english",
            max_features=100
        )
        tfidf = tfidf_vectorizer.fit_transform(abstracts)
        features = tfidf_vectorizer.get_feature_names_out()

        keywords_list = []
        for row in tfidf:
            indices = row.toarray()[0].argsort()[-top_n:][::-1]
            keywords_list.append([features[i] for i in indices])
        return keywords_list

    except Exception as e:
        print(f"⚠️ Keyword extraction failed: {e}")
        return [[] for _ in docs]


# ---------------- 3. Entity Extraction ---------------- #
def extract_entities(text):
    if not text:
        return []
    doc = nlp(text)
    return list(set(ent.text.strip() for ent in doc.ents if ent.text.strip()))


# ---------------- 4. Rule-based Category (Fallback) ---------------- #
CATEGORY_KEYWORDS = {
    "AI / Machine Learning": ["machine learning", "deep learning", "neural network"],
    "Data Management": ["metadata", "data management", "repository", "rdm"],
    "Computer Vision": ["image", "segmentation", "object detection"],
    "Natural Language Processing": ["nlp", "text mining", "language model"],
    "Healthcare / Bioinformatics": ["medical", "healthcare", "clinical", "bioinformatics"],
    "Cybersecurity": ["security", "encryption", "malware"],
    "Robotics": ["robot", "autonomous", "drone"],
    "Social Sciences / Psychology": ["psychology", "education", "behavior"],
    "Physics / Engineering": ["quantum", "energy", "physics", "engineering"],
}


def assign_category(text):
    if not text:
        return "Other"
    text = text.lower()
    for cat, words in CATEGORY_KEYWORDS.items():
        for w in words:
            if re.search(rf"\b{re.escape(w)}\b", text):
                return cat
    return "Other"


# ---------------- 5. Enrich Single PDF Metadata ---------------- #
def enrich_pdf_metadata(metadata):
    abstract = metadata.get("abstract", "")

    cleaned = clean_text(abstract)
    entities = extract_entities(abstract)

    ml_category = predict_ml_category(abstract)
    rule_category = assign_category(abstract)
    final_category = ml_category if ml_category else rule_category

    try:
        tfidf_vec = TfidfVectorizer(   # ✅ FIX: renamed
            stop_words="english",
            max_features=5
        )
        tfidf_vec.fit([abstract])
        keywords = list(tfidf_vec.get_feature_names_out())
    except Exception:
        keywords = []

    metadata.update({
        "cleaned_text": cleaned,
        "keywords": keywords,
        "entities": entities,
        "category": final_category
    })

    return metadata


# ---------------- 6. Enrich All DB Documents ---------------- #
def enrich_and_update():
    docs = list(collection.find())
    if not docs:
        print("⚠️ No documents found in database.")
        return

    keywords_list = extract_keywords(docs)

    for idx, doc in enumerate(docs):
        abstract = doc.get("abstract", "")

        cleaned = clean_text(abstract)
        entities = extract_entities(abstract)

        ml_category = predict_ml_category(abstract)
        rule_category = assign_category(abstract)
        final_category = ml_category if ml_category else rule_category

        print(
            f"ML={ml_category} | RULE={rule_category} | FINAL={final_category}"
        )


        enriched = {
            "cleaned_text": cleaned,
            "keywords": keywords_list[idx],
            "entities": entities,
            "category": final_category
        }

        collection.update_one({"_id": doc["_id"]}, {"$set": enriched})
        print(f"✅ Enriched: {doc.get('title', 'Untitled')} → {final_category}")


# ---------------- Manual Run ---------------- #
if __name__ == "__main__":
    enrich_and_update()
