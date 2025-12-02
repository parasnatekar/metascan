# check_mongo.py
from pymongo import MongoClient
import os, sys
uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
try:
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    # triggers exception if cannot connect
    info = client.server_info()
    print("MongoDB connection OK — version:", info.get("version"))
    client.close()
except Exception as e:
    print("MongoDB connection FAILED:", e)
    sys.exit(1)
