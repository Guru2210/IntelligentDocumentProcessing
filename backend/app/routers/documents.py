"""Documents router — upload, OCR, page images, word data."""
import io
import uuid
import base64
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Query
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Document, Page, Word, DetectedTable, SelectionMark, OCRStatus, LabelStatus
from app.config import settings

router = APIRouter(prefix="/api/v1/projects/{project_id}/documents", tags=["documents"])

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp"}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB


class DocumentOut(BaseModel):
    id: str
    filename: str
    original_filename: str
    page_count: int
    file_size: int
    ocr_status: str
    label_status: str
    is_scanned: bool
    created_at: str
    class Config:
        from_attributes = True


class WordOut(BaseModel):
    id: str
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    confidence: float
    line_index: int
    word_index: int


class PageOut(BaseModel):
    id: str
    page_number: int
    width: float
    height: float
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    word_count: int = 0


class TableBboxRequest(BaseModel):
    page_number: int
    bbox: List[float]


@router.get("/", response_model=List[DocumentOut])
def list_documents(project_id: str, db: Session = Depends(get_db)):
    docs = db.query(Document).filter(Document.project_id == project_id).order_by(Document.created_at).all()
    return [_doc_to_out(d) for d in docs]


@router.post("/", response_model=DocumentOut, status_code=201)
async def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
):
    from pathlib import Path
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}")

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(400, "File too large (max 100MB)")

    # Upload to MinIO
    from app.services.storage_service import upload_file, ensure_bucket_exists
    ensure_bucket_exists()
    doc_id = str(uuid.uuid4())
    safe_name = file.filename.replace(" ", "_")
    minio_key = f"projects/{project_id}/documents/{doc_id}/{safe_name}"
    upload_file(file_bytes, minio_key, content_type=file.content_type or "application/octet-stream")

    doc = Document(
        id=doc_id,
        project_id=project_id,
        filename=safe_name,
        original_filename=file.filename,
        minio_key=minio_key,
        file_size=len(file_bytes),
        ocr_status=OCRStatus.pending,
        label_status=LabelStatus.unlabeled,
    )
    db.add(doc)
    db.commit()

    # Run OCR in background
    background_tasks.add_task(_run_ocr_for_document, doc_id, project_id, file_bytes, safe_name)

    db.refresh(doc)
    return _doc_to_out(doc)


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(project_id: str, doc_id: str, db: Session = Depends(get_db)):
    doc = _get_doc_or_404(doc_id, project_id, db)
    return _doc_to_out(doc)


@router.delete("/{doc_id}", status_code=204)
def delete_document(project_id: str, doc_id: str, db: Session = Depends(get_db)):
    doc = _get_doc_or_404(doc_id, project_id, db)
    from app.services.storage_service import delete_file
    delete_file(doc.minio_key)
    db.delete(doc)
    db.commit()


@router.get("/{doc_id}/pages", response_model=List[PageOut])
def list_pages(project_id: str, doc_id: str, db: Session = Depends(get_db)):
    doc = _get_doc_or_404(doc_id, project_id, db)
    pages = db.query(Page).filter(Page.document_id == doc.id).order_by(Page.page_number).all()
    result = []
    for page in pages:
        word_count = db.query(Word).filter(Word.page_id == page.id).count()
        result.append(PageOut(
            id=str(page.id),
            page_number=page.page_number,
            width=page.width,
            height=page.height,
            word_count=word_count,
        ))
    return result


@router.get("/{doc_id}/pages/{page_number}/image")
def get_page_image(project_id: str, doc_id: str, page_number: int, db: Session = Depends(get_db)):
    """Return the rendered page image as PNG."""
    doc = _get_doc_or_404(doc_id, project_id, db)

    if doc.ocr_status != OCRStatus.complete:
        raise HTTPException(400, f"OCR not complete yet. Status: {doc.ocr_status}")

    page = db.query(Page).filter(
        Page.document_id == doc.id,
        Page.page_number == page_number,
    ).first()
    if not page:
        raise HTTPException(404, f"Page {page_number} not found")

    # If image is stored in MinIO, return it
    if page.image_key:
        try:
            from app.services.storage_service import download_file
            img_bytes = download_file(page.image_key)
            return Response(content=img_bytes, media_type="image/png")
        except Exception:
            pass

    # Fallback: re-render from PDF
    from app.services.storage_service import download_file
    from app.services.ocr_service import render_page_image
    pdf_bytes = download_file(doc.minio_key)
    img_bytes = render_page_image(pdf_bytes, page_number, dpi=settings.ocr_dpi)
    return Response(content=img_bytes, media_type="image/png")


