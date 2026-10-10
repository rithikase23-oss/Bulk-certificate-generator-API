"""
Jobs API Router
---------------
Beginner Note:
This router handles all certificate generation endpoints:
- POST /jobs: Accepts bulk requests, processes each recipient independently,
  and records results.
- GET /jobs/{job_id}: Returns job status and recipient-level progress.
- GET /jobs/{job_id}/certificates/{certificate_id}: Downloads an individual PDF.
- GET /jobs/{job_id}/download: Downloads a ZIP package of all successful PDFs.
"""

from pathlib import Path
from typing import List
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Job, Certificate
from app.schemas import (
    JobCreateRequest,
    JobCreateResponse,
    JobResponse,
    RecipientResultResponse,
)
from app.services.job_service import create_job_record, process_bulk_job
from app.storage import (
    build_job_zip_archive,
    is_safe_path,
)
from app.logger import logger

router = APIRouter(prefix="/jobs", tags=["Certificate Jobs"])


@router.post(
    "",
    response_model=JobCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create and process a bulk certificate job",
    description="Accepts bulk recipient data, validates input, and generates PDF certificates with resilient failure isolation.",
)
def create_job(
    payload: JobCreateRequest,
    background: bool = Query(
        False,
        description="If True, processes batch asynchronously in background. If False (default), completes synchronously before responding.",
    ),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
):
    """
    POST /jobs
    Accepts bulk recipient data and initiates certificate generation.
    """
    job = create_job_record(
        db=db,
        event_name=payload.event_name,
        issuer_name=payload.issuer_name,
        issue_date=payload.issue_date,
        certificate_title=payload.certificate_title or "Certificate of Achievement",
        issuer_title=payload.issuer_title or "Program Coordinator",
        organization_name=payload.organization_name or "Placement Assessment Board",
        total_recipients=len(payload.recipients),
    )

    if background:
        # Asynchronous background mode: response returns immediately in 'pending' status
        logger.info(f"Delegating Job {job.id} to background processing worker")
        background_tasks.add_task(process_bulk_job, job.id, payload.recipients, db)
        return JobCreateResponse(
            job_id=job.id,
            status="pending",
            total_recipients=job.total_recipients,
            successful_certificates=0,
            failed_certificates=0,
            message=f"Job queued for background processing. Poll status at /jobs/{job.id}.",
            job_status_url=f"/jobs/{job.id}",
            zip_download_url=None,
        )

    # Default synchronous mode: immediately processes all certificates
    processed_job = process_bulk_job(job.id, payload.recipients, db)
    zip_url = f"/jobs/{processed_job.id}/download" if processed_job.successful_certificates > 0 else None

    return JobCreateResponse(
        job_id=processed_job.id,
        status=processed_job.status,
        total_recipients=processed_job.total_recipients,
        successful_certificates=processed_job.successful_certificates,
        failed_certificates=processed_job.failed_certificates,
        message=(
            f"Processed {processed_job.total_recipients} recipient(s): "
            f"{processed_job.successful_certificates} succeeded, {processed_job.failed_certificates} failed."
        ),
        job_status_url=f"/jobs/{processed_job.id}",
        zip_download_url=zip_url,
    )


@router.get(
    "",
    response_model=List[JobResponse],
    summary="List all certificate jobs",
    description="Returns a paginated list of all certificate generation jobs and their current statuses.",
)
def list_jobs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    GET /jobs
    Retrieves all jobs with pagination.
    """
    jobs = db.query(Job).order_by(Job.created_at.desc()).offset(offset).limit(limit).all()
    return [_format_job_response(j) for j in jobs]


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Get job status and recipient details",
    description="Returns complete details for a specific bulk job including per-recipient certificate results.",
)
def get_job(job_id: str, db: Session = Depends(get_db)):
    """
    GET /jobs/{job_id}
    Retrieves status, progress counts, and all recipient outcomes for a given job.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found",
        )
    return _format_job_response(job)


