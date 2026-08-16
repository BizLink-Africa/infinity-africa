const METHOD_CLASSES: Record<string, string> = {
  GET: "bg-blue-100 text-blue-700",
  POST: "bg-primary-container/10 text-primary",
  PATCH: "bg-amber-100 text-amber-700",
  DELETE: "bg-red-100 text-red-700",
};

/** A single "METHOD /path — description" row, used to summarize an
 * endpoint at the top of its reference section. */
export function EndpointRow({
  method,
  path,
  description,
  auth,
}: {
  method: "GET" | "POST" | "PATCH" | "DELETE";
  path: string;
  description: string;
  auth?: string;
}) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 py-3.5 border-b border-outline-variant/40 last:border-b-0">
      <div className="flex items-center gap-3 shrink-0">
        <span className={`inline-flex w-16 justify-center px-2 py-1 rounded-full text-xs font-bold ${METHOD_CLASSES[method]}`}>
          {method}
        </span>
        <code className="text-sm font-mono text-on-surface">{path}</code>
      </div>
      <p className="text-sm text-on-surface-variant flex-1">{description}</p>
      {auth && <span className="text-xs font-semibold text-on-surface-variant shrink-0">{auth}</span>}
    </div>
  );
}
