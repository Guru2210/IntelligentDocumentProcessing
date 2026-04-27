"""Extraction router — run inference on new documents."""
import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ModelVersion, ExtractionJob, ExtractionStatus, Field
from app.config import settings

router = APIRouter(prefix="/api/v1", tags=["extraction"])


class ExtractionJobOut(BaseModel):
    id: str
    status: str
    model_version_id: str
    original_filename: Optional[str]
    overall_confidence: Optional[float]
    pages_processed: int
    created_at: str
    completed_at: Optional[str]


@router.post("/extract", response_model=ExtractionJobOut, status_code=202)
async def extract_document(
    model_id: str = Form(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    output_format: str = Form(default="json"),
    page_range: Optional[str] = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a document and run extraction with a trained model."""
    model_ver = db.query(ModelVersion).filter(ModelVersion.id == model_id).first()
    if not model_ver:
        raise HTTPException(404, f"Model {model_id} not found")
    if not model_ver.model_path:
        raise HTTPException(400, "Model has no saved weights yet")

    file_bytes = await file.read()

    # Upload to MinIO
    from app.services.storage_service import upload_file, ensure_bucket_exists
    ensure_bucket_exists()
    job_id = str(uuid.uuid4())
    safe_name = file.filename.replace(" ", "_")
    minio_key = f"extractions/{job_id}/{safe_name}"
    upload_file(file_bytes, minio_key)

    job = ExtractionJob(
        id=job_id,
        model_version_id=model_ver.id,
        document_key=minio_key,
        original_filename=file.filename,
        status=ExtractionStatus.queued,
        output_format=output_format,
    )
    db.add(job)
    db.commit()

    # Dispatch Celery task
    from app.workers.extraction_task import run_extraction_job
    run_extraction_job.delay(str(job_id))

    db.refresh(job)
    return _job_to_out(job)


@router.get("/jobs/{job_id}", response_model=ExtractionJobOut)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    job = db.query(ExtractionJob).filter(ExtractionJob.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    return _job_to_out(job)


@router.get("/results/{job_id}")
def get_job_result(job_id: str, format: str = "json", db: Session = Depends(get_db)):
    """Get extraction results in specified format."""
    job = db.query(ExtractionJob).filter(ExtractionJob.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status != ExtractionStatus.succeeded:
        raise HTTPException(400, f"Job status: {job.status}. Results not ready.")

    result = job.result_json or {}

    if format == "csv":
        from app.utils.export_utils import export_to_csv
        csv_bytes = export_to_csv(result)
        return Response(
            content=csv_bytes,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=extraction_{job_id}.csv"},
        )
    elif format == "excel":
        from app.utils.export_utils import export_to_excel
        xlsx_bytes = export_to_excel(result)
        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=extraction_{job_id}.xlsx"},
        )
    else:
        from app.utils.export_utils import export_to_json
        return Response(
            content=export_to_json(result),
            media_type="application/json",
        )


@router.post("/batch")
async def batch_extract(
    model_id: str = Form(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Submit multiple documents for batch extraction."""
    model_ver = db.query(ModelVersion).filter(ModelVersion.id == model_id).first()
    if not model_ver:
        raise HTTPException(404, f"Model {model_id} not found")

    from app.services.storage_service import upload_file, ensure_bucket_exists
    from app.workers.extraction_task import run_extraction_job
    ensure_bucket_exists()

    job_ids = []
    for file in files:
        file_bytes = await file.read()
        job_id = str(uuid.uuid4())
        minio_key = f"extractions/{job_id}/{file.filename.replace(' ', '_')}"
        upload_file(file_bytes, minio_key)

        job = ExtractionJob(
            id=job_id,
            model_version_id=model_ver.id,
            document_key=minio_key,
            original_filename=file.filename,
            status=ExtractionStatus.queued,
        )
        db.add(job)
        db.commit()
        run_extraction_job.delay(str(job_id))
        job_ids.append(str(job_id))

    return {"batch_job_ids": job_ids, "count": len(job_ids)}


def _job_to_out(job: ExtractionJob) -> ExtractionJobOut:
    return ExtractionJobOut(
        id=str(job.id),
        status=job.status,
        model_version_id=str(job.model_version_id),
        original_filename=job.original_filename,
        overall_confidence=job.overall_confidence,
        pages_processed=job.pages_processed or 0,
        created_at=str(job.created_at),
        completed_at=str(job.completed_at) if job.completed_at else None,
    )
