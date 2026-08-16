/** Live provider-health indicator — a ping animation for operational/degraded
 * states, a solid dot only (no animation) for down. */
export function PulsingDot({ color, animate = true }: { color: string; animate?: boolean }) {
  return (
    <span className="relative flex h-2.5 w-2.5">
      {animate && <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${color} opacity-75`} />}
      <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${color}`} />
    </span>
  );
}
