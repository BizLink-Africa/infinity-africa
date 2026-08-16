import { Icon } from "@/components/portal/icon";

export function SolutionCard({
  icon,
  title,
  description,
  chips,
}: {
  icon: string;
  title: string;
  description: string;
  chips?: string[];
}) {
  return (
    <div className="bg-surface-container-lowest border border-outline-variant/40 rounded-xl p-6 shadow-ambient hover:shadow-ambient-lg hover:-translate-y-0.5 transition-all duration-200">
      <div className="w-12 h-12 rounded-lg bg-primary-container/10 flex items-center justify-center mb-4">
        <Icon name={icon} className="text-primary-container text-[26px]" />
      </div>
      <h3 className="text-sm font-bold text-on-surface mb-1.5">{title}</h3>
      <p className="text-sm text-on-surface-variant leading-relaxed">{description}</p>
      {chips && chips.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-3">
          {chips.map((chip) => (
            <span key={chip} className="bg-primary-container/10 text-primary text-[11px] font-semibold px-2.5 py-1 rounded-full">
              {chip}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
