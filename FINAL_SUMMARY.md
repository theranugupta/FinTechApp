# Final Summary

## What I built
A full-stack FinPay admin refund module:
- **Backend (FastAPI + SQLModel + SQLite):** `POST /api/admin/transactions/{id}/refunds`
  plus read endpoints for transaction details and refund history. Enforces, server-side,
  every rule in the spec: authentication, refund permission, merchant scope, request
  validation, eligibility (SUCCESS only), INR only, single-refund limit, multiple partial
  refunds, over-refund prevention, idempotency (replay + 409 conflict), audit trail on every
  attempt, ledger/reversal entries, and data masking. All money checks and writes run inside
  one DB transaction with a row lock.
- **Frontend (Next.js + Tailwind + shadcn/ui):** transaction details page with masked data,
  remaining refundable amount, a refund modal (amount + reason), loading/error/success
  states, permission-based disabled button, double-submit prevention via a per-intent
  idempotency key, and refund history.
- **Tests:** 19 pytest cases covering the full assessment matrix — all passing.
- **AI governance:** CLAUDE.md, AI_WORKFLOW.md, two reusable skills, Cursor rules, and a
  prompt log documenting what I accepted and rejected from AI.

## AI tools used
Claude Code (Anthropic), used to scaffold and draft; all rules and security decisions were
verified by hand against the spec.

## What AI helped with
- Scaffolding the FastAPI app, SQLModel schema, and the Next.js/shadcn components fast.
- Drafting the AI-governance docs and the test matrix.
- Boilerplate (Pydantic schemas, API client, dialog wiring), which let me focus review time
  on the money-integrity paths.

## What AI got wrong or missed
- Initially computed the refunded total **outside** the DB lock (a time-of-check/time-of-use
  race that would allow over-refund). Fixed by moving the calculation inside the locked
  transaction.
- Suggested unnecessary infrastructure (a Redis idempotency store, an RBAC/rules "engine").
- Drafted refunds as immediately `SUCCESS` and marked the whole transaction `REFUNDED` on a
  partial refund — incorrect for async, partial refunds.
- On the frontend, tried to enforce the over-refund limit only in React and show optimistic
  success.
- Generated frontend UI components for the **wrong toolchain** (Base UI + Tailwind v4) when
  the project is Tailwind v3 — I replaced them with the classic Radix-based shadcn v3
  components.

## What I rejected from AI output
Over-refund total read outside the lock; Redis/rules-engine overengineering; immediate
`SUCCESS` + transaction `REFUNDED` on partial; frontend-only limit enforcement + optimistic
success; the Base UI / Tailwind v4 component set; and a soft "approve with minor changes"
verdict on the Task 7 review (it is a hard reject).

## Assumptions made
1. **Money is an integer** in the transaction's currency unit (spec shows `"amount": 5000`).
   No floats. If amounts are actually in paise, the same code holds — only the display unit
   changes.
2. **Auth is stubbed** with a token→user table (`auth.py`). In production the bearer token is
   a signed/opaque token validated by an identity service; permissions and merchant scope
   come from there.
3. **Refund starts `PENDING`**, matching the spec's example response. A separate
   settlement/webhook process would later move it to SUCCESS/FAILED (out of scope).
4. **PENDING + SUCCESS refunds both reserve the amount**; only `FAILED` refunds release it.
5. **404 vs 403 for out-of-scope reads:** the read endpoints return 404 (not 403) for
   out-of-scope transactions to avoid leaking existence; the write endpoint returns 403 with
   an audit entry.
6. **SQLite** stands in for Postgres; the locking code (`SELECT ... FOR UPDATE`) is written
   for Postgres and works because SQLite serializes writers.
7. **One transaction per page** in the demo UI (`TXN-10001`); a real dashboard would have
   search/routing.

## Tests added or planned
Added (pytest, all passing): unauthenticated → 401; no-permission → 403; wrong-merchant →
403; FAILED txn → 409; non-INR → 422; zero/negative/over-original → 422; multiple partial
refunds; over-refund across refunds → 422; same key+payload → same response (one refund);
same key+different payload → 409; two refunds cannot over-refund; success writes audit +
ledger; rejected attempt still audits; response masks sensitive data.
Planned with more time: true multi-threaded concurrency test against Postgres; frontend
component tests (React Testing Library) for disabled/double-submit/error states; idempotency
record TTL/expiry.

## Risks remaining
- **SQLite concurrency** serializes all writers (coarser than per-row locks) — a throughput
  bottleneck; production should use Postgres.
- **Concurrency is proven functionally (sequential) and by design**, not yet by a real
  parallel stress test.
- **Refund lifecycle** beyond `PENDING` (settlement, webhooks, reconciliation) is not built.
- **Idempotency records don't expire** — needs a TTL/cleanup job in production.
- **Deprecation warnings** from FastAPI's `on_event`/httpx TestClient (cosmetic; would
  migrate to lifespan handlers).
- **Auth is a stub** — real token validation and scope resolution must replace `auth.py`.

## What I would improve with more time
Migrate to Postgres + a real parallel concurrency test; replace the stubbed auth with real
token validation; add the refund settlement lifecycle + webhooks; add frontend unit tests;
add idempotency TTL and structured, PII-safe audit logging/observability; migrate the
FastAPI startup to lifespan handlers.

## Would I approve this for production?
**Conditional.**

Reason: The core money-integrity logic — authorization, merchant scope, validation,
eligibility, over-refund prevention, idempotency, audit, and ledger — is implemented,
enforced on the backend, and covered by passing tests, and the flawed reference code from
Task 7 would be rejected. It is production-*shaped*. But it is not production-*ready* until
the conditions above are met: move to Postgres with a verified parallel concurrency test,
replace the stubbed auth with real token validation, add the refund settlement lifecycle,
and add idempotency-record expiry plus real observability. With those, yes; as-is, it is a
solid, safe foundation but not something I would put in front of real money today.
