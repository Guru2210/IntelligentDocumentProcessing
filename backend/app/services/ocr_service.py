"""
OCR Service — extracts words with bounding boxes from PDFs and images.
Supports:
  - PyMuPDF (fitz): native PDF text extraction, word-level bboxes
  - EasyOCR: scanned/image-based documents
"""
import io
import os
import base64
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image
import numpy as np

from app.config import settings


class OCRResult:
    def __init__(self):
        self.pages: List[Dict] = []
        # Each page: {page_number, width, height, words: [...], lines: [...], tables: [...]}
        # Each word: {text, x0, y0, x1, y1, confidence, line_index, word_index, is_handwritten}


def extract_with_pymupdf(pdf_bytes: bytes, dpi: int = 200) -> OCRResult:
    """Extract text and bounding boxes from native PDF using PyMuPDF."""
    result = OCRResult()

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    for page_num in range(len(doc)):
        page = doc[page_num]
        rect = page.rect
        width = rect.width
        height = rect.height

        # Get words with bounding boxes
        words_raw = page.get_text("words")  # returns (x0,y0,x1,y1,word,block_no,line_no,word_no)

        words = []
        lines: Dict[int, List] = {}

        for word_data in words_raw:
            x0, y0, x1, y1, text, block_no, line_no, word_no = word_data

            if not text.strip():
                continue

            # Normalize to 0-1 space
            word = {
                "text": text,
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1,
                "confidence": 1.0,  # PyMuPDF doesn't give confidence for digital text
                "line_index": line_no,
                "word_index": word_no,
                "is_handwritten": False,
            }
            words.append(word)

            # Group into lines
            line_key = (block_no, line_no)
            if line_key not in lines:
                lines[line_key] = []
            lines[line_key].append(word)

        # Build line objects
        line_list = []
        for line_key in sorted(lines.keys()):
            line_words = lines[line_key]
            line_text = " ".join(w["text"] for w in line_words)
            line_x0 = min(w["x0"] for w in line_words)
            line_y0 = min(w["y0"] for w in line_words)
            line_x1 = max(w["x1"] for w in line_words)
            line_y1 = max(w["y1"] for w in line_words)
            line_list.append({
                "text": line_text,
                "x0": line_x0, "y0": line_y0, "x1": line_x1, "y1": line_y1,
            })

        # Render page to image
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")

        result.pages.append({
            "page_number": page_num + 1,
            "width": width,
            "height": height,
            "dpi": dpi,
            "image_b64": img_b64,
            "image_width": pix.width,
            "image_height": pix.height,
            "words": words,
            "lines": line_list,
        })

    doc.close()
    return result


def extract_with_easyocr(image_bytes: bytes, page_number: int = 1) -> Dict:
    """Extract text from a scanned image using EasyOCR."""
    try:
        import easyocr
    except ImportError:
        raise RuntimeError("EasyOCR not installed. Run: pip install easyocr")

    reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img_array = np.array(image)

    results = reader.readtext(img_array, detail=1, paragraph=False)

    width, height = image.size
    words = []
    lines = []

    for idx, (bbox, text, confidence) in enumerate(results):
        # bbox is [[x0,y0],[x1,y0],[x1,y1],[x0,y1]]
        xs = [pt[0] for pt in bbox]
        ys = [pt[1] for pt in bbox]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)

        # Split into words
        text_words = text.split()
        word_width = (x1 - x0) / max(len(text_words), 1)
        for wi, wtext in enumerate(text_words):
            wx0 = x0 + wi * word_width
            wx1 = wx0 + word_width
            words.append({
                "text": wtext,
                "x0": wx0, "y0": y0, "x1": wx1, "y1": y1,
                "confidence": float(confidence),
                "line_index": idx,
                "word_index": wi,
                "is_handwritten": False,
            })

        lines.append({
            "text": text,
            "x0": x0, "y0": y0, "x1": x1, "y1": y1,
        })

    # Convert image to base64
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return {
        "page_number": page_number,
        "width": width,
        "height": height,
        "dpi": 72,
        "image_b64": img_b64,
        "image_width": width,
        "image_height": height,
        "words": words,
        "lines": lines,
    }


def is_scanned_pdf(pdf_bytes: bytes, sample_pages: int = 3) -> bool:
    """Detect if a PDF is scanned (image-only) by checking text extraction."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_words = 0
    pages_to_check = min(sample_pages, len(doc))

    for i in range(pages_to_check):
        page = doc[i]
        words = page.get_text("words")
        total_words += len(words)

    doc.close()
    avg_words = total_words / max(pages_to_check, 1)
    return avg_words < 5  # fewer than 5 words per page = likely scanned


def run_ocr(file_bytes: bytes, filename: str, dpi: int = 200) -> OCRResult:
    """Main OCR entry point. Auto-detects native vs scanned."""
    filename_lower = filename.lower()

    if filename_lower.endswith(".pdf"):
        scanned = is_scanned_pdf(file_bytes)
        if scanned:
            # Convert PDF pages to images and run EasyOCR
            result = OCRResult()
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            for page_num in range(len(doc)):
                page = doc[page_num]
                mat = fitz.Matrix(dpi / 72, dpi / 72)
                pix = page.get_pixmap(matrix=mat)
                img_bytes = pix.tobytes("png")
                page_data = extract_with_easyocr(img_bytes, page_num + 1)
                page_data["width"] = page.rect.width
                page_data["height"] = page.rect.height
                result.pages.append(page_data)
            doc.close()
            return result
        else:
            return extract_with_pymupdf(file_bytes, dpi=dpi)
    elif filename_lower.endswith((".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp")):
        result = OCRResult()
        page_data = extract_with_easyocr(file_bytes, page_number=1)
        result.pages.append(page_data)
        return result
    else:
        raise ValueError(f"Unsupported file format: {filename}")


def render_page_image(pdf_bytes: bytes, page_number: int, dpi: int = 200) -> bytes:
    """Render a specific PDF page to a PNG image."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_number - 1]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    doc.close()
    return img_bytes
