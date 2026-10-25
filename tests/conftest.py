"""Test configuration, fixtures, and isolated database setup."""

import os
import shutil
import tempfile
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from app.database import Base, get_db
from app.main import app


@pytest.fixture(scope="session")
def test_temp_dir() -> Generator[str, None, None]:
    """Create and tear down a temporary directory for test database storage."""
    temp_dir = tempfile.mkdtemp(prefix="shortener_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="session")
def test_engine(test_temp_dir: str):
    """Engine configured with temporary file SQLite, WAL mode, and busy timeout."""
    db_path = os.path.join(test_temp_dir, "test.db")
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
        pool_pre_ping=True,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


@pytest.fixture(scope="session")
def session_factory(test_engine):
    """Sessionmaker bound to test engine."""
    return sessionmaker(
        bind=test_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )


@pytest.fixture(autouse=True)
def setup_database(test_engine) -> Generator[None, None, None]:
    """Create fresh tables before each test and drop them after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session(session_factory) -> Generator[Session, None, None]:
    """Provide a transactional SQLAlchemy session for test inspections and seeding."""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(session_factory, db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with dependency override and redirect following disabled."""
    def override_get_db() -> Generator[Session, None, None]:
        db = session_factory()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app=app, base_url="http://testserver", follow_redirects=False) as test_client:
        yield test_client

    app.dependency_overrides.clear()
