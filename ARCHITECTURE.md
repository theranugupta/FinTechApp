# ARCHITECTURE.md — Money Movement Design (FinPay)

How a payment/refund flows through the system, the services involved, and the
reliability guarantees money movement needs. Each concept is mapped to **what this
repo actually implements** vs. **what a production-scale system would add** — so the
design is honest about scope.

---

## 1. Transfer flow

```
Sender App
      │
      ▼
Transfer API
      │
      ▼
Validation Service
      │
      ▼
Ledger Service
      │
 ┌────┴─────┐
 │          │
Debit      Credit
 │          │
 └────┬─────┘
      ▼
Notification
```

Step by step:

| Step | Responsibility | In this repo |
|---|---|---|
| **Sender App** | Initiates the transfer/refund with an idempotency key; disables double-submit | Next.js admin UI (`RefundModal.tsx` generates one key per intent) |
| **Transfer API** | AuthN/AuthZ, request validation, idempotency gate | FastAPI endpoint `POST /api/admin/transactions/{id}/refunds` (`main.py`) |
| **Validation Service** | Business-rule checks: eligibility, currency, amount bounds, merchant scope | `refund_logic.py` steps 2–6 |
| **Ledger Service** | The money movement itself, inside one atomic transaction | `refund_logic.py` step 7 (locked txn → `Refund` + `LedgerEntry`) |
| **Debit / Credit** | Two balanced legs of the same movement (double-entry) | Single `REFUND_REVERSAL` ledger entry today; double-entry below is the production design |
| **Notification** | Tell the user/merchant the outcome (async, non-blocking) | Not implemented — designed below (event-driven) |

---

## 2. Key components

| Service | Responsibility | Status in this repo |
|---|---|---|
| **Account service** | Owns account identity, KYC state, account lifecycle (open/frozen/closed). Answers "may this account transact?" | Stubbed: `auth.py` models users, permissions, merchant scope |
| **Balance service** | Authoritative available/pending balance per account; answers "is there enough money?" | Derived: remaining refundable = `amount − Σ refunds` computed inside the DB lock |
| **Ledger service** | Append-only record of every money movement; the accounting source of truth. Never updated, only appended | `LedgerEntry` table (`models.py`); append-only by convention |
| **Transaction service** | Orchestrates a transfer end-to-end: validate → reserve → post → confirm; owns state machine (INITIATED → PENDING → SETTLED/FAILED) | `refund_logic.create_refund()` is this orchestrator for refunds; refunds start `PENDING` |
| **Notification service** | Emails/SMS/webhooks on state changes; retries with backoff; never blocks the money path | Not implemented (design: consume events, see §3.7) |
| **Audit service** | Immutable who-did-what-when for every attempt, success or failure; compliance queries | `AuditLog` table — written on **every** attempt, in the same DB transaction |

Rule of thumb: **the ledger is the source of truth for money; balances are a cached
projection of the ledger; audit is the source of truth for actions.**

---

## 3. Reliability concepts (the money guarantees)

### 3.1 Atomic debit and credit
A transfer's debit and credit must commit **together or not at all** — never one leg.
- **Here:** the refund row, ledger entry, idempotency record, and audit log are all
  written in **one DB transaction** (`session.commit()` once, in `refund_logic.py`).
  A failure anywhere rolls back everything — no half-written money state.
- **Production:** same principle; both ledger legs (debit + credit) in one ACID
  transaction when accounts live in the same DB.

### 3.2 Distributed transactions (multiple systems involved)
When debit and credit live in **different** systems (e.g. our ledger + a bank/UPI rail),
a single ACID transaction is impossible. Options, in order of preference:
1. **Avoid distribution** — keep both legs in one DB whenever possible (what we do).
2. **Saga pattern** — sequence of local transactions with compensations:
   `reserve debit → request credit → confirm` ; on failure run the compensating step
   (`release reserve`). State machine persisted so a crash can resume.
3. **Outbox pattern** — write the DB change and the "notify other system" event in one
   local transaction; a relay delivers the event at-least-once.
4. Two-phase commit (2PC) is generally avoided: blocking, fragile coordinators.
- **Here:** single SQLite/Postgres DB → not needed; the refund's `PENDING → SUCCESS`
  status models the async settlement leg a saga would confirm.

### 3.3 Double-entry bookkeeping
Every movement is recorded as **two entries that sum to zero**: a debit on one account
and a credit on another. Money is never created or destroyed, only moved.

```
Refund of ₹1,000 for TXN-10001:
  DEBIT  merchant_settlement_account   -1000 INR   (money leaves merchant)
  CREDIT customer_refund_account       +1000 INR   (money returns to customer)
Invariant: SUM(all entries for transfer_id) == 0
```
- **Here (simplified):** one `REFUND_REVERSAL` entry records the movement; the original
  transaction is never mutated (a common AI-generated bug — see `CODE_REVIEW.md`).
- **Production:** two `LedgerEntry` rows per movement with account ids + direction, and a
  nightly job asserting the zero-sum invariant per transfer and per account.

### 3.4 Optimistic locking
Detect concurrent writes instead of holding locks: each row carries a `version`; an
update does `UPDATE ... WHERE id = ? AND version = ?` — if 0 rows match, someone else
won; re-read and retry (or fail).
- **Here:** we use **pessimistic** locking instead (`SELECT ... FOR UPDATE` on the
  transaction row) because refund contention is per-transaction and short-lived — the
  simplest correct choice. See `DESIGN_IDEMPOTENCY.md`.
- **When optimistic wins:** high-read/low-conflict data (account profile, limits config),
  or when holding a row lock across a slow external call is unacceptable.

