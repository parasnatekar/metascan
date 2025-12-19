# ml/train_once.py
import sys
import os
import pickle

# -----------------------------
# 1️⃣ Add project root to path
# -----------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(PROJECT_ROOT)

# -----------------------------
# 2️⃣ Imports
# -----------------------------
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from db import collection

print("🔹 Loading documents from MongoDB...")

# -----------------------------
# 3️⃣ Fetch training data
# -----------------------------
docs = list(collection.find({
    "abstract": {"$exists": True, "$ne": ""},
    "category": {"$exists": True, "$ne": ""}
}))

texts = []
labels = []

for doc in docs:
    abstract = doc.get("abstract")
    category = doc.get("category")

    if isinstance(abstract, str) and isinstance(category, str):
        texts.append(abstract)
        labels.append(category)

# -----------------------------
# 4️⃣ Safety check
# -----------------------------
if len(texts) < 2:
    print("❌ Not enough labeled data to train ML model.")
    print("👉 Add at least 2 documents with categories.")
    sys.exit(1)

print(f"✅ Training on {len(texts)} documents")

# -----------------------------
# 5️⃣ Vectorization
# -----------------------------
vectorizer = TfidfVectorizer(
    stop_words="english",
    max_features=3000
)

X = vectorizer.fit_transform(texts)

# -----------------------------
# 6️⃣ Model training
# -----------------------------
model = LogisticRegression(
    max_iter=1000,
    n_jobs=1
)

model.fit(X, labels)

# -----------------------------
# 7️⃣ Save model SAFELY
# -----------------------------
MODEL_PATH = os.path.join(os.path.dirname(__file__), "ml_category_model.pkl")

with open(MODEL_PATH, "wb") as f:
    pickle.dump(
        {
            "vectorizer": vectorizer,
            "model": model
        },
        f
    )

print("🎉 ML Category Model trained successfully!")
print(f"📦 Saved at: {MODEL_PATH}")
