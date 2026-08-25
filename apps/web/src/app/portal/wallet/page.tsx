"use client";

import { useEffect, useState } from "react";

import { Card, tdClass, thClass } from "@/components/portal/card";
import { Icon } from "@/components/portal/icon";
import { KpiCard } from "@/components/portal/kpi-card";
import { PageHeader } from "@/components/portal/page-header";
import { StatusBadge } from "@/components/portal/status-badge";
import { formatCurrency, formatDateTime } from "@/lib/format";
import { getAvailableBalance, getMyMerchant, listWalletLedger } from "@/lib/portal/api";
import type { WalletLedgerEntry } from "@/lib/portal/types";

const CSV_HEADER = [
  "Date",
  "Transaction ID",
  "Description",
  "Direction",
  "Opening Balance",
  "Amount",
  "Closing Balance",
];

function csvCell(value: string): string {
  return `"${value.replace(/"/g, '""')}"`;
}

function ledgerToCsv(ledger: WalletLedgerEntry[]): string {
  const rows = ledger.map((entry) =>
    [
      formatDateTime(entry.date),
      entry.transaction_id ?? "",
      entry.description,
      entry.direction,
      entry.balance_before,
      `${entry.direction === "credit" ? "+" : "-"}${entry.amount}`,
      entry.balance_after,
    ]
      .map(csvCell)
      .join(","),
  );
  return [CSV_HEADER.map(csvCell).join(","), ...rows].join("\r\n");
}

export default function WalletPage() {
  const [availableBalance, setAvailableBalance] = useState<string | null>(null);
  const [ledger, setLedger] = useState<WalletLedgerEntry[]>([]);
  const [merchantCode, setMerchantCode] = useState<string | null>(null);

  useEffect(() => {
    getAvailableBalance().then(setAvailableBalance);
    listWalletLedger().then(setLedger);
    getMyMerchant().then((merchant) => setMerchantCode(merchant?.merchant_code ?? null));
  }, []);

  function handleExportCsv() {
    const blob = new Blob([ledgerToCsv(ledger)], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `infinity-africa-wallet-ledger-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title="Wallet"
        description="Your available balance and wallet activity."
        action={
          merchantCode ? (
            <p className="text-xs text-on-surface-variant">
              Merchant ID: <span className="font-mono font-semibold text-on-background">{merchantCode}</span>
            </p>
          ) : undefined
        }
      />

      <section className="grid grid-cols-1 sm:max-w-xs gap-4">
        <KpiCard
          variant="brand"
          icon="account_balance_wallet"
          label="Available Balance"
          value={availableBalance !== null ? formatCurrency(availableBalance, "TZS") : "—"}
        />
      </section>

      <Card padded={false}>
        <div className="p-5 pb-3 flex items-center justify-between gap-3">
          <h3 className="text-2xl font-semibold text-on-background">Wallet Ledger</h3>
          <button
            type="button"
            onClick={handleExportCsv}
            disabled={ledger.length === 0}
            className="flex items-center gap-2 bg-surface border border-outline-variant text-on-surface px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-surface-container-low transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Icon name="download" className="text-[18px]" />
            Export to Excel (CSV)
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left min-w-[1020px]">
            <thead>
              <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                <th className={thClass}>Date</th>
                <th className={thClass}>Transaction ID</th>
                <th className={thClass}>Description</th>
                <th className={thClass}>Type</th>
                <th className={thClass}>Opening Balance</th>
                <th className={thClass}>Amount</th>
                <th className={thClass}>Closing Balance</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {ledger.length === 0 ? (
                <tr>
                  <td className={`${tdClass} text-on-surface-variant`} colSpan={7}>
                    No wallet activity yet.
                  </td>
                </tr>
              ) : (
                ledger.map((entry) => (
                  <tr key={entry.id} className="border-t border-surface-container-highest">
                    <td className={`${tdClass} text-on-surface-variant text-xs whitespace-nowrap`}>{formatDateTime(entry.date)}</td>
                    <td className={`${tdClass} font-mono text-xs text-on-surface-variant`}>
                      {entry.transaction_id ? entry.transaction_id.slice(0, 8) : "—"}
                    </td>
                    <td className={tdClass}>{entry.description}</td>
                    <td className={tdClass}>
                      {entry.direction === "credit" ? (
                        <StatusBadge label="Credit" tone="positive" dot />
                      ) : (
                        <StatusBadge label="Debit" tone="neutral" />
                      )}
                    </td>
                    <td className={`${tdClass} text-on-surface-variant whitespace-nowrap`}>
                      {formatCurrency(entry.balance_before, "TZS")}
                    </td>
                    <td className={`${tdClass} font-semibold ${entry.direction === "credit" ? "text-primary" : "text-on-background"} whitespace-nowrap`}>
                      {entry.direction === "credit" ? "+" : "-"}
                      {formatCurrency(entry.amount, "TZS")}
                    </td>
                    <td className={`${tdClass} font-semibold whitespace-nowrap`}>{formatCurrency(entry.balance_after, "TZS")}</td>
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
