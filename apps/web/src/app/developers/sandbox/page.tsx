import { Callout } from "@/components/docs/callout";
import { CodeBlock } from "@/components/docs/code-block";
import { DocsPager } from "@/components/docs/docs-pager";

export const metadata = {
  title: "Sandbox Examples",
};

export default function SandboxPage() {
  return (
    <div>
      <p className="text-xs font-semibold text-primary uppercase tracking-wide mb-2">Examples</p>
      <h1 className="text-3xl md:text-4xl font-bold text-on-surface tracking-tight mb-4">Sandbox Examples</h1>
      <p className="text-lg text-on-surface-variant leading-relaxed mb-10 max-w-2xl">
        Every sandbox request runs against a mock payment network — no real money moves, no real SMS is sent, and
        nothing settles. Build and test your entire integration before switching to a live key.
      </p>

      <section className="mb-12">
        <h2 className="text-xl font-semibold text-on-surface mb-3">Getting a sandbox key</h2>
        <p className="text-sm text-on-surface-variant leading-relaxed">
          Generate one from the dashboard&apos;s API Keys page (choose the <strong>Sandbox</strong> tab), or via{" "}
          <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">POST /v1/merchants/{"{id}"}/api-keys</code> with{" "}
          <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">&quot;environment&quot;: &quot;sandbox&quot;</code> — see{" "}
          <a href="/developers/authentication" className="text-primary font-semibold hover:underline">
            API Key Authentication
          </a>
          .
        </p>
      </section>

      <section className="mb-12">
        <h2 className="text-xl font-semibold text-on-surface mb-3">How the mock provider behaves</h2>
        <p className="text-sm text-on-surface-variant leading-relaxed mb-4">
          A push or QR collection, and every disbursement, resolves with a configurable random failure rate — so your
          error-handling code gets exercised, not just the happy path. There&apos;s no need to configure anything;
          this is on by default in sandbox.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm border border-outline-variant/40 rounded-xl overflow-hidden">
            <thead className="bg-surface-container-low">
              <tr>
                <th className="px-4 py-2.5 font-semibold text-on-surface-variant">Behavior</th>
                <th className="px-4 py-2.5 font-semibold text-on-surface-variant">Default</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/30">
              <tr>
                <td className="px-4 py-2.5 text-on-surface">Random failure rate</td>
                <td className="px-4 py-2.5 font-mono text-xs text-on-surface-variant">10%</td>
              </tr>
              <tr>
                <td className="px-4 py-2.5 text-on-surface">Simulated approval delay</td>
                <td className="px-4 py-2.5 font-mono text-xs text-on-surface-variant">~0.3s</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className="mb-12">
        <h2 className="text-xl font-semibold text-on-surface mb-3">Resolving a push/QR collection manually</h2>
        <p className="text-sm text-on-surface-variant leading-relaxed mb-4">
          Collections initiated via <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">/v1/collections/{"{method}"}</code> stay{" "}
          <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">processing</code> until a
          provider callback resolves them — in sandbox, that&apos;s simulated by posting to the same webhook endpoint
          a real Selcom callback would land on, signed with your merchant&apos;s webhook secret:
        </p>
        <CodeBlock language="bash">{`curl -X POST https://sandbox.infinityafrica.net/v1/webhooks/selcom \\
  -H "Content-Type: application/json" \\
  -H "X-Selcom-Signature: $(echo -n '{"event_id":"evt_1","event_type":"collection.success","provider_reference":"MOCK-SELCOM-9F3A1C2B"}' \\
      | openssl dgst -sha256 -hmac "$SELCOM_WEBHOOK_SECRET" | cut -d' ' -f2)" \\
  -d '{"event_id":"evt_1","event_type":"collection.success","provider_reference":"MOCK-SELCOM-9F3A1C2B"}'`}</CodeBlock>
        <p className="text-sm text-on-surface-variant leading-relaxed mt-3">
          Use <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">provider_reference</code> from
          the collection or disbursement you want to resolve, and{" "}
          <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">event_type</code> of{" "}
          <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">collection.success</code>,{" "}
          <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">collection.failed</code>,{" "}
          <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">disbursement.success</code>,
          or <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">disbursement.failed</code>.
        </p>
        <Callout title="Public payment-link checkout resolves on its own">
          The public <code className="font-mono text-xs">.../collect</code> endpoint (what a customer hits on your
          checkout page) doesn&apos;t need this — it resolves synchronously in the same response, since the mock
          provider is called and checked immediately within that request.
        </Callout>
      </section>

      <section>
        <h2 className="text-xl font-semibold text-on-surface mb-3">A full sandbox test flow</h2>
        <ol className="space-y-3 text-sm text-on-surface-variant leading-relaxed list-decimal list-inside">
          <li>Generate a sandbox key and set it as your X-API-Key.</li>
          <li>
            Create a payment link (<code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">POST /v1/payment-links</code>)
            and open <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">public_url</code> in
            a browser.
          </li>
          <li>Complete checkout — the mock provider resolves it within the same request, roughly 90% of the time successfully.</li>
          <li>
            Check <code className="font-mono text-xs bg-surface-container-low px-1.5 py-0.5 rounded">GET /v1/merchants/{"{id}"}/transactions</code> and
            confirm a ledger entry appeared.
          </li>
          <li>Request a small disbursement and watch it resolve to SUCCESS or FAILED.</li>
          <li>Point your webhook_url at a local tunnel (e.g. ngrok) and confirm delivery of the resulting events.</li>
        </ol>
      </section>

      <DocsPager currentHref="/developers/sandbox" />
    </div>
  );
}
