import json
from db import collection

def ingest_documents(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        docs = json.load(f)
        if isinstance(docs, list):
            inserted = 0
            for doc in docs:
                exists = collection.find_one({
                    "title": doc.get("title"),
                    "publication_date": doc.get("publication_date")
                })
                if not exists:
                    collection.insert_one(doc)
                    inserted += 1
            print(f"{inserted} new documents ingested successfully (duplicates skipped).")
        else:
            print("Input file is not a list of documents.")

if __name__ == "__main__":
    ingest_documents("sample_docs.json")