@router.get(
    "/{job_id}/certificates/{certificate_id}",
    summary="Download individual certificate PDF",
    description="Streams or downloads an individual recipient's generated PDF certificate.",
)
def download_certificate(
    job_id: str,
    certificate_id: str,
    db: Session = Depends(get_db),
):
    """
    GET /jobs/{job_id}/certificates/{certificate_id}
    Downloads the PDF for an individual certificate.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found",
        )

    cert = db.query(Certificate).filter(
        Certificate.id == certificate_id,
        Certificate.job_id == job_id,
    ).first()

    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certificate '{certificate_id}' not found in job '{job_id}'",
        )

    if cert.status != "success":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Certificate generation did not succeed. Status: '{cert.status}'. Error: {cert.error_message}",
        )

    if not cert.pdf_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate file path record is missing",
        )

    pdf_file = Path(cert.pdf_path)
    if not is_safe_path(pdf_file):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generated certificate file was not found on server storage",
        )

    return FileResponse(
        path=str(pdf_file),
        media_type="application/pdf",
        filename=cert.pdf_filename or f"certificate_{cert.id[:8]}.pdf",
        headers={"Content-Disposition": f'inline; filename="{cert.pdf_filename}"'},
    )


@router.get(
    "/{job_id}/download",
    summary="Download ZIP package of all generated certificates",
    description="Downloads a compressed ZIP file containing all successfully generated PDF certificates for the job.",
)
def download_job_zip(job_id: str, db: Session = Depends(get_db)):
    """
    GET /jobs/{job_id}/download
    Downloads a ZIP archive of all successful certificates in the batch.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found",
        )

    if job.successful_certificates == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot download ZIP: No certificates were successfully generated for this job",
        )

    # Check if pre-built ZIP archive exists and is safe
    zip_path = None
    if job.zip_file_path:
        candidate = Path(job.zip_file_path)
        if is_safe_path(candidate):
            zip_path = candidate

    # If ZIP file is not yet built or missing, build it dynamically
    if not zip_path:
        successful_certs = (
            db.query(Certificate)
            .filter(Certificate.job_id == job_id, Certificate.status == "success")
            .all()
        )
        pdf_data = [
            (c.pdf_path, c.recipient_name)
            for c in successful_certs
            if c.pdf_path and Path(c.pdf_path).exists()
        ]
        if not pdf_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No PDF files could be found to package into a ZIP archive",
            )
        zip_path = build_job_zip_archive(job.id, job.event_name, pdf_data)
        job.zip_file_path = str(zip_path)
        db.commit()

    return FileResponse(
        path=str(zip_path),
        media_type="application/zip",
        filename=zip_path.name,
        headers={"Content-Disposition": f'attachment; filename="{zip_path.name}"'},
    )


def _format_job_response(job: Job) -> JobResponse:
    """
    Transforms an ORM Job model into a structured Pydantic JobResponse.
    """
    recipients_out = []
    for c in job.certificates:
        download_url = (
            f"/jobs/{job.id}/certificates/{c.id}"
            if c.status == "success"
            else None
        )
        recipients_out.append(
            RecipientResultResponse(
                certificate_id=c.id,
                recipient_name=c.recipient_name,
                recipient_email=c.recipient_email,
                recipient_identifier=c.recipient_identifier,
                status=c.status,
                error_message=c.error_message,
                certificate_hash=c.certificate_hash,
                download_url=download_url,
                created_at=c.created_at,
            )
        )

    zip_url = f"/jobs/{job.id}/download" if job.successful_certificates > 0 else None

    return JobResponse(
        job_id=job.id,
        status=job.status,
        event_name=job.event_name,
        certificate_title=job.certificate_title,
        issuer_name=job.issuer_name,
        issuer_title=job.issuer_title,
        organization_name=job.organization_name,
        issue_date=job.issue_date,
        total_recipients=job.total_recipients,
        successful_certificates=job.successful_certificates,
        failed_certificates=job.failed_certificates,
        zip_download_url=zip_url,
        created_at=job.created_at,
        updated_at=job.updated_at,
        recipients=recipients_out,
    )
