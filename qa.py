"""Paper Q&A panel (RAG-style) powered by Groq + Streamlit."""

from __future__ import annotations

import html
from typing import Any, Mapping

import streamlit as st


MODEL_NAME = "llama-3.3-70b-versatile"
MAX_CONTEXT_CHARS = 1200
MAX_HISTORY_MSGS = 6  # last 3 exchanges

@st.cache_resource(show_spinner=False)
def _get_groq_client():
    """Create and cache the Groq client.

    Returns None if the SDK is missing or GROQ_API_KEY is not configured.
    """
    try:
        from groq import Groq

        api_key = st.secrets.get("GROQ_API_KEY", "")
        if not api_key:
            return None
        return Groq(api_key=api_key)
    except Exception:
        return None


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x) for x in value if str(x).strip()]
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [str(value)]


def _htmlize(text: str) -> str:
    """Escape text for safe HTML embedding (keeps newlines)."""
    return html.escape(text or "").replace("\n", "<br>")


def _build_context(doc: Mapping[str, Any]) -> str:
    """Assemble all available paper fields into a rich context string."""
    parts = []

    title = doc.get("title", "")
    if title:
        parts.append(f"TITLE: {title}")

    authors = _as_str_list(doc.get("authors", []))
    if authors:
        parts.append(f"AUTHORS: {', '.join(authors)}")

    year = doc.get("year", "")
    if year:
        parts.append(f"YEAR: {year}")

    cat = doc.get("category", "")
    if cat:
        parts.append(f"CATEGORY: {cat}")

    doi = doc.get("doi", "")
    if doi:
        parts.append(f"DOI: {doi}")

    abstract = doc.get("abstract", "")
    if abstract and abstract != "Abstract not found.":
        parts.append(f"ABSTRACT:\n{abstract}")

    keywords = _as_str_list(doc.get("keywords", []))
    if keywords:
        parts.append(f"KEYWORDS: {', '.join(keywords)}")

    entities = _as_str_list(doc.get("entities", []))
    if entities:
        parts.append(f"NAMED ENTITIES: {', '.join(entities)}")

    topics = _as_str_list(doc.get("topics", []))
    if topics:
        parts.append(f"TOPICS: {', '.join(topics)}")

    cleaned = str(doc.get("cleaned_text", "") or "")
    if cleaned and len(cleaned) > 50:
        parts.append(f"PROCESSED TEXT:\n{cleaned[:MAX_CONTEXT_CHARS]}")

    return "\n\n".join(parts)


def _suggest_questions(doc: Mapping[str, Any]) -> list[str]:
    """Generate 4 smart starter questions based on paper metadata."""
    cat = str(doc.get("category", "") or "")

    questions = [
        f"What problem does this paper solve?",
        f"What methodology or approach is used?",
        f"What are the key findings or results?",
        f"What are the limitations of this research?",
    ]

    # Swap in paper-specific question based on category
    cat_questions = {
        "AI / Machine Learning":         "What ML model or architecture is proposed?",
        "Healthcare / Bioinformatics":    "What clinical or biological dataset was used?",
        "Natural Language Processing":    "What NLP task or benchmark is evaluated?",
        "Data Management":                "How does this improve data management practices?",
        "Computer Vision":                "What visual tasks or datasets are used?",
        "Physics / Engineering":          "What engineering problem is addressed?",
    }
    if cat in cat_questions:
        questions[1] = cat_questions[cat]

    return questions[:4]


def _call_groq(client, context: str, history: list[dict[str, str]], question: str) -> str:
    system_prompt = f"""You are an expert research assistant specialized in analyzing academic papers.
You have been given the following paper's information:

---
{context}
---

Answer questions about this paper accurately and concisely based ONLY on the information provided above.
If the answer cannot be determined from the provided information, say so clearly.
Format your answers in clear, readable prose. Use bullet points only when listing multiple distinct items.
Keep responses focused and under 250 words unless the question requires more detail."""

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for msg in history[-MAX_HISTORY_MSGS:]:
        if isinstance(msg, dict) and "role" in msg and "content" in msg:
            messages.append({"role": str(msg["role"]), "content": str(msg["content"])})
    messages.append({"role": "user", "content": question})

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.3,
            max_tokens=400,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as e:
        return f"I couldn’t reach the Q&A model right now. ({type(e).__name__})"


