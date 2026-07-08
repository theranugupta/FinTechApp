---
name: safe-fintech-change
description: >
  Run BEFORE editing any payment, refund, wallet, ledger, merchant, admin, or
  financial-data flow. Forces inspect-first, smallest-safe-change, and no guessing.
---

# Skill: Safe Fintech Change

Use this skill any time a change touches money: payments, refunds, wallets, ledger
entries, merchant scope, admin actions, or stored financial data. Do not skip it
because the change "looks small" — money bugs are often one-line bugs.

## You MUST complete these steps in order and show your work.

### 1. Inspect relevant files before editing
List and read the files involved: the endpoint, the models/schema, the business-logic
module, and the existing tests. Do not edit anything yet.

### 2. Summarize current behavior
In plain language, describe what the code does today — including validation, auth,
idempotency, and how totals are calculated. Base this on the CODE you just read,
not on assumptions or field names.

### 3. Propose the smallest safe change
State the minimal edit that solves ONLY the requested problem. No refactors, no new
dependencies, no new services/abstractions unless explicitly requested. If a bigger
change seems needed, explain why and ask before doing it.

### 4. Identify risks
Call out what could go wrong: over-refund, double refund, race conditions, auth
bypass, merchant-scope leak, PII/secret exposure, money rounding, wrong status
transition, breaking idempotency. Name the specific risk, not "it might break."

### 5. List tests
State which existing tests cover this and which NEW tests are needed. At minimum for
refund-adjacent code: eligibility, amount bounds, over-refund, idempotency
(same/different payload), auth, merchant scope, concurrency.

### 6. State assumptions
Write down every assumption. If any assumption is about a business rule and it is not
written in CLAUDE.md, STOP and ask a human. Do not proceed on a guessed rule.

### 7. Never guess
- Business rules come from CLAUDE.md verbatim. If missing/ambiguous → ask.
- Enforce money rules on the BACKEND. Frontend checks are UX only.
- Never expose or log secrets, tokens, PII, or raw payment data.

## Output format
Reply with sections: **Inspected**, **Current behavior**, **Proposed change**,
**Risks**, **Tests**, **Assumptions**. Only after this, produce the diff.
