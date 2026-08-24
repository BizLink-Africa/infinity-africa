/**
 * Supported mobile money operator strip — shown in the payment page
 * footer, not inside the Mobile Money Push card itself (keeps that card
 * uncluttered). Local static SVG assets only (public/assets/payment-logos)
 * — never hotlinked, and small enough (<1KB each) that this costs nothing
 * to load. next/image is skipped here on purpose: Next disallows
 * optimizing local SVGs unless `images.dangerouslyAllowSVG` is turned on
 * project-wide, which is a security-relevant config change out of scope
 * for a UI polish pass — a plain <img> of our own trusted local asset is
 * the simpler, equally-safe choice (same call selcom-qr-display.tsx
 * already made for its own <img> usage).
 */
const OPERATOR_LOGOS = [
  { src: "/assets/payment-logos/mpesa.svg", alt: "M-Pesa" },
  { src: "/assets/payment-logos/airtel-money.svg", alt: "Airtel Money" },
  { src: "/assets/payment-logos/tigo-pesa.svg", alt: "Mixx by Yas" },
  { src: "/assets/payment-logos/halopesa.svg", alt: "HaloPesa" },
  { src: "/assets/payment-logos/selcom-pesa.svg", alt: "Selcom Pesa" },
  { src: "/assets/payment-logos/tanqr.svg", alt: "TanQR / TIPS" },
];

export function PaymentMethodLogos() {
  return (
    <div className="flex flex-wrap items-center justify-center gap-2.5" role="list" aria-label="Supported payment methods">
      {OPERATOR_LOGOS.map((logo) => (
        // eslint-disable-next-line @next/next/no-img-element -- local static SVG; next/image can't optimize SVG without a project-wide security config change
        <img key={logo.src} src={logo.src} alt={logo.alt} role="listitem" className="h-6 w-auto rounded" />
      ))}
    </div>
  );
}
