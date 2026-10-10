"""
Safe Storage & File Management
------------------------------
Beginner Note:
Handling file uploads and downloads safely is crucial in web applications.
Malicious users often try "Path Traversal" attacks (e.g., passing '../../etc/passwd')
to read unauthorized files on the server.

This module enforces:
1. Canonical Path Resolution: Every file path must resolve strictly inside STORAGE_DIR.
2. Filename Sanitization: Disallows dangerous characters in filenames.
3. ZIP Archiving: Packages generated PDFs into compressed ZIP archives.
"""

import os
import re
import zipfile
from pathlib import Path
from typing import List, Tuple
from app.config import settings


def sanitize_filename(name: str) -> str:
    """
    Strips or replaces unsafe characters from a string to make it safe for filesystems.
    Example: "John Doe / Student?" -> "John_Doe___Student_"
    """
    # Replace whitespace and unsafe characters with underscores
    cleaned = re.sub(r"[^\w\-. ]", "_", name)
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned.strip("._") or "certificate"


def get_job_storage_dir(job_id: str) -> Path:
    """
    Returns the isolated directory for a specific job.
    Structure: {STORAGE_DIR}/jobs/{job_id}/
    """
    job_dir = (settings.STORAGE_DIR / "jobs" / job_id).resolve()
    # Path traversal protection
    if not job_dir.is_relative_to(settings.STORAGE_DIR):
        raise ValueError("Invalid job path: Directory traversal detected")
    job_dir.mkdir(parents=True, exist_ok=True)
    return job_dir


def get_certificate_filepath(job_id: str, cert_id: str, recipient_name: str) -> Path:
    """
    Generates a secure, unique filepath for an individual recipient's certificate.
    """
    job_dir = get_job_storage_dir(job_id)
    safe_name = sanitize_filename(recipient_name)
    filename = f"{cert_id[:8]}_{safe_name}.pdf"
    file_path = (job_dir / filename).resolve()
    
    # Path traversal protection
    if not file_path.is_relative_to(settings.STORAGE_DIR):
        raise ValueError("Invalid certificate path: Directory traversal detected")
        
    return file_path


def is_safe_path(target_path: Path) -> bool:
    """
    Verifies that target_path is strictly within the allowed STORAGE_DIR.
    """
    try:
        resolved = target_path.resolve()
        return resolved.is_relative_to(settings.STORAGE_DIR) and resolved.exists()
    except (ValueError, RuntimeError):
        return False


def build_job_zip_archive(job_id: str, event_name: str, certificates_data: List[Tuple[str, str]]) -> Path:
    """
    Creates a compressed ZIP archive containing all successfully generated PDFs.
    
    Args:
        job_id: UUID of the job
        event_name: Name of the event (used in ZIP filename)
        certificates_data: List of tuples (file_path_str, recipient_name)
        
    Returns:
        Path to the generated ZIP archive
    """
    job_dir = get_job_storage_dir(job_id)
    safe_event_name = sanitize_filename(event_name)
    zip_path = (job_dir / f"{safe_event_name}_certificates_{job_id[:8]}.zip").resolve()
    
    if not zip_path.is_relative_to(settings.STORAGE_DIR):
        raise ValueError("Invalid ZIP path: Directory traversal detected")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        used_arcnames = set()
        for pdf_path_str, recipient_name in certificates_data:
            pdf_path = Path(pdf_path_str)
            if pdf_path.exists() and is_safe_path(pdf_path):
                # Friendly filename inside the ZIP
                base_name = f"{sanitize_filename(recipient_name)}_certificate.pdf"
                arcname = base_name
                # Avoid collision if multiple recipients have the same name
                counter = 1
                while arcname in used_arcnames:
                    arcname = f"{sanitize_filename(recipient_name)}_{counter}_certificate.pdf"
                    counter += 1
                used_arcnames.add(arcname)
                zipf.write(pdf_path, arcname=arcname)

    return zip_path
