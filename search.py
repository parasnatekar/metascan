from db import collection

def search_docs(keyword=None, author=None, year=None, category=None, limit=20):
    query = {}

    if keyword:
        query["keywords"] = {"$in": [keyword.lower()]}  # exact match is better for keywords

    if author:
        query["authors"] = {"$elemMatch": {"$regex": f".*{author}.*", "$options": "i"}}

    if year:
        query["year"] = str(year)

    if category:
        query["category"] = {"$regex": f".*{category}.*", "$options": "i"}

    projection = {"_id": 0}  # exclude MongoDB object ID
    results = list(collection.find(query, projection).limit(limit))

    if not results:
        print("❌ No matching documents found.")
        return []

    print(f"✅ Found {len(results)} result(s):\n")
    for idx, doc in enumerate(results, 1):
        print(f"Result {idx}:")
        for k, v in doc.items():
            print(f"  {k}: {v}")
        print("-" * 40)

    return results

if __name__ == "__main__":
    # Uncomment these for interactive use:
    # keyword = input("Keyword (optional): ").strip() or None
    # author = input("Author (optional): ").strip() or None
    # year = input("Year (optional): ").strip() or None
    # category = input("Category (optional): ").strip() or None

    # Example query:
    results = search_docs(
        keyword="neural",
        author="Singh",
        year="2023",
        category="AI",
        limit=10
    )
