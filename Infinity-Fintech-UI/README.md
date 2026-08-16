# Infinity Africa UI

Working copy of the Infinity Africa fintech product UI (Tanzanian SME payments platform).
Started from Google Stitch–exported screens; the **landing page**, the full
**merchant portal**, and the full **super admin dashboard** have since been rebuilt
by hand into real, linked, multi-page experiences. The original unmodified Stitch
exports remain untouched at: `Desktop/stitch_infinity_fintech_landing_page/`.

## How to open the project

Every page is a **fully self-contained HTML file** — Tailwind CSS (CDN, JIT) and
Google Fonts load from CDN, all styling is inlined, and there is no build step and
no local server required. An internet connection is needed on first load for those
two CDN requests; everything else (icons, avatars, QR preview, product mockups) is
drawn with plain HTML/CSS/SVG, so nothing is hotlinked from external images.

To view a page, just open its `index.html` directly in a browser (double-click it,
or right-click → "Open with" → your browser).

- **Landing page** → start at `landing-page/index.html`
- **Merchant portal** → start at `merchant-portal/overview/index.html` and use the
  left sidebar to move between sections — all 13 sidebar links are real, working
  relative links between pages.
- **Super admin dashboard** → start at `super-admin/command-center/index.html` and
  use the left sidebar — all 19 sidebar links are real, working relative links.

## Folder structure

```
Infinity-Fintech-UI/
├── landing-page/                     → Public marketing landing page
│   └── index.html
├── merchant-portal/                  → Merchant-facing dashboard (13 pages)
│   ├── overview/                     → Dashboard home: KPIs, quick actions, recent activity
│   ├── collections/                  → Request one-off collections from customers
│   ├── payment-links/                → Create & share payment links, QR preview, links table
│   ├── invoices/                     → Create itemized invoices with Pay Now links
│   ├── customers/                    → Customer directory
│   ├── disbursements/                → Selcom Pesa / mobile money / bank payouts
│   ├── transactions/                 → Unified ledger (collections, disbursements, fees)
│   ├── wallet/                       → Balances + linked disbursement accounts
│   ├── pricing/                      → Fee schedule & current plan
│   ├── api-keys/                     → Sandbox/Live API key management
│   ├── reports/                      → Generate accounting/reconciliation reports
│   ├── settings/                     → Business profile, security, notifications, team
│   └── support/                      → Contact channels, ticket form, FAQ
├── super-admin/                       → Platform operator dashboard (19 pages)
│   ├── command-center/                → Overview: 8 platform KPIs, recent activity
│   ├── merchants/                     → Merchant Management: onboard, verify, suspend
│   ├── collections/                   → Platform-wide mobile money collections
│   ├── payment-links/                 → Payment Links Monitoring (all merchants)
│   ├── invoices/                      → Invoice Management (all merchants)
│   ├── customers/                     → Customer directory (all merchants)
│   ├── disbursements/                 → Disbursement Monitoring + high-value approval queue
│   ├── transactions/                  → Full platform ledger
│   ├── pricing-rules/                 → Platform default fees + merchant overrides
│   ├── api-keys/                      → Merchant API key oversight + platform rate limits
│   ├── webhooks/                      → Webhook Logs: delivery status per merchant
│   ├── reconciliation-center/         → Callback logs, unmatched txns, duplicates, retries
│   ├── settlement-accounts/           → Platform's own provider/bank settlement accounts
│   ├── compliance-kyc/                → KYC review queue + compliance flags
│   ├── dispute-management/            → Open/resolved payment disputes
│   ├── provider-status/               → Live uptime for every payment network
│   ├── audit-logs/                    → Admin action history
│   ├── support-tickets/               → Merchant support tickets escalated to the platform
│   └── settings/                      → Platform config, security, notifications, admin team
├── shared/                           → Assets/docs used across multiple apps
│   ├── secure-payment-page/          → Standalone secure checkout page (not yet rebuilt)
│   └── DESIGN.md                     → Design system reference (colors, type, spacing)
├── assets/                           → Reserved for shared local images/fonts if ever needed
└── README.md
```

| Section | Entry point | Status |
|---|---|---|
| Landing page | `landing-page/index.html` | Rebuilt — full marketing page with working nav & contact links |
| Merchant portal | `merchant-portal/overview/index.html` | Rebuilt — 13 linked pages with a shared sidebar/topbar shell |
| Super admin dashboard | `super-admin/command-center/index.html` | Rebuilt — 19 linked pages with a shared sidebar/topbar shell |
| Secure payment page | `shared/secure-payment-page/index.html` | Original Stitch export, not yet rebuilt |

`shared/secure-payment-page/` still keeps its original `screen.png` Stitch preview
next to the code, for reference. The rebuilt landing page, merchant portal, and
super admin dashboard don't need `screen.png` since their `index.html` *is* the
current design (the original `super-admin/command-center/screen.png` and
`operations-center/` export were used as the visual reference during the rebuild,
then superseded — `operations-center/` was removed since its content now lives
across the 19 dedicated pages).

## Design system (shared across merchant portal & super admin)

Both dashboards share one hand-written shell pattern (sidebar + topbar + mobile
drawer) and one set of reusable classes, so any page can be copied as a starting
point for a new one:

- **Colors**: green/white fintech palette from `shared/DESIGN.md` (`primary`
  `#005232`, `primary-container` `#006d44`, etc.), wired into each page's inline
  Tailwind config — identical values in both dashboards.
- **Status badges**: solid green = final positive (Paid/Completed/Successful), soft
  green = active/success, amber = pending/processing, red = failed/overdue/high-risk,
  gray = neutral (draft/expired/cancelled/reversed), blue = informational (sent).
- **Empty states**: icon + heading + description + CTA pattern — used on the
  merchant portal's API Keys/Reports/Support pages to show a first-run merchant's
  view.
- **Mobile**: sidebar becomes an off-canvas drawer (hamburger + overlay) below the
  `md` breakpoint; every table sits in a horizontally-scrollable wrapper so wide
  data never squashes the layout on small screens.

Super admin has a few distinct chrome choices to visually separate "operating the
platform" from "running your own business": a pill-shaped search bar, an "A"
admin-profile avatar instead of merchant initials, a "Platform Action" button in
place of "Upgrade Plan", and KPI cards with the icon in a top-right box (vs. the
merchant portal's icon-left row) — matching the original Stitch Command Center
reference. It also introduces a few admin-specific patterns: a warning-tinted KPI
card (amber, for "Failed Transactions"), an approve/reject button pair (used for
high-value disbursement approvals and KYC review), and a live-status pulsing dot
(used on Provider Status).

## Known limitations (next editing pass)

- `shared/secure-payment-page/` is still the raw Stitch export — external
  `lh3.googleusercontent.com` image links, no shared nav, and not yet restyled to
  match the rest of the product.
- All forms (payment link creation, invoice creation, disbursement requests,
  approvals, settings, support tickets, etc.) are visual-only — there's no backend,
  so submitting doesn't persist anything. That's expected for a static UI prototype.
- Each dashboard's shared shell is duplicated per-file (no templating layer), since
  this is plain static HTML with no build step — if you add a new page, copy the
  shell from an existing sibling page rather than writing it from scratch.
- The merchant portal and super admin dashboard are visually consistent but
  intentionally separate apps — there's no cross-linking between them (e.g. no
  "switch to admin view" link), matching how a real merchant vs. internal-staff
  login would be fully separate.
