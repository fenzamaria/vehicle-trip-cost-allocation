"""
Database connection setup. This is the piece that actually connects
SQLAlchemy to our SQLite file, and gives us a `Base` class that all
our model classes will inherit from.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()  # reads .env into environment variables

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./allocation.db")

# echo=False keeps SQL query logs quiet; flip to True if you ever want
# to see the raw SQL SQLAlchemy is generating, useful for debugging.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    FastAPI will call this for every request that needs database access.
    It opens a session, hands it to the route, then always closes it
    afterward (even if an error happens) — the `finally` guarantees that.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
