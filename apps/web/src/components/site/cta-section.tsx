import Link from "next/link";

import { Icon } from "@/components/portal/icon";

export function CTASection({
  title,
  description,
  primaryLabel,
  primaryHref,
  secondaryLabel,
  secondaryHref,
}: {
  title: string;
  description: string;
  primaryLabel: string;
  primaryHref: string;
  secondaryLabel?: string;
  secondaryHref?: string;
}) {
  return (
    <section className="py-16 px-4 md:px-10 bg-on-surface">
      <div className="max-w-[1280px] mx-auto rounded-2xl bg-surface p-10 md:p-14 text-center flex flex-col items-center gap-5 shadow-ambient-lg">
        <h2 className="text-2xl md:text-4xl font-bold text-on-surface tracking-tight max-w-2xl">{title}</h2>
        <p className="text-base text-on-surface-variant max-w-xl">{description}</p>
        <div className="flex flex-col sm:flex-row gap-4 mt-2">
          <Link
            href={primaryHref}
            className="inline-flex items-center justify-center gap-2 bg-primary-container text-on-primary text-sm font-medium px-8 py-3.5 rounded-lg hover:opacity-90 transition-opacity"
          >
            {primaryLabel}
            <Icon name="arrow_forward" className="text-[18px]" />
          </Link>
          {secondaryLabel && secondaryHref && (
            <Link
              href={secondaryHref}
              className="inline-flex items-center justify-center gap-2 border border-outline-variant text-on-surface text-sm font-medium px-8 py-3.5 rounded-lg hover:border-primary-container hover:text-primary-container transition-all"
            >
              {secondaryLabel}
            </Link>
          )}
        </div>
      </div>
    </section>
  );
}
