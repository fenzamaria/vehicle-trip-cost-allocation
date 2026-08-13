"""
Shared Pytest fixtures. The `db` fixture gives every test a completely
fresh, isolated in-memory SQLite database, seeded with the same JSON
data in data/seed/ — so tests never touch the real allocation.db file,
and tests can't leak state into each other.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from ingest import ingest_into_session


@pytest.fixture
def db():
    # In-memory SQLite — exists only for the duration of this one test,
    # then disappears automatically.
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()

    ingest_into_session(session, "data/seed")

    yield session
    session.close()
