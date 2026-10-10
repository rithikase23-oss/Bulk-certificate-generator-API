"""
API Integration & Route Test Suite
----------------------------------
Beginner Note:
FastAPI TestClient allows simulating real HTTP requests in Python memory
without needing to launch a background web server.

Tests cover:
1. Root and health check probes (GET /, GET /health)
2. Creating jobs (POST /jobs) with synchronous and background execution
3. Input validation for missing/invalid fields (HTTP 422)
4. Batch size limit defense (HTTP 422)
5. Retrieving job status and progress (GET /jobs/{id})
6. Independent certificate failure handling (partially_failed status)
7. Total batch failure handling (failed status)
8. Downloading individual PDF certificates (GET /jobs/{id}/certificates/{cert_id})
9. Downloading batch ZIP archives (GET /jobs/{id}/download)
10. Safe error handling for unknown IDs and failed certificates
"""

import io
import zipfile
import pytest
from fastapi.testclient import TestClient
from app.config import settings


def test_root_and_health_endpoints(client: TestClient):
    """
    Test that the root metadata and health check endpoints respond correctly.
    """
    res_root = client.get("/")
    assert res_root.status_code == 200
    data = res_root.json()
    assert data["status"] == "online"
    assert "POST /jobs" in data["endpoints"]["create_job"]
    assert "GET /health" in data["endpoints"]["health"]

    res_health = client.get("/health")
    assert res_health.status_code == 200
    health_data = res_health.json()
    assert health_data["status"] == "healthy"
    assert health_data["storage_accessible"] is True
    assert "max_recipients_per_batch" in health_data

    # Also test /api/health alias
    res_api_health = client.get("/api/health")
    assert res_api_health.status_code == 200


def test_create_job_success(client: TestClient, sample_valid_job_payload: dict):
    """
    Test creating a bulk certificate job with valid recipients.
    Expects 201 Created and successful generation for all recipients.
    """
    response = client.post("/jobs", json=sample_valid_job_payload)
    assert response.status_code == 201

    data = response.json()
    assert "job_id" in data
    assert data["status"] == "completed"
    assert data["total_recipients"] == 2
    assert data["successful_certificates"] == 2
    assert data["failed_certificates"] == 0
    assert data["zip_download_url"] is not None
    assert f"/jobs/{data['job_id']}/download" in data["zip_download_url"]


def test_create_job_input_validation(client: TestClient):
    """
    Test that missing or invalid required fields return 422 Unprocessable Entity.
    """
    # 1. Missing event_name
    bad_payload_1 = {
        "issuer_name": "Dr. Smith",
        "issue_date": "2026-10-10",
        "recipients": [{"name": "Test", "email": "test@example.com"}],
    }
    res1 = client.post("/jobs", json=bad_payload_1)
    assert res1.status_code == 422

    # 2. Blank event_name (whitespace only)
    bad_payload_2 = {
        "event_name": "   ",
        "issuer_name": "Dr. Smith",
        "issue_date": "2026-10-10",
        "recipients": [{"name": "Test", "email": "test@example.com"}],
    }
    res2 = client.post("/jobs", json=bad_payload_2)
    assert res2.status_code == 422

    # 3. Empty recipients array
    bad_payload_3 = {
        "event_name": "Python Sprint",
        "issuer_name": "Dr. Smith",
        "issue_date": "2026-10-10",
        "recipients": [],
    }
    res3 = client.post("/jobs", json=bad_payload_3)
    assert res3.status_code == 422

    # 4. Recipient with blank name
    bad_payload_4 = {
        "event_name": "Python Sprint",
        "issuer_name": "Dr. Smith",
        "issue_date": "2026-10-10",
        "recipients": [{"name": "   ", "email": "test@example.com"}],
    }
    res4 = client.post("/jobs", json=bad_payload_4)
    assert res4.status_code == 422


