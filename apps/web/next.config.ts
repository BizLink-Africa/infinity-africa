import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["@infinity/shared"],
  experimental: {
    serverActions: {
      // Onboarding submission (app/onboarding/page.tsx ->
      // submitOnboardingAction) uploads three real compliance documents
      // (NIDA, TIN certificate, business licence) as a single Server
      // Action request — Next.js's 1MB default body cap rejected a real
      // merchant's submission with a bare "This page couldn't load"
      // (confirmed via Vercel runtime error: "Body exceeded 1 MB limit.",
      // digest 3780544422@E394, 2026-08-29). 15mb comfortably covers
      // three phone-camera photos/scans without opening this up to
      // arbitrary large uploads.
      bodySizeLimit: "15mb",
    },
  },
};

export default nextConfig;
