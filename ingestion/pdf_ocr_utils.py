"""
pdf_ocr_utils.py — Document parsing utilities supporting text extraction from PDFs and OCR fallback.

Uses PyMuPDF (fitz) for text extraction and pytesseract for OCR fallback when pages
contain scanned images or when processing image files.
"""

import os
from typing import Optional


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text content from a PDF file.
    Attempts digital text extraction via PyMuPDF (fitz).
    If no text is found (e.g. scanned image), falls back to OCR via pytesseract.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"File not found: {pdf_path}")

    extracted_pages = []
    has_text = False

    try:
        import fitz  # PyMuPDF

        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            if text and text.strip():
                has_text = True
                extracted_pages.append(text.strip())
            else:
                # Attempt OCR on the page rendered as an image if digital text is empty
                ocr_text = _ocr_page_image(page)
                if ocr_text:
                    extracted_pages.append(ocr_text.strip())
        doc.close()
    except Exception as e:
        print(f"Warning: PyMuPDF extraction failed for {pdf_path}: {e}. Trying raw read.")

    if not extracted_pages and not has_text:
        # Final attempt: read with OCR on full doc if possible
        pass

    return "\n\n".join(extracted_pages)


def _ocr_page_image(page) -> str:
    """Helper to perform OCR on a single PDF page image."""
    try:
        import fitz
        import pytesseract
        from PIL import Image
        import io

        pix = page.get_pixmap(dpi=150)
        img = Image.open(io.BytesIO(pix.tobytes()))
        return pytesseract.image_to_string(img)
    except Exception:
        return ""


def extract_text_from_file(file_path: str) -> str:
    """
    Extract plain text from any supported document format (.txt, .pdf, .json, .csv).
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".txt" or ext == ".json" or ext == ".csv":
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    elif ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext in [".png", ".jpg", ".jpeg", ".tiff"]:
        try:
            import pytesseract
            from PIL import Image

            img = Image.open(file_path)
            return pytesseract.image_to_string(img)
        except Exception as e:
            print(f"Warning: OCR failed on image {file_path}: {e}")
            return ""
    else:
        # Fallback to UTF-8 text read
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
