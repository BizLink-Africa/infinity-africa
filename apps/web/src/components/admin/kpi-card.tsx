import { Icon } from "@/components/portal/icon";

/** Super admin KPI cards put the icon in a top-right box (vs. the merchant
 * portal's icon-left row) and support a tinted "warning" variant for
 * platform-health metrics like Failed Transactions. `variant="brand"` is
 * opt-in (default unchanged, so /admin/* pages keep their current look
 * unless a page explicitly asks for it) — `tone="warning"` still takes
 * priority over it, so a genuinely alarming number (e.g. open high-risk
 * alerts > 0) keeps its yellow warning treatment instead of being hidden
 * under brand green. */
export function AdminKpiCard({
  icon,
  label,
  value,
  caption,
  captionClassName = "text-on-surface-variant",
  trendIcon,
  tone = "default",
  variant = "default",
}: {
  icon: string;
  label: string;
  value: string;
  caption?: string;
  captionClassName?: string;
  trendIcon?: string;
  tone?: "default" | "warning";
  variant?: "default" | "brand";
}) {
  if (tone === "warning") {
    return (
      <div className="bg-[#FEFCE8] border border-[#FEF08A] rounded-xl p-6 shadow-ambient flex flex-col justify-between relative overflow-hidden">
        <div className="absolute right-0 top-0 w-24 h-24 bg-[#FEF08A]/30 rounded-bl-full" />
        <div className="flex justify-between items-start mb-4 relative">
          <span className="text-xs font-semibold text-[#854D0E] uppercase tracking-wider">{label}</span>
          <div className="p-2 bg-[#FEF08A]/50 rounded-lg text-[#854D0E]">
            <Icon name={icon} />
          </div>
        </div>
        <div className="relative">
          <div className="text-3xl font-bold text-[#854D0E]">{value}</div>
          {caption && <div className="text-xs text-[#A16207] mt-1">{caption}</div>}
        </div>
      </div>
    );
  }

  if (variant === "brand") {
    return (
      <div className="bg-primary rounded-xl p-6 shadow-ambient flex flex-col justify-between">
        <div className="flex justify-between items-start mb-4">
          <span className="text-xs font-semibold text-on-primary/70 uppercase tracking-wider">{label}</span>
          <div className="p-2 bg-on-primary/10 rounded-lg text-on-primary">
            <Icon name={icon} />
          </div>
        </div>
        <div>
          <div className="text-3xl font-bold text-on-primary">{value}</div>
          {caption && (
            <div className="text-xs mt-1 flex items-center gap-1 text-on-primary/70">
              {trendIcon && <Icon name={trendIcon} className="text-[14px]" />}
              {caption}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-surface rounded-xl p-6 border border-surface-container-highest/60 shadow-ambient flex flex-col justify-between hover:-translate-y-1 transition-transform duration-200">
      <div className="flex justify-between items-start mb-4">
        <span className="text-xs font-semibold text-on-surface-variant uppercase tracking-wider">{label}</span>
        <div className="p-2 bg-primary-container/10 rounded-lg text-primary">
          <Icon name={icon} />
        </div>
      </div>
      <div>
        <div className="text-3xl font-bold text-on-surface">{value}</div>
        {caption && (
          <div className={`text-xs mt-1 flex items-center gap-1 ${captionClassName}`}>
            {trendIcon && <Icon name={trendIcon} className="text-[14px]" />}
            {caption}
          </div>
        )}
      </div>
    </div>
  );
}
