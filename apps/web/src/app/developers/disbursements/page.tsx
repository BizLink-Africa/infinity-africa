import { Callout } from "@/components/docs/callout";
import { CodeBlock } from "@/components/docs/code-block";
import { DocsPager } from "@/components/docs/docs-pager";
import { EndpointRow } from "@/components/docs/endpoint-row";

export const metadata = {
  title: "Disbursements API",
};

export default function DisbursementsApiPage() {
  return (
    <div>
      <p className="text-xs font-semibold text-primary uppercase tracking-wide mb-2">API Reference</p>
      <h1 className="text-3xl md:text-4xl font-bold text-on-surface tracking-tight mb-4">Disbursements API</h1>
      <p className="text-lg text-on-surface-variant leading-relaxed mb-6 max-w-2xl">
        Send money out of your Infinity Africa balance — to a Selcom Pesa wallet, a mobile money number, or a bank account.
        Available balance is validated before anything is created.
      </p>

      <div className="mb-10 max-w-2xl">
        <Callout title="Withdrawals vs. Disbursements">
          In the Infinity Africa dashboard, merchants see this feature as <strong>Withdrawals</strong>. In the API, the
          technical endpoint may use <code className="font-mono text-xs">disbursements</code> for
          payment-provider compatibility.
        </Callout>
      </div>

      <section className="mb-12">
        <h2 className="text-xl font-semibold text-on-surface mb-3">Endpoints</h2>
        <div className="bg-surface-container-lowest border border-outline-variant/40 rounded-xl px-5">
          <EndpointRow method="POST" path="/v1/disbursements/selcom-pesa" description="Payout to a Selcom Pesa wallet — fastest, zero-fee route." auth="Idempotency-Key required" />
          <EndpointRow method="POST" path="/v1/disbursements/mobile-money" description="Payout to a mobile money number." auth="Idempotency-Key required" />
          <EndpointRow method="POST" path="/v1/disbursements/bank-account" description="Payout to a bank account (bank_name required)." auth="Idempotency-Key required" />
          <EndpointRow method="GET" path="/v1/disbursements" description="List disbursements (merchant_id required as a query param)." auth="dashboard or API key" />
          <EndpointRow method="GET" path="/v1/disbursements/{id}" description="Get a disbursement." auth="dashboard or API key" />
          <EndpointRow method="POST" path="/v1/disbursements/{id}/approve" description="Approve a payout held for high-value review." auth="super admin" />
          <EndpointRow method="POST" path="/v1/disbursements/{id}/reject" description="Reject it." auth="super admin" />
        </div>
      </section>

      <section className="mb-12">
        <h2 className="text-xl font-semibold text-on-surface mb-3">Request a payout</h2>
        <div className="space-y-4">
          <CodeBlock language="json — POST /v1/disbursements/mobile-money">{`{
  "merchant_id": "5c1f0b2a-3e21-4b9a-9c33-2f6a1d0e8b71",
  "amount": "80000.00",
  "destination_name": "Grace Mwakalinga",
  "destination_identifier": "+255754221908",
  "network": "M-Pesa"
}`}</CodeBlock>
          <CodeBlock language="json — 202 Accepted">{`{
  "success": true,
  "data": {
    "id": "c9d8e7f6-...",
    "merchant_id": "5c1f0b2a-3e21-4b9a-9c33-2f6a1d0e8b71",
    "method": "MOBILE_MONEY",
    "amount": "80000.00",
    "currency": "TZS",
    "destination_name": "Grace Mwakalinga",
    "destination_identifier": "+255754221908",
    "bank_name": null,
    "status": "SUCCESS",
    "requires_approval": false,
    "approved_by": null,
    "approved_at": null,
    "provider_reference": "MOCK-SELCOM-9F3A1C2B",
    "transaction_reference": "TXN-...",
    "fee_amount": "0.00",
    "net_amount": "80000.00",
    "initiated_at": "2026-08-14T09:00:00Z",
    "completed_at": "2026-08-14T09:00:02Z",
    "created_at": "2026-08-14T09:00:00Z",
    "updated_at": "2026-08-14T09:00:02Z"
  }
}`}</CodeBlock>
        </div>
        <p className="text-sm text-on-surface-variant leading-relaxed mt-4">
          For a bank account payout, add <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">bank_name</code> and
          set <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">destination_identifier</code> to
          the account number. <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">network</code> is
          optional and mobile-money-specific — omit it and Selcom detects the network automatically.
        </p>
      </section>

      <section className="mb-12">
        <h2 className="text-xl font-semibold text-on-surface mb-3">Insufficient balance</h2>
        <p className="text-sm text-on-surface-variant leading-relaxed mb-4">
          Before anything is created, Infinity Africa checks the amount against your current available balance. If it&apos;s
          not enough, you get a <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">409</code> and
          nothing is reserved or deducted:
        </p>
        <CodeBlock language="json — 409 Conflict">{`{
  "success": false,
  "error": {
    "code": "insufficient_balance",
    "message": "Insufficient balance: available TZS 45,000, requested TZS 80,000",
    "details": null
  }
}`}</CodeBlock>
      </section>

      <section className="mb-12">
        <h2 className="text-xl font-semibold text-on-surface mb-3">Unverified merchant</h2>
        <p className="text-sm text-on-surface-variant leading-relaxed mb-4">
          Withdrawals are only available to merchants who have completed onboarding verification. A merchant that
          isn&apos;t yet <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">active</code>/<code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">verified</code> gets
          the same <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">409</code> shape,
          before any balance check runs:
        </p>
        <CodeBlock language="json — 409 Conflict">{`{
  "success": false,
  "error": {
    "code": "withdrawal_restricted",
    "message": "Withdrawals require a verified, active merchant account. Complete onboarding verification first.",
    "details": null
  }
}`}</CodeBlock>
      </section>

      <section className="mb-12">
        <h2 className="text-xl font-semibold text-on-surface mb-3">Status lifecycle</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm border border-outline-variant/40 rounded-xl overflow-hidden">
            <thead className="bg-surface-container-low">
              <tr>
                <th className="px-4 py-2.5 font-semibold text-on-surface-variant">Status</th>
                <th className="px-4 py-2.5 font-semibold text-on-surface-variant">Meaning</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/30">
              {[
                ["PENDING", "Created. Held for approval if above the high-value threshold."],
                ["PROCESSING", "Balance reserved, payout sent to the provider."],
                ["SUCCESS", "Funds delivered. Terminal."],
                ["FAILED", "Provider declined — the balance reservation was automatically reversed."],
                ["REVERSED", "A previously-SUCCESS payout was later reversed."],
              ].map(([status, meaning]) => (
                <tr key={status}>
                  <td className="px-4 py-2.5 font-mono text-xs text-on-surface">{status}</td>
                  <td className="px-4 py-2.5 text-on-surface-variant">{meaning}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 className="text-xl font-semibold text-on-surface mb-3">High-value approval</h2>
        <Callout title="Large payouts are held for manual review">
          A disbursement above the platform&apos;s approval threshold comes back{" "}
          <code className="font-mono text-xs">PENDING</code> with <code className="font-mono text-xs">requires_approval: true</code> and
          is <em>not</em> sent to the provider until a super admin approves it. Poll{" "}
          <code className="font-mono text-xs">GET .../disbursements/{"{id}"}</code> or listen for{" "}
          <code className="font-mono text-xs">disbursement.success</code>/<code className="font-mono text-xs">disbursement.failed</code> to
          know the outcome.
        </Callout>
      </section>

      <DocsPager currentHref="/developers/disbursements" />
    </div>
  );
}
