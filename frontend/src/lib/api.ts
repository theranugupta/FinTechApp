// API client for the FinPay refund backend.
// The base URL is configurable so it works in dev and other environments.
// NOTE: the bearer token here is a DEV convenience so you can try different roles in
// the UI. In a real app the token comes from an auth/session provider, never hardcoded.

import { encryptPayload } from "@/lib/crypto";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type TransactionDetails = {
  transaction_id: string;
  user_id: string;
  merchant_id: string;
  amount: number;
  currency: string;
  status: string;
  payment_method: string; // already masked by the backend
  created_at: string;
  remaining_refundable: number;
  refund_allowed: boolean; // backend's authoritative "can this be refunded now?"
};

export type RefundRecord = {
  refund_id: string;
  amount: number;
  currency: string;
  status: string;
  reason: string | null;
  created_at: string;
};

export type RefundHistory = {
  transaction_id: string;
  remaining_refundable: number;
  refunds: RefundRecord[];
};

export type RefundResult = {
  refund_id: string;
  transaction_id: string;
  amount: number;
  currency: string;
  status: string;
  created_at: string;
};

// A small typed error so the UI can show the backend's message + status.
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export function getTransaction(id: string, token: string) {
  return fetch(`${API_BASE}/api/admin/transactions/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
  }).then((r) => handle<TransactionDetails>(r));
}

export function getRefundHistory(id: string, token: string) {
  return fetch(`${API_BASE}/api/admin/transactions/${id}/refunds`, {
    headers: { Authorization: `Bearer ${token}` },
  }).then((r) => handle<RefundHistory>(r));
}

export type DailyPoint = { date: string; count: number; total_amount: number };
export type DailyStats = { days: number; series: DailyPoint[] };

export function getDailyStats(token: string, days = 14) {
  return fetch(`${API_BASE}/api/admin/stats/daily-transactions?days=${days}`, {
    headers: { Authorization: `Bearer ${token}` },
  }).then((r) => handle<DailyStats>(r));
}

export type RefundStatusStats = { statuses: Record<string, number> };

export function getRefundStatusStats(token: string) {
  return fetch(`${API_BASE}/api/admin/stats/refund-status`, {
    headers: { Authorization: `Bearer ${token}` },
  }).then((r) => handle<RefundStatusStats>(r));
}

export async function createRefund(
  id: string,
  token: string,
  idempotencyKey: string,
  body: { amount: number; reason: string }
) {
  // Encrypt the request body (app-layer, on top of TLS). The backend accepts either an
  // encrypted envelope or plain JSON; we always send encrypted from the browser.
  const encrypted = await encryptPayload(body);
  const res = await fetch(`${API_BASE}/api/admin/transactions/${id}/refunds`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      "Idempotency-Key": idempotencyKey,
      "X-Encrypted": "true", // informational: signals the body is an encrypted envelope
    },
    body: JSON.stringify(encrypted),
  });
  return handle<RefundResult>(res);
}
