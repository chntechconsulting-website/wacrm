import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings

# Create engine for MySQL
try:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False
    )
except Exception as e:
    print(f"Warning: Failed to connect to MySQL database URL {settings.DATABASE_URL}: {e}")
    # Fallback to sqlite for testing if MySQL URL fails initialization
    fallback_url = "sqlite:///./wa_crm_fallback.db"
    print(f"Using fallback database: {fallback_url}")
    engine = create_engine(fallback_url, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
