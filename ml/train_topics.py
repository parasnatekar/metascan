from db import collection
from ml.topic_model import train_topic_model

texts = []

for doc in collection.find({}, {"abstract": 1}):
    if doc.get("abstract"):
        texts.append(doc["abstract"])

print(f"📄 Training on {len(texts)} documents")

train_topic_model(texts, n_topics=12)
