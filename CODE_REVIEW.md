# Task 7 — Review of the AI-Generated Refund Endpoint

The code under review:

```js
router.post("/api/admin/transactions/:id/refunds", async (req, res) => {
  const transaction = await Transaction.findByPk(req.params.id);
  if (!transaction) {
    return res.status(404).json({ error: "Transaction not found" });
  }
  const refund = await Refund.create({
    transactionId: transaction.id,
    amount: req.body.amount,
    reason: req.body.reason,
    status: "SUCCESS"
  });
  transaction.status = "REFUNDED";
  await transaction.save();
  return res.json(refund);
});
```

## 1. What is wrong with this code?

It ignores almost every business rule in the spec. Concretely:

1. **No authentication.** Anyone who can reach the route can issue refunds.
2. **No authorization / refund permission check.** A read-only support user could refund.
3. **No merchant-scope check.** An admin for Merchant A can refund Merchant B's transaction.
4. **No request validation.** `amount` can be `0`, negative, a string, or missing.
   `reason` is unchecked.
5. **No refund-eligibility check.** A `FAILED` or `PENDING` transaction can be refunded.
6. **No currency check.** Non-INR transactions are refundable, violating the spec.
7. **No single-refund limit.** `amount` can exceed the original transaction amount.
8. **No over-refund prevention.** It never sums prior refunds, so you can refund
   ₹1,000 five times against a ₹1,000 transaction. **This is direct financial loss.**
9. **No idempotency.** No `Idempotency-Key`. A timeout-retry creates a second refund.
10. **No concurrency control / transaction.** Two `refund.create` + `transaction.save`
    calls interleave with no lock; classic race → over-refund.
11. **Wrong status.** Refund is hardcoded `"SUCCESS"` immediately — refunds are async in
    reality and should start `PENDING`. It also blindly sets the *transaction* to
    `"REFUNDED"` even for a **partial** refund, which is factually wrong and corrupts state.
12. **No audit log.** No record of who attempted what — unacceptable for fintech.
13. **No ledger / reversal entry.** No money-movement record for finance/reconciliation.
14. **No error handling.** An exception in `Refund.create`/`save` is unhandled → 500 with
    no audit, and a partial write (refund created, transaction not updated) is possible
    because the two writes aren't in one transaction.
15. **No data masking.** It returns the raw refund/transaction object, potentially leaking
    sensitive fields.

## 2. What are the highest-risk issues?

In order of blast radius:

- **Over-refund (no total check) + no idempotency + no concurrency control.** These three
  together mean the system will pay out more than it received — a direct, unrecoverable
  money leak, triggerable by a normal retry or two clicks. This is the top risk.
- **No authentication / authorization / merchant scope.** Anyone can move money for any
  merchant. Complete access-control failure.
- **Marking the whole transaction `REFUNDED` on a partial refund** corrupts state and hides
  remaining refundable balance.

## 3. What would you fix first?

Stop the money leak and lock the door, in this order:
1. **Enforce auth + refund permission + merchant scope** (reject before any DB write).
2. **Add idempotency** (Idempotency-Key: replay same, 409 on conflict).
3. **Wrap the refund in a DB transaction with a row lock, recompute the refunded total,
   and reject over-refund.**
4. Then validation (amount > 0, ≤ original, INR), eligibility (SUCCESS only), start status
   `PENDING`, stop mutating the transaction status on partial refunds, add audit + ledger,
   and add error handling + masking.

This is exactly what `backend/refund_logic.py` + `backend/main.py` implement in this repo.

## 4. What tests would you add?

The full matrix (implemented in `backend/test_refunds.py`):
unauthenticated → 401; no-permission → 403; wrong-merchant → 403; FAILED txn → 409;
non-INR → 422; zero/negative/over-original amount → 422; multiple partial refunds allowed;
over-refund across refunds → 422; same key+payload → same response (one refund only);
same key+different payload → 409; two refunds cannot over-refund; success writes audit +
ledger; rejected attempt still writes audit; response masks sensitive data.

## 5. Would you approve this AI-generated code for production?

**No — hard reject.** It is not a "needs polish" diff; it is missing the entire security
and money-integrity layer. Approving it would allow unauthorized, unlimited, duplicable
refunds with no audit trail — the worst-case outcome for a payments system. It is a useful
*skeleton* of the happy path and nothing more. The correct action is to treat it as a
starting sketch and rebuild the enforcement around it (as done here), then require tests +
a diff review before merge.
