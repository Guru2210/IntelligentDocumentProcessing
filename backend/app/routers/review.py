"""Review queue router — human-in-the-loop correction workflow."""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ReviewItem, ReviewStatus, ExtractionJob

router = APIRouter(prefix="/api/v1/review", tags=["review"])


class ReviewItemOut(BaseModel):
    id: str
    extraction_job_id: str
    field_name: str
    predicted_value: Optional[str]
    predicted_confidence: Optional[float]
    corrected_value: Optional[str]
    bounding_regions: list
    page_number: int
    status: str
    original_filename: Optional[str]
    created_at: str


class ReviewAction(BaseModel):
    action: str  # "accept", "correct", "reject"
    corrected_value: Optional[str] = None
    reviewer_note: Optional[str] = None
    add_to_training: bool = False


@router.get("/", response_model=List[ReviewItemOut])
def list_review_items(
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    query = db.query(ReviewItem)
    if status:
        query = query.filter(ReviewItem.status == status)
    else:
        query = query.filter(ReviewItem.status == ReviewStatus.pending)

    items = query.order_by(ReviewItem.created_at.desc()).limit(limit).all()
    return [_review_to_out(item, db) for item in items]


@router.get("/stats")
def review_stats(db: Session = Depends(get_db)):
    """Get review queue statistics."""
    pending = db.query(ReviewItem).filter(ReviewItem.status == ReviewStatus.pending).count()
    accepted = db.query(ReviewItem).filter(ReviewItem.status == ReviewStatus.accepted).count()
    corrected = db.query(ReviewItem).filter(ReviewItem.status == ReviewStatus.corrected).count()
    rejected = db.query(ReviewItem).filter(ReviewItem.status == ReviewStatus.rejected).count()
    return {
        "pending": pending,
        "accepted": accepted,
        "corrected": corrected,
        "rejected": rejected,
        "total": pending + accepted + corrected + rejected,
    }


@router.patch("/{item_id}", response_model=ReviewItemOut)
def review_item(
    item_id: str,
    action: ReviewAction,
    db: Session = Depends(get_db),
):
    item = db.query(ReviewItem).filter(ReviewItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Review item not found")

    item.reviewed_at = datetime.utcnow()
    item.reviewer_note = action.reviewer_note

    if action.action == "accept":
        item.status = ReviewStatus.accepted
    elif action.action == "correct":
        item.status = ReviewStatus.corrected
        item.corrected_value = action.corrected_value
    elif action.action == "reject":
        item.status = ReviewStatus.rejected
    else:
        raise HTTPException(400, f"Unknown action: {action.action}")

    if action.add_to_training:
        item.added_to_training = True

    db.commit()
    db.refresh(item)
    return _review_to_out(item, db)


def _review_to_out(item: ReviewItem, db: Session) -> ReviewItemOut:
    job = db.query(ExtractionJob).filter(ExtractionJob.id == item.extraction_job_id).first()
    return ReviewItemOut(
        id=str(item.id),
        extraction_job_id=str(item.extraction_job_id),
        field_name=item.field_name,
        predicted_value=item.predicted_value,
        predicted_confidence=item.predicted_confidence,
        corrected_value=item.corrected_value,
        bounding_regions=item.bounding_regions or [],
        page_number=item.page_number or 1,
        status=item.status,
        original_filename=job.original_filename if job else None,
        created_at=str(item.created_at),
    )
