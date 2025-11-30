# enrich.py
from db import collection
import spacy
from sklearn.feature_extraction.text import TfidfVectorizer
from collections import Counter
import subprocess
import sys
import re

# ---------------- Load spaCy English model ---------------- #
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")


# ---------------- 1. Text Preprocessing ---------------- #
def clean_text(text):
    """
    Lemmatize text, remove stopwords, and keep only alphabetic tokens.
    Returns a clean, lowercase lemmatized string.
    """
    if not text:
        return ""
    doc = nlp(text.lower())
    tokens = [token.lemma_ for token in doc if not token.is_stop and token.is_alpha]
    return " ".join(tokens)


# ---------------- 2. Keyword Extraction ---------------- #
def extract_keywords(docs, top_n=5):
    """
    Extract top N keywords from a list of documents using TF-IDF.
    Expects docs = [{'abstract': '...'}, ...]
    """
    abstracts = [doc.get("abstract", "") for doc in docs]
    if not abstracts:
        return [[] for _ in docs]

    try:
        vectorizer = TfidfVectorizer(stop_words="english", max_features=100)
        tfidf = vectorizer.fit_transform(abstracts)
        feature_names = vectorizer.get_feature_names_out()

        keywords_matrix = []
        for row in tfidf:
            indices = row.toarray()[0].argsort()[-top_n:][::-1]
            keywords_matrix.append([feature_names[i] for i in indices])
        return keywords_matrix
    except Exception as e:
        print(f"⚠️ Keyword extraction failed: {e}")
        return [[] for _ in docs]


# ---------------- 3. Entity Extraction ---------------- #
def extract_entities(text):
    """
    Extract named entities (ORG, PERSON, GPE, etc.) from text.
    Returns a unique list of entity strings.
    """
    if not text:
        return []
    doc = nlp(text)
    return list(set(ent.text.strip() for ent in doc.ents if ent.text.strip()))


# ---------------- 4. Category Assignment ---------------- #
CATEGORY_KEYWORDS = {
    "AI / Machine Learning": [
        "machine learning", "deep learning", "neural network", "classification", "regression",
        "supervised", "unsupervised", "cnn", "rnn", "svm", "transformer"
    ],
    "Data Management": [
        "metadata", "data management", "repository", "ontology", "data sharing",
        "rdm", "database", "data curation", "data storage", "data pipeline"
    ],
    "Computer Vision": ["image", "object detection", "segmentation", "video analysis", "image processing"],
    "Natural Language Processing": [
        "nlp", "text mining", "language model", "bert", "transformer", "tokenization", "embedding"
    ],
    "Healthcare / Bioinformatics": [
        "medical", "healthcare", "patient", "disease", "clinical", "genomic", "bioinformatics", "covid"
    ],
    "Cybersecurity": [
        "security", "encryption", "cyber", "malware", "attack", "vulnerability", "firewall"
    ],
    "Robotics": ["robot", "autonomous", "manipulation", "drone", "actuator"],
    "Social Sciences / Psychology": [
        "psychology", "education", "survey", "behavior", "sociology", "learning", "cognitive"
    ],
    "Physics / Engineering": ["quantum", "particle", "energy", "battery", "solar", "physics", "engineering"],
}


def assign_category(text):
    """
    Assign a semantic category based on abstract keywords.
    Falls back to 'Other' if no match.
    """
    if not text:
        return "Other"

    text = text.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if re.search(rf"\b{re.escape(kw)}\b", text):
                return category

    return "Other"


# ---------------- 5. Enrichment for a single PDF ---------------- #
def enrich_pdf_metadata(metadata):
    """
    Enrich a single PDF metadata dictionary before inserting into MongoDB.
    Adds cleaned_text, keywords, entities, and category.
    """
    abstract = metadata.get("abstract", "")
    cleaned = clean_text(abstract)
    entities = extract_entities(abstract)
    category = assign_category(abstract)

    # Compute local TF-IDF keywords for just this abstract
    try:
        vectorizer = TfidfVectorizer(stop_words="english", max_features=5)
        tfidf = vectorizer.fit_transform([abstract])
        keywords = list(vectorizer.get_feature_names_out())
    except Exception:
        keywords = []

    metadata.update(
        {
            "cleaned_text": cleaned,
            "keywords": keywords,
            "entities": entities,
            "category": category,
        }
    )
    return metadata


# ---------------- 6. Bulk Enrichment for all DB docs ---------------- #
def enrich_and_update():
    """
    Enrich all documents in MongoDB with cleaned_text, keywords, entities, and category.
    """
    docs = list(collection.find())
    if not docs:
        print("⚠️ No documents found in database.")
        return

    keywords_list = extract_keywords(docs, top_n=5)

    for idx, doc in enumerate(docs):
        abstract = doc.get("abstract", "")
        cleaned = clean_text(abstract)
        entities = extract_entities(abstract)
        category = assign_category(abstract)
        keywords = keywords_list[idx]

        enriched = {
            "cleaned_text": cleaned,
            "keywords": keywords,
            "entities": entities,
            "category": category,
        }

        collection.update_one({"_id": doc["_id"]}, {"$set": enriched})
        print(f"✅ Enriched: {doc.get('title', 'Untitled')} → {category}")


# ---------------- Manual Testing ---------------- #
if __name__ == "__main__":
    enrich_and_update()
