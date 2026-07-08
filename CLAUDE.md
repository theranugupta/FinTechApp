# CLAUDE.md — FinPay Admin Refund Module

This file gives AI assistants (Claude Code, Cursor, Copilot, etc.) the context they
need to work safely in this **fintech** codebase. Read it fully before writing code.

## What this project is

An admin/support dashboard feature for issuing **refunds** against payment
transactions. Money is involved. Mistakes here cause real financial loss,
double refunds, or over-refunds. Treat every change as high risk.

## Tech stack

- **Backend:** Python 3.8, FastAPI, SQLModel (SQLAlchemy + Pydantic), SQLite.
- **Frontend:** Next.js (App Router), React, Tailwind CSS, shadcn/ui.
- **Tests:** pytest + FastAPI TestClient.

## The business rules are FIXED — do not invent them

These come from the product spec. **Never guess or "improve" them.** If a rule is
unclear, stop and ask a human. Do not infer intent from variable names.

| Area | Rule |
|---|---|
| Eligibility | Only `SUCCESS` transactions can be refunded |
| Currency | Only `INR` is supported |
| Amount | Refund amount must be `> 0` |
| Limit | A single refund cannot exceed the original transaction amount |
| Partial | Multiple partial refunds are allowed |
| Over-refund | Sum of all refunds must never exceed the original amount |
| Idempotency | Refund API must honour an `Idempotency-Key` header |
| Duplicate | Same key + same payload → return the ORIGINAL response |
| Conflict | Same key + different payload → return `409 Conflict` |
| Authorization | Only admin/support users **with refund permission** can refund |
| Merchant scope | An admin must not touch transactions outside their merchant scope |
| Audit | Every refund *attempt* (success or fail) creates an audit log |
| Ledger | A successful refund creates a reversal/ledger entry |
| Data privacy | Sensitive payment data must be masked in responses and UI |
| Frontend | Refund button is disabled when a refund is not allowed |

## Hard rules for any AI-generated change

1. **Do not guess business logic.** Use the table above verbatim. Ask if unsure.
2. **Inspect first.** Read the relevant models, endpoint, and tests before editing.
3. **Smallest safe change.** Solve only the requested problem. No speculative features.
4. **No new infrastructure** (queues, caches, message brokers, extra services,
   new DBs, ORMs, or heavy abstractions) unless explicitly asked.
5. **The backend is the source of truth.** All money rules MUST be enforced
   server-side. Frontend validation exists only for UX and can be bypassed.
6. **Never expose or hardcode** secrets, tokens, API keys, full card/UPI details,
   or PII. Mask sensitive fields. Never log raw payment data or tokens.
7. **Money integrity:** every write that touches balances/refunds must run inside
   a DB transaction and guard against concurrent over-refund (row lock / re-check
   totals inside the transaction).
8. **Idempotency is mandatory** on the refund endpoint. Retries must never create
   a second refund.
9. **Verify before accepting:** run `pytest`, review the diff, and confirm no
   unrelated files changed.

## Files that are risky to touch

- `backend/refund_logic.py` — the money rules live here. Changes need tests + review.
- `backend/models.py` — schema changes affect stored financial data.
- Anything touching auth, idempotency, or ledger. Flag these in the PR description.

## How to propose a change

State: (1) what you inspected, (2) current behavior, (3) the smallest change,
(4) risks, (5) which rules/tests cover it, (6) any assumptions. Then implement.
