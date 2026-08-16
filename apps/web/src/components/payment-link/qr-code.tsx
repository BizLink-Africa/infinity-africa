"use client";

import { useEffect, useRef } from "react";
import QRCode from "qrcode";

import { formatDateTime } from "@/lib/format";

/**
 * Renders a real, scannable QR code client-side (the `qrcode` package —
 * no network call, nothing sent to a third party) encoding whatever
 * payload the backend returned (e.g. a Dynamic QR collection's
 * qr_payload, or a payment link's own public_url). Standard black-on-white
 * modules — a colored/branded QR code can fail to scan reliably on some
 * wallet apps, and this is a money-moving code, so scan reliability wins
 * over theming here; the surrounding card stays green/white branded.
 */
export function QrCode({ payload, expiresAt }: { payload: string; expiresAt: string | null }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!canvasRef.current || !payload) return;
    QRCode.toCanvas(canvasRef.current, payload, {
      width: 176,
      margin: 1,
      color: { dark: "#000000", light: "#ffffff" },
    }).catch(() => {
      // Malformed/empty payload — the canvas just stays blank; the expiry
      // text below still renders so the customer isn't left with nothing.
    });
  }, [payload]);

  return (
    <div className="mt-4 flex flex-col items-center rounded border border-dashed border-outline-variant bg-surface-container p-5">
      <canvas ref={canvasRef} className="h-44 w-44 rounded bg-surface p-2 shadow-sm" />
      <p className="mt-3 text-xs font-medium text-on-surface-variant">
        Scan with your banking or mobile money app
      </p>
      {expiresAt && (
        <p className="mt-2 text-xs text-on-surface-variant">Code expires {formatDateTime(expiresAt)}</p>
      )}
    </div>
  );
}