@router.get("/{doc_id}/pages/{page_number}/words", response_model=List[WordOut])
def get_page_words(project_id: str, doc_id: str, page_number: int, db: Session = Depends(get_db)):
    """Return all OCR words for a page with bounding boxes."""
    doc = _get_doc_or_404(doc_id, project_id, db)
    page = db.query(Page).filter(
        Page.document_id == doc.id,
        Page.page_number == page_number,
    ).first()
    if not page:
        raise HTTPException(404, f"Page {page_number} not found")

    words = db.query(Word).filter(Word.page_id == page.id).order_by(Word.line_index, Word.word_index).all()
    return [
        WordOut(
            id=str(w.id),
            text=w.text,
            x0=w.x0, y0=w.y0, x1=w.x1, y1=w.y1,
            confidence=w.confidence,
            line_index=w.line_index,
            word_index=w.word_index,
        )
        for w in words
    ]


@router.patch("/{doc_id}/label-status", response_model=DocumentOut)
def update_label_status(
    project_id: str,
    doc_id: str,
    status: str = Query(..., description="unlabeled|in_progress|complete"),
    db: Session = Depends(get_db),
):
    doc = _get_doc_or_404(doc_id, project_id, db)
    if status not in ("unlabeled", "in_progress", "complete"):
        raise HTTPException(400, "Invalid status")
    doc.label_status = status
    db.commit()
    db.refresh(doc)
    return _doc_to_out(doc)


@router.post("/{doc_id}/extract-table-bbox")
def extract_table_bbox(project_id: str, doc_id: str, req: TableBboxRequest, db: Session = Depends(get_db)):
    """Extract a table structure using a user-drawn bounding box via pdfplumber."""
    import pdfplumber
    import io
    
    doc = _get_doc_or_404(doc_id, project_id, db)
    if not doc.minio_key:
        raise HTTPException(400, "Document PDF not found")

    page_obj = db.query(Page).filter(Page.document_id == doc.id, Page.page_number == req.page_number).first()
    if not page_obj:
        raise HTTPException(404, "Page not found")

    words = db.query(Word).filter(Word.page_id == page_obj.id).all()

    from app.services.storage_service import download_file
    try:
        pdf_bytes = download_file(doc.minio_key)
    except Exception as e:
        raise HTTPException(500, f"Error downloading PDF from storage: {e}")

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        if req.page_number < 1 or req.page_number > len(pdf.pages):
            raise HTTPException(400, "Invalid page number for PDF")

        pdf_page = pdf.pages[req.page_number - 1]

        # Crop the page to the bbox
        x0, y0, x1, y1 = req.bbox
        # Ensure correct box bounds within page boundaries
        crop_box = (
            max(0, min(x0, x1)), 
            max(0, min(y0, y1)), 
            min(pdf_page.width, max(x0, x1)), 
            min(pdf_page.height, max(y0, y1))
        )

        try:
            cropped = pdf_page.crop(crop_box)
            tables = cropped.find_tables()

            # Fallback to text strategy if no inner columns/borders were found
            if not tables or max((len([c for c in row.cells if c]) for row in tables[0].rows), default=0) <= 1:
                ts = {
                    "vertical_strategy": "text", 
                    "horizontal_strategy": "text",
                    "text_x_tolerance": 15,
                    "text_y_tolerance": 10,
                    "intersection_tolerance": 10
                }
                fallback_tables = cropped.find_tables(ts)
                if fallback_tables:
                    tables = fallback_tables
                    
        except Exception as e:
            raise HTTPException(500, f"Error finding tables within bbox: {e}")

        if not tables:
            return {"cells": []}

        # Use the first parsed table from the bounding area
        table = tables[0]
        cells_out = []

        for r_idx, row_obj in enumerate(table.rows):
            for c_idx, cell_bbox in enumerate(row_obj.cells):
                if not cell_bbox:
                    continue
                # cell_bbox is (x0, top, x1, bottom)
                c_x0, c_y0, c_x1, c_y1 = cell_bbox

                # Intersect with OCR words (if word center is within cell)
                cell_words = []
                for w in words:
                    w_cx = (w.x0 + w.x1) / 2
                    w_cy = (w.y0 + w.y1) / 2
                    if c_x0 <= w_cx <= c_x1 and c_y0 <= w_cy <= c_y1:
                        cell_words.append(w)

                if cell_words:
                    cell_words.sort(key=lambda w: (w.y0, w.x0))
                    text = " ".join([w.text for w in cell_words])
                    b_boxes = [[w.x0, w.y0, w.x1, w.y1] for w in cell_words]
                    word_ids = [str(w.id) for w in cell_words]

                    cells_out.append({
                        "row_index": r_idx,
                        "column_index": c_idx,
                        "text": text,
                        "word_ids": word_ids,
                        "bounding_boxes": b_boxes
                    })

        return {"cells": cells_out}


