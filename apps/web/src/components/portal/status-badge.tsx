import { Icon } from "./icon";

export type BadgeTone = "positive" | "positive-solid" | "pending" | "negative" | "neutral" | "info";

const TONE_CLASSES: Record<BadgeTone, string> = {
  positive: "bg-primary-container/10 text-primary",
  "positive-solid": "bg-primary text-on-primary",
  pending: "bg-amber-100 text-amber-700",
  negative: "bg-red-100 text-red-700",
  neutral: "bg-surface-container-highest text-on-surface-variant",
  info: "bg-blue-100 text-blue-700",
};

/** The pill-shaped status indicator used on every table/list across the
 * portal — solid green = final positive, soft green = active/success,
 * amber = pending/processing, red = failed/overdue, gray = neutral
 * (draft/expired/cancelled/inactive), blue = informational (sent). */
export function StatusBadge({
  label,
  tone,
  dot = false,
  icon,
  strikethrough = false,
}: {
  label: string;
  tone: BadgeTone;
  dot?: boolean;
  icon?: string;
  strikethrough?: boolean;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold ${TONE_CLASSES[tone]} ${strikethrough ? "line-through opacity-70" : ""}`}
    >
      {dot && <span className="w-1.5 h-1.5 rounded-full bg-current" />}
      {icon && <Icon name={icon} className="text-[12px]" />}
      {label}
    </span>
  );
}
