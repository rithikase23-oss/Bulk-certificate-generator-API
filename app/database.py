"""
Database Setup & Session Management
-----------------------------------
Beginner Note:
SQLAlchemy is an Object Relational Mapper (ORM). It allows us to interact with
relational databases (SQLite, PostgreSQL, MySQL) using Python classes and objects
instead of writing raw SQL queries.

- Engine: The core connection pool and dialect handler.
- SessionLocal: Factory for creating isolated database transactions.
- Base: The base class that our models inherit from.
- get_db(): A FastAPI dependency that gives each HTTP request its own clean DB session
  and automatically closes it when the request finishes.
"""

from typing import Generator
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import settings
from app.logger import logger

# Configure connect arguments based on database engine
# SQLite requires check_same_thread=False when used across multiple FastAPI worker threads
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

# Create the SQLAlchemy Engine
engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,
    future=True,
)

# Session factory bound to the engine
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
)

# Declarative base model class
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session to API route handlers.
    Ensures the session is cleanly closed even if an unhandled exception occurs.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Creates all database tables and ensures safe initial schema migration.
    Inspects existing tables and non-destructively adds missing columns if upgrading.
    """
    Base.metadata.create_all(bind=engine)

    # Safe Schema Evolution Strategy:
    # If tables already existed prior to model upgrades, inspect and migrate columns
    try:
        inspector = inspect(engine)
        if "certificates" in inspector.get_table_names():
            columns = [c["name"] for c in inspector.get_columns("certificates")]
            with engine.begin() as conn:
                if "updated_at" not in columns:
                    logger.info("Migrating schema: Adding missing 'updated_at' column to certificates table")
                    conn.execute(text("ALTER TABLE certificates ADD COLUMN updated_at DATETIME"))
    except Exception as e:
        logger.warning(f"Schema inspection warning (non-fatal): {str(e)}")