# ---- Background OCR task ----

def _run_ocr_for_document(doc_id: str, project_id: str, file_bytes: bytes, filename: str):
    """Run OCR and store results in the database."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        from app.models import Document, Page, Word, OCRStatus
        from app.services.ocr_service import run_ocr
        from app.services.storage_service import upload_file

        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            return

        doc.ocr_status = OCRStatus.processing
        db.commit()

        ocr_result = run_ocr(file_bytes, filename, dpi=settings.ocr_dpi)
        doc.page_count = len(ocr_result.pages)

        for page_data in ocr_result.pages:
            page = Page(
                document_id=doc.id,
                page_number=page_data["page_number"],
                width=page_data["width"],
                height=page_data["height"],
                dpi=page_data.get("dpi", 200),
            )
            db.add(page)
            db.flush()

            # Store page image in MinIO
            img_b64 = page_data.get("image_b64")
            if img_b64:
                img_bytes = base64.b64decode(img_b64)
                image_key = f"projects/{project_id}/documents/{doc_id}/pages/page_{page_data['page_number']}.png"
                upload_file(img_bytes, image_key, "image/png")
                page.image_key = image_key
                db.flush()

            # Store words
            for word_data in page_data.get("words", []):
                word = Word(
                    page_id=page.id,
                    text=word_data["text"],
                    x0=word_data["x0"],
                    y0=word_data["y0"],
                    x1=word_data["x1"],
                    y1=word_data["y1"],
                    confidence=word_data.get("confidence", 1.0),
                    line_index=word_data.get("line_index", 0),
                    word_index=word_data.get("word_index", 0),
                    is_handwritten=word_data.get("is_handwritten", False),
                )
                db.add(word)

        doc.ocr_status = OCRStatus.complete
        db.commit()

    except Exception as e:
        import traceback
        db.rollback()
        from app.models import OCRStatus
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.ocr_status = OCRStatus.failed
            db.commit()
        print(f"OCR error for {doc_id}: {e}\n{traceback.format_exc()}")
    finally:
        db.close()


# ---- Helpers ----

def _get_doc_or_404(doc_id: str, project_id: str, db: Session) -> Document:
    doc = db.query(Document).filter(Document.id == doc_id, Document.project_id == project_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


def _doc_to_out(d: Document) -> DocumentOut:
    return DocumentOut(
        id=str(d.id),
        filename=d.filename,
        original_filename=d.original_filename,
        page_count=d.page_count,
        file_size=d.file_size,
        ocr_status=d.ocr_status,
        label_status=d.label_status,
        is_scanned=d.is_scanned,
        created_at=str(d.created_at),
    )
