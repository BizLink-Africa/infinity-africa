"use client";

import { useEffect, useState } from "react";
import { DISBURSEMENT_METHOD_LABELS, DISBURSEMENT_METHOD_RECOMMENDED, DisbursementMethod } from "@infinity/shared";

import { Card, tdClass, thClass } from "@/components/portal/card";
import { Icon } from "@/components/portal/icon";
import { PageHeader } from "@/components/portal/page-header";
import { StatusBadge } from "@/components/portal/status-badge";
import { formatCurrency, formatDateTime } from "@/lib/format";
import { createDisbursement, getAvailableBalance, InsufficientBalanceError, listDisbursements } from "@/lib/portal/api";
import { disbursementBadge } from "@/lib/portal/status-tones";
import type { Disbursement } from "@/lib/portal/types";

const METHOD_CARDS: Array<{ method: DisbursementMethod; icon: string; description: string; settlement: string }> = [
  { method: DisbursementMethod.SELCOM_PESA, icon: "bolt", description: "Instant, zero-fee transfers within network. Priority routing for high-volume payouts.", settlement: "< 1 minute" },
  { method: DisbursementMethod.MOBILE_MONEY, icon: "phone_iphone", description: "M-Pesa, Tigo Pesa, Airtel Money & HaloPesa payouts direct to any wallet.", settlement: "1–5 minutes" },
  { method: DisbursementMethod.BANK_ACCOUNT, icon: "account_balance", description: "Direct transfer to any local commercial bank account, including CRDB & NMB.", settlement: "Same business day" },
];

/** Client-facing card/radio titles — merchants see "Withdraw to X"; the
 * technical DisbursementMethod enum and API stay unchanged underneath. */
const WITHDRAW_TITLES: Record<DisbursementMethod, string> = {
  [DisbursementMethod.SELCOM_PESA]: "Withdraw to Selcom Pesa",
  [DisbursementMethod.MOBILE_MONEY]: "Withdraw to Mobile Money",
  [DisbursementMethod.BANK_ACCOUNT]: "Withdraw to Bank Account",
};

const MOBILE_MONEY_NETWORKS = ["M-Pesa", "Tigo Pesa", "Airtel Money", "HaloPesa"];

/** Illustrative fee preview matching the rates shown on the Pricing page. */
const WITHDRAW_FEE_RATE: Record<DisbursementMethod, { label: string; compute: (amount: number) => number }> = {
  [DisbursementMethod.SELCOM_PESA]: { label: "Free", compute: () => 0 },
  [DisbursementMethod.MOBILE_MONEY]: { label: "1% per withdrawal", compute: (amount) => amount * 0.01 },
  [DisbursementMethod.BANK_ACCOUNT]: { label: "TZS 1,500 flat fee", compute: () => 1500 },
};

