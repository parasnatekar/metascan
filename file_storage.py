# file_storage.py

from bson import ObjectId
from db import fs
import gridfs


def save_pdf_to_gridfs(uploaded_pdf):
    """
    Store a PDF file in MongoDB GridFS.
    Returns the ObjectId of the stored file.
    """
    try:
        # Always read bytes once
        pdf_bytes = uploaded_pdf.read()

        if not pdf_bytes:
            raise ValueError("Empty PDF file")

        file_id = fs.put(
            pdf_bytes,
            filename=uploaded_pdf.name,
            contentType="application/pdf"
        )

        return file_id

    except Exception as e:
        print(f"[!] Error saving file to GridFS: {e}")
        return None


def download_pdf_from_gridfs(file_id):
    """
    Retrieve PDF file bytes from MongoDB GridFS.
    Returns bytes or None.
    """
    try:
        # Convert string -> ObjectId if needed
        if isinstance(file_id, str):
            file_id = ObjectId(file_id)

        # Fetch file
        grid_out = fs.get(file_id)

        # Read bytes safely
        pdf_bytes = grid_out.read()

        if not pdf_bytes:
            raise ValueError("Retrieved empty PDF")

        return pdf_bytes

    except gridfs.NoFile:
        print(f"[!] No PDF found in GridFS for file_id: {file_id}")
        return None

    except Exception as e:
        print(f"[!] Error retrieving PDF from GridFS: {e}")
        return None
