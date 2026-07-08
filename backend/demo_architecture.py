"""
Demo data for every concept in ARCHITECTURE.md.

These tables are a SANDBOX that makes the designed (📐) concepts tangible with real
rows — double-entry legs that sum to zero, a transfer state machine, an outbox, an
optimistic-lock version column, notifications with retries. They are deliberately
SEPARATE from the live refund money-path (models.py) so the assessment's core logic
stays untouched. Explicitly requested — not speculative infrastructure.

View it all at:  GET /api/admin/architecture/demo
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, Session, SQLModel, select


# ---------------------------------------------------------------------------------
# Tables (one per architecture concept)
# ---------------------------------------------------------------------------------

class DemoAccount(SQLModel, table=True):
    """Account service + Balance service + OPTIMISTIC LOCKING.
    `version` is the optimistic-lock column: writers do
    UPDATE ... SET version = version + 1 WHERE id = ? AND version = <read version>
    and treat 0 affected rows as a lost race."""

    account_id: str = Field(primary_key=True)
    owner: str                       # who owns it (user / merchant / rail)
    kind: str                        # CUSTOMER_WALLET | MERCHANT_SETTLEMENT | RAIL_SUSPENSE
    status: str = "ACTIVE"           # ACTIVE | FROZEN | CLOSED  (account lifecycle)
    balance: int = 0                 # projection of the ledger (Balance service)
    currency: str = "INR"
    version: int = 1                 # optimistic-lock version counter


class DemoTransfer(SQLModel, table=True):
    """Transaction service: the transfer state machine + duplicate prevention.
    `idempotency_key` is UNIQUE — retrying the same key can only replay this row."""

    transfer_id: str = Field(primary_key=True)
    idempotency_key: str = Field(unique=True, index=True)
    from_account: str
    to_account: str
    amount: int
    currency: str = "INR"
    # State machine: INITIATED -> PENDING -> SETTLED | FAILED (-> COMPENSATED)
    state: str
    failure_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DemoLedgerLeg(SQLModel, table=True):
    """Ledger service + DOUBLE-ENTRY BOOKKEEPING + compensation.
    Every transfer posts balanced legs; SUM(amount) per transfer_id must be 0.
    Compensation legs (entry_type=COMPENSATION) are how a cross-system failure is
    undone — append a reversing pair, never delete/update history."""

    id: Optional[int] = Field(default=None, primary_key=True)
    transfer_id: str = Field(index=True)
    account_id: str = Field(index=True)
    direction: str                   # DEBIT | CREDIT
    amount: int                      # signed: DEBIT negative, CREDIT positive
    entry_type: str = "TRANSFER"     # TRANSFER | COMPENSATION
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DemoOutboxEvent(SQLModel, table=True):
    """EVENT-DRIVEN ARCHITECTURE via the outbox pattern.
    The event row is written in the SAME DB transaction as the state change; a relay
    publishes unpublished rows to the broker at-least-once."""

    id: Optional[int] = Field(default=None, primary_key=True)
    event_type: str                  # e.g. transfer.settled / refund.failed
    aggregate_id: str                # the transfer it belongs to
    payload: str                     # JSON body the consumer receives
    published: bool = False          # relay flips this after successful publish
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DemoNotification(SQLModel, table=True):
    """Notification service: async consumer of outbox events. Retries with backoff;
    its failures NEVER touch the money path."""

    id: Optional[int] = Field(default=None, primary_key=True)
    transfer_id: str = Field(index=True)
    channel: str                     # EMAIL | SMS | WEBHOOK
    status: str                      # SENT | PENDING | FAILED
    retries: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------------
# Seed — one story per concept
# ---------------------------------------------------------------------------------

def seed_demo(session: Session) -> None:
    """Idempotent seed of the architecture sandbox."""
    if session.get(DemoAccount, "ACC-CUST-501") is not None:
        return  # already seeded

    # --- Accounts (Account + Balance service; note the optimistic-lock versions) ---
    session.add_all([
        DemoAccount(account_id="ACC-CUST-501", owner="USER-501",
                    kind="CUSTOMER_WALLET", balance=12000, version=3),
        DemoAccount(account_id="ACC-MER-900", owner="MER-900",
                    kind="MERCHANT_SETTLEMENT", balance=250000, version=7),
        DemoAccount(account_id="ACC-RAIL-UPI", owner="UPI-RAIL",
                    kind="RAIL_SUSPENSE", balance=0, version=2),
        DemoAccount(account_id="ACC-CUST-777", owner="USER-777",
                    kind="CUSTOMER_WALLET", status="FROZEN",  # lifecycle example
                    balance=500, version=1),
    ])

    # --- Transfer 1: the happy path — SETTLED payment, balanced double-entry -------
    session.add(DemoTransfer(
        transfer_id="TRF-1001", idempotency_key="pay-abc-1",
        from_account="ACC-CUST-501", to_account="ACC-MER-900",
        amount=5000, state="SETTLED",
    ))
    session.add_all([
        DemoLedgerLeg(transfer_id="TRF-1001", account_id="ACC-CUST-501",
                      direction="DEBIT", amount=-5000),
        DemoLedgerLeg(transfer_id="TRF-1001", account_id="ACC-MER-900",
                      direction="CREDIT", amount=5000),
    ])
    session.add_all([
        DemoOutboxEvent(event_type="transfer.created", aggregate_id="TRF-1001",
                        payload='{"transfer_id": "TRF-1001", "amount": 5000}',
                        published=True),
        DemoOutboxEvent(event_type="transfer.settled", aggregate_id="TRF-1001",
                        payload='{"transfer_id": "TRF-1001", "state": "SETTLED"}',
                        published=True),
    ])
    session.add(DemoNotification(transfer_id="TRF-1001", channel="EMAIL",
                                 status="SENT", retries=0))

    # --- Transfer 2: a saga mid-flight — PENDING refund via the rail ---------------
    # Money reserved out of the merchant account into rail suspense; the customer
    # credit happens when the rail confirms (saga step 2). Outbox row not yet published.
    session.add(DemoTransfer(
        transfer_id="TRF-1002", idempotency_key="refund-xyz-2",
        from_account="ACC-MER-900", to_account="ACC-CUST-501",
        amount=1000, state="PENDING",
    ))
    session.add_all([
        DemoLedgerLeg(transfer_id="TRF-1002", account_id="ACC-MER-900",
                      direction="DEBIT", amount=-1000),
        DemoLedgerLeg(transfer_id="TRF-1002", account_id="ACC-RAIL-UPI",
                      direction="CREDIT", amount=1000),
    ])
    session.add_all([
        DemoOutboxEvent(event_type="refund.created", aggregate_id="TRF-1002",
                        payload='{"transfer_id": "TRF-1002", "amount": 1000}',
                        published=True),
        DemoOutboxEvent(event_type="refund.settled", aggregate_id="TRF-1002",
                        payload='{"transfer_id": "TRF-1002", "state": "PENDING"}',
                        published=False),  # <- relay hasn't delivered this yet
    ])
    session.add(DemoNotification(transfer_id="TRF-1002", channel="SMS",
                                 status="PENDING", retries=1))

    # --- Transfer 3: FAILED + COMPENSATED — the saga's undo ------------------------
    # The rail rejected the credit AFTER our debit committed. We cannot roll back a
    # committed transaction, so we append reversing COMPENSATION legs instead.
    session.add(DemoTransfer(
        transfer_id="TRF-1003", idempotency_key="refund-bad-3",
        from_account="ACC-MER-900", to_account="ACC-CUST-777",
        amount=2000, state="FAILED", failure_reason="Rail rejected: account frozen",
    ))
    session.add_all([
        # original legs
        DemoLedgerLeg(transfer_id="TRF-1003", account_id="ACC-MER-900",
                      direction="DEBIT", amount=-2000),
        DemoLedgerLeg(transfer_id="TRF-1003", account_id="ACC-RAIL-UPI",
                      direction="CREDIT", amount=2000),
        # compensation legs (append-only undo; also sums to zero)
        DemoLedgerLeg(transfer_id="TRF-1003", account_id="ACC-RAIL-UPI",
                      direction="DEBIT", amount=-2000, entry_type="COMPENSATION"),
        DemoLedgerLeg(transfer_id="TRF-1003", account_id="ACC-MER-900",
                      direction="CREDIT", amount=2000, entry_type="COMPENSATION"),
    ])
    session.add_all([
        DemoOutboxEvent(event_type="refund.created", aggregate_id="TRF-1003",
                        payload='{"transfer_id": "TRF-1003", "amount": 2000}',
                        published=True),
        DemoOutboxEvent(event_type="refund.failed", aggregate_id="TRF-1003",
                        payload='{"transfer_id": "TRF-1003", "reason": "account frozen"}',
                        published=True),
        DemoOutboxEvent(event_type="refund.compensated", aggregate_id="TRF-1003",
                        payload='{"transfer_id": "TRF-1003", "state": "COMPENSATED"}',
                        published=True),
    ])
    session.add(DemoNotification(transfer_id="TRF-1003", channel="WEBHOOK",
                                 status="FAILED", retries=3))

    session.commit()


# ---------------------------------------------------------------------------------
# Read model for the demo endpoint
# ---------------------------------------------------------------------------------

def demo_snapshot(session: Session) -> dict:
    """Everything grouped by concept, ready to render. Also computes the double-entry
    zero-sum check live, so the invariant is demonstrated, not just asserted."""
    accounts = session.exec(select(DemoAccount)).all()
    transfers = session.exec(select(DemoTransfer)).all()
    legs = session.exec(select(DemoLedgerLeg)).all()
    events = session.exec(select(DemoOutboxEvent)).all()
    notifications = session.exec(select(DemoNotification)).all()

    zero_sum = {}
    for leg in legs:
        zero_sum[leg.transfer_id] = zero_sum.get(leg.transfer_id, 0) + leg.amount

    return {
        "accounts_and_optimistic_locking": [a.dict() for a in accounts],
        "transfer_state_machine": [t.dict() for t in transfers],
        "double_entry_ledger_legs": [l.dict() for l in legs],
        "double_entry_zero_sum_check": {
            tid: {"sum": total, "balanced": total == 0} for tid, total in zero_sum.items()
        },
        "outbox_events": [e.dict() for e in events],
        "notifications": [n.dict() for n in notifications],
        "duplicate_prevention_note": (
            "idempotency_key is UNIQUE on transfers: replaying 'pay-abc-1' can only "
            "return TRF-1001, never create a second transfer. The live refund API "
            "implements the full replay/409 behaviour (see DESIGN_IDEMPOTENCY.md)."
        ),
    }
