import { Callout } from "@/components/docs/callout";
import { CodeBlock } from "@/components/docs/code-block";
import { DocsPager } from "@/components/docs/docs-pager";
import { EndpointRow } from "@/components/docs/endpoint-row";

export const metadata = {
  title: "Collections API",
};

export default function CollectionsApiPage() {
  return (
    <div>
      <p className="text-xs font-semibold text-primary uppercase tracking-wide mb-2">API Reference</p>
      <h1 className="text-3xl md:text-4xl font-bold text-on-surface tracking-tight mb-4">Collections API</h1>
      <p className="text-lg text-on-surface-variant leading-relaxed mb-10 max-w-2xl">
        Pull a payment from a customer&apos;s phone. Four methods, one request shape: push a prompt to their handset
        (USSD Push, STK Push, or Selcom Pesa Push), or hand them a Dynamic QR code to scan — no phone number needed.
      </p>

      <section className="mb-12">
        <h2 className="text-xl font-semibold text-on-surface mb-3">Endpoints</h2>
        <div className="bg-surface-container-lowest border border-outline-variant/40 rounded-xl px-5">
          <EndpointRow method="POST" path="/v1/collections/ussd-push" description="Push a USSD prompt to the customer's phone." auth="Idempotency-Key required" />
          <EndpointRow method="POST" path="/v1/collections/stk-push" description="Push an STK (SIM Toolkit) prompt." auth="Idempotency-Key required" />
          <EndpointRow method="POST" path="/v1/collections/selcom-pesa-push" description="Push a Selcom Pesa wallet prompt." auth="Idempotency-Key required" />
          <EndpointRow method="POST" path="/v1/collections/dynamic-qr" description="Generate a scannable QR code — no phone number required." auth="Idempotency-Key required" />
          <EndpointRow method="GET" path="/v1/merchants/{merchant_id}/collections" description="List collections for a merchant." auth="dashboard" />
          <EndpointRow method="GET" path="/v1/merchants/{merchant_id}/collections/{collection_id}" description="Get a single collection." auth="dashboard" />
        </div>
      </section>

      <section className="mb-12">
        <h2 className="text-xl font-semibold text-on-surface mb-3">Push a collection</h2>
        <p className="text-sm text-on-surface-variant leading-relaxed mb-4">
          The three push endpoints share one request body — <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">customer_phone</code> is
          required for all three (validated: digits, optional leading <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">+</code>,
          9–15 digits). Which endpoint you call <em>is</em> the method — there&apos;s no separate <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">method</code> field
          to set.
        </p>
        <div className="space-y-4">
          <CodeBlock language="json — POST /v1/collections/stk-push">{`{
  "merchant_id": "5c1f0b2a-3e21-4b9a-9c33-2f6a1d0e8b71",
  "amount": "25000.00",
  "currency": "TZS",
  "customer_phone": "+255712345678",
  "merchant_reference": "ORDER-4821",
  "description": "2 bags of maize flour"
}`}</CodeBlock>
          <CodeBlock language="json — 202 Accepted">{`{
  "success": true,
  "data": {
    "id": "9b7e2c1a-...",
    "merchant_id": "5c1f0b2a-3e21-4b9a-9c33-2f6a1d0e8b71",
    "method": "STK_PUSH",
    "amount": "25000.00",
    "currency": "TZS",
    "customer_phone": "+255712345678",
    "merchant_reference": "ORDER-4821",
    "payment_link_id": null,
    "invoice_id": null,
    "status": "processing",
    "provider": "mock_selcom",
    "provider_reference": "MOCK-SELCOM-9F3A1C2B",
    "transaction_reference": "TXN-...",
    "message": "An STK push was sent to the customer's phone — awaiting approval.",
    "expires_at": null,
    "initiated_at": "2026-08-14T09:00:00Z",
    "completed_at": null,
    "created_at": "2026-08-14T09:00:00Z",
    "updated_at": "2026-08-14T09:00:00Z"
  }
}`}</CodeBlock>
        </div>
      </section>

      <section className="mb-12">
        <h2 className="text-xl font-semibold text-on-surface mb-3">Generate a Dynamic QR code</h2>
        <p className="text-sm text-on-surface-variant leading-relaxed mb-4">
          <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">/v1/collections/dynamic-qr</code> omits{" "}
          <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">customer_phone</code> entirely and returns
          two extra fields your app renders as a scannable code:
        </p>
        <CodeBlock language="json — 202 Accepted">{`{
  "success": true,
  "data": {
    "id": "2d4f8a91-...",
    "method": "DYNAMIC_QR",
    "amount": "15000.00",
    "currency": "TZS",
    "status": "processing",
    "qr_payload": "selcompay://qr?ref=MOCK-SELCOM-7C1E&amount=15000&currency=TZS",
    "qr_expires_at": "2026-08-14T09:05:00Z",
    "qr_image_url": null,
    "expires_at": "2026-08-14T09:05:00Z",
    "message": "Scan the QR code with a mobile money app to complete payment.",
    "...": "same fields as a push collection"
  }
}`}</CodeBlock>
        <p className="text-xs text-on-surface-variant leading-relaxed mt-3">
          <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">qr_image_url</code> is
          always <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">null</code> today —
          render <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">qr_payload</code> as
          a QR code client-side (e.g. with any standard QR-rendering library).
        </p>
      </section>

      <section className="mb-12">
        <h2 className="text-xl font-semibold text-on-surface mb-3">Request fields</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm border border-outline-variant/40 rounded-xl overflow-hidden">
            <thead className="bg-surface-container-low">
              <tr>
                <th className="px-4 py-2.5 font-semibold text-on-surface-variant">Field</th>
                <th className="px-4 py-2.5 font-semibold text-on-surface-variant">Type</th>
                <th className="px-4 py-2.5 font-semibold text-on-surface-variant">Notes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/30">
              {[
                ["merchant_id", "uuid", "Your merchant account ID."],
                ["amount", "decimal string", "Must be greater than 0."],
                ["currency", "string", 'Defaults to "TZS".'],
                ["customer_phone", "string", "Required on all push endpoints; omitted on dynamic-qr."],
                ["customer_id", "uuid, optional", "Link this collection to a saved customer."],
                ["customer_name", "string, optional", "Shown in the merchant dashboard alongside the collection."],
                ["customer_email", "string, optional", "Shown in the merchant dashboard alongside the collection."],
                ["merchant_reference", "string, optional", "Your own order/reference — max 100 characters."],
                ["payment_link_id", "uuid, optional", "Cross-validated: must belong to this merchant, be ACTIVE, and accept this method."],
                ["invoice_id", "uuid, optional", "Links this collection to an invoice — marked paid once the collection resolves successfully."],
                ["description", "string, optional", "Shown in the merchant dashboard."],
                ["callback_url", "string, optional", "Recorded alongside the collection; webhooks remain the delivery mechanism (see below)."],
              ].map(([field, type, notes]) => (
                <tr key={field}>
                  <td className="px-4 py-2.5 font-mono text-xs text-on-surface">{field}</td>
                  <td className="px-4 py-2.5 text-on-surface-variant">{type}</td>
                  <td className="px-4 py-2.5 text-on-surface-variant">{notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 className="text-xl font-semibold text-on-surface mb-3">Resolving a collection</h2>
        <p className="text-sm text-on-surface-variant leading-relaxed mb-4">
          A push or QR collection always comes back <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">status: &quot;processing&quot;</code> —
          the customer still has to approve it on their phone. It resolves to{" "}
          <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">successful</code> or{" "}
          <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">failed</code> asynchronously — listen for the{" "}
          <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">collection.success</code> /{" "}
          <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">collection.failed</code> webhook, or poll{" "}
          <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">GET .../collections/{"{collection_id}"}</code>.
        </p>
        <Callout title="Webhooks are the reliable way to resolve a collection">
          Don&apos;t block a customer-facing flow on polling — subscribe to{" "}
          <code className="font-mono text-xs">collection.success</code>/<code className="font-mono text-xs">collection.failed</code> on the{" "}
          <a href="/developers/webhooks" className="text-primary font-semibold hover:underline">
            Webhooks
          </a>{" "}
          page instead.
        </Callout>
      </section>

      <DocsPager currentHref="/developers/collections" />
    </div>
  );
}
