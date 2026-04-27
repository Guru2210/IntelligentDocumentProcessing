"""Projects router — CRUD for projects and field schemas."""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Project, Field, FieldColumn, FieldType, DataType, ModelType

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

# ---- Pydantic schemas ----

class FieldColumnCreate(BaseModel):
    column_name: str
    data_type: DataType = DataType.string
    order: int = 0

class FieldCreate(BaseModel):
    name: str
    field_type: FieldType = FieldType.text
    data_type: DataType = DataType.string
    is_required: bool = False
    color: str = "#3B82F6"
    columns: List[FieldColumnCreate] = []

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    model_type: ModelType = ModelType.template
    prebuilt_schema: Optional[str] = None

class FieldColumnOut(BaseModel):
    id: str
    column_name: str
    data_type: str
    order: int
    class Config:
        from_attributes = True

class FieldOut(BaseModel):
    id: str
    name: str
    field_type: str
    data_type: str
    is_required: bool
    order: int
    color: str
    columns: List[FieldColumnOut] = []
    class Config:
        from_attributes = True

class ProjectOut(BaseModel):
    id: str
    name: str
    description: Optional[str]
    model_type: str
    prebuilt_schema: Optional[str]
    fields: List[FieldOut] = []
    document_count: int = 0
    labeled_count: int = 0
    class Config:
        from_attributes = True

# ---- Prebuilt schemas ----
PREBUILT_SCHEMAS = {
    "invoice": [
        {"name": "vendor_name", "field_type": "text", "data_type": "string", "color": "#3B82F6"},
        {"name": "invoice_number", "field_type": "text", "data_type": "string", "color": "#8B5CF6"},
        {"name": "invoice_date", "field_type": "text", "data_type": "date", "color": "#10B981"},
        {"name": "due_date", "field_type": "text", "data_type": "date", "color": "#F59E0B"},
        {"name": "total_amount", "field_type": "text", "data_type": "number", "color": "#EF4444"},
        {"name": "tax_amount", "field_type": "text", "data_type": "number", "color": "#F97316"},
        {"name": "billing_address", "field_type": "text", "data_type": "string", "color": "#06B6D4"},
        {"name": "line_items", "field_type": "table", "data_type": "string", "color": "#7C3AED",
         "columns": [
             {"column_name": "description", "data_type": "string", "order": 0},
             {"column_name": "quantity", "data_type": "number", "order": 1},
             {"column_name": "unit_price", "data_type": "number", "order": 2},
             {"column_name": "total", "data_type": "number", "order": 3},
         ]},
    ],
    "receipt": [
        {"name": "merchant_name", "field_type": "text", "data_type": "string", "color": "#3B82F6"},
        {"name": "transaction_date", "field_type": "text", "data_type": "date", "color": "#10B981"},
        {"name": "total_amount", "field_type": "text", "data_type": "number", "color": "#EF4444"},
        {"name": "tax_amount", "field_type": "text", "data_type": "number", "color": "#F59E0B"},
        {"name": "tip_amount", "field_type": "text", "data_type": "number", "color": "#8B5CF6"},
        {"name": "items", "field_type": "table", "data_type": "string", "color": "#7C3AED",
         "columns": [
             {"column_name": "item", "data_type": "string", "order": 0},
             {"column_name": "price", "data_type": "number", "order": 1},
         ]},
    ],
    "id_document": [
        {"name": "full_name", "field_type": "text", "data_type": "string", "color": "#3B82F6"},
        {"name": "date_of_birth", "field_type": "text", "data_type": "date", "color": "#10B981"},
        {"name": "document_number", "field_type": "text", "data_type": "string", "color": "#8B5CF6"},
        {"name": "nationality", "field_type": "text", "data_type": "countryRegion", "color": "#F59E0B"},
        {"name": "expiry_date", "field_type": "text", "data_type": "date", "color": "#EF4444"},
    ],
    "bank_statement": [
        {"name": "account_number", "field_type": "text", "data_type": "string", "color": "#3B82F6"},
        {"name": "opening_balance", "field_type": "text", "data_type": "number", "color": "#10B981"},
        {"name": "closing_balance", "field_type": "text", "data_type": "number", "color": "#EF4444"},
        {"name": "statement_date", "field_type": "text", "data_type": "date", "color": "#F59E0B"},
        {"name": "transactions", "field_type": "table", "data_type": "string", "color": "#7C3AED",
         "columns": [
             {"column_name": "date", "data_type": "date", "order": 0},
             {"column_name": "description", "data_type": "string", "order": 1},
             {"column_name": "debit", "data_type": "number", "order": 2},
             {"column_name": "credit", "data_type": "number", "order": 3},
             {"column_name": "balance", "data_type": "number", "order": 4},
         ]},
    ],
}

# ---- Endpoints ----

