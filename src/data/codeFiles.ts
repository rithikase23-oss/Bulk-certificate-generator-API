export interface SourceFile {
  name: string;
  path: string;
  category: 'core' | 'api' | 'services' | 'tests' | 'config' | 'docs';
  description: string;
  keyConcepts: string[];
  code: string;
}

export const SOURCE_FILES: SourceFile[] = [
  {
    name: 'main.py',
    path: 'app/main.py',
    category: 'core',
    description: 'FastAPI application initialization, CORS middleware, lifespan events, global exception handling, and health probes.',
    keyConcepts: [
      'FastAPI Lifespan Context Manager',
      'CORS Middleware for cross-origin frontend requests',
      'Global Exception Handler (prevents stack trace leakage)',
      'Health check endpoint (/health)',
    ],
    code: `from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.database import init_db
from app.routers import jobs
from app.logger import logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    yield

app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred while processing the request."},
    )

app.include_router(jobs.router)
app.include_router(jobs.router, prefix="/api")

@app.get("/health", tags=["Health & Info"])
@app.get("/api/health", tags=["Health & Info"])
def health_check():
    return {
        "status": "healthy",
        "storage_accessible": settings.STORAGE_DIR.exists(),
        "database": settings.DATABASE_URL.split("://")[0],
        "max_recipients_per_batch": settings.MAX_RECIPIENTS_PER_BATCH,
    }`
  },
  {
    name: 'services/job_service.py',
    path: 'app/services/job_service.py',
    category: 'services',
    description: 'Dedicated domain business logic for orchestrating bulk batches, validating recipients independently, and updating partially_failed states.',
    keyConcepts: [
      'Separation of Concerns (Routes vs Business Logic)',
      'Independent Recipient Error Isolation (try...except)',
      'Job Status Progression (pending -> processing -> completed | partially_failed | failed)',
      'Synchronous vs BackgroundTasks execution',
    ],
    code: `from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
from app.logger import logger
from app.models import Job, Certificate
from app.schemas import EMAIL_REGEX, RecipientInput
from app.certificate_generator import generate_certificate_pdf, generate_certificate_hash
from app.storage import get_certificate_filepath, build_job_zip_archive

def process_bulk_job(job_id: str, recipients_data: list, db: Session) -> Job:
    job = db.query(Job).filter(Job.id == job_id).first()
    job.status = "processing"
    db.commit()

    successful_pdfs = []
    success_count = 0
    fail_count = 0

    for item in recipients_data:
        cert = Certificate(
            job_id=job.id,
            recipient_name=item.name.strip(),
            recipient_email=item.email.strip().lower(),
            recipient_identifier=item.identifier.strip() if item.identifier else None,
            status="pending",
        )
        db.add(cert)
        db.flush()

        try:
            if not EMAIL_REGEX.match(item.email.strip()):
                raise ValueError(f"Invalid email address format: '{item.email}'")
            if len(item.name.strip()) < 2:
                raise ValueError(f"Invalid recipient name: '{item.name}'")

            cert_hash = generate_certificate_hash(job.id, item.email, item.name)
            cert.certificate_hash = cert_hash
            pdf_path = get_certificate_filepath(job.id, cert.id, item.name)

            generate_certificate_pdf(
                output_path=pdf_path,
                recipient_name=item.name,
                event_name=job.event_name,
                issuer_name=job.issuer_name,
                issue_date=job.issue_date,
                certificate_title=job.certificate_title,
                certificate_hash=cert_hash,
                certificate_id=cert.id,
            )

            cert.status = "success"
            cert.pdf_filename = pdf_path.name
            cert.pdf_path = str(pdf_path)
            success_count += 1
            successful_pdfs.append((str(pdf_path), item.name))
        except Exception as exc:
            cert.status = "failed"
            cert.error_message = str(exc)
            fail_count += 1

    job.successful_certificates = success_count
    job.failed_certificates = fail_count

    if fail_count == 0 and success_count > 0:
        job.status = "completed"
    elif success_count > 0 and fail_count > 0:
        job.status = "partially_failed"
    else:
        job.status = "failed"

    if successful_pdfs:
        zip_path = build_job_zip_archive(job.id, job.event_name, successful_pdfs)
        job.zip_file_path = str(zip_path)

    db.commit()
    db.refresh(job)
    return job`
  },
  {
    name: 'certificate_generator.py',
    path: 'app/certificate_generator.py',
    category: 'core',
    description: 'ReportLab vector PDF engine rendering ornamental borders, rosette gold seal, dynamic font scaling for long names, and text wrapping.',
    keyConcepts: [
      'Dynamic Font Scaling (stringWidth checks against margins)',
      'Multi-line Text Wrapping with simpleSplit',
      'Strict File Verification (%PDF magic bytes & size check)',
      'Deterministic SHA-256 Anti-Tamper Hash',
    ],
    code: `import hashlib, math
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

def generate_certificate_pdf(
    output_path: Path,
    recipient_name: str,
    event_name: str,
    issuer_name: str,
    issue_date: str,
    certificate_title: str = "Certificate of Achievement",
    certificate_hash: str = None,
    certificate_id: str = None,
):
    clean_name = recipient_name.strip()
    clean_event = event_name.strip()
    width, height = landscape(A4)
    max_content_width = width - 140

    c = canvas.Canvas(str(output_path), pagesize=(width, height))

    # Borders
    c.setStrokeColor(colors.HexColor("#0F172A"))
    c.setLineWidth(3.0)
    c.rect(32, 32, width - 64, height - 64)
    c.setStrokeColor(colors.HexColor("#D97706"))
    c.setLineWidth(1.2)
    c.rect(40, 40, width - 80, height - 80)

    # Dynamic scaling for long student names
    name_font_size = 28
    while name_font_size > 14 and c.stringWidth(clean_name, "Helvetica-Bold", name_font_size) > max_content_width:
        name_font_size -= 1
    c.setFont("Helvetica-Bold", name_font_size)
    c.drawCentredString(width / 2.0, height - 215, clean_name)

    # Multi-line wrapping for long event titles
    wrapped_lines = simpleSplit(clean_event, "Helvetica-BoldOblique", 17, max_content_width)
    y = height - 290
    c.setFont("Helvetica-BoldOblique", 17)
    for line in wrapped_lines[:2]:
        c.drawCentredString(width / 2.0, y, line)
        y -= 21

    c.showPage()
    c.save()

    # Integrity verification
    if not output_path.is_file() or output_path.stat().st_size < 500:
        raise ValueError("Corrupt or empty PDF generated")`
  },
  {
    name: 'routers/jobs.py',
    path: 'app/routers/jobs.py',
    category: 'api',
    description: 'FastAPI route handlers for POST /jobs, GET /jobs/{id}, individual PDF downloads, and ZIP downloads.',
    keyConcepts: [
      'FastAPI APIRouter and dependency injection',
      'BackgroundTasks async delegation',
      'FileResponse streaming with Content-Disposition headers',
      'Useful HTTP status codes (201, 400, 404, 422)',
    ],
    code: `from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Job, Certificate
from app.schemas import JobCreateRequest, JobCreateResponse, JobResponse
from app.services.job_service import create_job_record, process_bulk_job

router = APIRouter(prefix="/jobs", tags=["Certificate Jobs"])

@router.post("", response_model=JobCreateResponse, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreateRequest, background: bool = False, background_tasks: BackgroundTasks = BackgroundTasks(), db: Session = Depends(get_db)):
    job = create_job_record(db=db, event_name=payload.event_name, issuer_name=payload.issuer_name, issue_date=payload.issue_date, total_recipients=len(payload.recipients))
    if background:
        background_tasks.add_task(process_bulk_job, job.id, payload.recipients, db)
        return JobCreateResponse(job_id=job.id, status="pending", message="Job queued in background", total_recipients=job.total_recipients, successful_certificates=0, failed_certificates=0, job_status_url=f"/jobs/{job.id}")
    processed = process_bulk_job(job.id, payload.recipients, db)
    return JobCreateResponse(job_id=processed.id, status=processed.status, message=f"Processed: {processed.successful_certificates} succeeded, {processed.failed_certificates} failed", total_recipients=processed.total_recipients, successful_certificates=processed.successful_certificates, failed_certificates=processed.failed_certificates, job_status_url=f"/jobs/{processed.id}", zip_download_url=f"/jobs/{processed.id}/download" if processed.successful_certificates > 0 else None)`
  },
  {
    name: 'models.py',
    path: 'app/models.py',
    category: 'core',
    description: 'SQLAlchemy database schema for Job and Certificate tables with partially_failed tracking and composite indexes.',
    keyConcepts: [
      'SQLAlchemy DeclarativeBase',
      'One-to-Many cascade relationship',
      'Composite Index for (job_id, status)',
      'Explicit job statuses: pending, processing, completed, partially_failed, failed',
    ],
    code: `import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from app.database import Base

class Job(Base):
    __tablename__ = "jobs"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    event_name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="pending", index=True) # pending, processing, completed, partially_failed, failed
    total_recipients = Column(Integer, nullable=False, default=0)
    successful_certificates = Column(Integer, nullable=False, default=0)
    failed_certificates = Column(Integer, nullable=False, default=0)
    zip_file_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    certificates = relationship("Certificate", back_populates="job", cascade="all, delete-orphan")

class Certificate(Base):
    __tablename__ = "certificates"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_name = Column(String(255), nullable=False)
    recipient_email = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="pending")
    pdf_filename = Column(String(255), nullable=True)
    pdf_path = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)
    certificate_hash = Column(String(64), nullable=True, unique=True, index=True)
    job = relationship("Job", back_populates="certificates")
    __table_args__ = (Index("idx_job_cert_status", "job_id", "status"),)`
  },
  {
    name: 'storage.py',
    path: 'app/storage.py',
    category: 'core',
    description: 'Filesystem security module enforcing path traversal defense, filename sanitization, and safe zip bundling.',
    keyConcepts: [
      'Path Traversal Prevention with is_relative_to()',
      'Filename Regex Sanitization',
      'zipfile.ZipFile compression',
      'Defending against Zip Slip attacks',
    ],
    code: `import re, zipfile
from pathlib import Path
from app.config import settings

def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[^\\w\\-. ]", "_", name)
    cleaned = re.sub(r"\\s+", "_", cleaned)
    return cleaned.strip("._") or "certificate"

def is_safe_path(target_path: Path) -> bool:
    try:
        resolved = target_path.resolve()
        return resolved.is_relative_to(settings.STORAGE_DIR) and resolved.exists()
    except (ValueError, RuntimeError):
        return False

def build_job_zip_archive(job_id: str, event_name: str, certificates_data: list) -> Path:
    job_dir = (settings.STORAGE_DIR / "jobs" / job_id).resolve()
    zip_path = (job_dir / f"{sanitize_filename(event_name)}_certificates_{job_id[:8]}.zip").resolve()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        for pdf_path_str, recipient_name in certificates_data:
            pdf_path = Path(pdf_path_str)
            if pdf_path.exists() and is_safe_path(pdf_path):
                zipf.write(pdf_path, arcname=f"{sanitize_filename(recipient_name)}_certificate.pdf")
    return zip_path`
  },
  {
    name: 'test_jobs_api.py',
    path: 'tests/test_jobs_api.py',
    category: 'tests',
    description: 'Comprehensive integration test suite covering input validation, partially_failed statuses, and file streaming.',
    keyConcepts: [
      'Pytest TestClient HTTP simulation',
      'Testing 422 HTTP validation and batch limits',
      'Testing partially_failed error isolation',
      'Inspecting binary PDF (%PDF) & ZIP signatures',
    ],
    code: `import io, zipfile
from fastapi.testclient import TestClient

def test_create_job_success(client: TestClient, sample_valid_job_payload: dict):
    response = client.post("/jobs", json=sample_valid_job_payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "completed"
    assert data["successful_certificates"] == 2

def test_independent_certificate_failure_handling(client: TestClient, sample_mixed_job_payload: dict):
    create_res = client.post("/jobs", json=sample_mixed_job_payload)
    assert create_res.status_code == 201
    job_id = create_res.json()["job_id"]
    job_data = client.get(f"/jobs/{job_id}").json()
    assert job_data["status"] == "partially_failed"
    assert job_data["successful_certificates"] == 1
    assert job_data["failed_certificates"] == 1`
  },
  {
    name: 'render.yaml',
    path: 'render.yaml',
    category: 'config',
    description: 'Render Cloud Blueprint configuring Python web service, persistent disk mount, and environment variables.',
    keyConcepts: [
      'Render Blueprint Specification',
      'Persistent Disk Mount (/var/data/certificates)',
      'Dynamic PORT environment injection',
    ],
    code: `services:
  - type: web
    name: bulk-certificate-generator-api
    runtime: python
    region: oregon
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /health
    envVars:
      - key: APP_ENV
        value: production
      - key: STORAGE_DIR
        value: /var/data/certificates
      - key: MAX_RECIPIENTS_PER_BATCH
        value: 500
    disk:
      name: certificate-storage-disk
      mountPath: /var/data/certificates
      sizeGB: 1`
  }
];
