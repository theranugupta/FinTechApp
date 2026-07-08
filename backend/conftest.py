"""
pytest fixtures. Each test gets a FRESH in-memory SQLite database so tests never
leak state into each other. We override the app's `get_session` dependency to use
the test database, and seed a known set of transactions.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import demo_architecture  # noqa: F401  (registers demo tables in SQLModel.metadata)
import main
from db import get_session
from models import Transaction


@pytest.fixture(name="session")
def session_fixture():
    # StaticPool + shared in-memory DB so every connection sees the same data.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                Transaction(transaction_id="TXN-10001", user_id="USER-501",
                            merchant_id="MER-900", amount=5000, currency="INR",
                            status="SUCCESS", payment_method="UPI-901234567890"),
                Transaction(transaction_id="TXN-FAILED", user_id="USER-501",
                            merchant_id="MER-900", amount=2000, currency="INR",
                            status="FAILED", payment_method="UPI"),
                Transaction(transaction_id="TXN-USD", user_id="USER-777",
                            merchant_id="MER-900", amount=100, currency="USD",
                            status="SUCCESS", payment_method="CARD"),
            ]
        )
        session.commit()
        yield session


@pytest.fixture(name="client")
def client_fixture(session):
    def _get_session_override():
        return session

    # Replace the real DB session with the test one, and skip startup seeding.
    main.app.dependency_overrides[get_session] = _get_session_override
    main.app.router.on_startup.clear()
    client = TestClient(main.app)
    yield client
    main.app.dependency_overrides.clear()


# Convenience header builders ------------------------------------------------------

def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def headers(token: str, idem_key: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Idempotency-Key": idem_key}
