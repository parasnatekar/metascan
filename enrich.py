# enrich.py

import os
import joblib
import subprocess
import sys
import re
import requests
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher

from db import collection
import spacy
from sklearn.feature_extraction.text import TfidfVectorizer

# ---------------- Load ML Category Model ---------------- #
MODEL_PATH = os.path.join("ml", "category_model.pkl")
VECTORIZER_PATH = os.path.join("ml", "category_vectorizer.pkl")

ml_model = None
ml_vectorizer = None

try:
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError("category_model.pkl not found")

    if not os.path.exists(VECTORIZER_PATH):
        raise FileNotFoundError("category_vectorizer.pkl not found")

    ml_model = joblib.load(MODEL_PATH)
    ml_vectorizer = joblib.load(VECTORIZER_PATH)

    print("✅ ML category model & vectorizer loaded successfully")

except Exception as e:
    print(f"⚠️ ML model loading failed: {e}")
    ml_model = None
    ml_vectorizer = None


# ---------------- Load spaCy Model ---------------- #
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")


# ---------------- External APIs ---------------- #
CROSSREF_API = "https://api.crossref.org/works/"
ARXIV_API = "http://export.arxiv.org/api/query"
OPENALEX_API = "https://api.openalex.org/works"


# ---------------- Helpers ---------------- #
def normalize_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def strip_jats(text):
    """
    Remove JATS XML tags that Crossref returns for some publishers.
    e.g. <jats:p>, <jats:italic>, <jats:sub> etc.
    Falls back gracefully if input is plain text with no tags.
    """
    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", " ", str(text))
    return re.sub(r"\s+", " ", cleaned).strip()


def is_valid_abstract(text, min_words=30):
    """
    Return True only if text has enough real words after stripping tags.
    Prevents storing empty strings or JATS-only noise as abstracts.
    """
    if not text:
        return False
    return len(strip_jats(text).split()) >= min_words


def text_similarity(a, b):
    a = normalize_text(a).lower()
    b = normalize_text(b).lower()
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


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
        tfidf_vectorizer = TfidfVectorizer(
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


# ---------------- 5. External Metadata Lookups ---------------- #
def lookup_crossref_by_doi(doi):
    if not doi:
        return None

    try:
        url = CROSSREF_API + doi
        response = requests.get(
            url,
            headers={"User-Agent": "MetaScan/1.0 (Research Metadata Indexing)"},
            timeout=20
        )

        if response.status_code != 200:
            return None

        data = response.json().get("message", {})

        title = ""
        if data.get("title"):
            title = normalize_text(data["title"][0])

        authors = []
        for a in data.get("author", []):
            given = a.get("given", "")
            family = a.get("family", "")
            name = normalize_text(f"{given} {family}")
            if name:
                authors.append(name)

        year = ""
        published = data.get("published-print") or data.get("published-online") or data.get("created")
        if published and "date-parts" in published:
            try:
                year = str(published["date-parts"][0][0])
            except Exception:
                year = ""

        # FIX: use strip_jats instead of strip_html to handle
        # Crossref's JATS XML format (e.g. <jats:p>...</jats:p>).
        # Only store the abstract if it has real content after stripping.
        raw_abstract = data.get("abstract", "")
        abstract = normalize_text(strip_jats(raw_abstract))
        if not is_valid_abstract(abstract):
            # Crossref returned no abstract or JATS-only noise —
            # set to None so merge_metadata keeps the local PDF abstract.
            abstract = None

        return {
            "title": title,
            "authors": authors,
            "year": year,
            "doi": data.get("DOI", doi),
            "abstract": abstract,       # None means "not available from Crossref"
            "source": "Crossref DOI"
        }

    except Exception as e:
        print(f"⚠️ Crossref lookup failed: {e}")
        return None


def lookup_arxiv_by_id(arxiv_id):
    if not arxiv_id:
        return None

    try:
        response = requests.get(
            ARXIV_API,
            params={"id_list": arxiv_id},
            headers={"User-Agent": "MetaScan/1.0"},
            timeout=20
        )

        if response.status_code != 200 or not response.text.strip():
            return None

        root = ET.fromstring(response.text)

        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom"
        }

        entry = root.find("atom:entry", ns)
        if entry is None:
            return None

        title = ""
        title_el = entry.find("atom:title", ns)
        if title_el is not None and title_el.text:
            title = normalize_text(title_el.text)

        abstract = ""
        summary_el = entry.find("atom:summary", ns)
        if summary_el is not None and summary_el.text:
            abstract = normalize_text(summary_el.text)

        authors = []
        for author in entry.findall("atom:author", ns):
            name_el = author.find("atom:name", ns)
            if name_el is not None and name_el.text:
                authors.append(normalize_text(name_el.text))

        year = ""
        published_el = entry.find("atom:published", ns)
        if published_el is not None and published_el.text:
            year = published_el.text[:4]

        return {
            "title": title,
            "authors": authors,
            "year": year,
            "doi": "",
            "abstract": abstract if is_valid_abstract(abstract) else None,
            "source": "arXiv API"
        }

    except Exception as e:
        print(f"⚠️ arXiv lookup failed: {e}")
        return None


