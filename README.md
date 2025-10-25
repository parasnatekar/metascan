# 📚 MetaScan – Research Metadata Indexing System

**MetaScan** is a research-oriented document processing and metadata indexing system inspired by the organizational data standards of **CERN**.  
It enables researchers to **extract**, **analyze**, and **search** scientific metadata using NLP, TF-IDF, and MongoDB — all through a simple, interactive **Streamlit dashboard**.

---

## 🚀 Features

- 🔍 **Smart Search** — Search by keywords, author, category, or year using MongoDB filters.  
- 🧠 **NLP-Powered Enrichment** — Uses spaCy and TF-IDF for automatic keyword extraction, lemmatization, and named entity recognition.  
- 🗂️ **Auto Categorization** — Assigns research categories (e.g., AI, Neuroscience, Energy) based on document metadata and NLP context.  
- 🧾 **PDF Metadata Extraction** — Upload research papers (PDF) and auto-extract key details like title, author, abstract, and keywords.  
- 📊 **Streamlit Dashboard** — Interactive UI for upload, search, and visualization with a clean, dark-themed `.streamlit/config.toml` setup.  
- ⚡ **MongoDB Backend** — Fast, scalable NoSQL database for document storage and indexing.  
- 📥 **Bulk Upload** — Supports batch ingestion from JSON files or folder-based uploads.  
- 🔧 **Configurable Architecture** — Modular structure, easy to extend with APIs or new processing pipelines.  

---

## 🛠️ Tech Stack

| Layer | Technologies |
|-------|---------------|
| **Frontend** | [Streamlit](https://streamlit.io/), HTML/CSS (custom config) |
| **Backend** | Python 3.x |
| **Database** | MongoDB (local or [MongoDB Atlas](https://www.mongodb.com/atlas)) |
| **NLP & ML** | spaCy, scikit-learn (TF-IDF) |
| **Utilities** | PyMuPDF / pdfminer.six (for PDF extraction), JSON, Git, VS Code |

---

## 📁 Project Structure

MetaScan/
├── dashboard.py # Main Streamlit dashboard (UI + Search)
├── db.py # MongoDB connection setup
├── ingest.py # JSON document ingestion script
├── enrich.py # NLP enrichment and categorization
├── search.py # Search logic and query builder
├── pdf_extractor.py # New module – PDF metadata extractor
├── setup_indexes.py # MongoDB indexing and optimization
├── sample_docs.json # Sample research data
├── .streamlit/
│ └── config.toml # Streamlit theme configuration
├── requirements.txt # Python dependencies
└── README.md # Project overview and documentation

yaml
Copy code

---

## ⚙️ Installation & Setup

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/parasnatekar/metascan.git
cd metascan
2️⃣ Create a Virtual Environment
bash
Copy code
python -m venv metascan_env
metascan_env\Scripts\activate       # For Windows
# OR
source metascan_env/bin/activate    # For macOS/Linux
3️⃣ Install Dependencies
bash
Copy code
pip install -r requirements.txt
4️⃣ Start MongoDB
Make sure MongoDB is running locally on localhost:27017.
Alternatively, connect to MongoDB Atlas by updating the connection string in db.py.

5️⃣ Run the Streamlit Dashboard
bash
Copy code
streamlit run dashboard.py
Open your browser at 👉 http://localhost:8501

🧩 Usage
📥 Uploading Documents
You can upload and index data in two ways:

Option A – Streamlit UI
Go to the dashboard sidebar.

Upload a .json or .pdf file.

Metadata and keywords will be auto-extracted and saved to MongoDB.

Option B – Command Line
bash
Copy code
python ingest.py
🔍 Searching
Use the dashboard’s filters to search by:

Keyword: “machine learning”

Author: “Smith”

Category: “Energy”

Year: “2023”

Results will appear instantly using MongoDB’s optimized text search.

🧠 NLP Workflow
Tokenization & Lemmatization via spaCy

TF-IDF keyword extraction

Named Entity Recognition (authors, institutions, topics)

Category assignment via rule-based tagging

Metadata stored in MongoDB for retrieval

🧾 PDF Metadata Extraction (New!)
The pdf_extractor.py module uses PyMuPDF and regex-based parsing to extract:

Title

Author(s)

Abstract

Keywords

You can directly upload research papers in PDF format — the system will parse and index metadata automatically.

🌟 Future Roadmap
✅ PDF metadata extraction
✅ Custom Streamlit theme config
🧩 RESTful API for programmatic access
📈 Analytics dashboard (keyword & category trends)
🧮 ML-based document categorization
🔐 User authentication & tagging
🌍 Multi-language support

👨‍💻 Author
Paras Natekar
🔗 LinkedIn
🌐 parasnatekar.vercel.app
📧 paraspnatekar@gmail.com

📄 License
This project is open-source under the MIT License.