# ml/topic_model.py

import pickle
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import TfidfVectorizer

MODEL_PATH = "ml/topic_model.pkl"
VECTORIZER_PATH = "ml/topic_vectorizer.pkl"


def train_topic_model(texts, n_topics=8):
    """
    Train LDA topic model on paper abstracts
    """
    vectorizer = TfidfVectorizer(
        stop_words="english",
        max_features=5000
    )

    X = vectorizer.fit_transform(texts)

    lda = LatentDirichletAllocation(
        n_components=n_topics,
        random_state=42
    )
    lda.fit(X)

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(lda, f)

    with open(VECTORIZER_PATH, "wb") as f:
        pickle.dump(vectorizer, f)

    print("✅ Topic model trained and saved")


def extract_topics(text, top_k=5):
    """
    Convert abstract → human readable topics
    """
    with open(MODEL_PATH, "rb") as f:
        lda = pickle.load(f)

    with open(VECTORIZER_PATH, "rb") as f:
        vectorizer = pickle.load(f)

    X = vectorizer.transform([text])
    topic_dist = lda.transform(X)[0]
    topic_id = topic_dist.argmax()

    feature_names = vectorizer.get_feature_names_out()
    topic_words = lda.components_[topic_id]
    top_words = topic_words.argsort()[-top_k:][::-1]

    return [feature_names[i] for i in top_words]
