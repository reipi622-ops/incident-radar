"""
Pytest configuration and shared fixtures.
Uses an in-memory SQLite database — no real Postgres required.

Isolation strategy:
  - session-scoped engine: schema created once
  - function-scoped db: each test gets a connection wrapped in a SAVEPOINT
    so db.commit() inside API handlers only commits to the savepoint,
    and teardown rolls the whole thing back — no state leaks between tests
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.core.database import Base, get_db
from app.main import app


@pytest.fixture(scope="session")
def engine():
    e = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=e)
    yield e
    Base.metadata.drop_all(bind=e)


@pytest.fixture(scope="function")
def db(engine):
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    # Nested savepoint so API-level commit() stays within the transaction
    session.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
