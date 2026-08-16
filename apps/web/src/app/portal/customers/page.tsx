"use client";

import { useEffect, useState } from "react";

import { Card, tdClass, thClass } from "@/components/portal/card";
import { Icon } from "@/components/portal/icon";
import { PageHeader } from "@/components/portal/page-header";
import { StatusBadge } from "@/components/portal/status-badge";
import { formatCurrency, formatDateTime } from "@/lib/format";
import { createCustomer, listCustomers } from "@/lib/portal/api";
import type { Customer } from "@/lib/portal/types";

export default function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    listCustomers().then(setCustomers);
  }, []);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!name) return;

    setSubmitting(true);
    try {
      const customer = await createCustomer({ name, phone: phone || null, email: email || null });
      setCustomers((prev) => [customer, ...prev]);
      setName("");
      setPhone("");
      setEmail("");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title="Customers"
        description="Everyone who has paid you, in one place."
        action={
          <a
            href="#add-customer"
            className="flex items-center justify-center gap-2 bg-primary-container text-on-primary px-4 py-2.5 rounded-lg text-sm font-medium hover:opacity-90 transition-opacity w-fit"
          >
            <Icon name="person_add" className="text-[18px]" />
            Add Customer
          </a>
        }
      />

      <Card id="add-customer" className="scroll-mt-24">
        <h3 className="text-2xl font-semibold text-on-background mb-5">Add Customer</h3>
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1.5" htmlFor="new-cust-name">
                Name
              </label>
              <input
                id="new-cust-name"
                className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary text-sm"
                placeholder="e.g. Baraka Mushi"
                type="text"
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1.5" htmlFor="new-cust-phone">
                Phone
              </label>
              <input
                id="new-cust-phone"
                className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary text-sm"
                placeholder="+255 7XX XXX XXX"
                type="tel"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1.5" htmlFor="new-cust-email">
                Email
              </label>
              <input
                id="new-cust-email"
                className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary text-sm"
                placeholder="e.g. baraka@example.com"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </div>
          </div>
          <button
            className="w-full sm:w-auto bg-primary-container text-on-primary text-sm font-medium py-3 px-6 rounded-lg hover:opacity-90 transition-opacity flex items-center justify-center gap-2 disabled:opacity-60"
            type="submit"
            disabled={submitting}
          >
            <Icon name="save" className="text-[20px]" />
            {submitting ? "Saving…" : "Save Customer"}
          </button>
        </form>
      </Card>

      <Card padded={false}>
        <div className="p-5 pb-3">
          <h3 className="text-2xl font-semibold text-on-background">All Customers</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left min-w-[720px]">
            <thead>
              <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                <th className={thClass}>Customer</th>
                <th className={thClass}>Phone</th>
                <th className={thClass}>Total Spent</th>
                <th className={thClass}>Last Transaction</th>
                <th className={thClass}>Status</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {customers.map((customer) => (
                <tr key={customer.id} className="border-t border-surface-container-highest">
                  <td className={tdClass}>
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-primary-container/15 text-primary flex items-center justify-center font-bold text-xs shrink-0">
                        {customer.name.charAt(0)}
                      </div>
                      <span className="font-medium text-on-background">{customer.name}</span>
                    </div>
                  </td>
                  <td className={`${tdClass} text-on-surface-variant`}>{customer.phone ?? customer.email ?? "—"}</td>
                  <td className={`${tdClass} font-semibold text-on-background`}>{formatCurrency(customer.total_spent, "TZS")}</td>
                  <td className={`${tdClass} text-on-surface-variant text-xs`}>
                    {customer.last_transaction_at ? formatDateTime(customer.last_transaction_at) : "—"}
                  </td>
                  <td className={tdClass}>
                    {customer.status === "active" ? (
                      <StatusBadge label="Active" tone="positive" dot />
                    ) : (
                      <StatusBadge label="Inactive" tone="neutral" />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
