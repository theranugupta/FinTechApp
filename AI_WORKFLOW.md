# AI_WORKFLOW.md — Using AI safely on the FinPay Refund Module

This document describes how AI coding tools (Claude Code, Cursor, Copilot, ChatGPT)
are used on this fintech codebase. The guiding principle: **AI accelerates typing and
review; it never owns a decision about money.** A human is responsible for every merged line.

---

## 1. How we give project context to AI

- `CLAUDE.md` (repo root) is the single source of truth for stack, business rules,
  and hard constraints. It is loaded into every AI session.
- `.cursor/rules/fintech-development.mdc` mirrors the same rules for Cursor users.
- Reusable **skills** live in `.agents/skills/` and are invoked by name before risky work.
- We point AI at the **actual artifacts** — the business-rules table, the models,
  the existing endpoint, and the tests — instead of describing them from memory.

## 2. How we stop AI from guessing business rules

- All refund rules are written down in `CLAUDE.md` verbatim. AI must quote them, not infer them.
- The **Safe Fintech Change** skill forces AI to first *summarize current behavior from
  the code* before proposing anything.
- If a rule is missing or ambiguous, the required response is **"stop and ask a human"** —
  never invent a threshold, rounding rule, currency behavior, or status transition.
- Naming is not a spec: AI must not conclude "there's a `retry_count` field, so retries
  are allowed" without a written rule.

## 3. How we stop AI from overengineering

- Rule: **smallest safe change that solves only the requested problem.**
- Banned without explicit approval: new queues, caches, brokers, microservices, extra
  databases, new ORMs, generic "framework" layers, premature abstraction.
- The **Anti-Overengineering Review** skill is run on every non-trivial diff/plan.
- Tests must be *proportional to risk* — cover the money rules thoroughly, don't write
  50 trivial tests for a getter.

## 4. How we prevent AI from touching risky files

- `.cursorignore` and `.aiexclude` hide secrets, env files, and infra config from AI context.
- `CLAUDE.md` names the high-risk files (`refund_logic.py`, `models.py`, auth, ledger).
  Changes to these require an explicit callout in the PR and human review.
- AI proposes a diff; a human applies/merges. AI does not push, deploy, or run migrations.
- Unrelated files must never appear in a diff. If they do, the change is rejected.

## 5. How we handle secrets, PII, payment data, tokens, production config

- **Never** paste real secrets, tokens, card/UPI numbers, or customer PII into a prompt.
- Secrets live in env vars / a secrets manager, never in code or in AI context.
  `.env*` is in `.cursorignore` and `.gitignore`.
- Sensitive fields are **masked** in API responses and UI (e.g. `UPI-****9012`).
- Logs never contain raw payment data, tokens, or full PII.
- Production config is off-limits to AI. AI works against local/dev fixtures only.

## 6. How we verify AI-generated code

Nothing is accepted blindly. For every AI change we:
1. **Read the full diff** — line by line, not just the summary.
2. **Run the tests:** `cd backend && . .venv/bin/activate && pytest -q`.
3. Confirm the **business rules** are enforced on the **backend**, not just the UI.
4. Check idempotency, over-refund, auth, and merchant-scope paths specifically.
5. Confirm **no unrelated files** changed and **no new dependencies** sneaked in.
6. Manually exercise the endpoint (curl / Swagger UI at `/docs`) for the happy path
   and at least one abuse path (over-refund, replay).

## 7. Commands / rules / skills we create for repeated use

- `CLAUDE.md` — always-on project context and hard rules.
- `.cursor/rules/fintech-development.mdc` — same, for Cursor.
- `.cursorignore` — keeps secrets/PII/infra out of AI context.
- **Skill: Safe Fintech Change** (`.agents/skills/safe-fintech-change/SKILL.md`) —
  run before editing any money/refund/ledger/auth flow.
- **Skill: Anti-Overengineering Review** (`.agents/skills/anti-overengineering-review/SKILL.md`) —
  run on any plan or diff to catch unnecessary complexity.
- Team habit: "diff review + `pytest` + one manual abuse test" before every accept.

---

### The one-line version
> Give AI the written rules, make it read the code before it writes, keep changes small,
> keep secrets out, enforce money rules on the backend, and verify with tests + a diff
> review + a manual abuse test — every time.
