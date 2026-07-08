"""
The heart of the refund module. ALL money rules are enforced here, on the backend.

Design goals:
- One place for the business rules (easy to review, easy to test).
- Every refund attempt is transactional and audited.
- Idempotency and over-refund are impossible to bypass, even under concurrent requests.

Flow of create_refund():
  1. Idempotency pre-check (replay or 409 on key reuse).
  2. Load transaction (404).
  3. Merchant-scope check (403).
  4. Eligibility: status must be SUCCESS (409).
  5. Currency must be INR (422).
  6. Single-refund limit: amount <= original (422).
  7. Inside a locked transaction: sum existing refunds, block over-refund (422),
     create the Refund + LedgerEntry + IdempotencyRecord, commit.
  8. Always write an AuditLog (success OR failure).
"""

# Makes all type hints lazy strings, so `tuple[int, dict]` works on Python 3.8.
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from models import AuditLog, IdempotencyRecord, LedgerEntry, Refund, Transaction
from schemas import RefundRequest, RefundResponse


class RefundError(Exception):
    """Raised for any business-rule failure. Carries the HTTP status + a safe message.
    The endpoint turns this into a JSON error response and an audit log."""

    def __init__(self, status_code: int, message: str, outcome: str):
        self.status_code = status_code
        self.message = message
        self.outcome = outcome  # short machine label for the audit log
        super().__init__(message)


