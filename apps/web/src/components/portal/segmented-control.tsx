/** The two-option pill toggle used for Sandbox/Live (API Keys) and
 * PDF/CSV (Reports). */
export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div className="inline-flex rounded-lg border border-surface-container-highest bg-surface-container-low p-1 gap-1">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={
            option.value === value
              ? "px-4 py-1.5 rounded-md bg-primary-container text-on-primary text-sm font-medium"
              : "px-4 py-1.5 rounded-md text-on-surface-variant text-sm font-medium hover:bg-surface-container-highest transition-colors"
          }
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
