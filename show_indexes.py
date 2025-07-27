from db import collection

if __name__ == "__main__":
    indexes = collection.index_information()
    for name, info in indexes.items():
        print(f"{name}: {info}")