def _request_hash(req: RefundRequest) -> str:
    """Stable fingerprint of the request body. Same body → same hash. Used to tell a
    genuine retry (same key + same hash) from key reuse (same key + different hash)."""
    canonical = json.dumps({"amount": req.amount, "reason": req.reason}, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _new_refund_id() -> str:
    """Unique refund id. We use a uuid suffix so ids never collide under concurrency.
    (Format mirrors the spec's 'REF-...'.)"""
    return "REF-" + uuid.uuid4().hex[:10].upper()


def _write_audit(
    session: Session,
    *,
    user_id: Optional[str],
    transaction_id: Optional[str],
    refund_id: Optional[str],
    outcome: str,
    detail: str,
) -> None:
    """Write an audit row. Called for BOTH success and failure. Never logs PII/secrets —
    only ids, amounts, and a short reason."""
    session.add(
        AuditLog(
            actor_user_id=user_id,
            transaction_id=transaction_id,
            refund_id=refund_id,
            outcome=outcome,
            detail=detail,
        )
    )


def create_refund(
    session: Session,
    *,
    user,                       # auth.User (has_refund_permission / can_access_merchant)
    transaction_id: str,
    req: RefundRequest,
    idempotency_key: str,
) -> tuple[int, dict]:
    """Create a refund (or replay an idempotent one). Returns (http_status, body_dict).

    Raising RefundError signals a rejection; the endpoint audits it and returns the error.
    A successful path audits + returns the response and stores the idempotency record.
    """
    req_hash = _request_hash(req)

    # --- 1. IDEMPOTENCY PRE-CHECK ------------------------------------------------
    # If we've already handled this key, either replay (same payload) or 409 (different).
    existing = session.get(IdempotencyRecord, idempotency_key)
    if existing is not None:
        if existing.request_hash == req_hash:
            # Genuine retry → replay the EXACT original response. No second refund.
            return existing.status_code, json.loads(existing.response_json)
        # Same key, different body → the client misused the key.
        _write_audit(
            session, user_id=user.user_id, transaction_id=transaction_id,
            refund_id=None, outcome="REJECTED_IDEMPOTENCY_CONFLICT",
            detail="Idempotency-Key reused with a different payload",
        )
        session.commit()
        raise RefundError(409, "Idempotency-Key reused with a different payload",
                          "REJECTED_IDEMPOTENCY_CONFLICT")

    # --- 2. LOAD TRANSACTION -----------------------------------------------------
    txn = session.get(Transaction, transaction_id)
    if txn is None:
        _write_audit(session, user_id=user.user_id, transaction_id=transaction_id,
                     refund_id=None, outcome="REJECTED_NOT_FOUND",
                     detail="Transaction not found")
        session.commit()
        raise RefundError(404, "Transaction not found", "REJECTED_NOT_FOUND")

    # --- 3. MERCHANT SCOPE -------------------------------------------------------
    # Authn/permission are checked in the endpoint (before we get here). Scope depends
    # on the transaction's merchant, so it is checked here. Do NOT leak existence: an
    # out-of-scope admin gets 403, same as if they lacked permission.
    if not user.can_access_merchant(txn.merchant_id):
        _write_audit(session, user_id=user.user_id, transaction_id=transaction_id,
                     refund_id=None, outcome="REJECTED_MERCHANT_SCOPE",
                     detail=f"User not scoped to merchant {txn.merchant_id}")
        session.commit()
        raise RefundError(403, "Not authorized for this merchant", "REJECTED_MERCHANT_SCOPE")

    # --- 4. ELIGIBILITY: only SUCCESS transactions can be refunded ---------------
    if txn.status != "SUCCESS":
        _write_audit(session, user_id=user.user_id, transaction_id=transaction_id,
                     refund_id=None, outcome="REJECTED_NOT_ELIGIBLE",
                     detail=f"Transaction status is {txn.status}")
        session.commit()
        raise RefundError(409, "Only SUCCESS transactions can be refunded",
                          "REJECTED_NOT_ELIGIBLE")

    # --- 5. CURRENCY: only INR ---------------------------------------------------
    if txn.currency != "INR":
        _write_audit(session, user_id=user.user_id, transaction_id=transaction_id,
                     refund_id=None, outcome="REJECTED_CURRENCY",
                     detail=f"Unsupported currency {txn.currency}")
        session.commit()
        raise RefundError(422, "Only INR is supported", "REJECTED_CURRENCY")

    # --- 6. SINGLE-REFUND LIMIT: amount cannot exceed the original ---------------
    # (amount > 0 is already guaranteed by the Pydantic schema, but we re-assert here
    #  because the backend must not trust the edge layer.)
    if req.amount <= 0:
        raise RefundError(422, "Refund amount must be greater than 0", "REJECTED_AMOUNT")
    if req.amount > txn.amount:
        _write_audit(session, user_id=user.user_id, transaction_id=transaction_id,
                     refund_id=None, outcome="REJECTED_EXCEEDS_ORIGINAL",
                     detail=f"amount {req.amount} > original {txn.amount}")
        session.commit()
        raise RefundError(422, "Refund amount cannot exceed the original transaction amount",
                          "REJECTED_EXCEEDS_ORIGINAL")

    # --- 7. OVER-REFUND CHECK + WRITES, ALL INSIDE ONE TRANSACTION ---------------
    # Lock the transaction row so two concurrent refunds cannot both read a stale total.
    # On Postgres this is a real row lock. On SQLite the enclosing write transaction
    # serializes writers, giving the same guarantee (see DESIGN_IDEMPOTENCY.md).
    locked_txn = session.exec(
        select(Transaction)
        .where(Transaction.transaction_id == transaction_id)
        .with_for_update()
    ).one()

    # Sum only refunds that consumed money (PENDING + SUCCESS both reserve the amount).
    prior_refunds = session.exec(
        select(Refund).where(
            Refund.transaction_id == transaction_id,
            Refund.status != "FAILED",
        )
    ).all()
    already_refunded = sum(r.amount for r in prior_refunds)
    remaining = locked_txn.amount - already_refunded

    if req.amount > remaining:
        _write_audit(session, user_id=user.user_id, transaction_id=transaction_id,
                     refund_id=None, outcome="REJECTED_OVER_REFUND",
                     detail=f"amount {req.amount} > remaining {remaining}")
        session.commit()
        raise RefundError(
            422,
            f"Total refunded amount cannot exceed original. Remaining refundable: {remaining}",
            "REJECTED_OVER_REFUND",
        )

    # All checks passed → create the refund, ledger entry, idempotency record, audit.
    refund = Refund(
        refund_id=_new_refund_id(),
        transaction_id=transaction_id,
        amount=req.amount,
        currency=locked_txn.currency,
        status="PENDING",                # created as PENDING per the spec's example response
        reason=req.reason,
        idempotency_key=idempotency_key,
    )
    session.add(refund)

    session.add(
        LedgerEntry(
            transaction_id=transaction_id,
            refund_id=refund.refund_id,
            entry_type="REFUND_REVERSAL",
            amount=req.amount,
            currency=locked_txn.currency,
        )
    )

    response = RefundResponse(
        refund_id=refund.refund_id,
        transaction_id=refund.transaction_id,
        amount=refund.amount,
        currency=refund.currency,
        status=refund.status,
        created_at=refund.created_at,
    )
    body = json.loads(response.model_dump_json())  # JSON-safe dict (datetime -> string)

    # Persist the idempotency record so a retry replays this exact response.
    session.add(
        IdempotencyRecord(
            idempotency_key=idempotency_key,
            transaction_id=transaction_id,
            request_hash=req_hash,
            status_code=201,
            response_json=json.dumps(body),
        )
    )

    _write_audit(session, user_id=user.user_id, transaction_id=transaction_id,
                 refund_id=refund.refund_id, outcome="SUCCESS",
                 detail=f"Refund {refund.amount} {refund.currency} created")

    try:
        session.commit()
    except IntegrityError:
        # Two concurrent requests raced with the SAME idempotency key. The unique PK on
        # IdempotencyRecord rejected the loser. Roll back and replay the winner's response.
        session.rollback()
        winner = session.get(IdempotencyRecord, idempotency_key)
        if winner is not None and winner.request_hash == req_hash:
            return winner.status_code, json.loads(winner.response_json)
        raise RefundError(409, "Concurrent request with the same Idempotency-Key",
                          "REJECTED_IDEMPOTENCY_RACE")

    return 201, body