def test_batch_size_limit_enforced(client: TestClient):
    """
    Test that exceeding MAX_RECIPIENTS_PER_BATCH returns 422 Unprocessable Entity.
    """
    original_limit = settings.MAX_RECIPIENTS_PER_BATCH
    try:
        settings.MAX_RECIPIENTS_PER_BATCH = 3  # Temporarily lower limit for test
        oversized_payload = {
            "event_name": "Large Batch Test",
            "issuer_name": "Director",
            "issue_date": "2026-10-10",
            "recipients": [
                {"name": f"Student {i}", "email": f"student{i}@example.com"}
                for i in range(4)
            ],
        }
        res = client.post("/jobs", json=oversized_payload)
        assert res.status_code == 422
        assert "maximum limit" in str(res.json()).lower()
    finally:
        settings.MAX_RECIPIENTS_PER_BATCH = original_limit


def test_job_status_and_progress_retrieval(client: TestClient, sample_valid_job_payload: dict):
    """
    Test GET /jobs/{job_id} retrieves accurate status, counts, and recipient results.
    """
    create_res = client.post("/jobs", json=sample_valid_job_payload)
    job_id = create_res.json()["job_id"]

    get_res = client.get(f"/jobs/{job_id}")
    assert get_res.status_code == 200

    job_data = get_res.json()
    assert job_data["job_id"] == job_id
    assert job_data["status"] == "completed"
    assert job_data["event_name"] == sample_valid_job_payload["event_name"]
    assert job_data["total_recipients"] == 2
    assert job_data["successful_certificates"] == 2
    assert job_data["failed_certificates"] == 0
    assert len(job_data["recipients"]) == 2

    # Verify recipient level details
    first_recipient = job_data["recipients"][0]
    assert first_recipient["status"] == "success"
    assert first_recipient["recipient_name"] in ["Aarav Patel", "Diya Sen"]
    assert first_recipient["download_url"].startswith(f"/jobs/{job_id}/certificates/")
    assert first_recipient["certificate_hash"] is not None

    # Verify 404 for non-existent job ID
    not_found_res = client.get("/jobs/00000000-0000-0000-0000-000000000000")
    assert not_found_res.status_code == 404
    assert "not found" in not_found_res.json()["detail"].lower()


def test_independent_certificate_failure_handling(client: TestClient, sample_mixed_job_payload: dict):
    """
    Critical Requirement Test:
    When one recipient fails (e.g. invalid email format), other recipients must still SUCCEED.
    The job status becomes 'partially_failed' rather than crashing the batch.
    """
    create_res = client.post("/jobs", json=sample_mixed_job_payload)
    assert create_res.status_code == 201

    job_id = create_res.json()["job_id"]
    get_res = client.get(f"/jobs/{job_id}")
    assert get_res.status_code == 200

    data = get_res.json()
    # Verified: status is explicitly partially_failed
    assert data["status"] == "partially_failed"
    assert data["total_recipients"] == 2
    assert data["successful_certificates"] == 1
    assert data["failed_certificates"] == 1

    recipients = {r["recipient_name"]: r for r in data["recipients"]}

    # Valid recipient must have succeeded
    valid_rec = recipients["Valid Student"]
    assert valid_rec["status"] == "success"
    assert valid_rec["error_message"] is None
    assert valid_rec["download_url"] is not None

    # Faulty recipient must have failed independently with an informative error message
    faulty_rec = recipients["Faulty Student"]
    assert faulty_rec["status"] == "failed"
    assert "Invalid email address format" in faulty_rec["error_message"]
    assert faulty_rec["download_url"] is None


def test_all_recipients_failed_job_status(client: TestClient):
    """
    Test that when all recipients fail, the job status is 'failed'.
    """
    all_bad_payload = {
        "event_name": "Failed Batch Test",
        "issuer_name": "Instructor",
        "issue_date": "2026-10-10",
        "recipients": [
            {"name": "Bad A", "email": "bad_email_1"},
            {"name": "Bad B", "email": "bad_email_2"},
        ],
    }
    create_res = client.post("/jobs", json=all_bad_payload)
    assert create_res.status_code == 201
    job_id = create_res.json()["job_id"]

    get_res = client.get(f"/jobs/{job_id}")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["status"] == "failed"
    assert data["successful_certificates"] == 0
    assert data["failed_certificates"] == 2
    assert data["zip_download_url"] is None


