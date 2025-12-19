# db.py

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import gridfs
import os

# --- Configurable Mongo URI ---
MONGO_URI = os.getenv("MONGO_URI")

# ✅ MINIMAL FALLBACK FOR LOCAL ONLY
if not MONGO_URI:
    MONGO_URI = "mongodb://localhost:27017/"

DB_NAME = "metascan"
COLLECTION_NAME = "documents"


# Return the DB object
def get_db(uri=MONGO_URI, db_name=DB_NAME):
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")  # check connection
        return client[db_name]
    except ConnectionFailure as e:
        print(f"[!] MongoDB connection failed: {e}")
        return None


# Return the collection object
def get_db_collection(uri=MONGO_URI, db_name=DB_NAME, collection_name=COLLECTION_NAME):
    db = get_db(uri, db_name)
    if db is not None:
        return db[collection_name]
    return None


# --- Initialize DB and Collection ---
db = get_db()
collection = db[COLLECTION_NAME] if db is not None else None


# --- GridFS Initialization ---
fs = gridfs.GridFS(db) if db is not None else None


# --- Standalone Test ---
if __name__ == "__main__":
    if db is not None:
        print(f"[+] DB Connected: {DB_NAME}")
        print(f"[+] Collection OK: {collection.name}")
        print(f"[+] GridFS Ready: {hasattr(fs, 'put')}")
    else:
        print("[!] Could not connect to MongoDB.")
