"""
FastAPI application for the FinPay Admin Refund Module.

Endpoints:
  POST /api/admin/transactions/{transaction_id}/refunds  -> create/replay a refund
  GET  /api/admin/transactions/{transaction_id}          -> transaction details (masked)
  GET  /api/admin/transactions/{transaction_id}/refunds  -> refund history + remaining

Order of enforcement on the POST (fail closed, cheapest/safest checks first):
  authn (401) -> permission (403) -> [into logic] merchant scope, eligibility,
  currency, amount, over-refund, idempotency -> audit -> ledger -> response.
"""

from typing import List, Optional

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from sqlmodel import Session, select

import crypto_utils
import refund_logic
from auth import User, get_current_user
from db import get_session, init_db
from models import Refund, Transaction
from schemas import RefundRequest, RefundResponse, mask_payment_method

app = FastAPI(title="FinPay Admin Refund Module")

# Allow the Next.js dev server to call the API in local development.
# Any localhost/127.0.0.1 port + http OR https (TLS) is allowed via regex so the dev port
# and scheme can change freely. Do NOT use this wildcard in production.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/crypto/public-key")
def crypto_public_key():
    """Serve the server's RSA public key so the client can encrypt request bodies.
    Public by design — a public key is not a secret. See crypto_utils.py / ENCRYPTION.md."""
    return {"algorithm": "RSA-OAEP-256", "public_key": crypto_utils.public_key_pem()}


