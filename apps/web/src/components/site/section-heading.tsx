export function SectionHeading({
  eyebrow,
  title,
  description,
  align = "center",
}: {
  eyebrow: string;
  title: string;
  description?: string;
  align?: "center" | "left";
}) {
  return (
    <div className={align === "center" ? "text-center" : "text-left"}>
      <span className="text-xs font-semibold text-primary-container uppercase tracking-wide">{eyebrow}</span>
      <h2 className="text-2xl md:text-4xl font-bold mt-2 mb-3 text-on-surface tracking-tight">{title}</h2>
      {description && (
        <p className={`text-base text-on-surface-variant max-w-2xl ${align === "center" ? "mx-auto" : ""}`}>{description}</p>
      )}
    </div>
  );
}
