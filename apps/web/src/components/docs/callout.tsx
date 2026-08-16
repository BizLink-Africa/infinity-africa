import { Icon } from "@/components/portal/icon";

const TONE_CLASSES: Record<string, { wrap: string; icon: string; iconName: string }> = {
  info: { wrap: "bg-primary-container/5 border-primary-container/20", icon: "text-primary", iconName: "info" },
  warning: { wrap: "bg-amber-50 border-amber-200", icon: "text-amber-600", iconName: "warning" },
};

export function Callout({ tone = "info", title, children }: { tone?: "info" | "warning"; title: string; children: React.ReactNode }) {
  const classes = TONE_CLASSES[tone];
  return (
    <div className={`flex gap-3 rounded-lg border p-4 ${classes.wrap}`}>
      <Icon name={classes.iconName} className={`text-[20px] shrink-0 ${classes.icon}`} />
      <div>
        <p className="text-sm font-semibold text-on-surface">{title}</p>
        <div className="text-sm text-on-surface-variant mt-1 leading-relaxed">{children}</div>
      </div>
    </div>
  );
}
