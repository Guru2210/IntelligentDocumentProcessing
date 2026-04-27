"""Labels router — save and retrieve label annotations per document."""
import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Label, Field, Document, Word, LabelStatus

router = APIRouter(prefix="/api/v1/projects/{project_id}/documents/{doc_id}/labels", tags=["labels"])


class LabelValueCreate(BaseModel):
    page: int
    text: str
    bounding_boxes: List[List[float]]  # list of [x0,y0,x1,y1] or [x0,y0,x1,y1,x2,y2,x3,y3]
    word_ids: List[str] = []
    row_index: Optional[int] = None
    column_name: Optional[str] = None


class LabelCreate(BaseModel):
    field_id: str
    values: List[LabelValueCreate]


class LabelBatchSave(BaseModel):
    labels: List[LabelCreate]
    mark_complete: bool = False


class LabelValueOut(BaseModel):
    id: str
    field_id: str
    field_name: str
    page_number: int
    text: Optional[str]
    bounding_boxes: List
    word_ids: List
    row_index: Optional[int]
    column_name: Optional[str]


@router.get("/", response_model=List[LabelValueOut])
def get_labels(project_id: str, doc_id: str, db: Session = Depends(get_db)):
    doc = _get_doc_or_404(doc_id, project_id, db)
    labels = db.query(Label).filter(Label.document_id == doc.id).all()
    result = []
    for lbl in labels:
        field = db.query(Field).filter(Field.id == lbl.field_id).first()
        result.append(LabelValueOut(
            id=str(lbl.id),
            field_id=str(lbl.field_id),
            field_name=field.name if field else "",
            page_number=lbl.page_number,
            text=lbl.text,
            bounding_boxes=lbl.bounding_boxes or [],
            word_ids=lbl.word_ids or [],
            row_index=lbl.row_index,
            column_name=lbl.column_name,
        ))
    return result


@router.post("/", response_model=Dict[str, Any], status_code=200)
def save_labels(
    project_id: str,
    doc_id: str,
    data: LabelBatchSave,
    db: Session = Depends(get_db),
):
    """
    Save (replace) all labels for a document.
    Clears existing labels for sent fields and saves new ones.
    """
    doc = _get_doc_or_404(doc_id, project_id, db)

    for label_data in data.labels:
        field = db.query(Field).filter(
            Field.id == label_data.field_id,
            Field.project_id == project_id,
        ).first()
        if not field:
            raise HTTPException(404, f"Field {label_data.field_id} not found")

        # Delete existing labels for this field+document
        db.query(Label).filter(
            Label.document_id == doc.id,
            Label.field_id == field.id,
        ).delete(synchronize_session=False)

        for val in label_data.values:
            # Resolve word text from word_ids if not provided
            text = val.text
            if not text and val.word_ids:
                words = db.query(Word).filter(Word.id.in_(val.word_ids)).all()
                text = " ".join(w.text for w in sorted(words, key=lambda w: (w.y0, w.x0)))

            label = Label(
                document_id=doc.id,
                field_id=field.id,
                page_number=val.page,
                text=text,
                bounding_boxes=val.bounding_boxes,
                word_ids=val.word_ids,
                row_index=val.row_index,
                column_name=val.column_name,
            )
            db.add(label)

    if data.mark_complete:
        doc.label_status = LabelStatus.complete
    elif doc.label_status == LabelStatus.unlabeled:
        doc.label_status = LabelStatus.in_progress

    db.commit()
    return {"saved": True, "label_status": doc.label_status}


@router.delete("/{label_id}", status_code=204)
def delete_label(project_id: str, doc_id: str, label_id: str, db: Session = Depends(get_db)):
    lbl = db.query(Label).filter(Label.id == label_id).first()
    if not lbl:
        raise HTTPException(404, "Label not found")
    db.delete(lbl)
    db.commit()


@router.get("/export")
def export_labels_json(project_id: str, doc_id: str, db: Session = Depends(get_db)):
    """Export labels in Azure DI-compatible .labels.json format."""
    doc = _get_doc_or_404(doc_id, project_id, db)
    labels = db.query(Label).filter(Label.document_id == doc.id).all()

    label_entries = []
    for lbl in labels:
        field = db.query(Field).filter(Field.id == lbl.field_id).first()
        label_entries.append({
            "label": field.name if field else "",
            "value": [{
                "page": lbl.page_number,
                "text": lbl.text or "",
                "boundingBoxes": lbl.bounding_boxes or [],
                "row": lbl.row_index,
                "column": lbl.column_name,
            }],
        })

    return {
        "document": doc.original_filename,
        "labels": label_entries,
    }


def _get_doc_or_404(doc_id: str, project_id: str, db: Session) -> Document:
    doc = db.query(Document).filter(Document.id == doc_id, Document.project_id == project_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc
