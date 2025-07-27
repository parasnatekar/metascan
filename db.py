# db.py

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import os

# --- Configurable Mongo URI (env variable preferred) ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = "metascan"
COLLECTION_NAME = "documents"

def get_db_collection(uri=MONGO_URI, db_name=DB_NAME, collection_name=COLLECTION_NAME):
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        client.admin.command('ping')  # Check connection
        db = client[db_name]
        collection = db[collection_name]
        return collection
    except ConnectionFailure as e:
        print(f"[!] MongoDB connection failed: {e}")
        return None

# Expose collection directly
collection = get_db_collection()

# --- Optional: Test when running standalone ---
if __name__ == "__main__":
    if collection:
        print(f"[+] Connected to MongoDB. Total documents: {collection.count_documents({})}")
        for doc in collection.find().limit(5):
            print(doc)
    else:
        print("[!] Could not connect to MongoDB.")