def test_download_individual_certificate(client: TestClient, sample_mixed_job_payload: dict):
    """
    Test GET /jobs/{job_id}/certificates/{certificate_id}:
    - Succeeded certificate downloads valid PDF binary (%PDF header)
    - Failed certificate returns 400 Bad Request
    - Non-existent certificate returns 404 Not Found
    """
    create_res = client.post("/jobs", json=sample_mixed_job_payload)
    job_id = create_res.json()["job_id"]

    job_data = client.get(f"/jobs/{job_id}").json()
    recipients = {r["recipient_name"]: r for r in job_data["recipients"]}

    valid_cert_id = recipients["Valid Student"]["certificate_id"]
    failed_cert_id = recipients["Faulty Student"]["certificate_id"]

    # 1. Download successful certificate
    pdf_res = client.get(f"/jobs/{job_id}/certificates/{valid_cert_id}")
    assert pdf_res.status_code == 200
    assert "application/pdf" in pdf_res.headers.get("content-type", "")
    assert pdf_res.content[:4] == b"%PDF"  # Standard PDF file signature

    # 2. Attempt to download failed certificate
    bad_pdf_res = client.get(f"/jobs/{job_id}/certificates/{failed_cert_id}")
    assert bad_pdf_res.status_code == 400
    assert "generation did not succeed" in bad_pdf_res.json()["detail"].lower()

    # 3. Non-existent certificate ID
    not_found_res = client.get(f"/jobs/{job_id}/certificates/unknown-cert-id")
    assert not_found_res.status_code == 404


def test_download_job_zip(client: TestClient, sample_valid_job_payload: dict):
    """
    Test GET /jobs/{job_id}/download:
    Downloads a valid ZIP archive containing only successfully generated PDFs.
    """
    create_res = client.post("/jobs", json=sample_valid_job_payload)
    job_id = create_res.json()["job_id"]

    zip_res = client.get(f"/jobs/{job_id}/download")
    assert zip_res.status_code == 200
    assert "application/zip" in zip_res.headers.get("content-type", "")

    # Verify that the response content is indeed a readable ZIP archive
    zip_bytes = io.BytesIO(zip_res.content)
    with zipfile.ZipFile(zip_bytes, "r") as zf:
        file_list = zf.namelist()
        # Should contain exactly 2 certificates
        assert len(file_list) == 2
        for filename in file_list:
            assert filename.endswith(".pdf")
            pdf_content = zf.read(filename)
            assert pdf_content[:4] == b"%PDF"


def test_download_zip_with_all_failed_recipients(client: TestClient):
    """
    Test that attempting to download a ZIP for a job where 0 certificates succeeded
    returns 400 Bad Request with a clear explanation.
    """
    all_failed_payload = {
        "event_name": "Failing Batch",
        "issuer_name": "Dean Test",
        "issue_date": "2026-10-10",
        "recipients": [
            {"name": "Bad Recipient 1", "email": "bad-email-1"},
            {"name": "Bad Recipient 2", "email": "bad-email-2"},
        ],
    }

    create_res = client.post("/jobs", json=all_failed_payload)
    job_id = create_res.json()["job_id"]

    zip_res = client.get(f"/jobs/{job_id}/download")
    assert zip_res.status_code == 400
    assert "no certificates were successfully generated" in zip_res.json()["detail"].lower()


def test_list_jobs_endpoint(client: TestClient, sample_valid_job_payload: dict):
    """
    Test GET /jobs lists all created jobs with pagination.
    """
    client.post("/jobs", json=sample_valid_job_payload)
    list_res = client.get("/jobs?limit=10&offset=0")
    assert list_res.status_code == 200
    jobs = list_res.json()
    assert isinstance(jobs, list)
    assert len(jobs) >= 1


def test_background_mode_job_creation(client: TestClient, sample_valid_job_payload: dict):
    """
    Test creating a job with background=true parameter.
    Verifies that the endpoint accepts the request and returns status='pending'.
    """
    response = client.post("/jobs?background=true", json=sample_valid_job_payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"
    assert "queued for background processing" in data["message"].lower()