### 3.5 Duplicate request prevention
Retries must never move money twice.
- **Here (implemented, tested):** mandatory `Idempotency-Key` header; store
  `key → (request_hash, response)`; same key + same payload → **replay** stored
  response; same key + different payload → **409**; unique PK on the key kills
  same-key races (the `IntegrityError` branch). UI reuses one key per refund intent,
  so timeout-retries and double-clicks collapse into one refund.
- **Production adds:** key TTL/expiry, and dedupe at the consumer side of every event
  stream (at-least-once delivery means consumers must be idempotent too).

### 3.6 Rollback / compensation
- **Rollback (implemented):** within the single DB transaction, any failure rolls back
  every write — refund, ledger, idempotency record, audit are all-or-nothing.
- **Compensation (design):** across systems you can't roll back someone else's commit;
  you execute a **compensating action** instead — e.g. if the credit leg fails after our
  debit committed, post a reversing ledger entry and mark the transfer `FAILED`.
  Compensations must themselves be idempotent and audited. This is the saga's "undo".

### 3.7 Event-driven architecture
Money state changes emit **events** (`refund.created`, `refund.settled`,
`refund.failed`); non-critical work (notifications, analytics, webhooks) subscribes
instead of sitting in the request path.
- **Why:** the money path stays fast and small; a notification outage can never block
  or fail a refund; consumers scale independently.
- **How (production):** the **outbox pattern** — insert the event row in the *same* DB
  transaction as the refund; a relay publishes to the broker (Kafka/SQS/…);
  consumers are idempotent (see 3.5) because delivery is at-least-once.
- **Here:** not implemented — deliberately. Per the anti-overengineering rule
  (`CLAUDE.md`: no new queues/brokers unless asked), a broker would be unjustified for
  this assessment's scope. The `AuditLog` + `LedgerEntry` rows written transactionally
  are exactly the rows an outbox relay would publish from, so the design slots in
  without reworking the money path.

---

## 4. What's real vs. designed — summary

| Guarantee | Status |
|---|---|
| Atomic writes (refund+ledger+idempotency+audit) | ✅ implemented & tested |
| Duplicate prevention (idempotency, replay, 409, race-safe) | ✅ implemented & tested |
| Over-refund prevention under concurrency (row lock + re-check) | ✅ implemented & tested |
| Audit on every attempt | ✅ implemented & tested |
| Ledger entry per successful refund | ✅ implemented & tested (single-entry) |
| Rollback within the transaction | ✅ implemented |
| Double-entry (two balanced legs) | 📐 designed (§3.3) |
| Saga / compensation across systems | 📐 designed (§3.2, §3.6) |
| Optimistic locking | 📐 designed; pessimistic chosen deliberately (§3.4) |
| Event-driven notifications (outbox) | 📐 designed (§3.7) |
| Separate Account/Balance/Notification services | 📐 designed (§2) |

The 📐 items are consciously **not** built into the money path: the assessment scope is
the refund module, and `CLAUDE.md` forbids speculative infrastructure. The design above
shows where each piece attaches when the system grows.

---

## 5. Demo data — every concept, live

Each 📐 concept is seeded as **real rows** in a sandbox (`backend/demo_architecture.py`,
separate tables — the refund money-path is untouched). Fetch it all:

```bash
curl -s http://localhost:8100/api/admin/architecture/demo \
  -H "Authorization: Bearer admin-token" | python3 -m json.tool
```

### The three demo transfers (one story per failure mode)

| Transfer | State | What it demonstrates |
|---|---|---|
| `TRF-1001` ₹5,000 | `SETTLED` | Happy path: balanced DEBIT/CREDIT legs, published events, EMAIL notification SENT |
| `TRF-1002` ₹1,000 | `PENDING` | Saga mid-flight: money reserved into `ACC-RAIL-UPI` suspense; `refund.settled` outbox event still **unpublished** (relay lag); SMS notification PENDING (retries=1) |
| `TRF-1003` ₹2,000 | `FAILED` | Compensation: rail rejected after our debit committed → two appended `COMPENSATION` legs reverse it (history never deleted); `refund.failed` + `refund.compensated` events; WEBHOOK notification FAILED (retries=3) |

### Concept → data mapping

| Concept | Demo data |
|---|---|
| Account service (lifecycle) | 4 accounts incl. `ACC-CUST-777` **FROZEN** |
| Balance service | `balance` column = projection of the ledger |
| Optimistic locking | `version` column (v3, v7, v2, v1) — writers `UPDATE ... WHERE version = <read>` and treat 0 rows as a lost race |
| Transaction service (state machine) | `SETTLED` / `PENDING` / `FAILED` transfers above |
| Double-entry bookkeeping | Every transfer has signed DEBIT/CREDIT legs; the endpoint computes the zero-sum check live: all three transfers `"balanced": true` — including the failed one *after* compensation |
| Duplicate prevention | `idempotency_key` UNIQUE on transfers (replaying `pay-abc-1` can only return `TRF-1001`); the full replay/409 behaviour is live on the real refund API |
| Rollback/compensation | `TRF-1003`'s two `entry_type=COMPENSATION` legs |
| Event-driven / outbox | 7 `DemoOutboxEvent` rows; one deliberately `published=false` to show the at-least-once relay in flight |
| Notification service | EMAIL SENT / SMS PENDING (retries=1) / WEBHOOK FAILED (retries=3) — failures never touch the money path |
| Audit service | Already live on the real refund path (`AuditLog` on every attempt) |

Covered by tests in `backend/test_architecture_demo.py` — most importantly
`test_double_entry_legs_sum_to_zero`, which asserts the zero-sum invariant for every
transfer including the compensated one.
