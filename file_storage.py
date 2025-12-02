# file_storage.py
from db import fs
import gridfs

def save_pdf_to_gridfs(uploaded_pdf):
    """Store PDF file in GridFS and return file_id."""
    try:
        file_id = fs.put(uploaded_pdf.read(), filename=uploaded_pdf.name)
        return file_id
    except Exception as e:
        print(f"[!] Error saving file to GridFS: {e}")
        return None


def download_pdf_from_gridfs(file_id):
    """Retrieve PDF file bytes from GridFS."""
    try:
        file_data = fs.get(file_id).read()
        return file_data
    except Exception as e:
        print(f"[!] Error retrieving PDF: {e}")
        return None
