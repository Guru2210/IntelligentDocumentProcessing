import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, Float, ForeignKey, JSON, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.database import Base
import enum


def _uuid():
    return str(uuid.uuid4())


class OCRStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    complete = "complete"
    failed = "failed"


class LabelStatus(str, enum.Enum):
    unlabeled = "unlabeled"
    in_progress = "in_progress"
    complete = "complete"


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=False)
    minio_key = Column(String(1000), nullable=False)
    file_size = Column(Integer, default=0)
    page_count = Column(Integer, default=0)
    ocr_status = Column(SAEnum(OCRStatus), default=OCRStatus.pending)
    label_status = Column(SAEnum(LabelStatus), default=LabelStatus.unlabeled)
    is_scanned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="documents")
    pages = relationship("Page", back_populates="document", cascade="all, delete-orphan", order_by="Page.page_number")
    labels = relationship("Label", back_populates="document", cascade="all, delete-orphan")


class Page(Base):
    __tablename__ = "pages"

    id = Column(String(36), primary_key=True, default=_uuid)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False)
    page_number = Column(Integer, nullable=False)
    width = Column(Float, nullable=False)
    height = Column(Float, nullable=False)
    image_key = Column(String(1000), nullable=True)
    dpi = Column(Integer, default=200)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="pages")
    words = relationship("Word", back_populates="page", cascade="all, delete-orphan")
    tables = relationship("DetectedTable", back_populates="page", cascade="all, delete-orphan")
    selection_marks = relationship("SelectionMark", back_populates="page", cascade="all, delete-orphan")


class Word(Base):
    __tablename__ = "words"

    id = Column(String(36), primary_key=True, default=_uuid)
    page_id = Column(String(36), ForeignKey("pages.id"), nullable=False)
    text = Column(String(1000), nullable=False)
    x0 = Column(Float, nullable=False)
    y0 = Column(Float, nullable=False)
    x1 = Column(Float, nullable=False)
    y1 = Column(Float, nullable=False)
    confidence = Column(Float, default=1.0)
    font_size = Column(Float, nullable=True)
    is_handwritten = Column(Boolean, default=False)
    line_index = Column(Integer, default=0)
    word_index = Column(Integer, default=0)

    page = relationship("Page", back_populates="words")


class DetectedTable(Base):
    __tablename__ = "detected_tables"

    id = Column(String(36), primary_key=True, default=_uuid)
    page_id = Column(String(36), ForeignKey("pages.id"), nullable=False)
    row_count = Column(Integer, default=0)
    column_count = Column(Integer, default=0)
    cells = Column(JSON, default=list)
    bounding_box = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    page = relationship("Page", back_populates="tables")


class SelectionMark(Base):
    __tablename__ = "selection_marks"

    id = Column(String(36), primary_key=True, default=_uuid)
    page_id = Column(String(36), ForeignKey("pages.id"), nullable=False)
    x0 = Column(Float, nullable=False)
    y0 = Column(Float, nullable=False)
    x1 = Column(Float, nullable=False)
    y1 = Column(Float, nullable=False)
    state = Column(String(20), default="unselected")
    confidence = Column(Float, default=1.0)

    page = relationship("Page", back_populates="selection_marks")


class Label(Base):
    __tablename__ = "labels"

    id = Column(String(36), primary_key=True, default=_uuid)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False)
    field_id = Column(String(36), ForeignKey("fields.id"), nullable=False)
    page_number = Column(Integer, nullable=False)
    text = Column(Text, nullable=True)
    bounding_boxes = Column(JSON, default=list)
    word_ids = Column(JSON, default=list)
    row_index = Column(Integer, nullable=True)
    column_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    document = relationship("Document", back_populates="labels")
    field = relationship("Field", back_populates="labels")
