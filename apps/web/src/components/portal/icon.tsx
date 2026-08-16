/** A Material Symbols Outlined glyph — see the stylesheet link in
 * app/layout.tsx. `filled` switches the icon to its solid variant (used for
 * the active sidebar item, matching the Stitch reference). */
export function Icon({
  name,
  className = "",
  filled = false,
}: {
  name: string;
  className?: string;
  filled?: boolean;
}) {
  return (
    <span
      className={`material-symbols-outlined ${className}`}
      style={filled ? { fontVariationSettings: "'FILL' 1" } : undefined}
    >
      {name}
    </span>
  );
}
