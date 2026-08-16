import { Icon } from "@/components/portal/icon";

export function ContactCard({
  icon,
  label,
  value,
  href,
}: {
  icon: string;
  label: string;
  value: string;
  href?: string;
}) {
  const content = (
    <>
      <div className="w-11 h-11 rounded-lg bg-primary-container/10 flex items-center justify-center shrink-0">
        <Icon name={icon} className="text-primary-container text-[22px]" />
      </div>
      <div>
        <p className="text-xs font-semibold text-on-surface-variant">{label}</p>
        <p className="text-sm font-semibold text-on-surface group-hover:text-primary-container transition-colors whitespace-nowrap">{value}</p>
      </div>
    </>
  );

  if (href) {
    return (
      <a href={href} className="flex items-center gap-4 group">
        {content}
      </a>
    );
  }

  return <div className="flex items-center gap-4">{content}</div>;
}
