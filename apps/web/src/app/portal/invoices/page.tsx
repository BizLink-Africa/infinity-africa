"use client";

import { useEffect, useMemo, useState } from "react";

import { Card, tdClass, thClass } from "@/components/portal/card";
import { Icon } from "@/components/portal/icon";
import { PageHeader } from "@/components/portal/page-header";
import { StatusBadge } from "@/components/portal/status-badge";
import { formatCurrency } from "@/lib/format";
import { createInvoice, listInvoices } from "@/lib/portal/api";
import { invoiceBadge } from "@/lib/portal/status-tones";
import type { Invoice } from "@/lib/portal/types";

interface DraftItem {
  key: number;
  description: string;
  quantity: string;
  unitPrice: string;
}

let draftKey = 0;
function emptyItem(): DraftItem {
  draftKey += 1;
  return { key: draftKey, description: "", quantity: "1", unitPrice: "" };
}

const FILTERS = ["All", "Unpaid", "Overdue"] as const;

export default function InvoicesPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("All");
  const [submitting, setSubmitting] = useState(false);

  const [customerName, setCustomerName] = useState("");
  const [customerContact, setCustomerContact] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [notes, setNotes] = useState("");
  const [items, setItems] = useState<DraftItem[]>([emptyItem(), emptyItem()]);

  useEffect(() => {
    listInvoices().then(setInvoices);
  }, []);

  const total = useMemo(
    () => items.reduce((sum, item) => sum + (Number(item.quantity) || 0) * (Number(item.unitPrice) || 0), 0),
    [items],
  );

  const filtered = useMemo(() => {
    if (filter === "All") return invoices;
    if (filter === "Overdue") return invoices.filter((invoice) => invoice.status === "OVERDUE");
    return invoices.filter((invoice) => ["SENT", "PARTIALLY_PAID", "OVERDUE"].includes(invoice.status));
  }, [invoices, filter]);

  function updateItem(key: number, patch: Partial<DraftItem>) {
    setItems((prev) => prev.map((item) => (item.key === key ? { ...item, ...patch } : item)));
  }

  function addItem() {
    setItems((prev) => [...prev, emptyItem()]);
  }

  function removeItem(key: number) {
    setItems((prev) => (prev.length > 1 ? prev.filter((item) => item.key !== key) : prev));
  }

  async function handleSubmit(sendNow: boolean) {
    const validItems = items.filter((item) => item.description && Number(item.unitPrice) > 0);
    if (!customerName || validItems.length === 0 || !dueDate) return;

    setSubmitting(true);
    try {
      const invoice = await createInvoice({
        customer_name: customerName,
        customer_phone: customerContact.includes("@") ? null : customerContact || null,
        customer_email: customerContact.includes("@") ? customerContact : null,
        due_date: dueDate,
        notes: notes || null,
        send_now: sendNow,
        items: validItems.map((item) => ({
          description: item.description,
          quantity: item.quantity,
          unit_price: item.unitPrice,
        })),
      });
      setInvoices((prev) => [invoice, ...prev]);
      setCustomerName("");
      setCustomerContact("");
      setDueDate("");
      setNotes("");
      setItems([emptyItem(), emptyItem()]);
    } finally {
      setSubmitting(false);
    }
  }

  const nextInvoiceNumber = `INV-${1043 + invoices.length}`;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Invoices"
        description="Bill your customers with itemized invoices and built-in Pay Now links."
        action={
          <a
            href="#create-invoice"
            className="flex items-center justify-center gap-2 bg-primary-container text-on-primary px-4 py-2.5 rounded-lg text-sm font-medium hover:opacity-90 transition-opacity w-fit"
          >
            <Icon name="add" className="text-[18px]" />
            New Invoice
          </a>
        }
      />

      <div className="flex flex-wrap gap-2">
        <StatusBadge label="Draft" tone="neutral" />
        <StatusBadge label="Sent" tone="info" />
        <StatusBadge label="Paid" tone="positive-solid" icon="check" />
        <StatusBadge label="Partially Paid" tone="pending" />
        <StatusBadge label="Overdue" tone="negative" />
        <StatusBadge label="Cancelled" tone="neutral" strikethrough />
      </div>

      <Card id="create-invoice" className="scroll-mt-24">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-2xl font-semibold text-on-background">Create Invoice</h3>
          <span className="text-xs font-semibold text-on-surface-variant bg-surface-container-low px-3 py-1.5 rounded-full">
            Invoice # {nextInvoiceNumber}
          </span>
        </div>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            handleSubmit(true);
          }}
          className="space-y-6"
        >
          <div className="grid sm:grid-cols-2 gap-5">
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1.5">Customer Name</label>
              <input
                className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary text-sm"
                placeholder="e.g. Juma Traders Ltd"
                type="text"
                value={customerName}
                onChange={(event) => setCustomerName(event.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1.5">Customer Phone / Email</label>
              <input
                className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary text-sm"
                placeholder="+255 7XX XXX XXX or email"
                type="text"
                value={customerContact}
                onChange={(event) => setCustomerContact(event.target.value)}
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-on-surface-variant mb-2">Items / Services</label>
            <div className="border border-surface-container-highest rounded-lg overflow-hidden">
              <div className="hidden sm:grid grid-cols-12 gap-2 bg-surface-container-low px-4 py-2 text-xs font-semibold text-on-surface-variant">
                <div className="col-span-5">Description</div>
                <div className="col-span-2">Qty</div>
                <div className="col-span-2">Unit Price</div>
                <div className="col-span-2 text-right">Amount</div>
                <div className="col-span-1" />
              </div>
              {items.map((item) => {
                const lineTotal = (Number(item.quantity) || 0) * (Number(item.unitPrice) || 0);
                return (
                  <div key={item.key} className="grid grid-cols-12 gap-2 px-4 py-3 items-center border-t border-surface-container-highest">
                    <input
                      className="col-span-12 sm:col-span-5 px-3 py-2 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm"
                      placeholder="e.g. Wholesale delivery — 50kg bags"
                      value={item.description}
                      onChange={(event) => updateItem(item.key, { description: event.target.value })}
                    />
                    <input
                      className="col-span-4 sm:col-span-2 px-3 py-2 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm"
                      type="number"
                      min="1"
                      value={item.quantity}
                      onChange={(event) => updateItem(item.key, { quantity: event.target.value })}
                    />
                    <input
                      className="col-span-4 sm:col-span-2 px-3 py-2 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm"
                      type="number"
                      min="0"
                      placeholder="70,000"
                      value={item.unitPrice}
                      onChange={(event) => updateItem(item.key, { unitPrice: event.target.value })}
                    />
                    <div className="col-span-3 sm:col-span-2 text-right font-semibold text-sm text-on-background">
                      {lineTotal > 0 ? lineTotal.toLocaleString() : "—"}
                    </div>
                    <button
                      type="button"
                      onClick={() => removeItem(item.key)}
                      className="col-span-1 flex justify-end text-on-surface-variant hover:text-error"
                      title="Remove item"
                    >
                      <Icon name="close" className="text-[18px]" />
                    </button>
                  </div>
                );
              })}
              <div className="flex items-center justify-between px-4 py-3 border-t border-surface-container-highest bg-surface-container-low/50">
                <button className="flex items-center gap-1 text-primary text-sm font-semibold" type="button" onClick={addItem}>
                  <Icon name="add_circle" className="text-[18px]" />
                  Add Item
                </button>
                <div className="text-right">
                  <span className="text-xs text-on-surface-variant mr-2">Total Amount</span>
                  <span className="text-2xl font-semibold text-on-background">{formatCurrency(String(total), "TZS")}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="grid sm:grid-cols-2 gap-5">
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1.5">Due Date</label>
              <input
                className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary text-sm"
                type="date"
                value={dueDate}
                onChange={(event) => setDueDate(event.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1.5">Notes (optional)</label>
              <input
                className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary text-sm"
                placeholder="Payment due within 14 days of receipt"
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
              />
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-3 pt-2">
            <button
              className="flex-1 bg-primary-container text-on-primary text-sm font-medium py-3 rounded-lg hover:opacity-90 transition-opacity flex items-center justify-center gap-2 disabled:opacity-60"
              type="submit"
              disabled={submitting}
            >
              <Icon name="send" className="text-[20px]" />
              Send Invoice with Pay Now Link
            </button>
            <button
              className="flex-1 sm:flex-none bg-surface border border-outline-variant text-on-surface text-sm font-medium py-3 px-6 rounded-lg hover:bg-surface-container-low transition-colors disabled:opacity-60"
              type="button"
              disabled={submitting}
              onClick={() => handleSubmit(false)}
            >
              Save as Draft
            </button>
          </div>
          <div className="bg-surface-container-low rounded-lg px-4 py-3 flex items-center gap-2 text-sm text-on-surface-variant">
            <Icon name="link" className="text-[18px] text-primary" />
            Pay Now link will be generated automatically:{" "}
            <span className="font-mono text-on-background">pay.infinityafrica.net/inv/{nextInvoiceNumber}</span>
          </div>
        </form>
      </Card>

      <Card padded={false}>
        <div className="flex flex-wrap items-center justify-between gap-3 p-5 pb-3">
          <h3 className="text-2xl font-semibold text-on-background">All Invoices</h3>
          <div className="flex flex-wrap gap-2">
            {FILTERS.map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setFilter(option)}
                className={
                  filter === option
                    ? "px-3 py-1.5 rounded-full bg-primary-container/10 text-primary text-xs font-semibold"
                    : "px-3 py-1.5 rounded-full text-on-surface-variant text-xs font-semibold hover:bg-surface-container-low"
                }
              >
                {option}
              </button>
            ))}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left min-w-[860px]">
            <thead>
              <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                <th className={thClass}>Invoice</th>
                <th className={thClass}>Customer</th>
                <th className={thClass}>Amount</th>
                <th className={thClass}>Due Date</th>
                <th className={thClass}>Status</th>
                <th className={`${thClass} text-right`}>Actions</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {filtered.map((invoice) => {
                const badge = invoiceBadge(invoice.status);
                return (
                  <tr key={invoice.id} className="border-t border-surface-container-highest">
                    <td className={`${tdClass} font-mono text-on-background`}>{invoice.invoice_number}</td>
                    <td className={`${tdClass} text-on-surface`}>{invoice.customer_name}</td>
                    <td className={`${tdClass} font-semibold text-on-background`}>{formatCurrency(invoice.total_amount, invoice.currency)}</td>
                    <td className={`${tdClass} text-xs ${invoice.status === "OVERDUE" ? "text-error font-semibold" : "text-on-surface-variant"}`}>
                      {invoice.status === "DRAFT" ? "—" : new Date(invoice.due_date).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })}
                    </td>
                    <td className={tdClass}>
                      <StatusBadge {...badge} />
                    </td>
                    <td className={`${tdClass} text-right`}>
                      <button className="p-1.5 text-on-surface-variant hover:text-primary" title="Copy Pay Now link">
                        <Icon name="content_copy" className="text-[18px]" />
                      </button>
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
