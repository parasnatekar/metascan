# pdf_extractor.py
import fitz
import re
import io
from enrich import clean_text, extract_keywords, extract_entities, assign_category
import spacy

# Load spaCy model safely
try:
    nlp = spacy.load("en_core_web_sm")
except Exception:
    nlp = None


# ----------- PDF TEXT + LAYOUT EXTRACTION ----------- #
def extract_pdf_text_and_layout(file, max_pages=2):
    """Extract text and layout info from first pages of a PDF."""
    data = file.read()
    doc = fitz.open(stream=data, filetype="pdf")
    text = ""
    blocks = []
    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        text += page.get_text("text")
        blocks.extend(page.get_text("dict")["blocks"])
    doc.close()
    return data, text, blocks


# ----------- TITLE DETECTION (font-based merging) ----------- #
def detect_title(blocks):
    """Detect full title by merging consecutive large-font spans."""
    spans = []
    for b in blocks:
        for line in b.get("lines", []):
            for s in line.get("spans", []):
                txt = s["text"].strip()
                if len(txt.split()) < 2:
                    continue
                if re.match(r"(?i)^(crc|journal|data\s*science|extinction\s*learning)", txt):
                    continue
                spans.append((txt, s["size"], s["bbox"][1]))

    if not spans:
        return "Untitled"

    max_font = max(s[1] for s in spans)
    title_spans = [s for s in spans if s[1] >= max_font - 0.5 and s[2] < 250]
    title_spans = sorted(title_spans, key=lambda x: x[2])

    # Merge consecutive title lines
    title = " ".join(s[0] for s in title_spans)
    title = re.sub(r"\s+", " ", title).strip()

    # Stop merging if we reach line ending with "Center" or "."
    title = re.split(r"(?<=Center|centre)\b|\.$", title)[0].strip()

    return title


# ----------- AUTHOR DETECTION ----------- #
def detect_authors(lines, title):
    """Find probable author names directly below the title."""
    try:
        idx = next(i for i, l in enumerate(lines) if title.split(":")[0] in l)
    except StopIteration:
        idx = 0

    block = " ".join(lines[idx + 1 : idx + 10])
    # Only allow capitalized name patterns (First Last or First M. Last)
    names = re.findall(r"\b[A-Z][a-z]+(?:\s[A-Z]\.)?\s[A-Z][a-z]+\b", block)
    names = [
        n
        for n in names
        if not re.search(
            r"(University|Research|Center|Metadata|Data|Core|Schema|Germany|JSON|Keywords|Collaboration)",
            n,
        )
    ]

    # spaCy fallback
    if not names and nlp:
        doc_nlp = nlp(block)
        names = [ent.text for ent in doc_nlp.ents if ent.label_ == "PERSON"]

    return list(dict.fromkeys(names)) or ["Unknown Author"]


# ----------- MAIN EXTRACTION FUNCTION ----------- #
def extract_metadata_from_pdf(file):
    file_bytes, text, blocks = extract_pdf_text_and_layout(file)
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # --- Title ---
    title = detect_title(blocks)

    # --- Authors ---
    authors = detect_authors(lines, title)

    # --- Abstract ---
    abs_match = re.search(
        r"(?is)\babstract\b[:\s-]*([\s\S]*?)(?=\n\s*(?:keywords|introduction|1\.|I\.|II\.))",
        text,
    )
    abstract = abs_match.group(1).strip() if abs_match else "Abstract not found."

    # --- Keywords ---
    kw_match = re.search(r"(?i)(keywords?)[:\s]*([^\n]+)", text)
    if kw_match:
        keywords = [k.strip() for k in re.split(r"[;,]", kw_match.group(2)) if k.strip()]
    else:
        keywords = extract_keywords([{"abstract": abstract}])[0]

    # --- Entities ---
    entities = extract_entities(abstract)

    # --- Category override ---
    cat = assign_category(abstract)
    if re.search(r"\b(metadata|rdm|data management|repository)\b", abstract, re.I):
        cat = "Data Management"

    # --- DOI (fix trailing text) ---
    doi_match = re.search(r"(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)", text.replace("\n", ""))
    doi = doi_match.group(1).strip() if doi_match else None

    # --- Year ---
    year_match = re.search(r"\b(19|20)\d{2}\b", text)
    year = year_match.group(0) if year_match else "Unknown Year"

    # --- Clean text ---
    cleaned = clean_text(abstract)

    metadata = {
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "keywords": keywords,
        "entities": entities,
        "category": cat,
        "doi": doi,
        "year": year,
        "cleaned_text": cleaned,
        "source": "Uploaded PDF",
    }
    return metadata


# ----------- STREAMLIT WRAPPER ----------- #
def process_pdf(file):
    """Wrapper for Streamlit dashboard compatibility."""
    return extract_metadata_from_pdf(file)
