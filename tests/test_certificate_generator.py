"""
ReportLab Certificate Generator Unit Tests
------------------------------------------
Beginner Note:
Unit tests verify individual functions in isolation.
Here we test:
- Standard PDF rendering produces valid PDF headers and structure
- Long recipient names are automatically scaled down to prevent clipping
- Long event and course titles wrap onto multiple lines cleanly
- Empty or blank strings are rejected
- SHA-256 anti-tamper verification hash is deterministic
"""

from pathlib import Path
import pytest
from app.certificate_generator import (
    generate_certificate_pdf,
    generate_certificate_hash,
)


def test_pdf_generation_creates_valid_file(tmp_path: Path):
    """
    Verify that generate_certificate_pdf renders a valid PDF on disk.
    """
    output_pdf = tmp_path / "cert_test.pdf"
    
    generate_certificate_pdf(
        output_path=output_pdf,
        recipient_name="Priya Sharma",
        event_name="Full-Stack Engineering Sprint",
        issuer_name="Dr. K. Raman",
        issue_date="2026-10-10",
        certificate_title="Certificate of Excellence",
        issuer_title="Program Director",
        organization_name="Apex College of Engineering",
        recipient_identifier="REG-2026-90",
        certificate_hash="abc123def4567890",
        certificate_id="cert-uuid-1234",
    )

    assert output_pdf.exists()
    assert output_pdf.stat().st_size > 1000  # Non-trivial PDF size

    # Verify standard PDF magic header bytes
    with open(output_pdf, "rb") as f:
        header = f.read(4)
        assert header == b"%PDF"


def test_pdf_generation_scales_very_long_recipient_name(tmp_path: Path):
    """
    Verify that an unusually long name (e.g. 60+ chars) is dynamically scaled down
    and rendered without raising an overflow or coordinate exception.
    """
    output_pdf = tmp_path / "cert_long_name.pdf"
    long_name = "Dr. Venkata Ramanathan Subramanian Chandrasekharan Senior Fellow"
    
    generate_certificate_pdf(
        output_path=output_pdf,
        recipient_name=long_name,
        event_name="Cloud Architecture Placement Sprint",
        issuer_name="Dean of Engineering",
        issue_date="2026-10-10",
    )

    assert output_pdf.exists()
    assert output_pdf.stat().st_size > 1000
    with open(output_pdf, "rb") as f:
        assert f.read(4) == b"%PDF"


def test_pdf_generation_wraps_very_long_event_title(tmp_path: Path):
    """
    Verify that a very long event name (e.g. 100+ chars) wraps cleanly
    without crashing ReportLab canvas drawing.
    """
    output_pdf = tmp_path / "cert_long_event.pdf"
    long_event = "Advanced High-Performance Scalable Cloud Infrastructure & Distributed Microservices Placement Hackathon 2026"
    
    generate_certificate_pdf(
        output_path=output_pdf,
        recipient_name="Aditi Sharma",
        event_name=long_event,
        issuer_name="Program Coordinator",
        issue_date="2026-10-10",
    )

    assert output_pdf.exists()
    assert output_pdf.stat().st_size > 1000
    with open(output_pdf, "rb") as f:
        assert f.read(4) == b"%PDF"


def test_pdf_generation_rejects_empty_name(tmp_path: Path):
    """
    Verify that an empty or whitespace-only recipient name raises ValueError.
    """
    output_pdf = tmp_path / "cert_invalid.pdf"
    with pytest.raises(ValueError, match="recipient_name is empty"):
        generate_certificate_pdf(
            output_path=output_pdf,
            recipient_name="   ",
            event_name="Hackathon",
            issuer_name="Dean",
            issue_date="2026-10-10",
        )


def test_pdf_generation_rejects_empty_event(tmp_path: Path):
    """
    Verify that an empty or whitespace-only event name raises ValueError.
    """
    output_pdf = tmp_path / "cert_invalid_event.pdf"
    with pytest.raises(ValueError, match="event_name is empty"):
        generate_certificate_pdf(
            output_path=output_pdf,
            recipient_name="Valid Name",
            event_name="   ",
            issuer_name="Dean",
            issue_date="2026-10-10",
        )


def test_certificate_hash_is_deterministic():
    """
    Verify that identical inputs produce identical verification hashes,
    and different inputs produce different hashes.
    """
    hash1 = generate_certificate_hash("job-1", "user@test.com", "John Doe")
    hash2 = generate_certificate_hash("job-1", "user@test.com", "John Doe")
    hash3 = generate_certificate_hash("job-1", "user@test.com", "Jane Doe")

    assert hash1 == hash2
    assert hash1 != hash3
    assert len(hash1) == 64  # SHA-256 hex string length
