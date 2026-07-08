"""
Test suite for the refund module (Task 8).

Each test maps to a row in the assessment's coverage table. Tests are named so a
reviewer can match them to the requirement at a glance.

Tokens (from auth.py):
  admin-token          -> ADMIN-1, refund permission, scoped to MER-900
  superadmin-token     -> ADMIN-0, refund permission, scope "*"
  support-noperm-token -> SUPPORT-2, NO refund permission, scoped to MER-900
  other-merchant-token -> ADMIN-3, refund permission, scoped to MER-111 (not MER-900)
"""

from sqlmodel import select

from conftest import auth, headers
from models import AuditLog, LedgerEntry

URL = "/api/admin/transactions/TXN-10001/refunds"


# --- Authentication ---------------------------------------------------------------

def test_unauthenticated_cannot_refund(client):
    r = client.post(URL, json={"amount": 100, "reason": "x"},
                    headers={"Idempotency-Key": "k1"})
    assert r.status_code == 401


def test_invalid_token_rejected(client):
    r = client.post(URL, json={"amount": 100, "reason": "x"},
                    headers=headers("garbage-token", "k1"))
    assert r.status_code == 401


# --- Authorization ----------------------------------------------------------------

def test_user_without_refund_permission_cannot_refund(client):
    r = client.post(URL, json={"amount": 100, "reason": "x"},
                    headers=headers("support-noperm-token", "k1"))
    assert r.status_code == 403


# --- Merchant scope ---------------------------------------------------------------

def test_admin_cannot_refund_out_of_scope_merchant(client):
    # ADMIN-3 is scoped to MER-111; TXN-10001 belongs to MER-900.
    r = client.post(URL, json={"amount": 100, "reason": "x"},
                    headers=headers("other-merchant-token", "k1"))
    assert r.status_code == 403


# --- Status / eligibility ---------------------------------------------------------

def test_failed_transaction_cannot_be_refunded(client):
    r = client.post("/api/admin/transactions/TXN-FAILED/refunds",
                    json={"amount": 100, "reason": "x"},
                    headers=headers("admin-token", "k1"))
    assert r.status_code == 409


def test_non_inr_currency_rejected(client):
    r = client.post("/api/admin/transactions/TXN-USD/refunds",
                    json={"amount": 50, "reason": "x"},
                    headers=headers("superadmin-token", "k1"))
    assert r.status_code == 422


def test_unknown_transaction_returns_404(client):
    r = client.post("/api/admin/transactions/TXN-NOPE/refunds",
                    json={"amount": 50, "reason": "x"},
                    headers=headers("superadmin-token", "k1"))
    assert r.status_code == 404


# --- Amount validation ------------------------------------------------------------

def test_zero_refund_rejected(client):
    r = client.post(URL, json={"amount": 0, "reason": "x"},
                    headers=headers("admin-token", "k1"))
    assert r.status_code == 422  # blocked by Pydantic gt=0


def test_negative_refund_rejected(client):
    r = client.post(URL, json={"amount": -100, "reason": "x"},
                    headers=headers("admin-token", "k1"))
    assert r.status_code == 422


def test_refund_greater_than_original_rejected(client):
    r = client.post(URL, json={"amount": 6000, "reason": "x"},
                    headers=headers("admin-token", "k1"))
    assert r.status_code == 422


# --- Partial refunds + over-refund ------------------------------------------------

def test_multiple_partial_refunds_allowed(client):
    r1 = client.post(URL, json={"amount": 2000, "reason": "part 1"},
                     headers=headers("admin-token", "k-a"))
    r2 = client.post(URL, json={"amount": 1500, "reason": "part 2"},
                     headers=headers("admin-token", "k-b"))
    assert r1.status_code == 201
    assert r2.status_code == 201
    # remaining should now be 5000 - 3500 = 1500
    hist = client.get(URL, headers=auth("admin-token")).json()
    assert hist["remaining_refundable"] == 1500
    assert len(hist["refunds"]) == 2


