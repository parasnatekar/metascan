import pickle
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

MODEL_PATH = "ml/category_model.pkl"
VECTORIZER_PATH = "ml/tfidf_vectorizer.pkl"


def train_category_model(texts, labels):
    """
    Train ML model using abstracts and categories
    """
    vectorizer = TfidfVectorizer(
        max_features=3000,
        stop_words="english"
    )

    X = vectorizer.fit_transform(texts)

    model = LogisticRegression(
        max_iter=1000,
        n_jobs=1
    )
    model.fit(X, labels)

    # Save model & vectorizer
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)

    with open(VECTORIZER_PATH, "wb") as f:
        pickle.dump(vectorizer, f)

    print("✅ ML category model trained and saved.")


def predict_category(text):
    """
    Predict category for a new abstract
    """
    try:
        with open(MODEL_PATH, "rb") as f:
            model = pickle.load(f)

        with open(VECTORIZER_PATH, "rb") as f:
            vectorizer = pickle.load(f)

        X = vectorizer.transform([text])
        return model.predict(X)[0]

    except Exception:
        return None
