import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const SITE_DESCRIPTION =
  "Payment infrastructure for African merchants, payment links, invoices, collections, and merchant tools.";

export const metadata: Metadata = {
  title: "Infinity Africa",
  description: SITE_DESCRIPTION,
  metadataBase: new URL("https://infinityafrica.net"),
  openGraph: {
    title: "Infinity Africa",
    description: SITE_DESCRIPTION,
    url: "https://infinityafrica.net",
    siteName: "Infinity Africa",
    images: ["/infinity-logo-v2.png"],
    locale: "en_US",
    type: "website",
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`}>
      <head>
        {/* eslint-disable-next-line @next/next/no-page-custom-font -- the
            no-page-custom-font rule predates the App Router; app/layout.tsx
            *is* the documented place for a site-wide font link. */}
        <link
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
