from db import collection
import spacy
from sklearn.feature_extraction.text import TfidfVectorizer

# Load spaCy English model
nlp = spacy.load("en_core_web_sm")

# --- 1. Text Preprocessing ---
def clean_text(text):
    doc = nlp(text.lower())
    tokens = [token.lemma_ for token in doc if not token.is_stop and token.is_alpha]
    return ' '.join(tokens)

# --- 2. Keyword Extraction ---
def extract_keywords(docs, top_n=5):
    abstracts = [doc.get('abstract', '') for doc in docs]
    vectorizer = TfidfVectorizer(stop_words='english')
    tfidf = vectorizer.fit_transform(abstracts)
    feature_names = vectorizer.get_feature_names_out()

    keywords_matrix = []
    for row in tfidf:
        indices = row.toarray()[0].argsort()[-top_n:][::-1]
        keywords_matrix.append([feature_names[i] for i in indices])
    return keywords_matrix

# --- 3. Entity Extraction ---
def extract_entities(text):
    doc = nlp(text)
    return list(set([ent.text for ent in doc.ents]))

# --- 4. Category Assignment (Rule-based) ---
PREDEFINED_CATEGORIES = {
    "AI": ["ai", "machine learning", "neural network", "deep learning"],
    "Energy": ["energy", "grid", "solar", "renewable", "battery"],
    "Healthcare": ["medicine", "diagnosis", "covid", "disease", "health"],
    "Physics": ["particle", "quantum", "relativity", "string theory"],
    "Robotics": ["robot", "automation", "control system"]
}

def assign_category(abstract):
    text = abstract.lower()
    for category, keywords in PREDEFINED_CATEGORIES.items():
        if any(kw in text for kw in keywords):
            return category
    return "Other"

# --- 5. Enrichment Pipeline ---
def enrich_and_update():
    docs = list(collection.find())
    if not docs:
        print("⚠️ No documents found in database.")
        return

    keywords_list = extract_keywords(docs, top_n=5)

    for idx, doc in enumerate(docs):
        abstract = doc.get('abstract', '')
        cleaned = clean_text(abstract)
        keywords = keywords_list[idx]
        entities = extract_entities(abstract)
        category = assign_category(abstract)

        enriched_fields = {
            "cleaned_text": cleaned,
            "keywords": keywords,
            "entities": entities,
            "category": category
        }

        collection.update_one({'_id': doc['_id']}, {'$set': enriched_fields})
        print(f"✅ Enriched: {doc.get('title', 'Untitled')}")

# For manual testing
if __name__ == "__main__":
    enrich_and_update()
