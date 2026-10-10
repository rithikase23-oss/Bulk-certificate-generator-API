"""
Application Configuration
-------------------------
Beginner Note:
Environment variables allow us to configure the application without modifying code.
In production (e.g., Render, Railway, AWS), we inject sensitive credentials and system
paths through environment variables like PORT, DATABASE_URL, and STORAGE_DIR.
"""

import os
from pathlib import Path


class Settings:
    """
    Central settings object reading from system environment variables.
    Provides safe defaults for quick local development.
    """

    # Server port (Render automatically provides the PORT environment variable;
    # in local development sandboxes, FASTAPI_PORT or safe fallback 8088 is used)
    _raw_port = os.getenv("FASTAPI_PORT") or os.getenv("PORT", "8000")
    try:
        _parsed_port = int(_raw_port)
        # Avoid conflicting with nginx (8080) or control plane (8000) in sandbox environments
        if _parsed_port in (8080, 8000) and os.getenv("RENDER") is None:
            PORT: int = int(os.getenv("FASTAPI_PORT", "8088"))
        else:
            PORT: int = _parsed_port
    except ValueError:
        PORT: int = 8088

    # Server host address (0.0.0.0 binds to all network interfaces for container/cloud deployment)
    HOST: str = os.getenv("HOST", "0.0.0.0")

    # Application environment: 'development', 'testing', or 'production'
    APP_ENV: str = os.getenv("APP_ENV", "development")

    # Maximum recipients permitted per batch request (defends against DoS and memory exhaustion)
    MAX_RECIPIENTS_PER_BATCH: int = int(os.getenv("MAX_RECIPIENTS_PER_BATCH", "500"))

    # Logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR')
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Database connection URL
    # Local default: lightweight file-based SQLite database
    # Production example: postgresql://user:pass@host:5432/dbname
    _raw_db_url: str = os.getenv("DATABASE_URL", "sqlite:///./certificates.db")

    # Render and older platforms sometimes provide 'postgres://' which SQLAlchemy 2.0 requires as 'postgresql://'
    if _raw_db_url.startswith("postgres://"):
        DATABASE_URL: str = _raw_db_url.replace("postgres://", "postgresql://", 1)
    else:
        DATABASE_URL: str = _raw_db_url

    # Storage directory where generated PDFs and batch ZIP archives will be saved
    # For Render production: map this path to a Render Persistent Disk (e.g., /var/data/certificates)
    STORAGE_DIR: Path = Path(os.getenv("STORAGE_DIR", "./certificates_storage")).resolve()

    # Application metadata
    APP_TITLE: str = "Bulk Certificate Generator API"
    APP_VERSION: str = "2.0.0"
    APP_DESCRIPTION: str = (
        "Production-grade, fault-tolerant bulk certificate generator API with ReportLab "
        "PDF generation, SQLite/PostgreSQL persistence, dynamic text scaling, and isolated error handling."
    )


# Instantiate a singleton settings instance
settings = Settings()

# Ensure the storage directory exists on startup
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