@app.get("/api/admin/stats/daily-transactions")
def daily_transactions(
    days: int = 14,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Aggregate transaction count + total amount per day for the last `days` days.
    Respects merchant scope: an admin only sees transactions for merchants in their scope."""
    from collections import defaultdict
    from datetime import datetime, timedelta

    days = max(1, min(days, 90))  # clamp to a sane range

    # Only aggregate transactions the caller is allowed to see (merchant scope).
    txns = session.exec(select(Transaction)).all()
    buckets = defaultdict(lambda: {"count": 0, "total_amount": 0})
    for t in txns:
        if not user.can_access_merchant(t.merchant_id):
            continue
        key = t.created_at.date().isoformat()
        buckets[key]["count"] += 1
        buckets[key]["total_amount"] += t.amount

    # Build a continuous series for the last `days` days (fill gaps with zeros).
    today = datetime.utcnow().date()
    series = []
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        series.append({
            "date": d,
            "count": buckets[d]["count"],
            "total_amount": buckets[d]["total_amount"],
        })
    return {"days": days, "series": series}


@app.get("/api/admin/architecture/demo")
def architecture_demo(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Demo data for every concept in ARCHITECTURE.md: accounts with optimistic-lock
    versions, the transfer state machine, double-entry legs (+ live zero-sum check),
    outbox events, and notifications. Sandbox data — separate from the refund path."""
    import demo_architecture
    demo_architecture.seed_demo(session)  # idempotent; makes the endpoint self-sufficient
    return demo_architecture.demo_snapshot(session)


@app.get("/api/admin/stats/refund-status")
def refund_status_breakdown(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Count refunds by status (PENDING/SUCCESS/FAILED) within the caller's merchant scope.
    Powers the refund-status doughnut chart."""
    from collections import defaultdict

    # Map transaction_id -> merchant_id so we can enforce scope on each refund.
    merchant_of = {t.transaction_id: t.merchant_id for t in session.exec(select(Transaction)).all()}
    counts = defaultdict(int)
    for r in session.exec(select(Refund)).all():
        merchant = merchant_of.get(r.transaction_id)
        if merchant is None or not user.can_access_merchant(merchant):
            continue
        counts[r.status] += 1
    return {"statuses": dict(counts)}


async def parse_refund_body(request: Request) -> RefundRequest:
    """Read the POST body and return a validated RefundRequest.

    Accepts EITHER a plain JSON body {amount, reason} OR an encrypted envelope
    {encryptedKey, iv, ciphertext}. This keeps the endpoint backward-compatible (and the
    test-suite, which sends plain JSON, unchanged) while supporting app-layer encryption.
    Validation still yields 422 exactly like the old `body: RefundRequest` did.
    """
    try:
        raw = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Request body must be JSON")

    if crypto_utils.looks_like_envelope(raw):
        try:
            raw = crypto_utils.decrypt_envelope(raw)
        except Exception:
            # Never leak crypto internals; a bad envelope is a client error.
            raise HTTPException(status_code=400, detail="Could not decrypt request body")

    try:
        return RefundRequest(**raw)
    except (ValidationError, TypeError) as e:
        # Mirror FastAPI's automatic 422 for invalid bodies.
        detail = e.errors() if isinstance(e, ValidationError) else str(e)
        raise HTTPException(status_code=422, detail=detail)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    _seed()
    # Seed the architecture-concepts sandbox (separate tables; see demo_architecture.py).
    from db import engine
    import demo_architecture
    with Session(engine) as session:
        demo_architecture.seed_demo(session)


def _seed() -> None:
    """Insert the spec's example transaction plus demo transactions spread over the last
    14 days (so the daily-transactions chart has real data to aggregate). Runs once."""
    from datetime import datetime, timedelta
    from db import engine

    with Session(engine) as session:
        if session.get(Transaction, "TXN-10001") is not None:
            return  # already seeded

        rows = [
            Transaction(transaction_id="TXN-10001", user_id="USER-501",
                        merchant_id="MER-900", amount=5000, currency="INR",
                        status="SUCCESS", payment_method="UPI"),
            Transaction(transaction_id="TXN-FAILED", user_id="USER-501",
                        merchant_id="MER-900", amount=2000, currency="INR",
                        status="FAILED", payment_method="UPI"),
            Transaction(transaction_id="TXN-USD", user_id="USER-777",
                        merchant_id="MER-900", amount=100, currency="USD",
                        status="SUCCESS", payment_method="CARD"),
        ]

        # Demo history for the chart: a deterministic, varied number of transactions per
        # day for MER-900 over the past 14 days (no randomness -> reproducible).
        today = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)
        for i in range(14):
            day = today - timedelta(days=i)
            count = 2 + (i * 3) % 5  # 2..6 transactions that day
            for j in range(count):
                amount = 1000 + ((i * 7 + j * 13) % 9) * 500  # 1000..5000
                rows.append(
                    Transaction(
                        transaction_id=f"TXN-D{i:02d}{j:02d}",
                        user_id="USER-900",
                        merchant_id="MER-900",
                        amount=amount,
                        currency="INR",
                        status="SUCCESS",
                        payment_method="UPI",
                        created_at=day,
                    )
                )
        session.add_all(rows)
        session.commit()

        # Seed a few demo refunds (against demo transactions, NOT TXN-10001) with varied
        # statuses so the refund-status doughnut has data on first load. These never touch
        # the interactive TXN-10001 flow.
        from models import Refund
        demo_refunds = []
        plan = [("SUCCESS", 6), ("PENDING", 3), ("FAILED", 2)]
        n = 0
        for status_val, qty in plan:
            for _ in range(qty):
                tx_id = f"TXN-D{(n % 14):02d}00"  # an existing demo transaction id
                demo_refunds.append(
                    Refund(
                        refund_id=f"REF-D{n:04d}",
                        transaction_id=tx_id,
                        amount=500,
                        currency="INR",
                        status=status_val,
                        reason="seed demo",
                    )
                )
                n += 1
        session.add_all(demo_refunds)
        session.commit()


def _masked_transaction(txn: Transaction) -> dict:
    """Transaction details with sensitive data masked. Never return raw PII."""
    return {
        "transaction_id": txn.transaction_id,
        "user_id": txn.user_id,
        "merchant_id": txn.merchant_id,
        "amount": txn.amount,
        "currency": txn.currency,
        "status": txn.status,
        "payment_method": mask_payment_method(txn.payment_method),
        "created_at": txn.created_at,
    }


def _refundable_remaining(session: Session, txn: Transaction) -> int:
    refunds = session.exec(
        select(Refund).where(
            Refund.transaction_id == txn.transaction_id,
            Refund.status != "FAILED",
        )
    ).all()
    return txn.amount - sum(r.amount for r in refunds)


@app.get("/api/admin/transactions/{transaction_id}")
def get_transaction(
    transaction_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    txn = session.get(Transaction, transaction_id)
    if txn is None or not user.can_access_merchant(txn.merchant_id):
        # Do not distinguish "not found" from "out of scope" — avoids leaking existence.
        raise HTTPException(status_code=404, detail="Transaction not found")
    data = _masked_transaction(txn)
    data["remaining_refundable"] = _refundable_remaining(session, txn)
    data["refund_allowed"] = (txn.status == "SUCCESS" and txn.currency == "INR"
                              and data["remaining_refundable"] > 0
                              and user.has_refund_permission())
    return data


@app.get("/api/admin/transactions/{transaction_id}/refunds")
def list_refunds(
    transaction_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    txn = session.get(Transaction, transaction_id)
    if txn is None or not user.can_access_merchant(txn.merchant_id):
        raise HTTPException(status_code=404, detail="Transaction not found")
    refunds = session.exec(
        select(Refund).where(Refund.transaction_id == transaction_id)
    ).all()
    return {
        "transaction_id": transaction_id,
        "remaining_refundable": _refundable_remaining(session, txn),
        "refunds": [
            {
                "refund_id": r.refund_id,
                "amount": r.amount,
                "currency": r.currency,
                "status": r.status,
                "reason": r.reason,
                "created_at": r.created_at,
            }
            for r in refunds
        ],
    }


@app.post(
    "/api/admin/transactions/{transaction_id}/refunds",
    response_model=RefundResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_refund_endpoint(
    transaction_id: str,
    response: Response,
    body: RefundRequest = Depends(parse_refund_body),  # plain JSON OR encrypted envelope
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(get_current_user),          # 401 if not authenticated
    session: Session = Depends(get_session),
):
    # Idempotency-Key is required on a money-mutating endpoint.
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required")

    # Authorization: must have refund permission (403). Merchant scope is checked in the
    # logic layer because it depends on the transaction's merchant.
    if not user.has_refund_permission():
        raise HTTPException(status_code=403, detail="Refund permission required")

    try:
        http_status, payload = refund_logic.create_refund(
            session,
            user=user,
            transaction_id=transaction_id,
            req=body,
            idempotency_key=idempotency_key,
        )
    except refund_logic.RefundError as e:
        # Business-rule rejection. Audit was already written inside the logic layer.
        raise HTTPException(status_code=e.status_code, detail=e.message)

    response.status_code = http_status  # 201 for new, or the replayed status for retries
    return payload
