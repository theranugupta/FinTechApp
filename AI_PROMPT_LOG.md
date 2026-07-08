# AI Prompt Log

## Tool used
Claude Code (Anthropic). Backend in Python/FastAPI, frontend in Next.js + Tailwind + shadcn/ui.

This log records the prompts that materially shaped the solution and — importantly — what
I *rejected* from the AI and why. AI accelerated typing and scaffolding; every business
rule and security decision was checked against the spec by hand.

---

## Prompt 1 — Project workflow & guardrails first
**Prompt (summary):** "Before writing code, set up the AI safety workflow for a fintech
refund module: CLAUDE.md with the frozen business rules, AI_WORKFLOW.md, and two skills
(safe-fintech-change, anti-overengineering-review). Rules must forbid guessing business
logic and overengineering."

**AI output accepted:** The structure and wording of `CLAUDE.md`, `AI_WORKFLOW.md`, the two
`SKILL.md` files, the Cursor rule, and `.cursorignore`. I kept the frozen business-rules
table so downstream code generation could not invent rules.

**AI output rejected:** An initial suggestion to add a generic "RBAC engine" and a
"rules engine" abstraction for the business rules.

**Why rejected:** Overengineering. The spec has ~14 fixed rules; a plain, readable function
is safer and more reviewable than a configurable engine. Flagged by the
anti-overengineering skill.

**Manual verification:** Re-read each rule in the file against the assessment PDF's rules
table to confirm none were dropped, added, or altered.

---

## Prompt 2 — Backend refund endpoint
**Prompt (summary):** "Implement POST /api/admin/transactions/:id/refunds in FastAPI +
SQLModel + SQLite. Cover auth, permission, merchant scope, validation, eligibility, partial
refunds, over-refund prevention, idempotency (same/diff payload), audit, ledger, errors.
Enforce ALL rules on the backend. Smallest safe design; no extra infrastructure."

**AI output accepted:** The layered check order (authn → permission → scope → eligibility →
currency → amount → over-refund inside a locked transaction), the `IdempotencyRecord` design
storing a request hash + response, the audit-on-every-attempt pattern, and the
`RefundError` → HTTP mapping.

**AI output rejected:**
- A first draft that read the refunded total *before* opening the transaction (would allow
  a concurrent over-refund).
- A suggestion to add Redis for idempotency storage.
- A draft that set `refund.status = "SUCCESS"` immediately and marked the whole transaction
  `REFUNDED`.

**Why rejected:**
- Reading the total outside the lock is a time-of-check/time-of-use race → over-refund. I
  moved the total calculation *inside* the locked transaction.
- Redis is unnecessary infrastructure; the same DB gives atomicity with the refund write.
  A separate store risks the refund and its idempotency record diverging.
- Refunds are asynchronous; `PENDING` is correct. Marking a transaction `REFUNDED` on a
  *partial* refund is factually wrong and hides remaining balance.

**Manual verification:** Wrote and ran `pytest` (19 tests) covering every rule incl.
concurrency/over-refund and both idempotency branches. Also exercised the live server with
`curl`: confirmed 201 on create, identical `refund_id` on replay, and 409 on key reuse with
a different payload.

---

## Prompt 3 — Frontend refund UI
**Prompt (summary):** "Build a Next.js + Tailwind + shadcn/ui transaction page: masked
details, refund history, remaining refundable, a refund modal with amount/reason,
loading/error/success states, permission-based disabled button, and double-submit
prevention. Make clear which validation is frontend (UX) vs backend (authoritative)."

**AI output accepted:** The `RefundModal` with a per-open idempotency key reused across
retries, submit-button disabling while in flight, backend-driven `refund_allowed` gating the
button, and rendering the backend's error message on failure.

**AI output rejected:** A draft that enforced the over-refund limit purely in the React
component and showed a success toast optimistically before the API responded.

**Why rejected:** Frontend checks are UX only and are bypassable; the backend must be the
source of truth (and it is — it re-checks and can still return 422). Optimistic success on a
money operation is unsafe — we must show success only after the backend confirms.

**Manual verification:** `npm run build` (typecheck + production build passed). Started the
backend + `next dev` together and confirmed the page renders and reads the API.

---

## Prompt 4 — Review the flawed endpoint (Task 7)
**Prompt (summary):** "Review this AI-generated Express refund handler; list what's wrong,
highest risks, what to fix first, tests to add, and whether to approve for production."

**AI output accepted:** The enumeration of missing controls. I re-derived each item directly
from the spec's rules table rather than trusting the list, and added the partial-refund
state-corruption bug (marking the whole transaction `REFUNDED`) and the missing-transaction
atomicity bug, which the first pass under-emphasized.

**AI output rejected:** A soft "approve with minor changes" verdict.

**Why rejected:** The code is missing the entire security + money-integrity layer; that is a
hard reject, not a nit. Softening the verdict would be the exact "accept AI output blindly"
failure the assessment warns about.

**Manual verification:** Cross-checked every listed defect against the implemented backend to
confirm each one is actually handled there.

---

## Final assumptions
See the shared list in `FINAL_SUMMARY.md` → "Assumptions made".
