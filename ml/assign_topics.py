# ml/assign_topics.py

from db import collection
from ml.topic_model import extract_topics


def assign_topics_to_papers():
    print("🔁 Assigning topics to papers...")

    count = 0
    for doc in collection.find({}, {"abstract": 1}):
        abstract = doc.get("abstract", "")
        if not abstract.strip():
            continue

        topics = extract_topics(abstract)

        collection.update_one(
            {"_id": doc["_id"]},
            {"$set": {"topics": topics}}
        )
        count += 1

    print(f"✅ Topics assigned to {count} papers")


if __name__ == "__main__":
    assign_topics_to_papers()
