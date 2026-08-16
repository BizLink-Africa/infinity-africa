import { Icon } from "@/components/portal/icon";
import { CTASection } from "@/components/site/cta-section";
import { Footer } from "@/components/site/footer";
import { Header } from "@/components/site/header";
import { SectionHeading } from "@/components/site/section-heading";

export const metadata = {
  title: "Payment Links | Infinity Africa",
  description: "Create shareable payment links with amount, customer phone, description, and expiry — let customers pay however suits them best.",
};

const CREATE_FIELDS = [
  { icon: "payments", label: "Amount", description: "Set a fixed amount in TZS for the customer to pay." },
  { icon: "call", label: "Customer Phone", description: "Attach a phone number so the customer gets notified automatically." },
  { icon: "description", label: "Description", description: "Add context so the customer knows exactly what they're paying for." },
  { icon: "schedule", label: "Expiry Time", description: "Set how long the link stays valid before it automatically expires." },
];

const SHARE_CHANNELS = ["WhatsApp", "SMS", "Email", "Instagram", "Website Checkout"];

const PAYMENT_METHODS = [
  { icon: "phone_iphone", label: "Push USSD" },
  { icon: "touch_app", label: "STK Push" },
  { icon: "bolt", label: "Selcom Pesa Push" },
];

const STATUSES: Array<{ label: string; tone: string }> = [
  { label: "Active", tone: "bg-primary-container/10 text-primary" },
  { label: "Paid", tone: "bg-primary text-on-primary" },
  { label: "Expired", tone: "bg-surface-container-highest text-on-surface-variant" },
  { label: "Cancelled", tone: "bg-red-100 text-red-700" },
];

export default function PaymentLinksPage() {
  return (
    <div className="bg-surface text-on-surface antialiased">
      <Header />
      <main>
        <section className="py-16 md:py-20 px-4 md:px-10 bg-surface-container-lowest">
          <div className="max-w-[1280px] mx-auto grid md:grid-cols-2 gap-14 items-center">
            <div>
              <span className="text-xs font-semibold text-primary-container uppercase tracking-wide">Payment Links</span>
              <h1 className="text-2xl md:text-4xl font-bold mt-2 mb-4 text-on-surface tracking-tight">
                Get paid without a website or app
              </h1>
              <p className="text-base text-on-surface-variant max-w-lg mb-8">
                Create a shareable payment link in seconds — set the amount, attach a customer phone number, add a
                description, and choose when it expires. Share it however your customer prefers, and let them pick
                the payment method that works for them.
              </p>
              <div className="flex flex-wrap gap-2">
                {SHARE_CHANNELS.map((channel) => (
                  <span key={channel} className="bg-surface border border-outline-variant/50 text-on-surface-variant text-xs font-semibold px-3 py-1.5 rounded-full">
                    {channel}
                  </span>
                ))}
              </div>
            </div>

            {/* Preview: customer payment link page */}
            <div className="relative flex items-center justify-center py-4">
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-64 h-64 bg-primary-container/15 rounded-full blur-3xl" />
              <div className="relative z-10 w-full max-w-sm bg-surface border border-outline-variant/50 rounded-2xl shadow-ambient-lg overflow-hidden">
                <div className="p-6 border-b border-outline-variant/40 text-center">
                  <span className="text-sm font-bold text-primary">Infinity Africa</span>
                  <p className="text-xs text-on-surface-variant mt-2">Amani Traders Ltd requests</p>
                  <p className="text-3xl font-bold text-on-surface mt-1">TZS 25,000</p>
                  <p className="text-xs text-on-surface-variant mt-1">Web design deposit · expires in 2 days</p>
                </div>
                <div className="p-6 space-y-2.5">
                  <p className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide mb-1">Choose a payment method</p>
                  {PAYMENT_METHODS.map((method, index) => (
                    <div
                      key={method.label}
                      className={`flex items-center gap-3 px-4 py-3 rounded-lg border text-sm font-medium ${
                        index === 0 ? "border-primary-container bg-primary-container/5 text-on-surface" : "border-outline-variant/50 text-on-surface-variant"
                      }`}
                    >
                      <Icon name={method.icon} className="text-[18px] text-primary-container" />
                      {method.label}
                    </div>
                  ))}
                  <button className="w-full mt-2 bg-primary-container text-on-primary text-sm font-medium py-3 rounded-lg">Pay Now</button>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="py-16 px-4 md:px-10 bg-surface">
          <div className="max-w-[1280px] mx-auto">
            <SectionHeading eyebrow="Creating a Link" title="What Goes Into a Payment Link" description="Every payment link carries everything the customer needs to pay with confidence." />
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-6 mt-10">
              {CREATE_FIELDS.map((field) => (
                <div key={field.label} className="bg-surface-container-lowest border border-outline-variant/40 rounded-xl p-6">
                  <Icon name={field.icon} className="text-primary-container text-[26px] mb-3 block" />
                  <h3 className="text-sm font-bold text-on-surface mb-1.5">{field.label}</h3>
                  <p className="text-sm text-on-surface-variant leading-relaxed">{field.description}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="py-16 px-4 md:px-10 bg-surface-container-lowest">
          <div className="max-w-[1280px] mx-auto text-center">
            <SectionHeading eyebrow="Link Status" title="Track Every Link From Creation to Payment" description="Every payment link moves through a clear lifecycle so you always know where it stands." />
            <div className="flex flex-wrap justify-center gap-3 mt-8">
              {STATUSES.map((status) => (
                <span key={status.label} className={`px-4 py-2 rounded-full text-sm font-semibold ${status.tone}`}>
                  {status.label}
                </span>
              ))}
            </div>
          </div>
        </section>

        <CTASection
          title="Create your first payment link"
          description="Tell us about your business and start sharing payment links with your customers."
          primaryLabel="Create Payment Link"
          primaryHref="/create-account"
          secondaryLabel="View API Docs"
          secondaryHref="/api-docs"
        />
      </main>
      <Footer />
    </div>
  );
}
