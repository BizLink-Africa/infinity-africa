"use client";

import { useEffect, useRef, useState } from "react";
import { jsPDF } from "jspdf";
import QRCode from "qrcode";

import { Icon } from "@/components/portal/icon";

// The exact copy the feature brief specifies — kept as named constants so
// the on-screen card and the downloaded PDF can never drift apart.
const QR_INSTRUCTION = "Scan with your camera or barcode scanner to open the Pay by Link page.";
const QR_PRINT_HELPER =
  "Print this on a poster, table tent, or receipt — anyone who scans it with a phone camera or barcode scanner lands on your Pay by Link page.";
const QR_PDF_FOOTER = "Secure payments powered by Infinity Africa.";

/** Fetches a same-origin public asset and returns it as a data URL plus
 * its natural pixel size — the size is what lets the PDF fit the logo
 * with object-contain math (never stretched, never cropped) instead of
 * guessing a fixed aspect ratio. Returns null on any failure (offline,
 * asset missing, ...) so the PDF still generates without a logo rather
 * than failing outright over a decorative image. */
async function loadImageAsDataUrl(url: string): Promise<{ dataUrl: string; width: number; height: number } | null> {
  try {
    const response = await fetch(url);
    if (!response.ok) return null;
    const blob = await response.blob();
    const dataUrl = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(blob);
    });
    const { width, height } = await new Promise<{ width: number; height: number }>((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve({ width: img.naturalWidth, height: img.naturalHeight });
      img.onerror = () => reject(new Error("Couldn't read image dimensions"));
      img.src = dataUrl;
    });
    return { dataUrl, width, height };
  } catch {
    return null;
  }
}

/** CSS object-contain, computed for a PDF's fixed-size image placement:
 * the largest (width, height) that fits inside (maxWidth, maxHeight)
 * without changing the aspect ratio — so the logo is never stretched or
 * cropped, only ever scaled down (or up) uniformly. */
function containSize(width: number, height: number, maxWidth: number, maxHeight: number) {
  const scale = Math.min(maxWidth / width, maxHeight / height);
  return { width: width * scale, height: height * scale };
}

async function generateQrPdf({
  merchantName,
  slug,
  publicUrl,
}: {
  merchantName: string;
  slug: string;
  publicUrl: string;
}) {
  // Generated fresh at print resolution — independent of the smaller
  // on-screen canvas this card also renders, so the PDF copy is never a
  // blurry upscale of a 176px preview.
  const qrDataUrl = await QRCode.toDataURL(publicUrl, {
    width: 900,
    margin: 2,
    color: { dark: "#000000", light: "#ffffff" },
  });
  const logo = await loadImageAsDataUrl("/brand/infinity-mark.png");

  const doc = new jsPDF({ unit: "mm", format: "a4", orientation: "portrait" });
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const centerX = pageWidth / 2;
  const textWidth = pageWidth - 40;

  let cursorY = 22;

  if (logo) {
    const { width, height } = containSize(logo.width, logo.height, 22, 22);
    doc.addImage(logo.dataUrl, "PNG", centerX - width / 2, cursorY, width, height);
    cursorY += height + 6;
  }

  doc.setFont("helvetica", "bold");
  doc.setFontSize(13);
  doc.setTextColor("#04332A");
  doc.text("Infinity Africa", centerX, cursorY, { align: "center" });
  cursorY += 14;

  doc.setFontSize(22);
  doc.setTextColor("#111111");
  doc.text(merchantName, centerX, cursorY, { align: "center" });
  cursorY += 14;

  const qrSize = 100;
  doc.addImage(qrDataUrl, "PNG", centerX - qrSize / 2, cursorY, qrSize, qrSize);
  cursorY += qrSize + 10;

  doc.setFont("helvetica", "normal");
  doc.setFontSize(11);
  doc.setTextColor("#000000");
  doc.text(publicUrl, centerX, cursorY, { align: "center" });
  cursorY += 10;

  doc.setFontSize(10);
  doc.setTextColor("#555555");
  const instructionLines: string[] = doc.splitTextToSize(QR_INSTRUCTION, textWidth);
  doc.text(instructionLines, centerX, cursorY, { align: "center" });
  cursorY += instructionLines.length * 5 + 8;

  doc.setFontSize(9);
  doc.setTextColor("#777777");
  const footerLines: string[] = doc.splitTextToSize(QR_PDF_FOOTER, textWidth);
  doc.text(footerLines, centerX, cursorY, { align: "center" });

  doc.setFontSize(9);
  doc.setTextColor("#999999");
  doc.text("Powered by Infinity Africa", centerX, pageHeight - 14, { align: "center" });

  doc.save(`pay-by-link-${slug}.pdf`);
}

export function PayByLinkQrCard({
  merchantName,
  slug,
  publicUrl,
}: {
  merchantName: string;
  slug: string;
  publicUrl: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!canvasRef.current || !publicUrl) return;
    QRCode.toCanvas(canvasRef.current, publicUrl, {
      width: 176,
      margin: 1,
      color: { dark: "#000000", light: "#ffffff" },
    }).catch(() => {
      // Malformed/empty payload — the canvas just stays blank; the
      // instruction text below still renders.
    });
  }, [publicUrl]);

  async function handleDownloadPdf() {
    if (!publicUrl) {
      setError("Pay by Link QR code is not available yet.");
      return;
    }
    setError(null);
    setGenerating(true);
    try {
      await generateQrPdf({ merchantName, slug, publicUrl });
    } catch {
      setError("QR PDF could not be generated. Please try again.");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="lg:col-span-2 bg-surface rounded-xl border border-surface-container-highest shadow-ambient p-6 flex flex-col items-center gap-4 h-fit">
      <h3 className="text-lg font-semibold text-on-background self-start">QR Code</h3>

      <div className="w-full flex flex-col items-center rounded border border-dashed border-outline-variant bg-surface-container p-5">
        {publicUrl ? (
          <canvas ref={canvasRef} className="h-44 w-44 rounded bg-surface p-2 shadow-sm" />
        ) : (
          <p className="text-sm text-error text-center">Pay by Link QR code is not available yet.</p>
        )}
        <p className="mt-3 text-xs font-medium text-on-surface-variant text-center break-words">{QR_INSTRUCTION}</p>
      </div>

      <button
        type="button"
        onClick={handleDownloadPdf}
        disabled={generating || !publicUrl}
        className="w-full flex items-center justify-center gap-2 border border-surface-container-highest text-on-surface text-sm font-medium py-2.5 rounded-lg hover:bg-surface-container-low transition-colors disabled:opacity-60"
      >
        <Icon name="picture_as_pdf" className="text-[18px]" />
        {generating ? "Preparing PDF…" : "Download QR PDF"}
      </button>
      {error && <p className="text-xs text-error text-center">{error}</p>}

      <p className="text-xs text-on-surface-variant text-center break-words">{QR_PRINT_HELPER}</p>
    </div>
  );
}
