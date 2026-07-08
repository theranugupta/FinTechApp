"""
Database models for the FinPay Admin Refund Module.

We use SQLModel = SQLAlchemy (the DB engine/ORM) + Pydantic (validation) in one class.
Each class below with `table=True` becomes a real database table.

MONEY NOTE: All amounts are stored as INTEGERS (never floats — floats lose precision
on money). We treat `amount` as a whole number in the transaction's currency unit,
matching the spec's example (`"amount": 5000`). This is documented as an assumption.
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    """Single source of 'now' so tests can reason about timestamps."""
    return datetime.utcnow()


class Transaction(SQLModel, table=True):
    """A payment a user made to a merchant. We only READ these; we never mutate
    the original transaction when refunding (a common bug — see the Task 7 review)."""

    transaction_id: str = Field(primary_key=True)  # e.g. "TXN-10001"
    user_id: str
    merchant_id: str                                # used for merchant-scope checks
    amount: int                                     # original paid amount (integer)
    currency: str                                   # only "INR" is supported
    status: str                                     # SUCCESS | FAILED | PENDING ...
    payment_method: str                             # e.g. "UPI" (masked before output)
    created_at: datetime = Field(default_factory=utcnow)


class Refund(SQLModel, table=True):
    """One refund against a transaction. Multiple partial refunds are allowed, so a
    transaction can have many Refund rows. The SUM of these must never exceed the
    transaction amount (over-refund rule)."""

    refund_id: str = Field(primary_key=True)        # e.g. "REF-70001"
    transaction_id: str = Field(foreign_key="transaction.transaction_id", index=True)
    amount: int
    currency: str
    status: str                                     # PENDING | SUCCESS | FAILED
    reason: Optional[str] = None
    idempotency_key: Optional[str] = None           # which request created it
    created_at: datetime = Field(default_factory=utcnow)


class IdempotencyRecord(SQLModel, table=True):
    """Stores the outcome of a refund request keyed by its Idempotency-Key.

    - `request_hash` is a fingerprint of the request body. Same key + same hash means
      a genuine retry → we replay the stored response. Same key + different hash means
      the client reused a key for a different request → we return 409 Conflict.
    - `response_json` + `status_code` let us replay the EXACT original response.
    """

    idempotency_key: str = Field(primary_key=True)  # the header value, e.g. "refund-abc-123"
    transaction_id: str = Field(index=True)
    request_hash: str                               # sha256 of the canonical request body
    status_code: int                                # HTTP status we returned originally
    response_json: str                              # the exact response body we returned
    created_at: datetime = Field(default_factory=utcnow)


class AuditLog(SQLModel, table=True):
    """Every refund ATTEMPT (success or failure) creates one of these. This is the
    audit trail — it must record who did what, to which transaction, and the outcome."""

    id: Optional[int] = Field(default=None, primary_key=True)
    actor_user_id: Optional[str] = None             # who attempted it (from the token)
    action: str = "REFUND_ATTEMPT"
    transaction_id: Optional[str] = None
    refund_id: Optional[str] = None
    outcome: str                                    # e.g. "SUCCESS", "REJECTED_OVER_REFUND"
    detail: Optional[str] = None                    # human-readable reason (no PII/secrets)
    created_at: datetime = Field(default_factory=utcnow)


class LedgerEntry(SQLModel, table=True):
    """A successful refund creates a reversal/ledger entry. This is the money movement
    record the finance/accounting side relies on."""

    id: Optional[int] = Field(default=None, primary_key=True)
    transaction_id: str = Field(index=True)
    refund_id: str = Field(index=True)
    entry_type: str = "REFUND_REVERSAL"
    amount: int                                     # positive amount reversed
    currency: str
    created_at: datetime = Field(default_factory=utcnow)
