import { Icon } from "./icon";

export function KpiCard({
  icon,
  iconClassName = "text-primary",
  label,
  value,
  caption,
  captionClassName = "text-outline",
  trendIcon,
}: {
  icon: string;
  iconClassName?: string;
  label: string;
  value: string;
  caption?: string;
  captionClassName?: string;
  trendIcon?: string;
}) {
  return (
    <div className="bg-surface rounded-xl p-4 border border-surface-container-highest/60 shadow-ambient">
      <div className="flex items-center gap-2 text-on-surface-variant mb-2">
        <Icon name={icon} className={`text-[18px] ${iconClassName}`} />
        <span className="text-sm font-medium">{label}</span>
      </div>
      <div className="text-2xl font-semibold text-on-background">{value}</div>
      {caption && (
        <div className={`text-xs mt-1 font-medium flex items-center gap-1 ${captionClassName}`}>
          {trendIcon && <Icon name={trendIcon} className="text-[14px]" />}
          {caption}
        </div>
      )}
    </div>
  );
}
