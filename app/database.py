"""
app/database.py
Konfigurasi SQLAlchemy — mendukung MySQL (PyMySQL) dan SQLite (untuk dev/testing)
"""

import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv

load_dotenv()

# ── Tentukan koneksi ──────────────────────────────────────────────────────────

# MySQL via PyMySQL
_HOST = os.getenv("DB_HOST", "database-1.c5esg26e2hc4.ap-southeast-2.rds.amazonaws.com")
_PORT = os.getenv("DB_PORT", "3306")
_NAME = os.getenv("DB_NAME", "harmoni")
_USER = os.getenv("DB_USER", "root")
_PASS = os.getenv("DB_PASSWORD", "HashtaM3yta!")
DATABASE_URL = f"mysql+pymysql://{_USER}:{_PASS}@{_HOST}:{_PORT}/{_NAME}?charset=utf8mb4"
_engine_kwargs = dict(
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=False,
)

engine = create_engine(DATABASE_URL, **_engine_kwargs)
#engine = create_engine("sqlite:///erp_dev.db", **_engine_kwargs)

class Base(DeclarativeBase):
    pass


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)



def get_db():
    """Context manager — gunakan: with get_db() as db: ..."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
