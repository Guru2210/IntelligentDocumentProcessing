"""Models router — model version management."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ModelVersion, Project

router = APIRouter(prefix="/api/v1/projects/{project_id}/models", tags=["models"])


class ModelVersionOut(BaseModel):
    id: str
    version: int
    model_type: str
    overall_accuracy: float
    field_metrics: dict
    training_doc_count: int
    is_active: bool
    description: Optional[str]
    created_at: str


@router.get("/", response_model=List[ModelVersionOut])
def list_models(project_id: str, db: Session = Depends(get_db)):
    versions = (
        db.query(ModelVersion)
        .filter(ModelVersion.project_id == project_id)
        .order_by(ModelVersion.version.desc())
        .all()
    )
    return [_mv_to_out(mv) for mv in versions]


@router.get("/{model_id}", response_model=ModelVersionOut)
def get_model(project_id: str, model_id: str, db: Session = Depends(get_db)):
    mv = db.query(ModelVersion).filter(
        ModelVersion.id == model_id,
        ModelVersion.project_id == project_id,
    ).first()
    if not mv:
        raise HTTPException(404, "Model not found")
    return _mv_to_out(mv)


@router.patch("/{model_id}/activate", response_model=ModelVersionOut)
def activate_model(project_id: str, model_id: str, db: Session = Depends(get_db)):
    """Set a model version as the active one for extraction."""
    db.query(ModelVersion).filter(ModelVersion.project_id == project_id).update({"is_active": False})
    mv = db.query(ModelVersion).filter(ModelVersion.id == model_id).first()
    if not mv:
        raise HTTPException(404, "Model not found")
    mv.is_active = True
    db.commit()
    db.refresh(mv)
    return _mv_to_out(mv)


@router.delete("/{model_id}", status_code=204)
def delete_model(project_id: str, model_id: str, db: Session = Depends(get_db)):
    mv = db.query(ModelVersion).filter(
        ModelVersion.id == model_id,
        ModelVersion.project_id == project_id,
    ).first()
    if not mv:
        raise HTTPException(404, "Model not found")
    if mv.is_active:
        raise HTTPException(400, "Cannot delete the active model. Activate another version first.")
    import shutil, os
    if mv.model_path and os.path.exists(mv.model_path):
        shutil.rmtree(mv.model_path, ignore_errors=True)
    db.delete(mv)
    db.commit()


@router.get("/active", response_model=Optional[ModelVersionOut])
def get_active_model(project_id: str, db: Session = Depends(get_db)):
    mv = db.query(ModelVersion).filter(
        ModelVersion.project_id == project_id,
        ModelVersion.is_active == True,
    ).first()
    return _mv_to_out(mv) if mv else None


def _mv_to_out(mv: ModelVersion) -> ModelVersionOut:
    return ModelVersionOut(
        id=str(mv.id),
        version=mv.version,
        model_type=mv.model_type,
        overall_accuracy=mv.overall_accuracy or 0.0,
        field_metrics=mv.field_metrics or {},
        training_doc_count=mv.training_doc_count or 0,
        is_active=mv.is_active,
        description=mv.description,
        created_at=str(mv.created_at),
    )
