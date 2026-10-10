"""
Application Logging Configuration
---------------------------------
Beginner Note:
Structured logging provides visibility into application runtime events,
such as request lifecycles, database operations, and PDF generation failures,
without cluttering responses with internal server stack traces.
"""

import logging
import sys
import os

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Configure root logger format with timestamps, logger name, and severity
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-7s | %(name)s:%(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("bulk_cert_api")