def test_over_refund_across_multiple_refunds_rejected(client):
    r1 = client.post(URL, json={"amount": 4000, "reason": "part 1"},
                     headers=headers("admin-token", "k-a"))
    assert r1.status_code == 201
    # Only 1000 remaining; asking for 2000 must be rejected.
    r2 = client.post(URL, json={"amount": 2000, "reason": "part 2"},
                     headers=headers("admin-token", "k-b"))
    assert r2.status_code == 422


def test_full_refund_allowed_then_further_refund_blocked(client):
    r1 = client.post(URL, json={"amount": 5000, "reason": "full"},
                     headers=headers("admin-token", "k-a"))
    assert r1.status_code == 201
    r2 = client.post(URL, json={"amount": 1, "reason": "extra"},
                     headers=headers("admin-token", "k-b"))
    assert r2.status_code == 422


# --- Idempotency ------------------------------------------------------------------

def test_same_key_same_payload_returns_same_response(client):
    body = {"amount": 1000, "reason": "same"}
    r1 = client.post(URL, json=body, headers=headers("admin-token", "idem-1"))
    r2 = client.post(URL, json=body, headers=headers("admin-token", "idem-1"))
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["refund_id"] == r2.json()["refund_id"]  # SAME refund, not a new one
    # And only ONE refund actually exists.
    hist = client.get(URL, headers=auth("admin-token")).json()
    assert len(hist["refunds"]) == 1
    assert hist["remaining_refundable"] == 4000


def test_same_key_different_payload_returns_409(client):
    r1 = client.post(URL, json={"amount": 1000, "reason": "a"},
                     headers=headers("admin-token", "idem-2"))
    r2 = client.post(URL, json={"amount": 2000, "reason": "b"},
                     headers=headers("admin-token", "idem-2"))
    assert r1.status_code == 201
    assert r2.status_code == 409


# --- Concurrency (functional: sequential proxy for the race) ----------------------

def test_two_refunds_cannot_over_refund(client):
    # Simulates two admins each asking for 3000 when only 5000 is refundable.
    # The second must fail because the first consumed 3000 (remaining 2000).
    r1 = client.post(URL, json={"amount": 3000, "reason": "admin A"},
                     headers=headers("admin-token", "conc-a"))
    r2 = client.post(URL, json={"amount": 3000, "reason": "admin B"},
                     headers=headers("admin-token", "conc-b"))
    assert r1.status_code == 201
    assert r2.status_code == 422
    hist = client.get(URL, headers=auth("admin-token")).json()
    assert hist["remaining_refundable"] == 2000  # never went negative


# --- Audit + ledger ---------------------------------------------------------------

def test_successful_refund_creates_audit_and_ledger(client, session):
    r = client.post(URL, json={"amount": 1000, "reason": "audit check"},
                    headers=headers("admin-token", "aud-1"))
    assert r.status_code == 201
    refund_id = r.json()["refund_id"]

    audits = session.exec(select(AuditLog).where(AuditLog.refund_id == refund_id)).all()
    assert any(a.outcome == "SUCCESS" for a in audits)

    ledgers = session.exec(select(LedgerEntry).where(LedgerEntry.refund_id == refund_id)).all()
    assert len(ledgers) == 1
    assert ledgers[0].amount == 1000
    assert ledgers[0].entry_type == "REFUND_REVERSAL"


def test_rejected_refund_still_creates_audit(client, session):
    # An over-limit refund is rejected but must still be audited.
    client.post(URL, json={"amount": 99999, "reason": "too big"},
                headers=headers("admin-token", "aud-2"))
    audits = session.exec(
        select(AuditLog).where(AuditLog.outcome == "REJECTED_EXCEEDS_ORIGINAL")
    ).all()
    assert len(audits) >= 1


# --- Data masking -----------------------------------------------------------------

def test_transaction_details_mask_payment_method(client):
    # TXN-10001 has payment_method "UPI-901234567890" in the test seed.
    r = client.get("/api/admin/transactions/TXN-10001", headers=auth("admin-token"))
    assert r.status_code == 200
    masked = r.json()["payment_method"]
    assert "901234567890" not in masked      # raw value not leaked
    assert masked.endswith("7890")           # only a safe suffix remains
    assert "****" in masked
