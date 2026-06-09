"""
Shared pytest fixtures and test data for the ARIA test suite.

All test files in this directory get these fixtures automatically.
Each test runs in its own DB transaction that is rolled back on completion,
so tests are fully isolated and order-independent.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, get_db
from main import app
from models.user import User
from routes.auth import get_current_user

# ── In-memory test database ───────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Create all tables once for the test session, drop them at the end."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    """
    Yields a DB session bound to a transaction that rolls back after each test.
    This keeps tests fully isolated without needing to truncate tables.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db):
    """
    FastAPI TestClient with get_db overridden to use the test transaction.
    send_email is NOT patched here — patch it per-test where needed.
    """
    def override_get_db():
        try:
            yield db
        finally:
            pass

    # Tests run as an admin (no login flow) so existing assertions see all data.
    admin = User(id=1, name="Test Admin", email="admin@test", role="admin",
                 password_hash="x", is_active=True)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: admin
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Reusable lead payloads ────────────────────────────────────────────────────

BROKER_PAYLOAD = {
    "first_name": "Rajesh",
    "email": "rajesh@brokerhouse.in",
    "phone": "9876543210",
    "state": "Maharashtra",
    "company_name": "Mehta Brokers",
    "types_of_business": "broker",
    "are_you_open_to_adopting_a_new_technology_platform": "yes",
    "do_you_currently_use_any_software": "no",
    "would_you_be_willing_to_evaluate_a_new_tech_solution": "yes",
    "platform": "fb",
}

AGENT_PAYLOAD = {
    "first_name": "Priya",
    "email": "priya@agents.in",
    "phone": "9123456780",
    "state": "Karnataka",
    "types_of_business": "insurance_agent",
    "are_you_open_to_adopting_a_new_technology_platform": "no",
    "do_you_currently_use_any_software": "yes",
    "would_you_be_willing_to_evaluate_a_new_tech_solution": "no",
    "platform": "ig",
}

INVALID_PAYLOAD = {
    "first_name": "Bot",
    "email": "spam@test.com",
    "types_of_business": "invalid",
    "platform": "fb",
}
