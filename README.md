# 📚 MetaScan – Research Metadata Indexing System

MetaScan is a powerful, research-oriented document processing and metadata indexing system inspired by the organizational standards of CERN. It ingests structured JSON research documents, applies advanced NLP techniques for enrichment, categorization, and keyword extraction, and enables fast local search via an intuitive Streamlit dashboard.

---

## 🚀 Features

- 🔍 **Advanced Search**: Filter documents by keyword, author, year, and category.
- 🧠 **NLP Enrichment**: Automatic keyword extraction, named entity recognition, and lemmatization.
- 🗂️ **Auto Categorization**: Rule-based category assignment (e.g., AI, Energy).
- 📊 **Streamlit Dashboard**: Easy-to-use UI with upload, search, and future analytics views.
- ⚡ **MongoDB Backend**: Fast and flexible NoSQL database for scalable document storage.
- 📥 **Bulk Upload**: Supports batch document ingestion from JSON files.

---

## 🛠️ Tech Stack

| Layer           | Technologies Used                          |
|----------------|---------------------------------------------|
| **Frontend**    | [Streamlit](https://streamlit.io/)         |
| **Backend**     | Python, Flask (optional for future API)    |
| **Database**    | MongoDB (Local or Cloud via MongoDB Atlas) |
| **NLP**         | spaCy, scikit-learn (TF-IDF)               |
| **Other Tools** | VS Code, Git, GitHub, JSON                 |

---

## 📁 Folder Structure

MetaScan/
├── dashboard.py # Main Streamlit dashboard UI
├── db.py # MongoDB connection setup
├── ingest.py # JSON document ingestion script
├── enrich.py # NLP + categorization processing
├── search.py # Search logic using MongoDB filters
├── setup_indexes.py # MongoDB indexing for optimization
├── sample_docs.json # Sample input file
├── requirements.txt # Python dependencies
└── README.md # Project overview & usage

yaml
Copy
Edit

---

## 🧪 How to Run Locally

### 1. Clone the Repo

```bash
git clone https://github.com/YOUR_USERNAME/metascan.git
cd metascan
2. Create Virtual Environment
bash
Copy
Edit
python -m venv metascan_env
source metascan_env/bin/activate      # For Linux/macOS
metascan_env\Scripts\activate         # For Windows
3. Install Dependencies
bash
Copy
Edit
pip install -r requirements.txt
4. Start MongoDB Server
Ensure MongoDB is running locally on localhost:27017.
Or edit db.py to connect with MongoDB Atlas cloud.

5. Launch the Dashboard
bash
Copy
Edit
streamlit run dashboard.py
Open in your browser at http://localhost:8501

📥 Ingest Sample Data
You can ingest documents using either:

Option A – Upload via UI
Use the sidebar "Upload JSON file" to load sample_docs.json

Option B – CLI Script
bash
Copy
Edit
python ingest.py
🔍 Example Search Queries
Try searching in the dashboard using:

Keyword: AI

Author: Smith

Year: 2023

Category: Energy

🧠 Future Enhancements
📈 Keyword frequency & category charts

📤 Export search results to CSV/Excel

🌐 RESTful API for integration

🧪 ML-based document categorization

🔐 User authentication & document tagging

🌍 Multi-language support

👨‍💻 Author
Paras Natekar
🔗 LinkedIn
📧 parasnatekar@example.com
🌐 Portfolio: parasnatekar.vercel.app

📄 License
This project is open-source under the MIT License.