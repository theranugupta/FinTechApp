"""
Request/response shapes (Pydantic models) and data-masking helpers.

Pydantic gives us FREE, declarative request validation: if the client sends a missing
or wrong-typed field, FastAPI returns 422 before our code even runs. We still enforce
the *business* amount rules (>0, <= original, over-refund) in the logic layer, because
"amount > 0" is a business rule, not just a type check — and the backend is authoritative.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class RefundRequest(BaseModel):
    """Body of POST .../refunds. `gt=0` rejects zero/negative at the edge (422),
    but the logic layer re-checks bounds too — never trust the edge alone."""

    amount: int = Field(gt=0, description="Refund amount, integer, must be > 0")
    reason: str = Field(min_length=1, max_length=500)


class RefundResponse(BaseModel):
    """Successful refund response, matching the spec exactly."""

    refund_id: str
    transaction_id: str
    amount: int
    currency: str
    status: str
    created_at: datetime


def mask_payment_method(method: str) -> str:
    """Mask sensitive payment detail before it leaves the backend.

    We only ever store a coarse method label here (e.g. "UPI"), but if it ever carried
    an identifier like a VPA or card, this keeps only a safe suffix: 'UPI-****9012'.
    Rule: never return raw payment identifiers or PII to the client.
    """
    if not method:
        return method
    if len(method) <= 4:
        return method  # nothing sensitive to hide (e.g. just "UPI")
    return f"{method[:3]}-****{method[-4:]}"
