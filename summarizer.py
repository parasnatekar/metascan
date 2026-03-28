# summarizer.py
# AI-powered paper summarization using Groq API (free tier, no region restrictions)
# Setup: pip install groq
# Get free API key at: https://console.groq.com  (sign up → API Keys → Create key)

import re
import json
import streamlit as st

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────

def _get_api_key() -> str | None:
    try:
        return st.secrets["GROQ_API_KEY"]
    except Exception:
        return st.session_state.get("_groq_api_key")


# ─────────────────────────────────────────────
# Core summarization prompt
# ─────────────────────────────────────────────

SUMMARY_PROMPT = """You are a research assistant. Given the metadata of an academic paper, produce a structured summary in exactly this JSON format (no markdown fences, raw JSON only):

{
  "tldr": "One sentence summary (max 25 words)",
  "problem": "What problem does this paper solve?",
  "method": "What approach or technique do they use?",
  "results": "What are the key findings or results?",
  "limitations": "What are the limitations or future work mentioned?",
  "audience": "Who would benefit from reading this paper?",
  "novelty_score": 7
}

novelty_score is an integer 1-10 estimating how novel/impactful this work is based on the abstract.

Paper metadata:
Title: PAPER_TITLE
Authors: PAPER_AUTHORS
Year: PAPER_YEAR
Category: PAPER_CATEGORY
Abstract: PAPER_ABSTRACT

Return only the raw JSON object. No explanation, no markdown."""


def summarize_paper(doc: dict) -> dict | None:
    if not GROQ_AVAILABLE:
        return {"error": "groq not installed. Run: pip install groq"}

    api_key = _get_api_key()
    if not api_key:
        return {"error": "NO_API_KEY"}

    abstract = (doc.get("abstract") or "").strip()
    if not abstract or abstract == "Abstract not found." or len(abstract.split()) < 20:
        return {"error": "Abstract too short or missing — cannot generate summary."}

    title    = doc.get("title", "Untitled")
    authors  = ", ".join(doc.get("authors", [])) if isinstance(doc.get("authors"), list) else str(doc.get("authors", ""))
    year     = str(doc.get("year", "Unknown"))
    category = doc.get("category", "Unknown")

    prompt = (SUMMARY_PROMPT
        .replace("PAPER_TITLE", title)
        .replace("PAPER_AUTHORS", authors)
        .replace("PAPER_YEAR", year)
        .replace("PAPER_CATEGORY", category)
        .replace("PAPER_ABSTRACT", abstract[:3000])
    )

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=600,
        )
        raw = response.choices[0].message.content.strip()

        # Strip accidental markdown fences
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)

        summary = json.loads(raw)
        return summary

    except json.JSONDecodeError:
        return {"error": "Model returned invalid JSON. Try regenerating."}
    except Exception as e:
        return {"error": f"Groq API error: {e}"}


# ─────────────────────────────────────────────
# Streamlit UI component
# ─────────────────────────────────────────────

def render_summary_card(doc: dict, key_prefix: str = ""):
    cache_key = f"summary_{key_prefix}"

    api_key = _get_api_key()
    if not api_key:
        st.warning("Add `GROQ_API_KEY` to `.streamlit/secrets.toml`.")
        manual_key = st.text_input(
            "Or paste your Groq API key here (temporary)",
            type="password",
            key=f"groq_key_input_{key_prefix}"
        )
        if manual_key:
            st.session_state["_groq_api_key"] = manual_key
            st.rerun()
        return

    if cache_key in st.session_state:
        _render_summary_result(st.session_state[cache_key])
        if st.button("🔄 Regenerate Summary", key=f"regen_{key_prefix}"):
            del st.session_state[cache_key]
            st.rerun()
        return

    if st.button("✨ Generate AI Summary", key=f"summarize_{key_prefix}", type="primary"):
        with st.spinner("Analyzing paper with Llama 3.3 70B..."):
            result = summarize_paper(doc)

        if result and "error" not in result:
            st.session_state[cache_key] = result
            st.rerun()
        else:
            err = result.get("error", "Unknown error") if result else "Unknown error"
            st.error(f"❌ Summary failed: {err}")


def _render_summary_result(summary: dict):
    novelty = summary.get("novelty_score", 0)
    try:
        novelty = int(novelty)
    except Exception:
        novelty = 0
    novelty = max(0, min(10, novelty))

    novelty_color = "#22C55E" if novelty >= 7 else "#F59E0B" if novelty >= 4 else "#EF4444"
    novelty_bar = "█" * novelty + "░" * (10 - novelty)

    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, rgba(15,23,42,0.95), rgba(30,41,59,0.95));
            border: 1px solid rgba(56,189,248,0.3);
            border-radius: 16px;
            padding: 20px 24px;
            margin: 12px 0;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        ">
            <div style="font-size:13px; color:#94A3B8; letter-spacing:1px; margin-bottom:8px;">
                ✨ AI SUMMARY — LLAMA 3.3 70B (GROQ)
            </div>
            <div style="font-size:17px; font-weight:700; color:#F1F5F9; border-left:3px solid #38BDF8; padding-left:12px; margin-bottom:16px; line-height:1.5;">
                {summary.get("tldr", "—")}
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px;">
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:14px;">
                    <div style="color:#38BDF8; font-size:11px; font-weight:700; margin-bottom:6px;">🎯 PROBLEM</div>
                    <div style="color:#CBD5E1; font-size:13px; line-height:1.5;">{summary.get("problem", "—")}</div>
                </div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:14px;">
                    <div style="color:#A78BFA; font-size:11px; font-weight:700; margin-bottom:6px;">🔬 METHOD</div>
                    <div style="color:#CBD5E1; font-size:13px; line-height:1.5;">{summary.get("method", "—")}</div>
                </div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:14px;">
                    <div style="color:#22C55E; font-size:11px; font-weight:700; margin-bottom:6px;">📊 RESULTS</div>
                    <div style="color:#CBD5E1; font-size:13px; line-height:1.5;">{summary.get("results", "—")}</div>
                </div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:14px;">
                    <div style="color:#F59E0B; font-size:11px; font-weight:700; margin-bottom:6px;">⚠️ LIMITATIONS</div>
                    <div style="color:#CBD5E1; font-size:13px; line-height:1.5;">{summary.get("limitations", "—")}</div>
                </div>
            </div>
            <div style="margin-top:14px; background:rgba(255,255,255,0.04); border-radius:10px; padding:14px;">
                <div style="color:#94A3B8; font-size:11px; font-weight:700; margin-bottom:6px;">👥 BEST FOR</div>
                <div style="color:#CBD5E1; font-size:13px;">{summary.get("audience", "—")}</div>
            </div>
            <div style="margin-top:14px; display:flex; align-items:center; gap:12px;">
                <div style="color:#94A3B8; font-size:12px;">Novelty Score</div>
                <div style="font-family:monospace; color:{novelty_color}; font-size:14px; letter-spacing:1px;">{novelty_bar}</div>
                <div style="color:{novelty_color}; font-weight:700;">{novelty}/10</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )