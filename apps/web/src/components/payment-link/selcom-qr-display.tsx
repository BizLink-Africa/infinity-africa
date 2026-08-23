import { QrCode } from "./qr-code";

/**
 * Renders exactly the `qr` value Selcom's create-order-minimal response
 * returned — never Infinity's own order_id, amount, merchant name, or
 * payment link URL, and never re-encoded. Selcom's docs don't pin down
 * one fixed format for this field, so the payload is inspected (never
 * transformed) to decide how to display it:
 *
 *   - starts with "http" -> Selcom returned a URL (an image asset or a
 *     link) — shown as an <img>, falling back to a plain link if it
 *     doesn't load as an image.
 *   - starts with "data:image" -> already a base64 image data URI —
 *     shown directly as an <img src>.
 *   - anything else (the confirmed case: Selcom's sample response is
 *     the literal string "QR", and real EMVCo payloads are plain text
 *     too) -> treated as EMVCo/text and encoded into a scannable QR
 *     image client-side via the existing QrCode component — the one
 *     transformation this ever does is turning text into its own
 *     picture, not altering the text itself.
 */
export function SelcomQrDisplay({ qr }: { qr: string }) {
  if (qr.startsWith("http") || qr.startsWith("data:image")) {
    return (
      <div className="mt-4 flex flex-col items-center rounded border border-dashed border-outline-variant bg-surface-container p-5">
        {/* eslint-disable-next-line @next/next/no-img-element -- external/data-URI payload from Selcom, not a local asset Next's optimizer should process */}
        <img src={qr} alt="Selcom payment QR code" className="h-44 w-44 rounded bg-surface object-contain p-2 shadow-sm" />
        <p className="mt-3 text-xs font-medium text-on-surface-variant">Scan this QR using your supported payment app.</p>
      </div>
    );
  }

  return <QrCode payload={qr} expiresAt={null} />;
}
