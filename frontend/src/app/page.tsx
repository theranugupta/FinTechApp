"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, ChevronsUpDown, X } from "lucide-react";
import {
  ApiError,
  getRefundHistory,
  getTransaction,
  RefundHistory,
  TransactionDetails,
} from "@/lib/api";
import { RefundModal } from "@/components/RefundModal";
import { Sidebar } from "@/components/Sidebar";
import { DailyTransactionsChart } from "@/components/DailyTransactionsChart";
import { RefundStatusChart } from "@/components/RefundStatusChart";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuCheckboxItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useTranslation } from "@/lib/i18n";

const TRANSACTION_ID = "TXN-10001";

const ROLES = [
  { token: "admin-token", labelKey: "role.admin" },
  { token: "support-noperm-token", labelKey: "role.support" },
  { token: "other-merchant-token", labelKey: "role.otherMerchant" },
];
const PERMISSIONED = new Set(["admin-token", "superadmin-token"]);

export default function Page() {
  const { t } = useTranslation();
  const [token, setToken] = useState(ROLES[0].token);
  const [txn, setTxn] = useState<TransactionDetails | null>(null);
  const [history, setHistory] = useState<RefundHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0); // bump to refetch the status doughnut

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [tx, h] = await Promise.all([
        getTransaction(TRANSACTION_ID, token),
        getRefundHistory(TRANSACTION_ID, token),
      ]);
      setTxn(tx);
      setHistory(h);
    } catch (e) {
      setTxn(null);
      setHistory(null);
      setError(e instanceof ApiError ? `${e.message} (HTTP ${e.status})` : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const activeRole = ROLES.find((r) => r.token === token) ?? ROLES[0];
  const disabledReason = !txn?.refund_allowed ? t("refund.notAllowed") : undefined;

  return (
    <div className="flex flex-col md:flex-row">
      <Sidebar />

      <main className="mx-auto w-full max-w-3xl space-y-8 p-4 py-8 sm:p-6">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight">
            <span className="text-brand-gradient">{t("page.title")}</span>
          </h1>
          <p className="text-sm text-muted-foreground">{t("page.subtitle")}</p>
        </div>

        {/* Role switcher */}
        <div className="space-y-1.5">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {t("page.viewAs")}
          </p>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                className="w-full justify-between rounded-xl border-border/60 bg-background/50 font-normal backdrop-blur"
              >
                {t(activeRole.labelKey)}
                <ChevronsUpDown className="h-4 w-4 opacity-60" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-[var(--radix-dropdown-menu-trigger-width)]">
              <DropdownMenuLabel>{t("page.viewAs")}</DropdownMenuLabel>
              <DropdownMenuSeparator />
              {ROLES.map((r) => (
                <DropdownMenuCheckboxItem
                  key={r.token}
                  checked={token === r.token}
                  onCheckedChange={() => setToken(r.token)}
                >
                  {t(r.labelKey)}
                </DropdownMenuCheckboxItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* OVERVIEW / DAILY TRANSACTIONS CHART */}
        <Section id="overview" title={t("chart.title")} subtitle={t("chart.subtitle")}>
          <DailyTransactionsChart token={token} />
        </Section>

        {loading && <p className="text-sm text-muted-foreground">{t("common.loading")}</p>}

        {!loading && error && (
          <p className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-600 dark:text-red-400">
            {error}
          </p>
        )}

        {!loading && txn && history && (
          <>
            {/* TRANSACTION DETAILS */}
            <Section id="details" title={t("nav.details")}>
              <div className="mb-3 flex items-center justify-between">
                <span className="font-semibold">{txn.transaction_id}</span>
                <Badge
                  className={txn.status === "SUCCESS" ? "bg-brand-gradient text-white" : undefined}
                  variant={txn.status === "SUCCESS" ? "default" : "secondary"}
                >
                  {txn.status}
                </Badge>
              </div>
              <div className="space-y-2.5 text-sm">
                <Row label={t("txn.user")} value={txn.user_id} />
                <Row label={t("txn.merchant")} value={txn.merchant_id} />
                <Row label={t("txn.amount")} value={`${txn.amount} ${txn.currency}`} />
                {/* Sensitive payment data masked by the backend. */}
                <Row label={t("txn.paymentMethod")} value={txn.payment_method} />
                <Row
                  label={t("txn.remaining")}
                  value={`${txn.remaining_refundable} ${txn.currency}`}
                  highlight
                />
              </div>
            </Section>

            {/* REFUND ELIGIBILITY */}
            <Section id="eligibility" title={t("nav.eligibility")}>
              <div className="mb-4">
                <Badge
                  className={txn.refund_allowed ? "bg-brand-gradient text-white" : undefined}
                  variant={txn.refund_allowed ? "default" : "secondary"}
                >
                  {txn.refund_allowed ? t("eligibility.eligible") : t("eligibility.notEligible")}
                </Badge>
              </div>
              <div className="space-y-2">
                <CheckRow ok={txn.status === "SUCCESS"} label={t("eligibility.status")} />
                <CheckRow ok={txn.currency === "INR"} label={t("eligibility.currency")} />
                <CheckRow ok={txn.remaining_refundable > 0} label={t("eligibility.remaining")} />
                <CheckRow ok={PERMISSIONED.has(token)} label={t("eligibility.permission")} />
              </div>
            </Section>

            {/* INITIATE REFUND */}
            <Section id="initiate" title={t("nav.initiate")}>
              <p className="mb-4 text-sm text-muted-foreground">{t("initiate.desc")}</p>
              <RefundModal
                transactionId={txn.transaction_id}
                token={token}
                currency={txn.currency}
                remaining={txn.remaining_refundable}
                disabled={!txn.refund_allowed}
                disabledReason={disabledReason}
                onRefunded={() => {
                  load();
                  setRefreshKey((k) => k + 1); // refresh the status doughnut too
                }}
              />
              {!txn.refund_allowed && (
                <p className="mt-2 text-xs text-muted-foreground">{disabledReason}</p>
              )}
            </Section>

            {/* REFUND STATUS */}
            <Section id="status" title={t("nav.status")}>
              <div className="grid gap-6 md:grid-cols-2">
                <div>
                  <div className="grid grid-cols-3 gap-3">
                    <StatTile
                      label={t("status.totalRefunded")}
                      value={`${txn.amount - txn.remaining_refundable}`}
                    />
                    <StatTile
                      label={t("status.remaining")}
                      value={`${txn.remaining_refundable}`}
                    />
                    <StatTile label={t("status.count")} value={`${history.refunds.length}`} />
                  </div>
                  {history.refunds.length > 0 && (
                    <ul className="mt-4 space-y-2">
                      {history.refunds.map((r) => (
                        <li
                          key={r.refund_id}
                          className="flex items-center justify-between text-sm"
                        >
                          <span className="font-medium">{r.refund_id}</span>
                          <Badge variant="secondary">{r.status}</Badge>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <div>
                  <p className="mb-2 text-center text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {t("statusChart.title")}
                  </p>
                  <RefundStatusChart token={token} refreshKey={refreshKey} />
                </div>
              </div>
            </Section>

            {/* REFUND HISTORY */}
            <Section id="history" title={t("nav.history")}>
              {history.refunds.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t("history.empty")}</p>
              ) : (
                <ul className="divide-y divide-border/60 text-sm">
                  {history.refunds.map((r) => (
                    <li key={r.refund_id} className="flex items-center justify-between py-2.5">
                      <span className="text-muted-foreground">
                        <span className="font-medium text-foreground">{r.refund_id}</span>
                        {r.reason ? ` — ${r.reason}` : ""}
                      </span>
                      <span className="flex items-center gap-2 font-medium">
                        {r.amount} {r.currency}
                        <Badge variant="secondary">{r.status}</Badge>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Section>
          </>
        )}
      </main>
    </div>
  );
}

function Section({
  id,
  title,
  subtitle,
  children,
}: {
  id: string;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-24">
      <Card className="overflow-hidden border-border/60 bg-card/80 shadow-lg backdrop-blur">
        <div className="h-1 w-full bg-brand-gradient" />
        <CardHeader>
          <CardTitle>{title}</CardTitle>
          {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
        </CardHeader>
        <CardContent>{children}</CardContent>
      </Card>
    </section>
  );
}

function Row({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div className="flex justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className={highlight ? "font-bold text-brand-gradient" : "font-medium"}>{value}</span>
    </div>
  );
}

function CheckRow({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <span
        className={
          "flex h-5 w-5 items-center justify-center rounded-full " +
          (ok
            ? "bg-primary/10 text-foreground"
            : "bg-red-500/15 text-red-600 dark:text-red-400")
        }
      >
        {ok ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />}
      </span>
      <span className={ok ? "" : "text-muted-foreground"}>{label}</span>
    </div>
  );
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border/60 bg-background/40 p-3 text-center">
      <p className="text-xl font-bold text-brand-gradient">{value}</p>
      <p className="mt-1 text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
    </div>
  );
}
