# enrich.py

from db import collection
import spacy
from sklearn.feature_extraction.text import TfidfVectorizer

# Load spaCy model
nlp = spacy.load("en_core_web_sm")

# --- Text Cleaning ---
def clean_text(text):
    doc = nlp(text.lower())
    return ' '.join([token.lemma_ for token in doc if not token.is_stop and token.is_alpha])

# --- Keyword Extraction ---
def extract_keywords(docs, top_n=5):
    abstracts = [doc.get('abstract', '') for doc in docs]
    vectorizer = TfidfVectorizer(stop_words='english')
    tfidf = vectorizer.fit_transform(abstracts)
    feature_names = vectorizer.get_feature_names_out()

    keywords_for_docs = []
    for row in tfidf:
        top_indices = row.toarray()[0].argsort()[-top_n:][::-1]
        keywords_for_docs.append([feature_names[i] for i in top_indices])
    return keywords_for_docs

# --- Entity Extraction ---
def extract_entities(text):
    doc = nlp(text)
    return list(set([ent.text for ent in doc.ents]))

# --- Rule-Based Categorization ---
PREDEFINED_CATEGORIES = {
    "Artificial Intelligence": ["ai", "machine learning", "neural network", "deep learning"],
    "Energy": ["energy", "grids", "renewable", "solar", "wind"],
    "Quantum Physics": ["quantum", "entanglement", "superposition", "qubit"],
    "Biotech": ["protein", "genome", "dna", "rna"],
    "Other": []  # fallback
}

def assign_category(abstract):
    abstract = abstract.lower()
    for category, keywords in PREDEFINED_CATEGORIES.items():
        if any(word in abstract for word in keywords):
            return category
    return "Other"

# --- Document Enrichment Pipeline ---
def enrich_and_update():
    docs = list(collection.find())
    keywords_matrix = extract_keywords(docs, top_n=5)

    for idx, doc in enumerate(docs):
        abstract = doc.get('abstract', '')

        enriched_fields = {
            "cleaned_text": clean_text(abstract),
            "entities": extract_entities(abstract),
            "keywords": keywords_matrix[idx],
            "category": assign_category(abstract)
        }

        collection.update_one({'_id': doc['_id']}, {'$set': enriched_fields})
        print(f"[+] Enriched: {doc.get('title', 'Untitled')}")

if __name__ == "__main__":
    enrich_and_update()
