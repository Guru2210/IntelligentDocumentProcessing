import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, Float, ForeignKey, JSON, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.database import Base
import enum


def _uuid():
    return str(uuid.uuid4())


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class TrainingJob(Base):
    __tablename__ = "training_jobs"

    id = Column(String(36), primary_key=True, default=_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    model_type = Column(String(50), nullable=False)
    status = Column(SAEnum(JobStatus), default=JobStatus.queued)
    celery_task_id = Column(String(255), nullable=True)
    document_count = Column(Integer, default=0)
    log = Column(Text, default="")
    metrics = Column(JSON, default=dict)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="training_jobs")
    model_version = relationship("ModelVersion", back_populates="training_job", uselist=False)


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id = Column(String(36), primary_key=True, default=_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    training_job_id = Column(String(36), ForeignKey("training_jobs.id"), nullable=True)
    version = Column(Integer, default=1)
    model_type = Column(String(50), nullable=False)
    model_path = Column(String(1000), nullable=True)
    overall_accuracy = Column(Float, default=0.0)
    field_metrics = Column(JSON, default=dict)
    training_doc_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="model_versions")
    training_job = relationship("TrainingJob", back_populates="model_version")
    extraction_jobs = relationship("ExtractionJob", back_populates="model_version")
