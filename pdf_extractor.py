import fitz  # PyMuPDF
import re
from enrich import clean_text, extract_keywords, extract_entities, assign_category

def extract_text_from_pdf(file):
    """Extract full text from PDF file."""
    pdf_doc = fitz.open(stream=file.read(), filetype="pdf")
    text = ""
    for page in pdf_doc:
        text += page.get_text("text")
    return text

def extract_metadata_from_text(text):
    """Extract metadata heuristically from PDF text."""
    lines = text.split("\n")
    lines = [l.strip() for l in lines if l.strip()]

    # --- Title Extraction ---
    title = lines[0] if lines else "Untitled"

    # --- Abstract Extraction ---
    abstract = ""
    abs_match = re.search(r"(?i)(abstract)\s*[:\-]?\s*(.+?)(?=\n\s*[A-Z]{3,}|Introduction|1\.|\Z)", text, re.S)
    if abs_match:
        abstract = abs_match.group(2).strip()
    else:
        abstract = "Not available"

    # --- Author Extraction ---
    author_candidates = [l for l in lines[1:6] if re.search(r"[A-Z][a-z]+\s+[A-Z][a-z]+", l)]
    authors = author_candidates[0] if author_candidates else "Unknown"

    # --- Keyword Extraction ---
    cleaned = clean_text(text)
    keywords = extract_keywords(cleaned)

    # --- Entity Extraction ---
    entities = extract_entities(cleaned)

    # --- Category Assignment ---
    category = assign_category(text)

    # --- Construct Metadata Document ---
    metadata = {
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "keywords": keywords,
        "entities": entities,
        "category": category
    }

    return metadata
