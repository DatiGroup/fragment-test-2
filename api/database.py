import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent / ".env")


def get_database_url() -> str:
    """
    Construct DATABASE_URL from individual parameters or use DATABASE_URL directly.

    Supports two modes:
    1. Individual parameters (preferred, matches k8s manifest):
       - DB_NAME, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD
    2. Direct DATABASE_URL (legacy/fallback)
    """
    # First check for individual parameters
    db_name = os.getenv("DB_NAME")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT", "5432")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")

    if all([db_name, db_host, db_user, db_password]):
        return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    # Fallback to DATABASE_URL for backward compatibility
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    raise RuntimeError(
        "Database configuration missing. Set either:\n"
        "  - Individual parameters: DB_NAME, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD\n"
        "  - Or: DATABASE_URL"
    )


DATABASE_URL = get_database_url()

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
