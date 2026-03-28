# pdf_extractor.py
import fitz
import re
from enrich import clean_text, extract_keywords, extract_entities, assign_category
import spacy

# Load spaCy model safely
try:
    nlp = spacy.load("en_core_web_sm")
except Exception:
    nlp = None


# ----------- PDF TEXT + LAYOUT EXTRACTION ----------- #
def extract_pdf_text_and_layout(file, max_pages=3):
    """Extract text and layout info from first pages of a PDF."""
    file.seek(0)
    data = file.read()
    doc = fitz.open(stream=data, filetype="pdf")

    text = ""
    blocks = []

    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        page_text = page.get_text("text")
        if page_text:
            text += page_text + "\n"

        page_dict = page.get_text("dict")
        blocks.extend(page_dict.get("blocks", []))

    doc.close()
    return data, text, blocks


# ----------- TITLE DETECTION (font-based merging) ----------- #
def detect_title(blocks):
    """Detect full title by merging consecutive large-font spans."""
    spans = []

    for b in blocks:
        if "lines" not in b:
            continue

        for line in b.get("lines", []):
            for s in line.get("spans", []):
                txt = s.get("text", "").strip()
                if len(txt.split()) < 2:
                    continue

                if re.match(r"(?i)^(abstract|keywords|introduction|doi|journal|volume|issue)$", txt):
                    continue

                # Skip arXiv / preprint header lines
                if re.search(r"(?i)arxiv:\d{4}\.\d+", txt):
                    continue

                if re.search(r"\[[a-zA-Z\-.]+\]", txt):
                    continue

                if re.search(r"(?i)^\d{1,2}\s+[A-Za-z]{3}\s+\d{4}$", txt):
                    continue

                spans.append((txt, s.get("size", 0), s.get("bbox", [0, 0, 0, 0])[1]))

    if not spans:
        return "Untitled"

    max_font = max(s[1] for s in spans)
    title_spans = [s for s in spans if s[1] >= max_font - 0.5 and s[2] < 260]
    title_spans = sorted(title_spans, key=lambda x: x[2])

    title = " ".join(s[0] for s in title_spans)
    title = re.sub(r"\s+", " ", title).strip()

    # Remove obvious trailing junk
    title = re.sub(r"(?i)\babstract\b.*$", "", title).strip()
    title = re.sub(r"\s{2,}", " ", title).strip()

    if len(title) < 8:
        return "Untitled"

    return title


# ----------- AUTHOR DETECTION ----------- #
def detect_authors(lines, title):
    """Find probable author names directly below the title."""
    try:
        idx = next(i for i, l in enumerate(lines) if title[:40].lower() in l.lower())
    except StopIteration:
        idx = 0

    candidate_block = " ".join(lines[idx + 1: idx + 8])

    # Remove emails, affiliations, and symbols
    candidate_block = re.sub(r"\S+@\S+", " ", candidate_block)
    candidate_block = re.sub(r"(?i)\b(university|department|school|college|institute|hospital|laboratory|centre|center)\b.*", " ", candidate_block)
    candidate_block = re.sub(r"[\d*†‡§]+", " ", candidate_block)

    # Regex for names
    names = re.findall(
        r"\b[A-Z][a-z]+(?:\s[A-Z]\.)?(?:\s[A-Z][a-z]+){1,2}\b",
        candidate_block
    )

    names = [
        n for n in names
        if not re.search(
            r"(Abstract|Keywords|Introduction|Figure|Table|Department|University|Research|Center|Centre|Metadata|Data|Germany|JSON|Collaboration)",
            n
        )
    ]

    # spaCy fallback
    if not names and nlp:
        doc_nlp = nlp(candidate_block)
        names = [ent.text for ent in doc_nlp.ents if ent.label_ == "PERSON"]

    # unique + limit
    names = list(dict.fromkeys([n.strip() for n in names if n.strip()]))

    return names if names else []


