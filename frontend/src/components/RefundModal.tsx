"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, createRefund, RefundResult } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

type Props = {
  transactionId: string;
  token: string;
  currency: string;
  remaining: number; // remaining refundable, from the backend
  disabled: boolean; // backend-derived permission/eligibility gate
  disabledReason?: string;
  onRefunded: () => void; // parent re-fetches details + history after success
};

export function RefundModal({
  transactionId,
  token,
  currency,
  remaining,
  disabled,
  disabledReason,
  onRefunded,
}: Props) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false); // drives loading + double-submit guard
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<RefundResult | null>(null);
  // One idempotency key per modal-open. Retries (incl. accidental double clicks or a
  // timeout-retry) reuse THIS key, so the backend collapses them into one refund.
  const [idempotencyKey, setIdempotencyKey] = useState("");

  // FRONTEND VALIDATION IS UX ONLY. The backend re-checks every rule and is the source
  // of truth. These checks just give instant feedback and stop obviously-bad submits.
  function uxValidate(): string | null {
    const n = Number(amount);
    if (!amount || Number.isNaN(n)) return t("validation.amountInvalid");
    if (!Number.isInteger(n)) return t("validation.amountInteger");
    if (n <= 0) return t("validation.amountPositive");
    if (n > remaining) return t("validation.amountExceeds", { remaining });
    if (!reason.trim()) return t("validation.reasonRequired");
    return null;
  }

  function openModal() {
    setAmount("");
    setReason("");
    setError(null);
    setSuccess(null);
    setSubmitting(false);
    setIdempotencyKey(crypto.randomUUID()); // fresh key for a fresh refund intent
    setOpen(true);
  }

  async function handleSubmit() {
    if (submitting) return; // hard guard against double-submit
    const uxError = uxValidate();
    if (uxError) {
      setError(uxError);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const result = await createRefund(transactionId, token, idempotencyKey, {
        amount: Number(amount),
        reason: reason.trim(),
      });
      setSuccess(result);
      onRefunded(); // let the parent refresh remaining amount + history
    } catch (e) {
      // Show the BACKEND's message — it is authoritative (e.g. over-refund, 409 conflict).
      if (e instanceof ApiError) setError(`${e.message} (HTTP ${e.status})`);
      else setError(t("error.generic"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => (o ? openModal() : setOpen(false))}>
      <DialogTrigger asChild>
        {/* Permission-based disabled state comes from the backend's refund_allowed. */}
        <Button disabled={disabled} title={disabled ? disabledReason : undefined}>
          {t("refund.issue")}
        </Button>
      </DialogTrigger>

      <DialogContent className="border-border/60 bg-card/95 backdrop-blur">
        <DialogHeader>
          <DialogTitle>{t("modal.title", { id: transactionId })}</DialogTitle>
          <DialogDescription>
            {t("modal.remaining")}:{" "}
            <span className="font-semibold text-brand-gradient">
              {remaining} {currency}
            </span>
          </DialogDescription>
        </DialogHeader>

        {success ? (
          // SUCCESS STATE
          <div className="space-y-1.5 rounded-xl border border-border bg-secondary p-4 text-sm">
            <p className="font-semibold text-foreground">
              ✓ {t("modal.successTitle")}
            </p>
            <p>{t("modal.refundId")}: {success.refund_id}</p>
            <p>{t("txn.amount")}: {success.amount} {success.currency}</p>
            <p>{t("modal.status")}: {success.status}</p>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="amount">{t("modal.amount", { currency })}</Label>
              <Input
                id="amount"
                inputMode="numeric"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder={t("modal.amountPlaceholder", { remaining })}
                disabled={submitting}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="reason">{t("modal.reason")}</Label>
              <Input
                id="reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder={t("modal.reasonPlaceholder")}
                disabled={submitting}
              />
            </div>

            {/* ERROR STATE */}
            {error && (
              <p className="rounded-xl border border-red-500/30 bg-red-500/10 p-2.5 text-sm text-red-600 dark:text-red-400">
                {error}
              </p>
            )}
          </div>
        )}

        <DialogFooter>
          {success ? (
            <Button onClick={() => setOpen(false)}>{t("common.close")}</Button>
          ) : (
            <Button onClick={handleSubmit} disabled={submitting}>
              {/* LOADING STATE + double-submit prevention */}
              {submitting ? t("modal.processing") : t("modal.confirm")}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
