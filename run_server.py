#!/usr/bin/env python3
"""
Local Development Server Launcher
---------------------------------
Run this script to start the FastAPI server locally:
    python run_server.py
"""

import uvicorn
from app.config import settings

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Starting Bulk Certificate Generator API Server")
    print(f"📍 Host: {settings.HOST}:{settings.PORT}")
    print(f"📚 Interactive Swagger UI: http://localhost:{settings.PORT}/docs")
    print(f"📖 ReDoc Documentation: http://localhost:{settings.PORT}/redoc")
    print(f"💾 Storage Directory: {settings.STORAGE_DIR}")
    print(f"🗄️  Database: {settings.DATABASE_URL}")
    print("=" * 60)
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
