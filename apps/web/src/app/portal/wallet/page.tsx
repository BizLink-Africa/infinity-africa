"use client";

import { useEffect, useState } from "react";

import { Card, tdClass, thClass } from "@/components/portal/card";
import { KpiCard } from "@/components/portal/kpi-card";
import { PageHeader } from "@/components/portal/page-header";
import { StatusBadge } from "@/components/portal/status-badge";
import { formatCurrency, formatDateTime } from "@/lib/format";
import { getAvailableBalance, listWalletLedger } from "@/lib/portal/api";
import type { WalletLedgerEntry } from "@/lib/portal/types";

export default function WalletPage() {
  const [availableBalance, setAvailableBalance] = useState<string | null>(null);
  const [ledger, setLedger] = useState<WalletLedgerEntry[]>([]);

  useEffect(() => {
    getAvailableBalance().then(setAvailableBalance);
    listWalletLedger().then(setLedger);
  }, []);

  return (
    <div className="space-y-8">
      <PageHeader title="Wallet" description="Your available balance and wallet activity." />

      <section className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <KpiCard
          icon="account_balance_wallet"
          label="Available Balance"
          value={availableBalance !== null ? formatCurrency(availableBalance, "TZS") : "—"}
          caption="Ready to withdraw"
        />
        {/* Infinity Africa doesn't track a separate "pending clearance" or
            "chargeback reserve" balance yet — shown honestly as unavailable
            rather than a fabricated number. */}
        <KpiCard icon="hourglass_empty" label="Pending Clearance" value="—" caption="Not tracked yet" />
        <KpiCard icon="lock" label="Reserved Funds" value="—" caption="Not tracked yet" />
      </section>

      <Card padded={false}>
        <div className="p-5 pb-3">
          <h3 className="text-2xl font-semibold text-on-background">Wallet Ledger</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left min-w-[760px]">
            <thead>
              <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                <th className={thClass}>Date</th>
                <th className={thClass}>Description</th>
                <th className={thClass}>Type</th>
                <th className={thClass}>Amount</th>
                <th className={thClass}>Balance After</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {ledger.length === 0 ? (
                <tr>
                  <td className={`${tdClass} text-on-surface-variant`} colSpan={5}>
                    No wallet activity yet.
                  </td>
                </tr>
              ) : (
                ledger.map((entry) => (
                  <tr key={entry.id} className="border-t border-surface-container-highest">
                    <td className={`${tdClass} text-on-surface-variant text-xs`}>{formatDateTime(entry.date)}</td>
                    <td className={tdClass}>{entry.description}</td>
                    <td className={tdClass}>
                      {entry.direction === "credit" ? (
                        <StatusBadge label="Credit" tone="positive" dot />
                      ) : (
                        <StatusBadge label="Debit" tone="neutral" />
                      )}
                    </td>
                    <td className={`${tdClass} font-semibold ${entry.direction === "credit" ? "text-primary" : "text-on-background"}`}>
                      {entry.direction === "credit" ? "+" : "-"}
                      {formatCurrency(entry.amount, "TZS")}
                    </td>
                    <td className={`${tdClass} font-semibold`}>{formatCurrency(entry.balance_after, "TZS")}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
