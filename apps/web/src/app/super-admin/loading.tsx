export default function SuperAdminLoading() {
  return (
    <div className="space-y-8 animate-pulse">
      <div className="h-8 w-64 bg-surface-container-highest rounded-lg" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-28 bg-surface-container-highest rounded-xl" />
        ))}
      </div>
      <div className="h-72 bg-surface-container-highest rounded-xl" />
    </div>
  );
}
