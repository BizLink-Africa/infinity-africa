import { notFound } from "next/navigation";
import Link from "next/link";

import { Card, tdClass, thClass } from "@/components/portal/card";
import { Icon } from "@/components/portal/icon";
import { PageHeader } from "@/components/portal/page-header";
import { StatusBadge } from "@/components/portal/status-badge";
import { formatCurrency, formatDateTime } from "@/lib/format";
import {
  disableProductionApiAccessAction,
  enableProductionApiAccessAction,
  approveIpAllowlistEntryAction,
  rejectIpAllowlistEntryAction,
} from "@/lib/admin/live-actions";
import {
  getAdminMerchant,
  listAdminCollections,
  listAdminInvoices,
  listAdminIpAllowlist,
  listAdminMerchantApiKeys,
  listAdminPaymentLinks,
  listAdminRiskAlerts,
  listAdminWithdrawals,
  listPricingRulesForMerchant,
} from "@/lib/admin/live-api";
import { getOnboardingSubmission } from "@/lib/onboarding/api";
import { merchantStatusBadge } from "@/lib/admin/status-tones";

export const metadata = {
  title: "Merchant Detail | Infinity Africa Super Admin",
};

function SectionCard({ title, viewAllHref, children }: { title: string; viewAllHref?: string; children: React.ReactNode }) {
  return (
    <Card padded={false}>
      <div className="p-5 pb-3 flex items-center justify-between">
        <h3 className="text-xl font-semibold text-on-background">{title}</h3>
        {viewAllHref && (
          <Link href={viewAllHref} className="text-xs font-semibold text-primary hover:underline">
            View all
          </Link>
        )}
      </div>
      {children}
    </Card>
  );
}

function EmptyRow({ label }: { label: string }) {
  return <p className="px-5 pb-5 text-sm text-on-surface-variant">{label}</p>;
}

