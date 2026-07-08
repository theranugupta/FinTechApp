---
name: anti-overengineering-review
description: >
  Run on any plan or diff to catch unnecessary complexity before it lands.
  Rejects speculative features, needless dependencies, and premature abstraction.
---

# Skill: Anti-Overengineering Review

Use this skill to review a proposed plan or diff. Goal: keep the change minimal,
correct, and safe for fintech production. Answer every question with evidence from
the diff, not opinion.

## Checklist — answer each explicitly

1. **Did the change solve ONLY the requested problem?**
   List anything in the diff that is not needed for the stated task. Flag it for removal.

2. **Were new dependencies added unnecessarily?**
   Check `requirements`/`package.json`. Every new dependency must be justified. Prefer
   the standard library / existing tools. Reject "nice to have" packages.

3. **Were new services or abstractions added unnecessarily?**
   No new queues, caches, brokers, microservices, config layers, generic "managers",
   or interfaces-with-one-implementation unless explicitly required. Inline beats
   premature abstraction.

4. **Were unrelated files changed?**
   Any file touched that is not part of the task → reject that part of the diff.
   Formatting-only churn in unrelated files is not allowed.

5. **Is there a simpler approach?**
   Describe the simplest implementation that still satisfies the rules and tests.
   If the diff is more complex than that, ask the author to simplify.

6. **Are tests proportional to risk?**
   Money paths (over-refund, idempotency, auth, concurrency) → thorough tests.
   Trivial code → no need for exhaustive tests. Not the reverse.

7. **Is the implementation safe for fintech production?**
   Confirm: backend enforces the money rules, writes are transactional, idempotency
   holds, over-refund is impossible, no secrets/PII exposed, errors are handled.

## Verdict
End with one of: **APPROVE**, **APPROVE WITH CHANGES** (list them), or **REJECT**
(state the blocking reasons). Bias toward the smallest change that is provably safe.
