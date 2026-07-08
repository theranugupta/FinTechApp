"""
Database engine + session setup (SQLite via SQLModel).

We use SQLite because it needs zero setup and still gives us real transactions. The
concurrency model differs from Postgres (see DESIGN_IDEMPOTENCY.md), but the *code
pattern* — do all money checks and writes inside one transaction — is identical and
ports directly to Postgres with `SELECT ... FOR UPDATE`.
"""

from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine

# check_same_thread=False lets the FastAPI TestClient / dev server share the connection.
DATABASE_URL = "sqlite:///./finpay.db"
engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})


def init_db() -> None:
    """Create tables. Imported models must be loaded before this is called."""
    import models  # noqa: F401  (ensures model classes are registered)
    import demo_architecture  # noqa: F401  (architecture-demo sandbox tables)
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency that yields a DB session and closes it afterwards."""
    with Session(engine) as session:
        yield session
