import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, Float, ForeignKey, JSON, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.database import Base
import enum


def _uuid():
    return str(uuid.uuid4())


class ModelType(str, enum.Enum):
    template = "template"
    neural = "neural"
    composed = "composed"


class FieldType(str, enum.Enum):
    text = "text"
    table = "table"
    checkbox = "checkbox"
    signature = "signature"


class DataType(str, enum.Enum):
    string = "string"
    number = "number"
    date = "date"
    time = "time"
    integer = "integer"
    selectionMark = "selectionMark"
    countryRegion = "countryRegion"
    phoneNumber = "phoneNumber"


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    model_type = Column(SAEnum(ModelType), default=ModelType.template)
    prebuilt_schema = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    fields = relationship("Field", back_populates="project", cascade="all, delete-orphan", order_by="Field.order")
    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")
    training_jobs = relationship("TrainingJob", back_populates="project", cascade="all, delete-orphan")
    model_versions = relationship("ModelVersion", back_populates="project", cascade="all, delete-orphan")


class Field(Base):
    __tablename__ = "fields"

    id = Column(String(36), primary_key=True, default=_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    name = Column(String(255), nullable=False)
    field_type = Column(SAEnum(FieldType), default=FieldType.text)
    data_type = Column(SAEnum(DataType), default=DataType.string)
    is_required = Column(Boolean, default=False)
    order = Column(Integer, default=0)
    color = Column(String(20), default="#3B82F6")
    table_mode = Column(String(20), default="normal")   # "normal" or "advanced"
    rows_per_record = Column(Integer, default=1)         # physical rows per logical record
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="fields")
    columns = relationship("FieldColumn", back_populates="field", cascade="all, delete-orphan")
    labels = relationship("Label", back_populates="field", cascade="all, delete-orphan")


class FieldColumn(Base):
    __tablename__ = "field_columns"

    id = Column(String(36), primary_key=True, default=_uuid)
    field_id = Column(String(36), ForeignKey("fields.id"), nullable=False)
    column_name = Column(String(255), nullable=False)
    data_type = Column(SAEnum(DataType), default=DataType.string)
    order = Column(Integer, default=0)
    row_level = Column(Integer, default=0)               # sub-row within a record (advanced tables)

    field = relationship("Field", back_populates="columns")
