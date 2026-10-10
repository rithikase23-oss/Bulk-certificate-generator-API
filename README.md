# 🎓 Bulk Certificate Generator API (Production Edition)
> **College Placement Assessment Backend Project**  
> A production-grade, fault-tolerant Python REST API built with **FastAPI**, **SQLAlchemy**, and **ReportLab** for bulk certificate generation, isolated failure handling, and multi-format downloads.

[![Pytest Test Suite](https://img.shields.io/badge/pytest-18%20passed-success?logo=pytest)](https://docs.pytest.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-v0.110+-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![ReportLab](https://img.shields.io/badge/ReportLab-v5.0-blue)](https://www.reportlab.com)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue?logo=python)](https://python.org)

---

## 📋 Table of Contents
1. [Project Overview & Architecture](#-project-overview--architecture)
2. [Technology Stack](#-technology-stack)
3. [Folder Structure](#-folder-structure)
4. [Local Setup Instructions (Windows, macOS & Linux)](#-local-setup-instructions)
5. [Running Automated Tests](#-running-automated-tests)
6. [API Endpoints & Sample Payloads](#-api-endpoints--sample-payloads)
7. [Fault Tolerance & Error Isolation](#-fault-tolerance--error-isolation)
8. [Certificate Generation & Dynamic Typography](#-certificate-generation--dynamic-typography)
9. [Safe File Handling & Security Defenses](#-safe-file-handling--security-defenses)
10. [Render Cloud Deployment Guide](#-render-cloud-deployment-guide)
11. [Persistent Storage vs Ephemeral Filesystems](#-persistent-storage-vs-ephemeral-filesystems)
12. [Design Decisions, Trade-Offs & Limitations](#-design-decisions-trade-offs--limitations)
13. [College Placement Interview Q&A](#-college-placement-interview-qa)
14. [Git Commands to Push to GitHub](#-git-commands-to-push-to-github)

---

## 🌟 Project Overview & Architecture

Educational institutions, hackathons, and corporate placement drives regularly need to issue hundreds or thousands of personalized certificates of achievement. Traditional scripts crash when encountering a single malformed email address or special character, wasting time and compute resources.

The **Bulk Certificate Generator API** solves this challenge with:
- **Resilient Bulk Processing**: Validates batches and processes each recipient independently. A failure in Recipient #3 never halts Recipient #4 through #100.
- **Explicit Job Statuses**: Tracks jobs through `pending`, `processing`, `completed`, `partially_failed`, and `failed`.
- **Vector-Grade PDF Generation**: Uses ReportLab to generate landscape A4 certificates with ornamental borders, official seals, customizable typography, and anti-tamper SHA-256 verification hashes.
- **Dynamic Text Scaling**: Long student names and extended course titles automatically scale down and wrap to prevent margin clipping or overlap.
- **Relational Persistence**: Uses SQLAlchemy to maintain state across jobs and individual certificate records. Compatible with SQLite out-of-the-box and PostgreSQL in production.
- **Multi-Format Downloads**: Supports individual PDF retrieval (`GET /jobs/{id}/certificates/{cert_id}`) and bulk compressed ZIP downloads (`GET /jobs/{id}/download`).

```
                    [ Client (Browser / cURL / Script) ]
                                    │
                      HTTP REST API (JSON / FileStream)
                                    │
                            ┌───────▼────────┐
                            │ FastAPI App    │
                            │ (app/main.py)  │
                            └───────┬────────┘
                                    │
                            ┌───────▼────────┐
                            │ Router Layer   │
                            │ (routers/jobs) │
                            └───────┬────────┘
                                    │
                            ┌───────▼────────┐
                            │ Service Layer  │
                            │ (services/job) │
                            └───────┬────────┘
                                    │
             ┌──────────────────────┼──────────────────────┐
             │                      │                      │
      ┌──────▼──────┐       ┌───────▼──────┐        ┌──────▼──────┐
      │ Pydantic    │       │ SQLAlchemy   │        │ ReportLab   │
      │ Validation  │       │ SQLite/Postgres│      │ PDF Engine  │
      │(schemas.py) │       │ (models.py)  │        │ (generator) │
      └─────────────┘       └──────────────┘        └──────┬──────┘
                                                           │
                                                    ┌──────▼──────┐
                                                    │ Safe Disk   │
                                                    │ Storage/ZIP │
                                                    │(storage.py) │
                                                    └─────────────┘
```

---

## 🛠️ Technology Stack

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Framework** | **FastAPI 0.110+** | High-performance asynchronous web framework with automatic OpenAPI/Swagger documentation. |
| **Server** | **Uvicorn** | ASGI web server reading the dynamic cloud `$PORT`. |
| **Database ORM** | **SQLAlchemy 2.0** | Relational mapping for `Job` and `Certificate` tables (SQLite default, PostgreSQL ready). |
| **Data Validation**| **Pydantic v2** | Request validation, type enforcement, and response serialization. |
| **PDF Rendering** | **ReportLab 5.0** | Low-level vector PDF engine drawing borders, rosette seals, signatures, and typography. |
| **Testing** | **Pytest & TestClient** | Automated integration and unit tests with in-memory SQLite fixture isolation. |
| **Logging** | **Standard Logging** | Structured timestamps and severity logging without leaking internal traces. |

---

## 📂 Folder Structure

```text
├── app/
│   ├── __init__.py               # Package marker and version info
│   ├── config.py                 # Reads PORT, DATABASE_URL, STORAGE_DIR, MAX_RECIPIENTS
│   ├── database.py               # SQLAlchemy engine, session maker, Base, and get_db()
│   ├── logger.py                 # Structured application logging configuration
│   ├── models.py                 # Job and Certificate database table definitions
│   ├── schemas.py                # Pydantic request validation and response models
│   ├── certificate_generator.py  # ReportLab PDF template with borders, seal, and typography
│   ├── storage.py                # Path traversal security, filename sanitizing, and ZIP archiver
│   ├── services/
│   │   ├── __init__.py           # Services package marker
│   │   └── job_service.py        # Business logic for batch execution & failure isolation
│   ├── routers/
│   │   ├── __init__.py           # Routers package marker
│   │   └── jobs.py               # POST /jobs, GET /jobs/{id}, individual & ZIP download routes
│   └── main.py                   # FastAPI initialization, CORS, lifespan, and health check routes
├── tests/
│   ├── __init__.py               # Tests package marker
│   ├── conftest.py               # Pytest fixtures: temporary test DB, TestClient, sample payloads
│   ├── test_jobs_api.py          # API route tests (creation, validation, isolation, downloads)
│   └── test_certificate_generator.py # Unit tests for ReportLab PDF rendering & SHA-256 hashes
├── requirements.txt              # Pinned production dependencies
├── render.yaml                   # Render Blueprint with web service, persistent disk, and DB
├── Procfile                      # Process file for cloud PaaS (Render, Heroku, Railway)
├── run_server.py                 # Friendly runner script for local development
├── .env.example                  # Template configuration without secrets
├── .gitignore                    # Prevents checking in PDFs, SQLite DBs, and temp files
└── README.md                     # Complete project documentation
```

---

## 💻 Local Setup Instructions

### Prerequisites
- Python 3.10, 3.11, or 3.12 installed
- Git installed

---

### Windows Setup Instructions

#### Using Windows PowerShell:
```powershell
# 1. Clone the repository
git clone <your-repo-url>
cd bulk-certificate-generator

# 2. Create virtual environment
python -m venv venv

# 3. Activate virtual environment
.\venv\Scripts\Activate.ps1

# If PowerShell script execution policy blocks activation, run once:
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run the server
python run_server.py
```

#### Using Windows Command Prompt (CMD):
```cmd
:: 1. Clone the repository
git clone <your-repo-url>
cd bulk-certificate-generator

:: 2. Create virtual environment
python -m venv venv

:: 3. Activate virtual environment
venv\Scripts\activate.bat

:: 4. Install dependencies
pip install -r requirements.txt

:: 5. Run the server
python run_server.py
```

---

### macOS & Linux Setup Instructions
```bash
# 1. Clone and enter directory
git clone <your-repo-url>
cd bulk-certificate-generator

# 2. Create virtual environment
python3 -m venv venv

# 3. Activate virtual environment
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run the server
python3 run_server.py
```

Once running, access:
- **API Base**: `http://localhost:8000`
- **Interactive Swagger Documentation**: `http://localhost:8000/docs`
- **ReDoc Documentation**: `http://localhost:8000/redoc`
- **Health Check**: `http://localhost:8000/health`

---

## 🧪 Running Automated Tests

We use `pytest` with FastAPI's `TestClient`. Tests automatically initialize a clean temporary SQLite database in an isolated directory, guaranteeing zero pollution of your local database.

Run all tests:
```bash
pytest -v
```

### Test Suite Output (18/18 Passing):
```text
tests/test_certificate_generator.py::test_pdf_generation_creates_valid_file PASSED [  5%]
tests/test_certificate_generator.py::test_pdf_generation_scales_very_long_recipient_name PASSED [ 11%]
tests/test_certificate_generator.py::test_pdf_generation_wraps_very_long_event_title PASSED [ 16%]
tests/test_certificate_generator.py::test_pdf_generation_rejects_empty_name PASSED [ 22%]
tests/test_certificate_generator.py::test_pdf_generation_rejects_empty_event PASSED [ 27%]
tests/test_certificate_generator.py::test_certificate_hash_is_deterministic PASSED [ 33%]
tests/test_jobs_api.py::test_root_and_health_endpoints PASSED            [ 38%]
tests/test_jobs_api.py::test_create_job_success PASSED                   [ 44%]
tests/test_jobs_api.py::test_create_job_input_validation PASSED          [ 50%]
tests/test_jobs_api.py::test_batch_size_limit_enforced PASSED            [ 55%]
tests/test_jobs_api.py::test_job_status_and_progress_retrieval PASSED    [ 61%]
tests/test_jobs_api.py::test_independent_certificate_failure_handling PASSED [ 66%]
tests/test_jobs_api.py::test_all_recipients_failed_job_status PASSED     [ 72%]
tests/test_jobs_api.py::test_download_individual_certificate PASSED      [ 77%]
tests/test_jobs_api.py::test_download_job_zip PASSED                     [ 83%]
tests/test_jobs_api.py::test_download_zip_with_all_failed_recipients PASSED [ 88%]
tests/test_jobs_api.py::test_list_jobs_endpoint PASSED                   [ 94%]
tests/test_jobs_api.py::test_background_mode_job_creation PASSED         [100%]
======================== 18 passed in 0.74s =========================
```

---

## 📡 API Endpoints & Sample Payloads

### 1. `POST /jobs` — Create & Process Bulk Certificates
Accepts bulk recipient data, validates fields, and generates PDF certificates.

#### Sample Request:
```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "event_name": "Full-Stack Python Placement Sprint 2026",
    "certificate_title": "Certificate of Achievement",
    "issuer_name": "Dr. Sarah Jenkins",
    "issuer_title": "Dean of Academic Affairs",
    "organization_name": "Apex Institute of Technology",
    "issue_date": "October 10, 2026",
    "recipients": [
      {
        "name": "Aditi Sharma",
        "email": "aditi.sharma@example.edu",
        "identifier": "CS-2026-089"
      },
      {
        "name": "Karthik Verma",
        "email": "karthik.verma@example.edu",
        "identifier": "CS-2026-092"
      },
      {
        "name": "Invalid Candidate",
        "email": "not-a-valid-email-format",
        "identifier": "ERR-001"
      }
    ]
  }'
```

#### Response (HTTP 201 Created):
```json
{
  "job_id": "4b6845fb-1f29-43c2-bf62-383a1a5ce9fa",
  "status": "partially_failed",
  "total_recipients": 3,
  "successful_certificates": 2,
  "failed_certificates": 1,
  "message": "Processed 3 recipient(s): 2 succeeded, 1 failed.",
  "job_status_url": "/jobs/4b6845fb-1f29-43c2-bf62-383a1a5ce9fa",
  "zip_download_url": "/jobs/4b6845fb-1f29-43c2-bf62-383a1a5ce9fa/download"
}
```

---

### 2. `GET /jobs/{job_id}` — Check Job Status & Recipient Results

#### Sample Request:
```bash
curl -X GET http://localhost:8000/jobs/4b6845fb-1f29-43c2-bf62-383a1a5ce9fa
```

#### Response (HTTP 200 OK):
```json
{
  "job_id": "4b6845fb-1f29-43c2-bf62-383a1a5ce9fa",
  "status": "partially_failed",
  "event_name": "Full-Stack Python Placement Sprint 2026",
  "certificate_title": "Certificate of Achievement",
  "issuer_name": "Dr. Sarah Jenkins",
  "issuer_title": "Dean of Academic Affairs",
  "organization_name": "Apex Institute of Technology",
  "issue_date": "October 10, 2026",
  "total_recipients": 3,
  "successful_certificates": 2,
  "failed_certificates": 1,
  "zip_download_url": "/jobs/4b6845fb-1f29-43c2-bf62-383a1a5ce9fa/download",
  "created_at": "2026-10-10T16:40:00.123456",
  "updated_at": "2026-10-10T16:40:00.890123",
  "recipients": [
    {
      "certificate_id": "9d1b0693-559e-4c75-ae90-7608ee859074",
      "recipient_name": "Aditi Sharma",
      "recipient_email": "aditi.sharma@example.edu",
      "recipient_identifier": "CS-2026-089",
      "status": "success",
      "error_message": null,
      "certificate_hash": "b640cac08f5848e558a504fb4ea9f1b683a9033927b2adbc1a775510407f802d",
      "download_url": "/jobs/4b6845fb-1f29-43c2-bf62-383a1a5ce9fa/certificates/9d1b0693-559e-4c75-ae90-7608ee859074",
      "created_at": "2026-10-10T16:40:00.234567"
    },
    {
      "certificate_id": "18f56e07-f38b-4a57-ab5d-4f1f51cb3201",
      "recipient_name": "Invalid Candidate",
      "recipient_email": "not-a-valid-email-format",
      "recipient_identifier": "ERR-001",
      "status": "failed",
      "error_message": "Invalid email address format: 'not-a-valid-email-format'",
      "certificate_hash": null,
      "download_url": null,
      "created_at": "2026-10-10T16:40:00.345678"
    }
  ]
}
```

---

### 3. `GET /jobs/{job_id}/certificates/{certificate_id}` — Download Individual PDF
Streams the generated PDF certificate with `Content-Disposition: inline`.

```bash
curl -O -J http://localhost:8000/jobs/4b6845fb-1f29-43c2-bf62-383a1a5ce9fa/certificates/9d1b0693-559e-4c75-ae90-7608ee859074
```

---

### 4. `GET /jobs/{job_id}/download` — Download All as ZIP Archive
Downloads a compressed ZIP containing only successfully generated certificates.

```bash
curl -O -J http://localhost:8000/jobs/4b6845fb-1f29-43c2-bf62-383a1a5ce9fa/download
```

---

### 5. `GET /health` — Health Check Probe

```bash
curl http://localhost:8000/health
```
```json
{
  "status": "healthy",
  "storage_accessible": true,
  "database": "sqlite",
  "max_recipients_per_batch": 500,
  "version": "2.0.0"
}
```

---

## 🛡️ Fault Tolerance & Error Isolation

In bulk generation systems, **one bad record must never abort the remaining batch**.

### How Error Isolation Works:
1. **Pydantic Structural Gatekeeping**: If the overall JSON payload is malformed (e.g., missing `event_name` or empty `recipients`), the request is rejected immediately with **422 Unprocessable Entity**.
2. **Per-Recipient Error Boundary**:
   In `app/services/job_service.py`, each recipient is evaluated inside an isolated `try...except` block:
   ```python
   for item in recipients_data:
       try:
           # 1. Validate individual email format with RFC regex
           # 2. Check for empty recipient name
           # 3. Render and verify ReportLab PDF on disk
           cert.status = "success"
           successful_pdfs.append(...)
       except Exception as exc:
           # Isolates failure strictly to this recipient record!
           cert.status = "failed"
           cert.error_message = str(exc)
   ```
3. **Transparent Job Status States**:
   - `completed`: 100% of recipients generated successfully (0 failures).
   - `partially_failed`: At least one certificate succeeded, but one or more failed.
   - `failed`: 0 certificates succeeded.

---

## 🎨 Certificate Generation & Dynamic Typography

In a production environment, recipient names vary widely in length (from 4 characters to 70+ characters).

### Key Rendering Features (`app/certificate_generator.py`):
1. **Dynamic Font Scaling for Names**:
   Instead of hardcoding font sizes, the generator checks text width against the printable margin width:
   ```python
   name_font_size = 28
   while name_font_size > 14 and c.stringWidth(name, "Helvetica-Bold", name_font_size) > max_width:
       name_font_size -= 1
   ```
2. **Text Wrapping for Long Event Titles**:
   Uses `reportlab.lib.utils.simpleSplit` to break long course titles across multiple centered lines without colliding with the signature footer.
3. **Strict Post-Generation Verification**:
   Before a recipient record is marked as `success`, the backend verifies:
   - The file exists on disk.
   - The file size is greater than 500 bytes.
   - The binary header begins with `%PDF`.
4. **Anti-Tamper Cryptographic Hash**:
   Generates a deterministic SHA-256 hash `hashlib.sha256(f"{job_id}:{email}:{name}")` printed on the certificate for independent verification.

---

## 🔒 Safe File Handling & Security Defenses

1. **Path Traversal Defense (`is_safe_path`)**:
   All file accesses resolve canonical paths using Python's `Path.resolve()` and verify `resolved.is_relative_to(settings.STORAGE_DIR)`. Any attempt to access paths with `../../` is blocked.
2. **Filename Sanitization (`sanitize_filename`)**:
   Recipient names can contain illegal filesystem characters (`/`, `\`, `..`, `%00`). They are sanitized with regex before constructing filenames.
3. **Zip Slip Prevention**:
   When writing files to the ZIP archive in `storage.py`, arcnames are explicitly controlled and sanitized.
4. **Information Disclosure Defense**:
   A global exception handler catches unexpected runtime errors and returns a generic `500 Internal Server Error` message rather than exposing Python tracebacks to external callers.
5. **Batch Size Enforcement**:
   The `MAX_RECIPIENTS_PER_BATCH` setting defends against resource exhaustion and denial of service.

---

## 🚀 Render Cloud Deployment Guide

### Step 1: Push Project to GitHub
Ensure you are in the repository root and push all files:
```bash
git init
git add .
git commit -m "feat: complete bulk certificate generator API with ReportLab and Pytest"
git branch -M main
git remote add origin https://github.com/<your-username>/bulk-certificate-generator.git
git push -u origin main
```

### Step 2: Deploy Using Render Blueprint (Recommended)
1. Go to [dashboard.render.com](https://dashboard.render.com).
2. Click **New +** -> **Blueprint**.
3. Select your GitHub repository.
4. Render detects `render.yaml` and provisions:
   - Python Web Service
   - Persistent Disk mounted at `/var/data/certificates`
   - Managed PostgreSQL database
5. Click **Apply**.

### Step 3: Manual Web Service Setup (Alternative)
If not using Blueprints:
1. **Environment**: Python
2. **Build Command**: `pip install -r requirements.txt`
3. **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. **Environment Variables**:
   - `PORT`: `8000` (Render overrides dynamically)
   - `STORAGE_DIR`: `/var/data/certificates`
   - `APP_ENV`: `production`
5. **Disks**: Add a Disk named `cert-disk` mounted at `/var/data/certificates` (1 GB).

---

## 💾 Persistent Storage vs Ephemeral Filesystems

### Why Persistent Storage is Mandatory:
Cloud containers on Render, Heroku, or AWS use **ephemeral (temporary) filesystems**.
- When a container restarts, redeploys, or spins down due to inactivity, local files in `./storage` are wiped clean!
- Without persistent storage, users trying to download a certificate generated 2 hours ago will receive **404 Not Found**.

### Our Solution:
1. We mount a **Render Persistent Disk** to `/var/data/certificates`.
2. The application reads `STORAGE_DIR` from environment variables, seamlessly switching from `./certificates_storage` locally to `/var/data/certificates` on Render.
3. For enterprise AWS deployments, `app/storage.py` isolates filesystem logic so swapping disk writes for Amazon S3 / Google Cloud Storage can be accomplished without altering API routes.

---

## ⚖️ Design Decisions, Trade-Offs & Limitations

1. **Synchronous Execution vs Background Queues**:
   - *Decision*: By default, `POST /jobs` processes synchronously, while also offering `POST /jobs?background=true` via FastAPI `BackgroundTasks`.
   - *Rationale*: ReportLab renders vector PDFs in ~3-5ms. A standard batch of 50-100 placement certificates finishes in under 0.5 seconds. For educational placement assessments, synchronous execution avoids requiring heavy distributed queues (Celery, Redis, RabbitMQ).
   - *Limitation*: For massive batches of 10,000+ recipients, a dedicated distributed worker queue (Celery + Redis) would be preferable to avoid HTTP timeouts.
2. **SQLite vs PostgreSQL**:
   - *Decision*: SQLite locally for zero-friction setup, PostgreSQL ready in production via `DATABASE_URL`.
   - *Rationale*: Students can clone and run `pytest -v` immediately without running Docker or a local database server.
3. **No Authentication Added**:
   - *Decision*: Authentication was omitted in accordance with placement assessment instructions to keep evaluation focused on bulk processing, ReportLab PDF rendering, and failure resilience.

---

## 🎯 College Placement Interview Q&A

**Q1: How does your API handle a corrupt email in a 1,000-student batch?**  
> *"In `job_service.py`, each recipient is processed in an isolated `try...except` block. If recipient #2 fails email validation or PDF rendering, their record is saved with `status: 'failed'` and an error description, while recipients #1, #3, and all others succeed. The job transitions to `partially_failed` rather than crashing the batch."*

**Q2: What is the risk of saving files directly to a cloud container without a disk mount?**  
> *"Cloud platforms like Render utilize ephemeral filesystems. Any dyno restart or deployment wipes the container's storage, causing subsequent GET requests for certificates to return 404. We solve this by mounting a persistent disk to `/var/data/certificates` via `render.yaml`."*

**Q3: How do you defend against Path Traversal and Zip Slip attacks?**  
> *"In `app/storage.py`, we resolve every path using `Path.resolve()` and verify that `path.is_relative_to(STORAGE_DIR)` is True. Any relative path containing `../../` outside the directory raises a ValueError. Furthermore, filenames are normalized using regex before saving."*

**Q4: How do you prevent long recipient names from overflowing the certificate margin?**  
> *"In `app/certificate_generator.py`, we dynamically compute text width using `canvas.stringWidth()`. If the student's name exceeds the available margin width, the font size scales down from 28pt to 14pt. For long event titles, we use `simpleSplit` to wrap text onto multiple lines."*

---

## 💻 Git Commands to Push to GitHub

```bash
# 1. Initialize git repository
git init

# 2. Stage all source files (gitignore protects temporary files)
git add .

# 3. Commit with semantic message
git commit -m "feat: complete Bulk Certificate Generator API with ReportLab, SQLAlchemy, and Pytest"

# 4. Set main branch
git branch -M main

# 5. Add your GitHub remote repository
git remote add origin https://github.com/<your-username>/bulk-certificate-generator.git

# 6. Push to GitHub
git push -u origin main
```