export default async function SuperAdminMerchantDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: merchantId } = await params;

  const merchant = await getAdminMerchant(merchantId);
  if (!merchant) notFound();

  const [collections, paymentLinks, invoices, apiKeys, withdrawals, pricingRules, kyc, riskAlerts, ipAllowlist] =
    await Promise.all([
      listAdminCollections({ merchantId }),
      listAdminPaymentLinks({ merchantId }),
      listAdminInvoices({ merchantId }),
      listAdminMerchantApiKeys(merchantId),
      listAdminWithdrawals({ merchantId }),
      listPricingRulesForMerchant(merchantId),
      getOnboardingSubmission(merchantId),
      listAdminRiskAlerts({ merchantId }),
      listAdminIpAllowlist({ merchantId }),
    ]);

  const totalCollected = collections
    .filter((c) => c.status === "successful")
    .reduce((sum, c) => sum + Number(c.net_amount ?? c.amount), 0);
  const totalWithdrawn = withdrawals
    .filter((w) => w.status === "SUCCESS")
    .reduce((sum, w) => sum + Number(w.amount), 0);
  const openAlerts = riskAlerts.filter((a) => a.status === "OPEN" || a.status === "UNDER_REVIEW").length;

  const badge = merchantStatusBadge(merchant.account_status);

  return (
    <div className="space-y-8">
      <PageHeader
        title={merchant.business_name}
        description={`${merchant.email}${merchant.contact_phone ? ` · ${merchant.contact_phone}` : ""}`}
        action={<StatusBadge {...badge} />}
      />

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide mb-1.5">
              Production API Access
            </p>
            <p className="text-sm text-on-surface-variant">
              {merchant.api_production_enabled
                ? "Enabled — this merchant can create and use live API keys."
                : "Disabled — this merchant can only create sandbox API keys."}
            </p>
          </div>
          {merchant.api_production_enabled ? (
            <form action={disableProductionApiAccessAction.bind(null, merchantId)}>
              <button
                type="submit"
                className="border border-error text-error text-sm font-medium py-2 px-4 rounded-lg hover:bg-error-container/10 transition-colors"
              >
                Disable Production Access
              </button>
            </form>
          ) : (
            <form action={enableProductionApiAccessAction.bind(null, merchantId)}>
              <button
                type="submit"
                disabled={merchant.account_status !== "active" || merchant.kyc_status !== "verified"}
                title={
                  merchant.account_status !== "active" || merchant.kyc_status !== "verified"
                    ? "This merchant must be approved and KYC-verified first"
                    : undefined
                }
                className="bg-primary-container text-on-primary text-sm font-medium py-2 px-4 rounded-lg hover:opacity-90 transition-opacity disabled:opacity-60"
              >
                Enable Production Access
              </button>
            </form>
          )}
        </div>
      </Card>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
        <Card>
          <p className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide mb-2">Available Balance</p>
          <p className="text-2xl font-bold text-on-background">{formatCurrency(merchant.available_balance, "TZS")}</p>
        </Card>
        <Card>
          <p className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide mb-2">Total Collected</p>
          <p className="text-2xl font-bold text-on-background">{formatCurrency(String(totalCollected), "TZS")}</p>
        </Card>
        <Card>
          <p className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide mb-2">Total Withdrawn</p>
          <p className="text-2xl font-bold text-on-background">{formatCurrency(String(totalWithdrawn), "TZS")}</p>
        </Card>
        <Card>
          <p className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide mb-2">Open Risk Alerts</p>
          <p className={`text-2xl font-bold ${openAlerts > 0 ? "text-error" : "text-on-background"}`}>{openAlerts}</p>
        </Card>
      </div>

      <SectionCard title="Collections" viewAllHref={`/super-admin/collections?merchant_id=${merchantId}`}>
        {collections.length === 0 ? (
          <EmptyRow label="No collections yet." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left min-w-[700px]">
              <thead>
                <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                  <th className={thClass}>Source</th>
                  <th className={thClass}>Method</th>
                  <th className={thClass}>Amount</th>
                  <th className={thClass}>Status</th>
                  <th className={thClass}>Date</th>
                </tr>
              </thead>
              <tbody className="text-sm">
                {collections.slice(0, 10).map((row) => (
                  <tr key={row.collection_id} className="border-t border-surface-container-highest">
                    <td className={`${tdClass} text-xs text-on-surface-variant`}>{row.source ?? "—"}</td>
                    <td className={tdClass}>{row.method}</td>
                    <td className={`${tdClass} font-semibold`}>{formatCurrency(row.amount, row.currency)}</td>
                    <td className={tdClass}>{row.status}</td>
                    <td className={`${tdClass} text-xs text-on-surface-variant`}>{formatDateTime(row.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SectionCard title="Payment Links">
          {paymentLinks.length === 0 ? (
            <EmptyRow label="No payment links yet." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left min-w-[500px]">
                <thead>
                  <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                    <th className={thClass}>Amount</th>
                    <th className={thClass}>Status</th>
                    <th className={thClass}>Created</th>
                  </tr>
                </thead>
                <tbody className="text-sm">
                  {paymentLinks.slice(0, 10).map((row) => (
                    <tr key={row.link_id} className="border-t border-surface-container-highest">
                      <td className={`${tdClass} font-semibold`}>{formatCurrency(row.amount, row.currency)}</td>
                      <td className={tdClass}>{row.status}</td>
                      <td className={`${tdClass} text-xs text-on-surface-variant`}>{formatDateTime(row.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>

        <SectionCard title="Invoices">
          {invoices.length === 0 ? (
            <EmptyRow label="No invoices yet." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left min-w-[500px]">
                <thead>
                  <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                    <th className={thClass}>Invoice</th>
                    <th className={thClass}>Amount</th>
                    <th className={thClass}>Status</th>
                  </tr>
                </thead>
                <tbody className="text-sm">
                  {invoices.slice(0, 10).map((row) => (
                    <tr key={row.invoice_id} className="border-t border-surface-container-highest">
                      <td className={`${tdClass} text-xs font-mono`}>{row.invoice_number}</td>
                      <td className={`${tdClass} font-semibold`}>{formatCurrency(row.total_amount, "TZS")}</td>
                      <td className={tdClass}>{row.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>

        <SectionCard title="API Keys">
          {apiKeys.length === 0 ? (
            <EmptyRow label="No API keys issued." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left min-w-[500px]">
                <thead>
                  <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                    <th className={thClass}>Name</th>
                    <th className={thClass}>Environment</th>
                    <th className={thClass}>Status</th>
                  </tr>
                </thead>
                <tbody className="text-sm">
                  {apiKeys.map((row) => (
                    <tr key={row.id} className="border-t border-surface-container-highest">
                      <td className={tdClass}>
                        <div className="font-medium">{row.name}</div>
                        <div className="text-xs font-mono text-on-surface-variant">{row.key_prefix}…</div>
                      </td>
                      <td className={`${tdClass} text-xs`}>{row.environment}</td>
                      <td className={tdClass}>{row.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>

        <SectionCard title="Withdrawals" viewAllHref={`/super-admin/withdrawals?merchant_id=${merchantId}`}>
          {withdrawals.length === 0 ? (
            <EmptyRow label="No withdrawals yet." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left min-w-[500px]">
                <thead>
                  <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                    <th className={thClass}>Amount</th>
                    <th className={thClass}>Status</th>
                    <th className={thClass}>Date</th>
                  </tr>
                </thead>
                <tbody className="text-sm">
                  {withdrawals.slice(0, 10).map((row) => (
                    <tr key={row.withdrawal_id} className="border-t border-surface-container-highest">
                      <td className={`${tdClass} font-semibold`}>{formatCurrency(row.amount, row.currency)}</td>
                      <td className={tdClass}>{row.status}</td>
                      <td className={`${tdClass} text-xs text-on-surface-variant`}>{formatDateTime(row.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>

        <SectionCard title="Pricing Rules" viewAllHref={`/super-admin/pricing-rules?merchant_id=${merchantId}`}>
          {pricingRules.length === 0 ? (
            <EmptyRow label="No merchant-specific pricing — platform fallback applies." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left min-w-[500px]">
                <thead>
                  <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                    <th className={thClass}>Label</th>
                    <th className={thClass}>Fee</th>
                    <th className={thClass}>Active</th>
                  </tr>
                </thead>
                <tbody className="text-sm">
                  {pricingRules.map((row) => (
                    <tr key={row.id} className="border-t border-surface-container-highest">
                      <td className={tdClass}>{row.label ?? row.channel ?? "General"}</td>
                      <td className={tdClass}>
                        {row.percentage_fee}% + {formatCurrency(row.flat_fee, "TZS")}
                      </td>
                      <td className={tdClass}>{row.is_active ? "Yes" : "No"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>

        <SectionCard title="Risk / Fraud Alerts">
          {riskAlerts.length === 0 ? (
            <EmptyRow label="No fraud alerts recorded." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left min-w-[500px]">
                <thead>
                  <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                    <th className={thClass}>Rule</th>
                    <th className={thClass}>Level</th>
                    <th className={thClass}>Status</th>
                  </tr>
                </thead>
                <tbody className="text-sm">
                  {riskAlerts.slice(0, 10).map((row) => (
                    <tr key={row.alert_id} className="border-t border-surface-container-highest">
                      <td className={`${tdClass} text-xs`}>{row.rule_code}</td>
                      <td className={tdClass}>{row.risk_level}</td>
                      <td className={tdClass}>{row.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>
        <SectionCard title="IP Allowlist">
          {ipAllowlist.length === 0 ? (
            <EmptyRow label="No IP addresses configured — production keys are unrestricted." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left min-w-[560px]">
                <thead>
                  <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                    <th className={thClass}>IP / CIDR</th>
                    <th className={thClass}>Environment</th>
                    <th className={thClass}>Status</th>
                    <th className={`${thClass} text-right`}>Actions</th>
                  </tr>
                </thead>
                <tbody className="text-sm">
                  {ipAllowlist.map((row) => (
                    <tr key={row.id} className="border-t border-surface-container-highest">
                      <td className={tdClass}>
                        <div className="font-mono text-xs">{row.ip_address_or_cidr}</div>
                        <div className="text-xs text-on-surface-variant">{row.label}</div>
                      </td>
                      <td className={`${tdClass} text-xs capitalize`}>{row.environment}</td>
                      <td className={tdClass}>{row.status}</td>
                      <td className={`${tdClass} text-right whitespace-nowrap`}>
                        {row.status === "pending" && (
                          <div className="flex items-center justify-end gap-1">
                            <form action={approveIpAllowlistEntryAction.bind(null, row.id, merchantId)}>
                              <button type="submit" className="p-1.5 text-on-surface-variant hover:text-primary" title="Approve">
                                <Icon name="check_circle" className="text-[18px]" />
                              </button>
                            </form>
                            <form action={rejectIpAllowlistEntryAction.bind(null, row.id, merchantId)}>
                              <button type="submit" className="p-1.5 text-on-surface-variant hover:text-error" title="Reject">
                                <Icon name="cancel" className="text-[18px]" />
                              </button>
                            </form>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>
      </div>

      <SectionCard title="KYC Documents">
        {!kyc || kyc.documents.length === 0 ? (
          <EmptyRow label="No KYC documents uploaded yet." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left min-w-[600px]">
              <thead>
                <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                  <th className={thClass}>Document</th>
                  <th className={thClass}>Status</th>
                  <th className={thClass}>Uploaded</th>
                  <th className={`${thClass} text-right`}>File</th>
                </tr>
              </thead>
              <tbody className="text-sm">
                {kyc.documents.map((doc) => (
                  <tr key={doc.id} className="border-t border-surface-container-highest">
                    <td className={tdClass}>
                      {doc.document_type}
                      {doc.document_type === "BUSINESS_LICENCE" && (
                        <span className="ml-2 text-xs text-on-surface-variant">(optional)</span>
                      )}
                    </td>
                    <td className={tdClass}>{doc.upload_status}</td>
                    <td className={`${tdClass} text-xs text-on-surface-variant`}>{formatDateTime(doc.uploaded_at)}</td>
                    <td className={`${tdClass} text-right`}>
                      {doc.signed_url ? (
                        <a href={doc.signed_url} target="_blank" rel="noreferrer" className="text-primary hover:underline">
                          <Icon name="description" className="text-[18px]" />
                        </a>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </div>
  );
}