export function WithdrawalsView() {
  const [disbursements, setDisbursements] = useState<Disbursement[]>([]);
  const [balance, setBalance] = useState<string>("0");
  const [method, setMethod] = useState<DisbursementMethod>(DisbursementMethod.SELCOM_PESA);
  const [recipientName, setRecipientName] = useState("");
  const [recipientIdentifier, setRecipientIdentifier] = useState("");
  const [bankName, setBankName] = useState("");
  const [network, setNetwork] = useState("");
  const [amount, setAmount] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listDisbursements().then(setDisbursements);
    getAvailableBalance().then(setBalance);
  }, []);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    if (!recipientName || !recipientIdentifier || !amount) return;
    if (method === DisbursementMethod.BANK_ACCOUNT && !bankName) {
      setError("Bank name is required for bank account payouts.");
      return;
    }

    setSubmitting(true);
    try {
      const disbursement = await createDisbursement({
        method,
        destination_name: recipientName,
        destination_identifier: recipientIdentifier,
        bank_name: method === DisbursementMethod.BANK_ACCOUNT ? bankName : null,
        network: method === DisbursementMethod.MOBILE_MONEY ? network || null : null,
        amount,
        description: notes || null,
      });
      setDisbursements((prev) => [disbursement, ...prev]);
      setRecipientName("");
      setRecipientIdentifier("");
      setBankName("");
      setNetwork("");
      setAmount("");
      setNotes("");
    } catch (err) {
      if (err instanceof InsufficientBalanceError) {
        setError(err.message);
      } else {
        setError("Something went wrong requesting this withdrawal.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader title="Withdrawals" description="Withdraw funds to Selcom Pesa, mobile wallets, or bank accounts." />

      <section className="grid grid-cols-1 sm:grid-cols-3 gap-5">
        {METHOD_CARDS.map((card) => {
          const recommended = DISBURSEMENT_METHOD_RECOMMENDED[card.method];
          return (
            <div
              key={card.method}
              id={card.method === DisbursementMethod.SELCOM_PESA ? "selcom-pesa" : card.method === DisbursementMethod.MOBILE_MONEY ? "mobile-money" : "bank-account"}
              className={
                recommended
                  ? "scroll-mt-24 bg-surface rounded-xl border-2 border-primary shadow-ambient p-6 relative"
                  : "scroll-mt-24 bg-surface rounded-xl border border-surface-container-highest shadow-ambient p-6"
              }
            >
              {recommended && (
                <div className="absolute -top-3 left-5 bg-accent text-primary px-2.5 py-1 rounded-full text-[11px] font-semibold flex items-center gap-1 border border-primary/20">
                  <Icon name="check" className="text-[12px] font-bold" />
                  Highly Recommended
                </div>
              )}
              <div className={`w-12 h-12 rounded-full bg-surface-container-highest mb-4 flex items-center justify-center ${recommended ? "text-primary" : "text-secondary"}`}>
                <Icon name={card.icon} className="text-[24px]" />
              </div>
              <h4 className="text-lg font-semibold text-on-background mb-1">{WITHDRAW_TITLES[card.method]}</h4>
              <p className="text-sm text-on-surface-variant mb-4">{card.description}</p>
              <div className="flex items-center justify-between text-xs font-semibold text-on-surface-variant border-t border-surface-container-highest pt-3">
                <span>Avg. settlement</span>
                <span className={recommended ? "text-primary" : "text-on-surface"}>{card.settlement}</span>
              </div>
            </div>
          );
        })}
      </section>

      <Card id="request-withdrawal" className="scroll-mt-24">
        <h3 className="text-2xl font-semibold text-on-background mb-5">Request a Withdrawal</h3>
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-on-surface-variant mb-2">Withdrawal Method</label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {METHOD_CARDS.map((card) => (
                <label
                  key={card.method}
                  className={
                    method === card.method
                      ? "flex items-center gap-2 border-2 border-primary bg-primary-container/10 rounded-lg px-4 py-3 cursor-pointer"
                      : "flex items-center gap-2 border border-surface-container-highest rounded-lg px-4 py-3 cursor-pointer hover:border-primary/50"
                  }
                >
                  <input
                    checked={method === card.method}
                    onChange={() => setMethod(card.method)}
                    className="text-primary-container focus:ring-primary"
                    name="method"
                    type="radio"
                  />
                  <span className="font-medium text-sm text-on-surface">{WITHDRAW_TITLES[card.method]}</span>
                </label>
              ))}
            </div>
          </div>
          <div className="grid sm:grid-cols-2 gap-5">
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1.5">Destination Name</label>
              <input
                className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary text-sm"
                placeholder="e.g. Selcom Pesa Merchant Wallet"
                type="text"
                value={recipientName}
                onChange={(event) => setRecipientName(event.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1.5">Destination Number / Account</label>
              <input
                className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary text-sm"
                placeholder="+255 7XX XXX XXX or account no."
                type="text"
                value={recipientIdentifier}
                onChange={(event) => setRecipientIdentifier(event.target.value)}
              />
            </div>
          </div>
          {method === DisbursementMethod.BANK_ACCOUNT && (
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1.5">Bank Name</label>
              <input
                className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary text-sm"
                placeholder="e.g. CRDB Bank"
                type="text"
                value={bankName}
                onChange={(event) => setBankName(event.target.value)}
              />
            </div>
          )}
          {method === DisbursementMethod.MOBILE_MONEY && (
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1.5">Network (optional)</label>
              <select
                className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary text-sm"
                value={network}
                onChange={(event) => setNetwork(event.target.value)}
              >
                <option value="">Detect automatically</option>
                {MOBILE_MONEY_NETWORKS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="grid sm:grid-cols-2 gap-5">
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1.5">Amount (TZS)</label>
              <div className="relative">
                <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-on-surface-variant text-sm font-semibold">
                  TZS
                </span>
                <input
                  className="w-full pl-12 pr-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary text-sm"
                  placeholder="500,000"
                  type="number"
                  min="1"
                  value={amount}
                  onChange={(event) => setAmount(event.target.value)}
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1.5">Notes (optional)</label>
              <input
                className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary text-sm"
                placeholder="e.g. Weekly supplier payout"
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
              />
            </div>
          </div>
          <div className="bg-surface-container-low rounded-lg px-4 py-3 text-sm space-y-2">
            <p className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide">Fee Preview</p>
            <div className="flex items-center justify-between">
              <span className="text-on-surface-variant">Available Balance</span>
              <span className="font-semibold text-on-background">{formatCurrency(balance, "TZS")}</span>
            </div>
            <div className="flex items-center justify-between border-t border-surface-container-highest pt-2">
              <span className="text-on-surface-variant">Fee ({WITHDRAW_FEE_RATE[method].label})</span>
              <span className="font-semibold text-on-background">
                {formatCurrency(WITHDRAW_FEE_RATE[method].compute(Number(amount) || 0), "TZS")}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-on-surface-variant">You&apos;ll Receive</span>
              <span className="font-semibold text-primary">
                {formatCurrency(Math.max(0, (Number(amount) || 0) - WITHDRAW_FEE_RATE[method].compute(Number(amount) || 0)), "TZS")}
              </span>
            </div>
          </div>
          {error && (
            <div className="flex items-center gap-2 bg-red-50 text-error rounded-lg px-4 py-3 text-sm">
              <Icon name="error" className="text-[18px]" />
              {error}
            </div>
          )}
          <button
            className="w-full sm:w-auto bg-primary-container text-on-primary text-sm font-medium py-3 px-8 rounded-lg hover:opacity-90 transition-opacity flex items-center justify-center gap-2 disabled:opacity-60"
            type="submit"
            disabled={submitting}
          >
            <Icon name="send" className="text-[20px]" />
            {submitting ? "Requesting…" : "Request Withdrawal"}
          </button>
        </form>
      </Card>

      <Card padded={false}>
        <div className="p-5 pb-3">
          <h3 className="text-2xl font-semibold text-on-background">Withdrawal History</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left min-w-[860px]">
            <thead>
              <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                <th className={thClass}>Date</th>
                <th className={thClass}>Destination</th>
                <th className={thClass}>Method</th>
                <th className={thClass}>Amount</th>
                <th className={thClass}>Reference</th>
                <th className={thClass}>Status</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {disbursements.map((disbursement) => {
                const badge = disbursementBadge(disbursement.status);
                return (
                  <tr key={disbursement.id} className="border-t border-surface-container-highest">
                    <td className={`${tdClass} text-on-surface-variant text-xs`}>{formatDateTime(disbursement.initiated_at)}</td>
                    <td className={`${tdClass} font-medium text-on-background`}>{disbursement.destination_name}</td>
                    <td className={`${tdClass} text-on-surface-variant`}>{DISBURSEMENT_METHOD_LABELS[disbursement.method]}</td>
                    <td className={`${tdClass} font-semibold text-on-background`}>{formatCurrency(disbursement.amount, disbursement.currency)}</td>
                    <td className={`${tdClass} text-on-surface-variant text-xs font-mono`}>
                      {disbursement.transaction_reference ?? disbursement.provider_reference ?? "—"}
                    </td>
                    <td className={tdClass}>
                      <StatusBadge {...badge} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
