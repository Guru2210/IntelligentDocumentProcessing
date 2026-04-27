import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, Float, ForeignKey, JSON, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.database import Base
import enum


def _uuid():
    return str(uuid.uuid4())


class ExtractionStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    succeeded = "succeeded"
    failed = "failed"


class ReviewStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    corrected = "corrected"
    rejected = "rejected"


class ExtractionJob(Base):
    __tablename__ = "extraction_jobs"

    id = Column(String(36), primary_key=True, default=_uuid)
    model_version_id = Column(String(36), ForeignKey("model_versions.id"), nullable=False)
    document_key = Column(String(1000), nullable=False)
    original_filename = Column(String(500), nullable=True)
    status = Column(SAEnum(ExtractionStatus), default=ExtractionStatus.queued)
    celery_task_id = Column(String(255), nullable=True)
    result_json = Column(JSON, nullable=True)
    overall_confidence = Column(Float, nullable=True)
    output_format = Column(String(20), default="json")
    error_message = Column(Text, nullable=True)
    pages_processed = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    model_version = relationship("ModelVersion", back_populates="extraction_jobs")
    review_items = relationship("ReviewItem", back_populates="extraction_job", cascade="all, delete-orphan")


class ReviewItem(Base):
    __tablename__ = "review_items"

    id = Column(String(36), primary_key=True, default=_uuid)
    extraction_job_id = Column(String(36), ForeignKey("extraction_jobs.id"), nullable=False)
    field_name = Column(String(255), nullable=False)
    predicted_value = Column(Text, nullable=True)
    predicted_confidence = Column(Float, nullable=True)
    corrected_value = Column(Text, nullable=True)
    bounding_regions = Column(JSON, default=list)
    page_number = Column(Integer, default=1)
    status = Column(SAEnum(ReviewStatus), default=ReviewStatus.pending)
    reviewed_at = Column(DateTime, nullable=True)
    reviewer_note = Column(Text, nullable=True)
    added_to_training = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    extraction_job = relationship("ExtractionJob", back_populates="review_items")
