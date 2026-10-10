"""
FastAPI Application Entry Point
-------------------------------
Beginner Note:
This is the heart of our backend application.
- Creates the FastAPI app instance
- Registers CORS middleware to allow cross-origin requests
- Initializes database tables upon startup
- Attaches the API routers
- Catches unhandled exceptions safely without leaking internal stack traces
- Reads the PORT environment variable for cloud platforms (Render, Heroku, AWS)
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_db
from app.routers import jobs
from app.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager runs code before the server starts accepting requests
    and when the server shuts down.
    """
    logger.info("Initializing Bulk Certificate Generator application...")
    # 1. Initialize SQLite / PostgreSQL tables
    init_db()
    # 2. Ensure storage directory exists
    settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Storage directory confirmed at {settings.STORAGE_DIR}")
    logger.info(f"Database dialect: {settings.DATABASE_URL.split('://')[0]}")
    yield
    logger.info("Application shutdown completed.")


app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Enable CORS for local testing, frontend integration, and remote clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global unhandled exception handler to defend against leaking internal traces
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred while processing the request."},
    )

# Include Jobs router:
# Mounted at both root /jobs and /api/jobs for maximum compatibility
app.include_router(jobs.router)
app.include_router(jobs.router, prefix="/api")


@app.get("/", tags=["Health & Info"])
def root():
    """
    Root endpoint: returns API metadata, status, and navigation links.
    """
    return {
        "app": settings.APP_TITLE,
        "version": settings.APP_VERSION,
        "status": "online",
        "documentation": "/docs",
        "redoc": "/redoc",
        "storage_directory": str(settings.STORAGE_DIR),
        "endpoints": {
            "create_job": "POST /jobs",
            "get_job_status": "GET /jobs/{job_id}",
            "download_certificate": "GET /jobs/{job_id}/certificates/{certificate_id}",
            "download_zip": "GET /jobs/{job_id}/download",
            "list_jobs": "GET /jobs",
            "health": "GET /health",
        },
    }


@app.get("/health", tags=["Health & Info"])
@app.get("/api/health", tags=["Health & Info"])
def health_check():
    """
    Health check probe endpoint for cloud deployments (Render, Kubernetes, Docker).
    """
    return {
        "status": "healthy",
        "storage_accessible": settings.STORAGE_DIR.exists(),
        "database": settings.DATABASE_URL.split("://")[0],
        "max_recipients_per_batch": settings.MAX_RECIPIENTS_PER_BATCH,
        "version": settings.APP_VERSION,
    }


if __name__ == "__main__":
    import uvicorn
    # Beginner Note:
    # On Render, the PORT environment variable is automatically supplied.
    # settings.PORT automatically parses it.
    logger.info(f"Starting uvicorn server on {settings.HOST}:{settings.PORT}")
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.APP_ENV == "development",
    )
