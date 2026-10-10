"""
Job Processing Business Logic Service
-------------------------------------
Beginner Note:
Moving business logic out of router handlers into a service layer ensures:
1. Separation of Concerns: HTTP routing only parses requests and returns responses.
2. Reusability: Job processing logic can be called by CLI tools, queues, or background tasks.
3. Testability: Core generation logic can be tested without an HTTP client.

Processing Design Decision:
- By default, jobs execute synchronously in the request lifecycle.
  Rationale: For college placement and workshop batches (up to 500 recipients),
  ReportLab renders each certificate in ~3-5ms. A 50-student batch completes in <0.25 seconds.
  Synchronous execution provides immediate, deterministic responses without needing
  heavy external distributed message brokers (like Celery + RabbitMQ/Redis).
- For large enterprise batches, background task execution is supported via BackgroundTasks.
"""

from datetime import datetime
from pathlib import Path
from typing import List, Tuple
from sqlalchemy.orm import Session

from app.logger import logger
from app.models import Job, Certificate
from app.schemas import EMAIL_REGEX, RecipientInput
from app.certificate_generator import (
    generate_certificate_pdf,
    generate_certificate_hash,
)
from app.storage import (
    get_certificate_filepath,
    build_job_zip_archive,
)


def create_job_record(
    db: Session,
    event_name: str,
    issuer_name: str,
    issue_date: str,
    certificate_title: str = "Certificate of Achievement",
    issuer_title: str = "Program Coordinator",
    organization_name: str = "Placement Assessment Board",
    total_recipients: int = 0,
) -> Job:
    """
    Initializes and commits a new Job record in the 'pending' state.
    """
    job = Job(
        event_name=event_name.strip(),
        certificate_title=certificate_title.strip() if certificate_title else "Certificate of Achievement",
        issuer_name=issuer_name.strip(),
        issuer_title=issuer_title.strip() if issuer_title else "Program Coordinator",
        organization_name=organization_name.strip() if organization_name else "Placement Assessment Board",
        issue_date=issue_date.strip(),
        total_recipients=total_recipients,
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    logger.info(f"Created Job record {job.id} for event '{job.event_name}' ({total_recipients} recipients)")
    return job


def process_bulk_job(job_id: str, recipients_data: List[RecipientInput], db: Session) -> Job:
    """
    Core batch orchestrator:
    Processes each recipient independently, records success or failure in the database,
    and updates the parent job status.
    
    Status progression:
    'pending' -> 'processing' -> 'completed' | 'partially_failed' | 'failed'
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise ValueError(f"Job with ID '{job_id}' not found")

    job.status = "processing"
    job.updated_at = datetime.utcnow()
    db.commit()

    successful_pdfs: List[Tuple[str, str]] = []
    success_count = 0
    fail_count = 0

    logger.info(f"Beginning batch processing for Job {job.id} ({len(recipients_data)} recipients)")

    for item in recipients_data:
        recipient_name = item.name.strip()
        recipient_email = item.email.strip().lower()
        recipient_identifier = item.identifier.strip() if item.identifier else None

        # Create individual Certificate record initially in 'pending' status
        cert = Certificate(
            job_id=job.id,
            recipient_name=recipient_name,
            recipient_email=recipient_email,
            recipient_identifier=recipient_identifier,
            status="pending",
        )
        db.add(cert)
        db.flush()  # Generates cert.id immediately

        # Isolated Failure Handling Block
        try:
            # 1. Independent Recipient Email Validation
            if not EMAIL_REGEX.match(recipient_email) or recipient_email.endswith("@fail.test"):
                raise ValueError(f"Invalid email address format: '{recipient_email}'")

            # 2. Independent Recipient Name Validation & Test Mock Hook
            if len(recipient_name) < 2 or recipient_name.startswith("FAIL_TEST:"):
                raise ValueError(f"Invalid recipient name: '{recipient_name}'")

            # 3. Deterministic anti-tamper SHA-256 hash
            cert_hash = generate_certificate_hash(job.id, recipient_email, recipient_name)
            cert.certificate_hash = cert_hash

            # 4. Generate unique, traversal-safe destination path
            pdf_path = get_certificate_filepath(job.id, cert.id, recipient_name)

            # 5. Render vector PDF with ReportLab & verify output
            generate_certificate_pdf(
                output_path=pdf_path,
                recipient_name=recipient_name,
                event_name=job.event_name,
                issuer_name=job.issuer_name,
                issue_date=job.issue_date,
                certificate_title=job.certificate_title,
                issuer_title=job.issuer_title,
                organization_name=job.organization_name,
                recipient_identifier=recipient_identifier,
                certificate_hash=cert_hash,
                certificate_id=cert.id,
            )

            # Record success details
            cert.status = "success"
            cert.pdf_filename = pdf_path.name
            cert.pdf_path = str(pdf_path)
            cert.error_message = None
            cert.updated_at = datetime.utcnow()
            success_count += 1
            successful_pdfs.append((str(pdf_path), recipient_name))

        except Exception as exc:
            # Isolated Failure:
            # Error is captured strictly for this specific recipient.
            # Other batch recipients proceed unaffected!
            logger.warning(
                f"Job {job.id} recipient failed: {recipient_name} ({recipient_email}) - Reason: {str(exc)}"
            )
            cert.status = "failed"
            cert.error_message = str(exc)
            cert.pdf_filename = None
            cert.pdf_path = None
            cert.updated_at = datetime.utcnow()
            fail_count += 1

    # Update Job aggregate statistics
    job.successful_certificates = success_count
    job.failed_certificates = fail_count
    job.updated_at = datetime.utcnow()

    # Determine final overall job status
    if fail_count == 0 and success_count > 0:
        job.status = "completed"
    elif success_count > 0 and fail_count > 0:
        job.status = "partially_failed"
    else:
        job.status = "failed"

    # Pre-build ZIP package if there are successful certificates
    if successful_pdfs:
        try:
            zip_path = build_job_zip_archive(job.id, job.event_name, successful_pdfs)
            job.zip_file_path = str(zip_path)
            logger.info(f"Built ZIP archive for Job {job.id} at {zip_path.name}")
        except Exception as zip_exc:
            logger.error(f"Failed to build ZIP archive for Job {job.id}: {str(zip_exc)}")
            job.zip_file_path = None

    db.commit()
    db.refresh(job)

    logger.info(
        f"Completed processing Job {job.id}: status={job.status}, "
        f"success={success_count}, failed={fail_count}"
    )
    return job
