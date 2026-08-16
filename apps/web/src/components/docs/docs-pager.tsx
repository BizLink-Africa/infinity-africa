import Link from "next/link";

import { Icon } from "@/components/portal/icon";

import { DOCS_NAV } from "./nav-items";

const FLAT_NAV = DOCS_NAV.flatMap((group) => group.items);

export function DocsPager({ currentHref }: { currentHref: string }) {
  const index = FLAT_NAV.findIndex((item) => item.href === currentHref);
  const prev = index > 0 ? FLAT_NAV[index - 1] : null;
  const next = index >= 0 && index < FLAT_NAV.length - 1 ? FLAT_NAV[index + 1] : null;

  if (!prev && !next) return null;

  return (
    <div className="mt-16 pt-8 border-t border-outline-variant/40 flex items-center justify-between gap-4">
      {prev ? (
        <Link
          href={prev.href}
          className="flex items-center gap-2 text-sm font-medium text-on-surface-variant hover:text-primary transition-colors"
        >
          <Icon name="arrow_back" className="text-[18px]" />
          <span>
            <span className="block text-xs text-on-surface-variant/70">Previous</span>
            {prev.label}
          </span>
        </Link>
      ) : (
        <span />
      )}
      {next && (
        <Link
          href={next.href}
          className="flex items-center gap-2 text-sm font-medium text-on-surface-variant hover:text-primary transition-colors text-right ml-auto"
        >
          <span>
            <span className="block text-xs text-on-surface-variant/70">Next</span>
            {next.label}
          </span>
          <Icon name="arrow_forward" className="text-[18px]" />
        </Link>
      )}
    </div>
  );
}
