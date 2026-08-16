export function FeatureGrid({ children, columns = 3 }: { children: React.ReactNode; columns?: 2 | 3 | 4 }) {
  const colsClass = columns === 2 ? "md:grid-cols-2" : columns === 4 ? "md:grid-cols-4" : "md:grid-cols-3";
  return <div className={`grid grid-cols-1 ${colsClass} gap-6`}>{children}</div>;
}
