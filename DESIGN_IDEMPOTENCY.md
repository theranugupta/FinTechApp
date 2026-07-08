# Task 4 — Idempotency & Concurrency Design

How the FinPay refund module prevents **duplicate** refunds (same request sent twice)
and **excessive** refunds (concurrent requests that together exceed the balance).

The two problems are different and need two different mechanisms:

| Problem | Cause | Mechanism |
|---|---|---|
| Duplicate refund | Client retries the *same* request (timeout, double-click) | **Idempotency-Key** |
| Excessive refund | *Different* requests race on the same balance | **DB transaction + row lock + re-check total** |

---

## Scenario A — ₹5,000 refund, UI times out and retries

> Support initiated a ₹5,000 refund. The admin UI timed out and retried. The system
> must not create two refunds.

Both requests carry the **same `Idempotency-Key`** (the frontend generates ONE key per
refund intent and reuses it on retry — see `RefundModal.tsx`).

1. Request 1 arrives, no record exists for the key → we process it, create the refund,
   and store an `IdempotencyRecord { key, request_hash, status_code, response_json }`.
2. Request 2 (the retry) arrives with the same key. We find the stored record.
   Its `request_hash` matches (same body) → we **replay the stored response**. No second
   refund is created.

Result: exactly one ₹5,000 refund, and the client gets the same `refund_id` both times.
(Verified by `test_same_key_same_payload_returns_same_response`.)

---

## Scenario B — two admins each submit ₹3,000; only ₹5,000 refundable

> Two admins submit ₹3,000 refunds at the same time. Total refunds must not exceed ₹5,000.

These are **different** requests (different keys), so idempotency does not help — this is a
race on the shared balance. We serialize them with a database transaction + row lock:

1. Each request opens a DB transaction and takes a **row lock** on the transaction row
   (`SELECT ... FOR UPDATE`). Only one request holds the lock at a time.
2. Inside the lock, it **re-computes** the total already refunded from the `refund` table
   and derives `remaining`. This read is fresh because the other request cannot commit
   while the lock is held.
3. Admin A: `remaining = 5000`, requests 3000 → OK. Creates refund, commits, releases lock.
4. Admin B: now acquires the lock, recomputes `remaining = 2000`, requests 3000 →
   `3000 > 2000` → **rejected with 422** and an audit log. Never goes negative.

Result: total refunded = ₹3,000, remaining = ₹2,000.
(Verified by `test_two_refunds_cannot_over_refund`.)

The critical rule: **the total is recomputed *inside* the locked transaction, never read
before the lock.** Reading the total outside the lock is the classic time-of-check /
time-of-use bug that lets both requests see "5000 remaining".

---

## The 7 points asked for

### 1. Idempotency key storage
A dedicated `IdempotencyRecord` table, primary key = the `Idempotency-Key` header value.
Each row stores: the key, `transaction_id`, a `request_hash` (sha256 of the canonical
request body), the `status_code`, and the exact `response_json` we returned. The record
is written **in the same transaction** as the refund, so either both persist or neither.

### 2. Same key + same payload
`request_hash` matches → we return the stored `status_code` + `response_json` verbatim.
No new refund, no new ledger entry. This makes retries safe.

### 3. Same key + different payload
`request_hash` differs → the client reused a key for a different request (a client bug or
an attack). We return **409 Conflict** and audit `REJECTED_IDEMPOTENCY_CONFLICT`. We do
NOT process it — that would let a key be silently overloaded.

### 4. Database transaction
All money checks and writes (over-refund check → create refund → ledger entry →
idempotency record → audit) happen inside **one** transaction and commit atomically.
If anything fails, we roll back and nothing is half-written.

### 5. Row locking / concurrency control
`SELECT ... FOR UPDATE` on the transaction row serializes concurrent refunds for the same
transaction. On **Postgres** this is a true row lock. On **SQLite** (used here for zero
setup) writers are serialized at the database level, giving the same guarantee — the code
is identical and ports to Postgres unchanged. A second safety net: the `IdempotencyRecord`
primary key is unique, so two concurrent requests with the *same key* can't both insert;
the loser catches the `IntegrityError` and replays the winner's response
(see the `except IntegrityError` branch in `refund_logic.create_refund`).

### 6. Refund total calculation
`already_refunded = sum(amount for refunds where status != 'FAILED')`.
`remaining = transaction.amount - already_refunded`. A new refund is allowed only if
`0 < amount <= remaining`. PENDING and SUCCESS refunds both reserve the amount so an
in-flight PENDING refund cannot be double-spent. (If a refund later moves to FAILED, its
amount is released because FAILED rows are excluded from the sum.)

### 7. Audit trail
**Every** attempt — success or rejection — writes an `AuditLog` row with the actor, the
transaction, the outcome code (e.g. `SUCCESS`, `REJECTED_OVER_REFUND`,
`REJECTED_IDEMPOTENCY_CONFLICT`), and a short, PII-free reason. The audit write is part of
the same transaction as the decision, so we never lose the record of what happened.

---

## Trade-offs & notes
- **SQLite vs Postgres:** SQLite serializes writers globally (coarser than a per-row lock),
  which is fine for an assessment but would be a throughput bottleneck in production.
  Production would use Postgres with `SELECT ... FOR UPDATE` (already how the code reads).
- **Idempotency record retention:** in production these rows would expire (e.g. 24–72h TTL)
  so the table doesn't grow forever. Out of scope here.
- **Failed attempts are not stored as idempotent outcomes** — only successful refunds get an
  `IdempotencyRecord`. A rejected request can be retried with a corrected payload. A reused
  key with a *different* payload still returns 409 because the successful record exists.
