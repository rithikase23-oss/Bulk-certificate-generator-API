"""
Pytest Fixtures & Test Setup
----------------------------
Beginner Note:
conftest.py is automatically discovered by pytest.
Fixtures defined here can be used in any test function simply by passing their
name as a parameter.

In these tests:
- We use an isolated temporary SQLite database file or in-memory DB so tests never
  pollute your actual certificates.db.
- We use an isolated temporary directory for generated PDFs.
- We override FastAPI's `get_db` dependency so the app routes use the test DB.
"""

import shutil
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base, get_db
from app.main import app

# Create a temporary directory for test certificate storage
TEST_STORAGE_DIR = Path(tempfile.mkdtemp(prefix="test_cert_storage_"))

# Create an isolated test SQLite database
TEST_DB_FILE = TEST_STORAGE_DIR / "test_certificates.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_FILE}"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
    future=True,
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """
    Session-level fixture:
    Configures temporary storage and ensures clean teardown after all tests run.
    """
    original_storage = settings.STORAGE_DIR
    settings.STORAGE_DIR = TEST_STORAGE_DIR
    settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    
    yield
    
    # Teardown: restore original storage and delete temp files
    settings.STORAGE_DIR = original_storage
    if TEST_STORAGE_DIR.exists():
        shutil.rmtree(TEST_STORAGE_DIR, ignore_errors=True)


@pytest.fixture(scope="function")
def db_session():
    """
    Function-level fixture:
    Recreates tables fresh for each individual test to guarantee test isolation.
    """
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session):
    """
    TestClient fixture with dependency override for get_db.
    Allows simulating HTTP requests against the FastAPI app.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_valid_job_payload():
    """
    A standard valid bulk request payload containing 2 recipients.
    """
    return {
        "event_name": "Full-Stack Python Campus Drive 2026",
        "certificate_title": "Certificate of Excellence",
        "issuer_name": "Dr. R. Miller",
        "issuer_title": "Director of Placements",
        "organization_name": "Apex University",
        "issue_date": "2026-10-10",
        "recipients": [
            {
                "name": "Aarav Patel",
                "email": "aarav.patel@example.com",
                "identifier": "CS-001",
            },
            {
                "name": "Diya Sen",
                "email": "diya.sen@example.com",
                "identifier": "CS-002",
            },
        ],
    }


@pytest.fixture
def sample_mixed_job_payload():
    """
    A payload containing 1 valid recipient and 1 invalid recipient (bad email)
    to test independent failure handling.
    """
    return {
        "event_name": "AI Systems Hackathon",
        "certificate_title": "Certificate of Participation",
        "issuer_name": "Prof. Alan Grant",
        "issuer_title": "Hackathon Chair",
        "organization_name": "Apex University",
        "issue_date": "2026-10-10",
        "recipients": [
            {
                "name": "Valid Student",
                "email": "valid.student@example.com",
                "identifier": "VAL-101",
            },
            {
                "name": "Faulty Student",
                "email": "not-a-valid-email-format",  # Malformed email intentionally
                "identifier": "ERR-999",
            },
        ],
    }