def render_qa_panel(doc: Mapping[str, Any], key_prefix: str = ""):
    """
    Render the full Q&A chat panel for a paper.
    Call this inside any paper expander.
    """
    paper_id = str(doc.get("_id", key_prefix))
    hist_key  = f"qa_history_{paper_id}"
    input_key = f"qa_input_{paper_id}"

    client = _get_groq_client()

    # ── Styles (injected once) ──
    st.markdown("""
    <style>
    .qa-panel {
        background: #070B0F;
        border: 1px solid rgba(0,224,255,0.15);
        border-radius: 12px;
        padding: 20px 22px 16px;
        margin-top: 12px;
    }
    .qa-label {
        font-family: 'Space Mono', monospace;
        font-size: 10px;
        color: #00E0FF;
        letter-spacing: 3px;
        margin-bottom: 14px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .qa-label::after {
        content: '';
        flex: 1;
        height: 1px;
        background: linear-gradient(to right, rgba(0,224,255,0.3), transparent);
    }
    .qa-bubble-user {
        background: rgba(0,224,255,0.07);
        border: 1px solid rgba(0,224,255,0.15);
        border-radius: 10px 10px 0 10px;
        padding: 11px 15px;
        margin: 10px 0 4px auto;
        max-width: 82%;
        font-family: 'Inter', sans-serif;
        font-size: 13px;
        color: #E8EDF2;
        width: fit-content;
        float: right;
        clear: both;
    }
    .qa-bubble-ai {
        background: rgba(13,17,23,0.9);
        border: 1px solid rgba(255,255,255,0.07);
        border-left: 3px solid #00E0FF;
        border-radius: 0 10px 10px 10px;
        padding: 12px 16px;
        margin: 4px 0 10px 0;
        max-width: 88%;
        font-family: 'Inter', sans-serif;
        font-size: 13px;
        color: #C8D0D8;
        line-height: 1.65;
        clear: both;
    }
    .qa-ai-label {
        font-family: 'Space Mono', monospace;
        font-size: 9px;
        color: #00E0FF;
        letter-spacing: 1px;
        margin-bottom: 6px;
    }
    .qa-pill {
        display: inline-block;
        font-family: 'Space Mono', monospace;
        font-size: 10px;
        padding: 5px 11px;
        border: 1px solid rgba(0,224,255,0.2);
        border-radius: 20px;
        color: #00E0FF;
        background: rgba(0,224,255,0.05);
        cursor: pointer;
        margin: 3px 3px 3px 0;
        transition: all 0.15s;
    }
    .qa-pill:hover {
        background: rgba(0,224,255,0.12);
        border-color: rgba(0,224,255,0.4);
    }
    .qa-clear {
        float: none;
        clear: both;
    }
    </style>
    """, unsafe_allow_html=True)

    if client is None:
        st.markdown("""
        <div style="background:rgba(255,107,53,0.08); border:1px solid rgba(255,107,53,0.2);
            border-radius:8px; padding:12px 16px; font-family:'Space Mono',monospace;
            font-size:11px; color:#FF6B35;">
            ⚠️ GROQ_API_KEY not found in secrets.toml — Q&A unavailable
        </div>
        """, unsafe_allow_html=True)
        return

    context = _build_context(doc)

    # Init history
    history = st.session_state.setdefault(hist_key, [])

    def ask_and_append(question: str) -> None:
        q = (question or "").strip()
        if not q:
            return
        with st.spinner(""):
            answer = _call_groq(client, context, history, q)
        history.append({"role": "user", "content": q})
        history.append({"role": "assistant", "content": answer})
        st.session_state[hist_key] = history
        st.rerun()

    # ── Panel header ──
    st.markdown("""
    <div class="qa-panel">
        <div class="qa-label">⬡ PAPER Q&A — LLAMA 3.3 70B</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Suggested questions (only when no history) ──
    if not history:
        suggestions = _suggest_questions(doc)
        st.markdown("""
        <div style="font-family:'Space Mono',monospace; font-size:10px; color:#5A6472;
            letter-spacing:1px; margin: 12px 0 8px;">SUGGESTED QUESTIONS</div>
        """, unsafe_allow_html=True)

        cols = st.columns(2)
        for i, q in enumerate(suggestions):
            with cols[i % 2]:
                if st.button(q, key=f"{key_prefix}_suggest_{i}", use_container_width=True):
                    ask_and_append(q)

    # ── Conversation history ──
    if history:
        st.markdown('<div style="margin-top:16px;">', unsafe_allow_html=True)
        for msg in history:
            if msg["role"] == "user":
                st.markdown(
                    f'<div class="qa-bubble-user">{_htmlize(str(msg.get("content", "")))}</div>',
                    unsafe_allow_html=True,
                )
            else:
                content = _htmlize(str(msg.get("content", "")))
                st.markdown(f"""
                <div class="qa-bubble-ai">
                    <div class="qa-ai-label">METASCAN AI</div>
                    {content}
                </div>
                """, unsafe_allow_html=True)
        st.markdown('<div class="qa-clear"></div></div>', unsafe_allow_html=True)

    # ── Input row ──
    st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)
    col_input, col_btn, col_clear = st.columns([5, 1, 1])

    with col_input:
        user_q = st.text_input(
            "", placeholder="Ask anything about this paper...",
            key=input_key, label_visibility="collapsed"
        )
    with col_btn:
        send = st.button("Ask →", key=f"{key_prefix}_send", use_container_width=True)
    with col_clear:
        if st.button("Clear", key=f"{key_prefix}_clear", use_container_width=True):
            st.session_state[hist_key] = []
            st.rerun()

    if send and user_q.strip():
        ask_and_append(user_q)

    # Follow-up pills (after at least one exchange)
    if history:
        followups = [
            "Can you elaborate on the methodology?",
            "What datasets were used?",
            "How does this compare to prior work?",
            "What future work is suggested?",
        ]
        st.markdown("""
        <div style="font-family:'Space Mono',monospace; font-size:10px; color:#5A6472;
            letter-spacing:1px; margin: 12px 0 6px;">FOLLOW-UP</div>
        """, unsafe_allow_html=True)
        fu_cols = st.columns(2)
        for i, fq in enumerate(followups):
            with fu_cols[i % 2]:
                if st.button(fq, key=f"{key_prefix}_fu_{i}", use_container_width=True):
                    ask_and_append(fq)

                    