import { Callout } from "@/components/docs/callout";
import { CodeBlock } from "@/components/docs/code-block";
import { DocsPager } from "@/components/docs/docs-pager";
import { EndpointRow } from "@/components/docs/endpoint-row";

export const metadata = {
  title: "Webhooks",
};

const EVENTS: Array<{ event: string; description: string; live: boolean }> = [
  { event: "collection.success", description: "A push or QR collection was confirmed by the customer.", live: true },
  { event: "collection.failed", description: "A push or QR collection was declined or timed out.", live: true },
  { event: "disbursement.success", description: "A payout was delivered.", live: true },
  { event: "disbursement.failed", description: "A payout was declined; its balance reservation was reversed.", live: true },
  { event: "disbursement.reversed", description: "A previously successful payout was reversed by the provider after settlement.", live: true },
  { event: "payment_link.paid", description: "A payment link (including one generated from an invoice) was paid.", live: true },
  { event: "invoice.paid", description: "An invoice reached PAID.", live: true },
  { event: "collection.pending", description: "Reserved for a future intermediate collection state.", live: false },
  { event: "invoice.overdue", description: "Reserved for a scheduled past-due sweep.", live: false },
  { event: "payment_link.created", description: "Reserved.", live: false },
  { event: "payment_link.expired", description: "Reserved for a scheduled expiry sweep.", live: false },
  { event: "refund.succeeded", description: "Reserved — refunds aren't issued yet.", live: false },
  { event: "refund.failed", description: "Reserved.", live: false },
  { event: "chargeback.opened", description: "Reserved.", live: false },
  { event: "chargeback.resolved", description: "Reserved.", live: false },
];

export default function WebhooksPage() {
  return (
    <div>
      <p className="text-xs font-semibold text-primary uppercase tracking-wide mb-2">API Reference</p>
      <h1 className="text-3xl md:text-4xl font-bold text-on-surface tracking-tight mb-4">Webhooks</h1>
      <p className="text-lg text-on-surface-variant leading-relaxed mb-10 max-w-2xl">
        Infinity Africa notifies your server the moment a collection resolves, a payout completes, or an invoice gets paid —
        so you don&apos;t have to poll. Configure your endpoint once; every event after that is pushed to you.
      </p>

      <section className="mb-12">
        <h2 className="text-xl font-semibold text-on-surface mb-3">Configuring your endpoint</h2>
        <p className="text-sm text-on-surface-variant leading-relaxed mb-4">
          Set your webhook URL and choose which events to subscribe to from the Merchant Portal&apos;s{" "}
          <strong>Webhooks</strong> page — generate a signing secret there too (shown once, like an API key), and use
          the page&apos;s <strong>Send Test Webhook</strong> button to confirm your endpoint is reachable before
          going live. The same page shows the status of your most recent delivery attempt.
        </p>
        <EndpointRow method="GET" path="/v1/merchant/webhook-config" description="Read your current webhook URL, subscribed events, and whether a secret is set." auth="MERCHANT_ADMIN, MERCHANT_STAFF" />
        <div className="mt-3">
          <EndpointRow method="PATCH" path="/v1/merchant/webhook-config" description="Set the URL/events, and optionally regenerate the signing secret (returned once, in the response)." auth="MERCHANT_ADMIN, DEVELOPER" />
        </div>
        <div className="mt-3">
          <EndpointRow method="POST" path="/v1/merchant/webhook-config/test" description="Send a signed sample payload to your configured URL right now and report the result." auth="MERCHANT_ADMIN, DEVELOPER" />
        </div>
        <div className="mt-3">
          <EndpointRow method="GET" path="/v1/merchant/webhook-events" description="List your own outbound delivery queue." auth="MERCHANT_ADMIN, MERCHANT_STAFF" />
        </div>
      </section>

      <section className="mb-12">
        <h2 className="text-xl font-semibold text-on-surface mb-3">Event types</h2>
        <p className="text-sm text-on-surface-variant leading-relaxed mb-4">
          The events below are the ones your integration should actually handle. A few additional names are reserved
          in the schema for features on the roadmap (refunds, chargebacks, scheduled sweeps) — you&apos;ll see them
          in the enum, but nothing emits them yet.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm border border-outline-variant/40 rounded-xl overflow-hidden">
            <thead className="bg-surface-container-low">
              <tr>
                <th className="px-4 py-2.5 font-semibold text-on-surface-variant">Event</th>
                <th className="px-4 py-2.5 font-semibold text-on-surface-variant">Fires when</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/30">
              {EVENTS.map((item) => (
                <tr key={item.event} className={item.live ? "" : "opacity-50"}>
                  <td className="px-4 py-2.5 font-mono text-xs text-on-surface">{item.event}</td>
                  <td className="px-4 py-2.5 text-on-surface-variant">
                    {item.description}
                    {!item.live && <span className="ml-2 text-[11px] font-semibold text-on-surface-variant/70">(reserved)</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mb-12">
        <h2 className="text-xl font-semibold text-on-surface mb-3">Payload shape</h2>
        <CodeBlock language="json — POST to your webhook_url">{`{
  "event_name": "collection.success",
  "payload": {
    "collection_id": "9b7e2c1a-...",
    "amount": "25000.00",
    "currency": "TZS"
  },
  "created_at": "2026-08-14T09:00:12Z"
}`}</CodeBlock>
      </section>

      <section className="mb-12">
        <h2 className="text-xl font-semibold text-on-surface mb-3">Verifying a delivery</h2>
        <p className="text-sm text-on-surface-variant leading-relaxed mb-4">
          Every delivery is signed with your merchant&apos;s webhook secret, sent as{" "}
          <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">X-Infinity-Signature</code>: an
          HMAC-SHA256 hex digest of the exact raw request body. Recompute it and compare — don&apos;t trust a
          delivery that doesn&apos;t match, and use a constant-time comparison to avoid leaking timing information.
        </p>
        <CodeBlock language="python">{`import hashlib
import hmac

def verify_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)`}</CodeBlock>
      </section>

      <section>
        <h2 className="text-xl font-semibold text-on-surface mb-3">Retries</h2>
        <p className="text-sm text-on-surface-variant leading-relaxed mb-4">
          Every event is recorded to your delivery queue the moment it happens. Automatic retry-with-backoff delivery
          is on the roadmap but not live yet — for now, use{" "}
          <strong>Send Test Webhook</strong> on the Portal&apos;s Webhooks page to confirm your endpoint responds
          correctly, and{" "}
          <a href="/developers/transaction-status" className="text-primary font-semibold hover:underline">
            Transaction Status
          </a>{" "}
          to poll as a fallback. Respond quickly to real deliveries once retries ship — do your processing
          asynchronously after returning <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">200</code>,
          rather than making Infinity Africa wait on it.
        </p>
        <Callout title="Design for at-least-once delivery">
          Once automatic retries are live, treat every delivery as at-least-once, not exactly-once. Key your own
          processing off the resource ID inside <code className="font-mono text-xs">payload</code> (e.g.{" "}
          <code className="font-mono text-xs">collection_id</code>) and make handling that ID idempotent now, so a
          duplicate delivery is a safe no-op later.
        </Callout>
      </section>

      <DocsPager currentHref="/developers/webhooks" />
    </div>
  );
}
