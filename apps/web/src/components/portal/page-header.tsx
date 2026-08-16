export function PageHeader({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <header className="flex flex-col md:flex-row md:items-end justify-between gap-4">
      <div>
        <h2 className="text-3xl font-bold tracking-tight text-on-background">{title}</h2>
        <p className="text-lg text-on-surface-variant mt-1">{description}</p>
      </div>
      {action}
    </header>
  );
}