@router.get("/", response_model=List[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    result = []
    for p in projects:
        from app.models.document import Document, LabelStatus
        doc_count = db.query(Document).filter(Document.project_id == p.id).count()
        labeled_count = db.query(Document).filter(
            Document.project_id == p.id,
            Document.label_status == LabelStatus.complete,
        ).count()
        po = ProjectOut(
            id=str(p.id),
            name=p.name,
            description=p.description,
            model_type=p.model_type,
            prebuilt_schema=p.prebuilt_schema,
            fields=[_field_to_out(f) for f in p.fields],
            document_count=doc_count,
            labeled_count=labeled_count,
        )
        result.append(po)
    return result


@router.post("/", response_model=ProjectOut, status_code=201)
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    existing = db.query(Project).filter(Project.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Project '{data.name}' already exists.")

    project = Project(
        name=data.name,
        description=data.description,
        model_type=data.model_type,
        prebuilt_schema=data.prebuilt_schema,
    )
    db.add(project)
    db.flush()

    # Apply prebuilt schema if provided
    if data.prebuilt_schema and data.prebuilt_schema in PREBUILT_SCHEMAS:
        colors = ["#3B82F6", "#8B5CF6", "#10B981", "#F59E0B", "#EF4444", "#F97316", "#06B6D4", "#7C3AED"]
        for i, field_def in enumerate(PREBUILT_SCHEMAS[data.prebuilt_schema]):
            field = Field(
                project_id=project.id,
                name=field_def["name"],
                field_type=field_def.get("field_type", "text"),
                data_type=field_def.get("data_type", "string"),
                color=field_def.get("color", colors[i % len(colors)]),
                order=i,
            )
            db.add(field)
            db.flush()
            for ci, col in enumerate(field_def.get("columns", [])):
                fc = FieldColumn(
                    field_id=field.id,
                    column_name=col["column_name"],
                    data_type=col.get("data_type", "string"),
                    order=ci,
                )
                db.add(fc)

    db.commit()
    db.refresh(project)
    return ProjectOut(
        id=str(project.id),
        name=project.name,
        description=project.description,
        model_type=project.model_type,
        prebuilt_schema=project.prebuilt_schema,
        fields=[_field_to_out(f) for f in project.fields],
        document_count=0,
        labeled_count=0,
    )


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = _get_project_or_404(project_id, db)
    from app.models.document import Document, LabelStatus
    doc_count = db.query(Document).filter(Document.project_id == project.id).count()
    labeled_count = db.query(Document).filter(
        Document.project_id == project.id,
        Document.label_status == LabelStatus.complete,
    ).count()
    return ProjectOut(
        id=str(project.id),
        name=project.name,
        description=project.description,
        model_type=project.model_type,
        prebuilt_schema=project.prebuilt_schema,
        fields=[_field_to_out(f) for f in project.fields],
        document_count=doc_count,
        labeled_count=labeled_count,
    )


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, db: Session = Depends(get_db)):
    project = _get_project_or_404(project_id, db)
    db.delete(project)
    db.commit()


@router.post("/{project_id}/fields", response_model=FieldOut, status_code=201)
def add_field(project_id: str, data: FieldCreate, db: Session = Depends(get_db)):
    project = _get_project_or_404(project_id, db)
    order = db.query(Field).filter(Field.project_id == project.id).count()
    field = Field(
        project_id=project.id,
        name=data.name,
        field_type=data.field_type,
        data_type=data.data_type,
        is_required=data.is_required,
        color=data.color,
        order=order,
    )
    db.add(field)
    db.flush()
    for i, col in enumerate(data.columns):
        fc = FieldColumn(
            field_id=field.id,
            column_name=col.column_name,
            data_type=col.data_type,
            order=col.order or i,
        )
        db.add(fc)
    db.commit()
    db.refresh(field)
    return _field_to_out(field)


@router.put("/{project_id}/fields/{field_id}", response_model=FieldOut)
def update_field(project_id: str, field_id: str, data: FieldCreate, db: Session = Depends(get_db)):
    field = db.query(Field).filter(Field.id == field_id, Field.project_id == project_id).first()
    if not field:
        raise HTTPException(404, "Field not found")
    field.name = data.name
    field.field_type = data.field_type
    field.data_type = data.data_type
    field.is_required = data.is_required
    field.color = data.color

    # Rebuild columns
    for old_col in field.columns:
        db.delete(old_col)
    db.flush()
    for i, col in enumerate(data.columns):
        fc = FieldColumn(
            field_id=field.id,
            column_name=col.column_name,
            data_type=col.data_type,
            order=col.order or i,
        )
        db.add(fc)
    db.commit()
    db.refresh(field)
    return _field_to_out(field)


@router.delete("/{project_id}/fields/{field_id}", status_code=204)
def delete_field(project_id: str, field_id: str, db: Session = Depends(get_db)):
    field = db.query(Field).filter(Field.id == field_id, Field.project_id == project_id).first()
    if not field:
        raise HTTPException(404, "Field not found")
    db.delete(field)
    db.commit()


@router.get("/prebuilt-schemas", response_model=List[str])
def list_prebuilt_schemas():
    return list(PREBUILT_SCHEMAS.keys())


# ---- Helpers ----

def _get_project_or_404(project_id: str, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, f"Project {project_id} not found")
    return project


def _field_to_out(f: Field) -> FieldOut:
    return FieldOut(
        id=str(f.id),
        name=f.name,
        field_type=f.field_type,
        data_type=f.data_type,
        is_required=f.is_required,
        order=f.order,
        color=f.color,
        columns=[FieldColumnOut(id=str(c.id), column_name=c.column_name, data_type=c.data_type, order=c.order) for c in f.columns],
    )