def reconstruct_openalex_abstract(inverted_index):
    if not inverted_index:
        return ""

    words = []
    for word, positions in inverted_index.items():
        for pos in positions:
            words.append((pos, word))

    words.sort(key=lambda x: x[0])
    return " ".join(word for _, word in words)


def lookup_openalex_by_title(title):
    if not title:
        return None

    try:
        response = requests.get(
            OPENALEX_API,
            params={
                "search": title,
                "per-page": 3
            },
            headers={"User-Agent": "MetaScan/1.0"},
            timeout=20
        )

        if response.status_code != 200:
            return None

        results = response.json().get("results", [])
        if not results:
            return None

        best_item = None
        best_score = 0.0

        for item in results:
            candidate_title = normalize_text(item.get("display_name", ""))
            score = text_similarity(title, candidate_title)

            if score > best_score:
                best_score = score
                best_item = item

        # Only accept OpenAlex match if similarity is strong enough
        if not best_item or best_score < 0.80:
            return None

        authors = []
        for a in best_item.get("authorships", []):
            author_obj = a.get("author", {})
            name = normalize_text(author_obj.get("display_name", ""))
            if name:
                authors.append(name)

        abstract = reconstruct_openalex_abstract(best_item.get("abstract_inverted_index"))

        doi = best_item.get("doi", "")
        if doi:
            doi = doi.replace("https://doi.org/", "").strip()

        year = best_item.get("publication_year", "")

        return {
            "title": normalize_text(best_item.get("display_name", title)),
            "authors": authors,
            "year": str(year) if year else "",
            "doi": doi,
            "abstract": normalize_text(abstract) if is_valid_abstract(abstract) else None,
            "source": "OpenAlex title search"
        }

    except Exception as e:
        print(f"⚠️ OpenAlex lookup failed: {e}")
        return None


def merge_metadata(local_meta, external_meta):
    """
    Merge external API result into local PDF metadata.

    Rules:
    - title, authors, year, doi: prefer external if non-empty
    - abstract: use external ONLY if it passes is_valid_abstract()
                otherwise keep local PDF abstract (never overwrite with empty/None)
    """
    if not external_meta:
        return local_meta

    merged = dict(local_meta)

    if external_meta.get("title"):
        merged["title"] = external_meta["title"]

    if external_meta.get("authors"):
        merged["authors"] = external_meta["authors"]

    if external_meta.get("year"):
        merged["year"] = external_meta["year"]

    if external_meta.get("doi"):
        merged["doi"] = external_meta["doi"]

    if external_meta.get("source"):
        merged["source"] = external_meta["source"]

    # Abstract: only replace if external abstract is genuinely valid.
    # This covers three cases:
    #   1. Crossref returns no abstract (None)         → keep local
    #   2. Crossref returns JATS-only garbage (None)   → keep local
    #   3. Crossref/arXiv/OpenAlex returns real text   → use it
    external_abstract = external_meta.get("abstract")
    if is_valid_abstract(external_abstract):
        merged["abstract"] = external_abstract
        print(f"✅ Abstract from {external_meta.get('source', 'API')} "
              f"({len(external_abstract.split())} words)")
    else:
        # Keep whatever local extraction found — even if imperfect
        local_abstract = local_meta.get("abstract", "")
        if is_valid_abstract(local_abstract):
            print(f"ℹ️ API had no abstract — keeping local PDF abstract "
                  f"({len(local_abstract.split())} words)")
        else:
            print("⚠️ No valid abstract from API or local extraction.")

    return merged


# ---------------- 6. Enrich Single PDF Metadata ---------------- #
def enrich_pdf_metadata(metadata):
    # ----- External enrichment priority -----
    doi = (metadata.get("doi") or "").strip()
    arxiv_id = (metadata.get("arxiv_id") or "").strip()
    title = (metadata.get("title") or "").strip()

    external_meta = None

    # 1. Highest priority: DOI -> Crossref
    if doi:
        external_meta = lookup_crossref_by_doi(doi)

    # 2. Next priority: arXiv ID -> arXiv API
    if not external_meta and arxiv_id:
        external_meta = lookup_arxiv_by_id(arxiv_id)

    # 3. Next priority: title -> OpenAlex
    if not external_meta and title and title.lower() != "untitled":
        external_meta = lookup_openalex_by_title(title)

    # 4. Final fallback: local extracted metadata stays as-is
    metadata = merge_metadata(metadata, external_meta)

    # ----- Internal enrichment after merge -----
    abstract = metadata.get("abstract", "")

    cleaned = clean_text(abstract)
    entities = extract_entities(abstract)

    ml_category = predict_ml_category(abstract)
    rule_category = assign_category(abstract)
    final_category = ml_category if ml_category else rule_category

    try:
        tfidf_vec = TfidfVectorizer(
            stop_words="english",
            max_features=5
        )
        tfidf_vec.fit([abstract])
        keywords = list(tfidf_vec.get_feature_names_out())
    except Exception:
        keywords = metadata.get("keywords", []) or []

    metadata.update({
        "cleaned_text": cleaned,
        "keywords": keywords,
        "entities": entities,
        "category": final_category
    })

    return metadata


# ---------------- 7. Enrich All DB Documents ---------------- #
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

        print(f"ML={ml_category} | RULE={rule_category} | FINAL={final_category}")

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