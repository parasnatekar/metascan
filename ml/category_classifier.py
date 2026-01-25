# category_classifier.py

from pymongo import MongoClient
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib

# -----------------------------
# 1. MongoDB connection
# -----------------------------
client = MongoClient("mongodb://localhost:27017/")
db = client["metascan"]
collection = db["documents"]  # ✅ confirmed

# -----------------------------
# 2. Load data
# -----------------------------
texts = []
labels = []

for doc in collection.find({"category": {"$exists": True}}):
    title = doc.get("title", "")
    abstract = doc.get("abstract", "")
    category = doc.get("category")

    text = f"{title} {abstract}".strip()

    if text and category:
        texts.append(text)
        labels.append(category)

print(f"\nLoaded {len(texts)} labeled documents")

# -----------------------------
# 3. Train-test split
# -----------------------------
X_train, X_test, y_train, y_test = train_test_split(
    texts,
    labels,
    test_size=0.2,
    random_state=42,
    stratify=labels
)

# -----------------------------
# 4. Vectorization
# -----------------------------
vectorizer = TfidfVectorizer(
    max_features=5000,
    ngram_range=(1, 2),
    stop_words="english"
)

X_train_vec = vectorizer.fit_transform(X_train)
X_test_vec = vectorizer.transform(X_test)

# -----------------------------
# 5. Model training
# -----------------------------
model = LogisticRegression(
    max_iter=1000,
    n_jobs=-1
)

model.fit(X_train_vec, y_train)

# -----------------------------
# 6. Evaluation
# -----------------------------
y_pred = model.predict(X_test_vec)

accuracy = accuracy_score(y_test, y_pred)

print("\n============================")
print(f"Validation Accuracy: {accuracy:.4f}")
print("============================\n")
print(classification_report(y_test, y_pred))

# -----------------------------
# 7. Save BOTH model & vectorizer
# -----------------------------
joblib.dump(model, "category_model.pkl")
joblib.dump(vectorizer, "category_vectorizer.pkl")

print("\n✅ category_model.pkl saved")
print("✅ category_vectorizer.pkl saved")
print("🎉 Training completed")
