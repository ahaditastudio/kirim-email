import fitz  # PyMuPDF


def get_pdf_info(file_path: str) -> dict:
    """Get PDF metadata: page count, file size."""
    doc = fitz.open(file_path)
    page_count = doc.page_count
    doc.close()
    return {
        "page_count": page_count,
    }
