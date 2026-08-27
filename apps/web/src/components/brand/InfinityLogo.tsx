/**
 * The real Infinity Africa brand mark — replaces the generic `all_inclusive`
 * Material Symbol glyph that stood in for it across the Super Admin portal,
 * Merchant Portal, public site, and auth pages before this component
 * existed. Renders from the static asset at /brand/infinity-logo.png
 * (apps/web/public/brand/infinity-logo.png), never a temporary upload path.
 *
 * Color AND size for the optional "Infinity Africa" wordmark are
 * deliberately NOT hardcoded here — the wordmark span sets neither, so it
 * inherits `color` and `font-size` from whatever wraps this component. Pass
 * a color utility (text-white, text-primary, text-on-primary, ...) and,
 * where the surrounding context isn't already the right size (e.g. a small
 * badge), a text-size utility (text-xs, text-lg, ...) in `className` — the
 * same way every call site already set its own color and size before this
 * component existed. This is what makes one component work unmodified on a
 * dark sidebar, a light navbar, or either OS/site theme.
 */
export function InfinityLogo({
  size = 32,
  showText = false,
  className = "",
}: {
  /** Height/width of the mark in px. Sidebars/headers typically want 36–48. */
  size?: number;
  /** Show the "Infinity Africa" wordmark beside the mark. */
  showText?: boolean;
  /** Applied to the outer wrapper — put text color/size, gap, or margin overrides here. */
  className?: string;
}) {
  return (
    <span className={`inline-flex items-center gap-2 text-current ${className}`}>
      {/* eslint-disable-next-line @next/next/no-img-element -- this codebase
          has no next/image usage anywhere else (see selcom-qr-display.tsx's
          identical suppression); a plain <img> matches the rest of the app
          and needs no image-optimizer config for one small static asset. */}
      <img
        src="/brand/infinity-logo.png"
        alt="Infinity Africa logo"
        width={size}
        height={size}
        style={{ width: size, height: size }}
        className="object-contain shrink-0"
      />
      {showText && <span className="font-bold tracking-tight leading-none">Infinity Africa</span>}
    </span>
  );
}
