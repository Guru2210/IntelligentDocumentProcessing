"""Training router — trigger training jobs and stream progress."""
import asyncio
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Project, TrainingJob, ModelVersion, JobStatus, Document, LabelStatus

router = APIRouter(prefix="/api/v1/projects/{project_id}/train", tags=["training"])


class TrainRequest(BaseModel):
    model_type: str = "template"  # "template" or "neural"
    force: bool = False  # allow training with < 5 docs


class TrainingJobOut(BaseModel):
    id: str
    project_id: str
    model_type: str
    status: str
    document_count: int
    log: str
    metrics: dict
    error_message: Optional[str]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]


@router.post("/", response_model=TrainingJobOut, status_code=201)
def start_training(
    project_id: str,
    req: TrainRequest,
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    labeled_count = db.query(Document).filter(
        Document.project_id == project_id,
        Document.label_status == LabelStatus.complete,
    ).count()

    if labeled_count < 5 and not req.force:
        raise HTTPException(
            400,
            f"Need at least 5 labeled documents (have {labeled_count}). Use force=true to override."
        )

    # Create training job
    job = TrainingJob(
        project_id=project_id,
        model_type=req.model_type,
        status=JobStatus.queued,
        document_count=labeled_count,
        log="",
        metrics={},
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Dispatch Celery task
    from app.workers.training_task import run_training_job
    run_training_job.delay(str(job.id))

    return _job_to_out(job)


@router.get("/jobs", response_model=list)
def list_training_jobs(project_id: str, db: Session = Depends(get_db)):
    jobs = (
        db.query(TrainingJob)
        .filter(TrainingJob.project_id == project_id)
        .order_by(TrainingJob.created_at.desc())
        .all()
    )
    return [_job_to_out(j) for j in jobs]


@router.get("/jobs/{job_id}", response_model=TrainingJobOut)
def get_training_job(project_id: str, job_id: str, db: Session = Depends(get_db)):
    job = db.query(TrainingJob).filter(
        TrainingJob.id == job_id,
        TrainingJob.project_id == project_id,
    ).first()
    if not job:
        raise HTTPException(404, "Training job not found")
    return _job_to_out(job)


@router.get("/jobs/{job_id}/stream")
async def stream_training_log(project_id: str, job_id: str, db: Session = Depends(get_db)):
    """SSE endpoint — stream training log updates in real-time."""
    async def event_generator():
        last_length = 0
        max_polls = 600  # 10 minutes max

        for _ in range(max_polls):
            # Re-query job
            from app.database import SessionLocal
            local_db = SessionLocal()
            try:
                job = local_db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
                if not job:
                    yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                    break

                current_log = job.log or ""
                if len(current_log) > last_length:
                    new_content = current_log[last_length:]
                    for line in new_content.strip().split("\n"):
                        if line:
                            yield f"data: {json.dumps({'type': 'log', 'message': line})}\n\n"
                    last_length = len(current_log)

                if job.status in ("succeeded", "failed"):
                    yield f"data: {json.dumps({'type': 'complete', 'status': job.status, 'metrics': job.metrics or {}})}\n\n"
                    break
            finally:
                local_db.close()

            await asyncio.sleep(1.0)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


def _job_to_out(job: TrainingJob) -> TrainingJobOut:
    return TrainingJobOut(
        id=str(job.id),
        project_id=str(job.project_id),
        model_type=job.model_type,
        status=job.status,
        document_count=job.document_count or 0,
        log=job.log or "",
        metrics=job.metrics or {},
        error_message=job.error_message,
        created_at=str(job.created_at),
        started_at=str(job.started_at) if job.started_at else None,
        completed_at=str(job.completed_at) if job.completed_at else None,
    )