# ----------- ABSTRACT DETECTION ----------- #
def detect_abstract(text):
    """
    Extract abstract using multiple patterns tried in order.
    Handles standard headers, Elsevier spaced-letter format, and loose fallbacks.
    Returns empty string if no valid abstract found (minimum 30 words required).
    """
    if not text:
        return ""

    def is_valid(candidate, min_words=30):
        """Clean up and validate a candidate abstract string."""
        candidate = re.sub(r"\s+", " ", candidate).strip()
        return len(candidate.split()) >= min_words, candidate

    # --- Pattern 1: Standard "Abstract" header with known section end markers ---
    m = re.search(
        r"(?is)\babstract\b[:\s\-]*([\s\S]*?)"
        r"(?=\n\s*(?:keywords?|index\s*terms?|introduction|1[\.\s]|I[\.\s]|II[\.\s]|materials\s*and\s*methods|methodology))",
        text,
    )
    if m:
        ok, candidate = is_valid(m.group(1))
        if ok:
            return candidate

    # --- Pattern 2: Elsevier spaced-letter "A B S T R A C T" format ---
    # e.g. "A B S T R A C T" on its own line followed by the body
    m = re.search(
        r"(?is)A\s+B\s+S\s+T\s+R\s+A\s+C\s+T\s*([\s\S]*?)"
        r"(?=\n\s*(?:keywords?|index\s*terms?|introduction|1[\.\s]|©|\d{4}\s*the\s*author))",
        text,
    )
    if m:
        ok, candidate = is_valid(m.group(1))
        if ok:
            return candidate

    # --- Pattern 3: Loose fallback — grab up to 1800 chars after "abstract" ---
    m = re.search(r"(?is)\babstract\b[:\s\-]*([\s\S]{150,1800})", text)
    if m:
        # Cut at first likely section header
        chunk = re.split(
            r"(?is)\n\s*(?:keywords?|index\s*terms?|introduction|1[\.\s]|materials\s*and\s*methods)",
            m.group(1)
        )[0]
        ok, candidate = is_valid(chunk)
        if ok:
            return candidate

    # --- Pattern 4: Last resort plain search without relying on the word "abstract" ---
    lowered = text.lower()
    start = lowered.find("abstract")
    if start != -1:
        chunk = text[start + len("abstract"):start + 2500]
        chunk = re.sub(r"^[:\s\-]+", "", chunk).strip()
        chunk = re.split(
            r"(?is)\b(keywords?|index\s*terms?|introduction|materials\s*and\s*methods|methodology)\b",
            chunk
        )[0].strip()
        ok, candidate = is_valid(chunk)
        if ok:
            return candidate

    return ""


# ----------- DOI DETECTION ----------- #
def detect_doi(text):
    if not text:
        return None

    doi_match = re.search(
        r"\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)\b",
        text.replace("\n", " ")
    )
    return doi_match.group(1).strip() if doi_match else None


# ----------- ARXIV DETECTION ----------- #
def detect_arxiv_id(text):
    if not text:
        return None

    match = re.search(r"arxiv:(\d{4}\.\d+)", text, re.I)
    if match:
        return match.group(1)

    return None


# ----------- YEAR DETECTION ----------- #
def detect_year(text):
    if not text:
        return ""

    years = re.findall(r"\b(19\d{2}|20\d{2})\b", text[:4000])
    if years:
        return years[0]

    return ""


# ----------- KEYWORD DETECTION ----------- #
def detect_keywords(text, abstract):
    kw_match = re.search(r"(?i)\b(keywords?|index terms)\b[:\s]*([^\n]+)", text)
    if kw_match:
        return [k.strip() for k in re.split(r"[;,]", kw_match.group(2)) if k.strip()]

    # fallback to your existing keyword extractor
    fallback_keywords = extract_keywords([{"abstract": abstract}])
    if fallback_keywords and len(fallback_keywords) > 0:
        return fallback_keywords[0]

    return []


# ----------- MAIN EXTRACTION FUNCTION ----------- #
def extract_metadata_from_pdf(file):
    file_bytes, text, blocks = extract_pdf_text_and_layout(file)
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # --- Title ---
    title = detect_title(blocks)

    # --- Authors ---
    authors = detect_authors(lines, title)

    # --- Abstract ---
    abstract = detect_abstract(text)

    # --- Keywords ---
    keywords = detect_keywords(text, abstract)

    # --- Entities ---
    entities = extract_entities(abstract) if abstract else []

    # --- Category ---
    cat = assign_category(abstract or text[:2000])
    if re.search(r"\b(metadata|rdm|data management|repository)\b", abstract or text, re.I):
        cat = "Data Management"

    # --- DOI ---
    doi = detect_doi(text)

    # --- arXiv ---
    arxiv_id = detect_arxiv_id(text)

    # --- Year ---
    year = detect_year(text)

    # --- Clean text ---
    cleaned = clean_text(abstract if abstract else text[:3000])

    metadata = {
        "title": title if title else file.name.replace(".pdf", ""),
        "authors": authors,
        "abstract": abstract if abstract else "",
        "keywords": keywords,
        "entities": entities,
        "category": cat if cat else "Uncategorized",
        "doi": doi,
        "arxiv_id": arxiv_id,
        "year": year if year else "",
        "cleaned_text": cleaned,
        "raw_text": text[:15000],   # for later enrichment fallback
        "source": "Uploaded PDF",
    }
    return metadata


# ----------- STREAMLIT WRAPPER ----------- #
def process_pdf(file):
    """Wrapper for Streamlit dashboard compatibility."""
    return extract_metadata_from_pdf(file)