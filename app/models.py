"""
SQLAlchemy Database Models
--------------------------
Beginner Note:
Models define the database schema (tables and columns).
We have two connected tables:
1. Job: Represents the overall bulk generation request (batch metadata, counts, status).
2. Certificate: Represents one recipient's certificate in that batch, tracking whether
   their individual PDF succeeded or failed, and where the file is stored.

This 1-to-Many relationship allows us to track failures per-recipient without
failing the whole job!
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from app.database import Base


class Job(Base):
    """
    Represents a bulk certificate generation batch job.
    """
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    event_name = Column(String(255), nullable=False)
    certificate_title = Column(String(255), nullable=False, default="Certificate of Achievement")
    issuer_name = Column(String(255), nullable=False)
    issuer_title = Column(String(255), nullable=True, default="Program Coordinator")
    organization_name = Column(String(255), nullable=False, default="Placement Assessment Board")
    issue_date = Column(String(50), nullable=False)
    
    # Status progression:
    # 'pending' -> 'processing' -> 'completed' | 'partially_failed' | 'failed'
    status = Column(String(50), nullable=False, default="pending", index=True)
    
    total_recipients = Column(Integer, nullable=False, default=0)
    successful_certificates = Column(Integer, nullable=False, default=0)
    failed_certificates = Column(Integer, nullable=False, default=0)
    
    # Path to the compiled ZIP archive containing all successful PDFs
    zip_file_path = Column(String(500), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # 1-to-many relationship with certificates
    certificates = relationship(
        "Certificate",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="Certificate.created_at",
    )

    def __repr__(self) -> str:
        return f"<Job id={self.id} event='{self.event_name}' status='{self.status}'>"


class Certificate(Base):
    """
    Represents an individual recipient's certificate within a Job.
    Tracks success/failure status independently.
    """
    __tablename__ = "certificates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    recipient_name = Column(String(255), nullable=False)
    recipient_email = Column(String(255), nullable=False)
    recipient_identifier = Column(String(100), nullable=True)  # Roll number or student ID
    
    # Status: 'pending', 'processing', 'success', 'failed'
    status = Column(String(50), nullable=False, default="pending", index=True)
    
    # File details (populated if success)
    pdf_filename = Column(String(255), nullable=True)
    pdf_path = Column(String(500), nullable=True)
    
    # Error message (populated if failed, e.g., invalid email or PDF rendering error)
    error_message = Column(Text, nullable=True)
    
    # Unique verification identifier displayed on the certificate
    certificate_hash = Column(String(64), nullable=True, unique=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Back-reference to the parent job
    job = relationship("Job", back_populates="certificates")

    # Composite index for querying successful certificates per job
    __table_args__ = (
        Index("idx_job_cert_status", "job_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Certificate id={self.id} recipient='{self.recipient_name}' status='{self.status}'>"
