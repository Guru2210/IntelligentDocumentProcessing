"""
Async extraction task for batch processing.
Works in two modes:
  1. With Redis/Celery: dispatched as a Celery task (production)
  2. Without Redis/Celery: runs in a background thread (local dev fallback)
"""
import os
import threading
from datetime import datetime
from typing import Optional

from app.config import settings

def _db_write(fn):
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        result = fn(db)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def _db_read(fn):
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        return fn(db)
    finally:
        db.close()

def execute_extraction(extraction_job_id: str, celery_task_id: Optional[str] = None):
    from app.models.extraction import ExtractionJob, ExtractionStatus, ReviewItem
    from app.models.training import ModelVersion
    from app.models.project import Field

    # 1. Mark as processing and fetch data
    def _start(db):
        job = db.query(ExtractionJob).filter(ExtractionJob.id == extraction_job_id).first()
        if not job:
            raise ValueError("Job not found")
        job.status = ExtractionStatus.processing
        if celery_task_id:
            job.celery_task_id = celery_task_id
            
        model_ver = db.query(ModelVersion).filter(ModelVersion.id == job.model_version_id).first()
        if not model_ver:
            raise ValueError("Model version not found")
            
        fields = db.query(Field).filter(Field.project_id == model_ver.project_id).all()
        return {
            "document_key": job.document_key,
            "original_filename": job.original_filename or "document.pdf",
            "output_format": job.output_format,
            "model_path": model_ver.model_path,
            "model_type": model_ver.model_type,
            "model_id": str(model_ver.id),
            "field_names": [f.name for f in fields],
            "field_types": {f.name: str(f.field_type).replace("FieldType.", "") for f in fields},
            "field_columns": {
                f.name: [c.column_name for c in sorted(f.columns, key=lambda c: c.order)]
                for f in fields if f.columns
            },
        }

    try:
        job_info = _db_write(_start)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        def _fail(db):
            job = db.query(ExtractionJob).filter(ExtractionJob.id == extraction_job_id).first()
            if job:
                job.status = ExtractionStatus.failed
                job.error_message = str(e)
        try: _db_write(_fail)
        except: pass
        return {"error": str(e)}

    # 2. Run extraction logic
    try:
        from app.services.storage_service import download_file
        file_bytes = download_file(job_info["document_key"])
        
        from app.services.inference_service import run_extraction
        result = run_extraction(
            file_bytes=file_bytes,
            filename=job_info["original_filename"],
            model_path=job_info["model_path"],
            model_type=job_info["model_type"],
            field_names=job_info["field_names"],
            field_types=job_info.get("field_types", {}),
            field_columns=job_info.get("field_columns", {}),
            output_format=job_info["output_format"],
        )
        
        result["modelId"] = job_info["model_id"]
        result["extractionJobId"] = extraction_job_id

        # 3. Save result and review items
        def _save(db):
            job = db.query(ExtractionJob).filter(ExtractionJob.id == extraction_job_id).first()
            if not job:
                return
            job.result_json = result
            job.overall_confidence = result.get("confidence", 0.0)
            job.status = ExtractionStatus.succeeded
            job.completed_at = datetime.utcnow()
            job.pages_processed = len(result.get("pages", []))
            
            threshold = settings.review_confidence_threshold
            for field_name, field_data in result.get("fields", {}).items():
                if isinstance(field_data, dict):
                    conf = field_data.get("confidence", 1.0)
                    if conf < threshold:
                        value = (
                            field_data.get("valueString")
                            or str(field_data.get("valueNumber", ""))
                            or field_data.get("valueDate", "")
                        )
                        bboxes = field_data.get("boundingRegions", [])
                        page_num = bboxes[0].get("pageNumber", 1) if bboxes else 1
                        
                        ri = ReviewItem(
                            extraction_job_id=job.id,
                            field_name=field_name,
                            predicted_value=str(value),
                            predicted_confidence=conf,
                            bounding_regions=bboxes,
                            page_number=page_num,
                        )
                        db.add(ri)

        _db_write(_save)
        return {"extraction_job_id": extraction_job_id, "confidence": result.get("confidence")}

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        def _fail2(db):
            job = db.query(ExtractionJob).filter(ExtractionJob.id == extraction_job_id).first()
            if job:
                job.status = ExtractionStatus.failed
                job.error_message = str(e)
        try: _db_write(_fail2)
        except: pass
        print(f"[Extraction] Job {extraction_job_id} failed: {e}\n{tb}")
        raise

def run_in_thread(extraction_job_id: str):
    t = threading.Thread(
        target=execute_extraction,
        args=(extraction_job_id,),
        daemon=True,
        name=f"extract-{extraction_job_id[:8]}"
    )
    t.start()
    return t

class _LazyTask:
    _task = None
    _tried = False

    def _get_task(self):
        if not self._tried:
            self._tried = True
            try:
                from app.workers.celery_app import celery_app
                if celery_app is None:
                    return None
                
                @celery_app.task(bind=True, name="extraction.run_extraction_job")
                def _celery_run(self, extraction_job_id: str):
                    return execute_extraction(extraction_job_id, celery_task_id=self.request.id)
                self._task = _celery_run
            except Exception as e:
                print(f"[Extraction] Celery not available: {e}")
        return self._task

    def delay(self, extraction_job_id: str):
        task = self._get_task()
        if task:
            try:
                task.delay(extraction_job_id)
                return
            except Exception as e:
                print(f"[Extraction] Celery dispatch failed ({e}), using thread fallback")
        run_in_thread(extraction_job_id)

run_extraction_job = _LazyTask()
