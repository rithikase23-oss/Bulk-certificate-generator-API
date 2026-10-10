"""
Pydantic Schemas for Request Validation and Response Serialization
------------------------------------------------------------------
Beginner Note:
Pydantic models act as automated gatekeepers:
1. Request Schemas: Validate data sent by clients in HTTP request bodies. If a client
   omits a required field or sends the wrong data type, Pydantic immediately returns
   a clean 422 Unprocessable Entity error.
2. Response Schemas: Ensure consistent, predictable JSON output structure to clients.
"""

import re
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from app.config import settings

# RFC 5322 compatible regex for recipient email validation
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class RecipientInput(BaseModel):
    """
    Schema for an individual recipient inside a bulk certificate request.
    """
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Full name of the recipient to be printed on the certificate",
        examples=["Aditi Sharma"],
    )
    email: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Recipient email address for record keeping",
        examples=["aditi.sharma@example.edu"],
    )
    identifier: Optional[str] = Field(
        None,
        max_length=100,
        description="Optional unique student roll number, candidate ID, or employee code",
        examples=["CS-2026-089"],
    )

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Recipient name cannot be blank or whitespace only")
        return stripped

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("identifier")
    @classmethod
    def normalize_identifier(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            stripped = v.strip()
            return stripped if stripped else None
        return None


class JobCreateRequest(BaseModel):
    """
    Schema for POST /jobs: Bulk certificate generation request payload.
    """
    event_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Name of the course, competition, or workshop",
        examples=["Full-Stack Engineering Placement Sprint 2026"],
    )
    certificate_title: Optional[str] = Field(
        "Certificate of Achievement",
        min_length=2,
        max_length=255,
        description="Header title displayed on the certificate",
        examples=["Certificate of Excellence"],
    )
    issuer_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Name of the authority issuing the certificate",
        examples=["Dr. Ramesh Kumar"],
    )
    issuer_title: Optional[str] = Field(
        "Head of Placement & Corporate Relations",
        max_length=255,
        description="Designation of the issuing authority",
        examples=["Director of Training & Placements"],
    )
    organization_name: Optional[str] = Field(
        "Apex Institute of Technology",
        max_length=255,
        description="Issuing organization, college, or university name",
        examples=["Apex Institute of Technology"],
    )
    issue_date: str = Field(
        ...,
        min_length=4,
        max_length=50,
        description="Date of certificate issuance (e.g. 'October 10, 2026' or '2026-10-10')",
        examples=["October 10, 2026"],
    )
    recipients: List[RecipientInput] = Field(
        ...,
        min_length=1,
        description=f"List of recipients to generate certificates for (1 to {settings.MAX_RECIPIENTS_PER_BATCH} allowed)",
    )

    @field_validator("event_name", "issuer_name", "issue_date")
    @classmethod
    def validate_non_blank_strings(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field cannot be blank or whitespace only")
        return stripped

    @model_validator(mode="after")
    def validate_batch_size(self):
        """
        Enforce max recipients limit to defend server resources.
        """
        if len(self.recipients) > settings.MAX_RECIPIENTS_PER_BATCH:
            raise ValueError(
                f"Batch exceeds maximum limit of {settings.MAX_RECIPIENTS_PER_BATCH} recipients. "
                f"Received {len(self.recipients)}."
            )
        return self


class RecipientResultResponse(BaseModel):
    """
    Schema for an individual recipient's result within a job response.
    """
    model_config = ConfigDict(from_attributes=True)

    certificate_id: str = Field(..., description="Unique certificate UUID")
    recipient_name: str
    recipient_email: str
    recipient_identifier: Optional[str] = None
    status: str = Field(..., description="'success', 'failed', 'processing', or 'pending'")
    error_message: Optional[str] = Field(None, description="Detailed reason if certificate failed")
    certificate_hash: Optional[str] = Field(None, description="Unique anti-tamper verification hash")
    download_url: Optional[str] = Field(None, description="API endpoint to download this individual PDF")
    created_at: datetime


class JobResponse(BaseModel):
    """
    Schema for GET /jobs/{job_id}: Full job status with individual recipient breakdown.
    """
    model_config = ConfigDict(from_attributes=True)

    job_id: str
    status: str = Field(..., description="'pending', 'processing', 'completed', 'partially_failed', or 'failed'")
    event_name: str
    certificate_title: str
    issuer_name: str
    issuer_title: Optional[str] = None
    organization_name: str
    issue_date: str
    total_recipients: int
    successful_certificates: int
    failed_certificates: int
    zip_download_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    recipients: List[RecipientResultResponse]


class JobCreateResponse(BaseModel):
    """
    Response returned after POST /jobs.
    """
    job_id: str
    status: str
    total_recipients: int
    successful_certificates: int
    failed_certificates: int
    message: str
    job_status_url: str
    zip_download_url: Optional[str] = None
