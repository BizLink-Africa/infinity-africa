"use client";

import { useState } from "react";

import { Icon } from "@/components/portal/icon";

/** The dark code block used throughout the docs — same visual language as
 * the landing page's "Developer API" snippet and the merchant portal's API
 * Keys quick-start block. */
export function CodeBlock({ language, children }: { language?: string; children: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(children);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API unavailable — no-op, the code is still selectable.
    }
  }

  return (
    <div className="rounded-lg border border-white/10 bg-on-surface overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-white/10">
        <span className="text-xs font-semibold text-white/40 uppercase tracking-wide">{language ?? "text"}</span>
        <button onClick={handleCopy} className="text-white/40 hover:text-white/80 transition-colors" title="Copy">
          <Icon name={copied ? "check" : "content_copy"} className="text-[16px]" />
        </button>
      </div>
      <pre className="p-4 overflow-x-auto text-[13px] leading-relaxed text-primary-fixed font-mono">
        <code>{children}</code>
      </pre>
    </div>
  );
}
