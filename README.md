# 🔬 MetaScan — Research Intelligence System

> An AI-powered research paper ingestion, enrichment, and discovery platform built for serious researchers.

![Python](https://img.shields.io/badge/Python-3.11-blue?style=flat-square&logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-1.x-FF4B4B?style=flat-square&logo=streamlit)
![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-47A248?style=flat-square&logo=mongodb)
![Groq](https://img.shields.io/badge/Groq-LLaMA_3.3_70B-orange?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## What is MetaScan?

MetaScan is a full-stack research document intelligence system. You upload a PDF research paper — MetaScan automatically extracts its metadata, enriches it with NLP, classifies it with ML, stores it in MongoDB, and makes it searchable, summarizable, and queryable via AI.

It was built with a **Research Terminal** aesthetic — dark, precise, and data-dense — inspired by the organizational standards of CERN.

---

## ✨ Features

### 📄 PDF Intelligence Pipeline
- Uploads PDFs and auto-extracts **title, authors, abstract, keywords, DOI, year** using PyMuPDF font-size analysis and regex parsing
- Handles Elsevier, arXiv, IEEE, and general academic PDF layouts
- Detects and warns on duplicate papers (by DOI or normalized title)

### 🧠 NLP Enrichment
- **Tokenization & Lemmatization** via spaCy `en_core_web_sm`
- **TF-IDF keyword extraction** (scikit-learn) — top 5 keywords per paper
- **Named Entity Recognition** — extracts authors, institutions, locations
- **Auto-categorization** — ML Logistic Regression classifier + rule-based fallback across 9 research domains

### ✨ AI Paper Summarization
- One-click structured summary using **Groq API → LLaMA 3.3 70B**
- Returns: TL;DR, Problem, Method, Results, Limitations, Audience, Novelty Score (1–10)
- Rendered as a dark glass card with a novelty bar
- Cached per session to avoid redundant API calls

### 💬 Paper Q&A (RAG)
- Full conversational chat interface per paper
- **RAG architecture** — builds rich context from all paper fields, injects into LLM prompt
- Auto-generates 4 smart suggested questions based on paper category
- Maintains conversation history per paper across follow-ups
- Follow-up pill buttons for common research questions
- Powered by **Groq API → LLaMA 3.3 70B**

### 🔍 Semantic Search
- TF-IDF + cosine similarity across full corpus (title, abstract, keywords, entities, topics, authors, category)
- Filters by keyword, author, year, category
- Returns similarity scores per result
- Similar papers recommendation engine (cosine similarity on abstracts)

### 📊 Analytics Dashboard
- Category distribution donut chart
- Papers by year bar chart
- Top keywords horizontal bar with drill-down
- Most bookmarked papers leaderboard

### 🔐 Authentication System
- Email + password login with bcrypt hashing
- **OTP email verification** on registration (SMTP)
- **Google OAuth** login (no password needed)
- Role-based access: `user` and `admin`
- Audit logging for all auth events

### 🛡️ Admin Panel
- **User Management** — promote/demote/cascade-delete users with their papers and GridFS files
- **Paper Management** — filter, search, delete papers; GridFS orphan file detection and cleanup
- **Admin Analytics** — storage gauge, processing latency charts, login rhythm, top contributors, search intelligence, failed login monitoring, full audit trail

### ⭐ Bookmarks & Personal Library
- Bookmark any paper from Search
- Dedicated Bookmarks page with AI Summary and Q&A per saved paper
- My Uploads page showing all papers you've contributed

### ☁️ MongoDB GridFS Storage
- PDF binaries stored in GridFS (not filesystem)
- Lazy PDF loading — bytes fetched and cached only when download requested
- Orphan detection — finds GridFS files not referenced by any paper document

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Frontend** | Streamlit + Custom CSS | UI framework with terminal aesthetic |
| **Styling** | Syne + Space Mono + Inter (Google Fonts) | Typography system |
| **Charts** | Plotly Graph Objects | All analytics visualizations |
| **Database** | MongoDB (local or Atlas) | Document storage and indexing |
| **File Storage** | MongoDB GridFS | PDF binary storage |
| **NLP** | spaCy `en_core_web_sm` | Tokenization, lemmatization, NER |
| **Search** | scikit-learn TF-IDF + cosine similarity | Semantic search and recommendations |
| **ML Classification** | Logistic Regression on TF-IDF vectors | Auto paper categorization |
| **AI Summarization** | Groq API → LLaMA 3.3 70B | Structured paper summaries |
| **Paper Q&A** | Groq API → LLaMA 3.3 70B + RAG | Conversational paper Q&A |
| **PDF Extraction** | PyMuPDF (fitz) | PDF text and layout parsing |
| **Auth** | bcrypt + smtplib OTP + Google OAuth | User authentication |
| **Topic Modeling** | scikit-learn LDA | Unsupervised topic discovery |

---

## 📁 Project Structure

```
MetaScan/
├── dashboard.py            # Main Streamlit app — all pages and navigation
├── search.py               # TF-IDF search engine + Search UI module
├── qa.py                   # RAG-based Paper Q&A module (Groq + LLaMA)
├── summarizer.py           # AI summarization module (Groq + LLaMA)
├── enrich.py               # NLP enrichment pipeline (spaCy + TF-IDF)
├── pdf_extractor.py        # PDF metadata extraction (PyMuPDF + regex)
├── db.py                   # MongoDB connection and GridFS setup
├── file_storage.py         # GridFS save/download/delete helpers
├── ingest.py               # Bulk JSON ingestion script
├── pipeline.py             # Standalone NLP enrichment pipeline
├── check_mongo.py          # MongoDB connection health check
├── setup_indexes.py        # MongoDB index optimization
├── sample_docs.json        # Sample research documents for testing
│
├── auth/
│   ├── login_view.py       # Login UI, Google OAuth, OTP flow
│   └── register_view.py    # Registration with OTP email verification
│
├── admin/
│   ├── user_management.py  # User CRUD, role management, cascade delete
│   ├── paper_management.py # Paper CRUD, GridFS orphan cleanup
│   ├── admin_analytics.py  # Infrastructure, engagement, security analytics
│   └── logger.py           # Auth, search, admin, and perf event logging
│
├── ml/
│   ├── category_classifier.py  # Train Logistic Regression category model
│   ├── train_once.py           # One-shot model training script
│   ├── recommender.py          # Similar papers via cosine similarity
│   ├── topic_model.py          # LDA topic model training and inference
│   ├── train_topics.py         # Train topic model on corpus
│   ├── assign_topics.py        # Assign topics to all papers in DB
│   ├── category_model.pkl      # Trained classifier (generated)
│   └── category_vectorizer.pkl # Trained vectorizer (generated)
│
├── .streamlit/
│   ├── config.toml         # Streamlit dark theme config
│   └── secrets.toml        # API keys and SMTP config (not committed)
│
├── requirements.txt
└── README.md
```

---

## ⚙️ Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/parasnatekar/metascan.git
cd metascan
```

### 2. Create a Virtual Environment

```bash
python -m venv metascan_env

# Windows
metascan_env\Scripts\activate

# macOS / Linux
source metascan_env/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Secrets

Create `.streamlit/secrets.toml`:

```toml
# MongoDB
MONGO_URI = "mongodb+srv://user:password@cluster.mongodb.net/"

# Groq (free at console.groq.com)
GROQ_API_KEY = "gsk_your_key_here"

# SMTP for OTP emails
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SMTP_USER = "your@gmail.com"
SMTP_PASS = "your_app_password"

# Google OAuth (optional)
GOOGLE_CLIENT_ID     = "your_client_id"
GOOGLE_CLIENT_SECRET = "your_client_secret"
GOOGLE_REDIRECT_URI  = "http://localhost:8501/"
```

### 5. Start MongoDB

Either run MongoDB locally on `localhost:27017` or use a MongoDB Atlas connection string in secrets.

### 6. (Optional) Train the ML Category Classifier

```bash
python ml/train_once.py
```

Requires at least a few documents already ingested with category labels.

### 7. Run the App

```bash
streamlit run dashboard.py
```

Open your browser at **http://localhost:8501**

---

## 🔄 Full Data Flow

```
User uploads PDF
       ↓
PyMuPDF extracts text + layout blocks
Font-size analysis → Title detection
Regex → Abstract, Keywords, DOI, Year
spaCy NER → Author names
       ↓
NLP Enrichment Pipeline:
  → spaCy lemmatizes + cleans abstract
  → TF-IDF extracts top 5 keywords
  → ML Logistic Regression predicts category
  → Rule-based fallback if model unavailable
       ↓
Paper saved to MongoDB
PDF binary saved to MongoDB GridFS
       ↓
User searches → TF-IDF scores corpus → ranked results
       ↓
User opens paper:
  → Groq LLaMA generates structured summary (6 fields + novelty score)
  → User asks question → context assembled → Groq answers from paper context
  → Conversation history maintained per paper in session
```

---

## 🤖 AI Features in Detail

### Summarization
Sends a structured prompt to `llama-3.3-70b-versatile` via Groq forcing JSON output with 7 fields. The model is instructed not to hallucinate — if information is unavailable it leaves the field empty rather than inventing content.

### Paper Q&A (RAG)
Rather than sending just the question, the system first **builds a context string** from every available field of the paper (title, authors, abstract, keywords, entities, topics, cleaned text). This context is injected into the system prompt, and the LLM is instructed to answer only from that context. The last 3 conversation exchanges are included in each request to support follow-up questions.

### Why Groq
Groq provides free inference for LLaMA 3.3 70B with no region restrictions and ~500 tokens/sec throughput — far faster than any other free option, with no quota issues.

---

## 📊 Research Categories

MetaScan auto-classifies papers into:

- AI / Machine Learning
- Data Management
- Computer Vision
- Natural Language Processing
- Healthcare / Bioinformatics
- Cybersecurity
- Robotics
- Social Sciences / Psychology
- Physics / Engineering
- Other

---

## 🌟 Roadmap

| Status | Feature |
|--------|---------|
| ✅ | PDF metadata extraction |
| ✅ | NLP enrichment pipeline |
| ✅ | ML-based auto-categorization |
| ✅ | TF-IDF semantic search |
| ✅ | AI paper summarization (Groq + LLaMA) |
| ✅ | Paper Q&A with RAG (Groq + LLaMA) |
| ✅ | User authentication (OTP + Google OAuth) |
| ✅ | Admin panel (users, papers, analytics) |
| ✅ | MongoDB GridFS PDF storage |
| ✅ | Analytics dashboard |
| ✅ | Bookmark system |
| ✅ | Audit logging |
| 🔜 | Citation extraction & graph visualization |
| 🔜 | Author profile pages |
| 🔜 | RESTful API |
| 🔜 | Multi-language support |

---

## 👨‍💻 Author

**Paras Natekar**  
🔗 [LinkedIn](https://linkedin.com/in/parasnatekar)  
🌐 [parasnatekar.vercel.app](https://parasnatekar.vercel.app)  
📧 paraspnatekar@gmail.com

---

## 📄 License

This project is open-source under the [MIT License](LICENSE).