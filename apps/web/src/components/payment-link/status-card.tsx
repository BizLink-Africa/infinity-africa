import { formatCurrency } from "@/lib/format";

export type StatusVariant =
  | "unavailable"
  | "expired"
  | "cancelled"
  | "paid"
  | "processing"
  | "success"
  | "error";

interface StatusCardProps {
  variant: StatusVariant;
  title: string;
  message?: string;
  summary?: { merchantName: string; amount: string; currency: string };
  children?: React.ReactNode;
}

const ICON_WRAP_CLASS: Record<StatusVariant, string> = {
  unavailable: "bg-surface-container text-on-surface-variant",
  expired: "bg-surface-container text-on-surface-variant",
  cancelled: "bg-surface-container text-on-surface-variant",
  paid: "bg-accent text-primary",
  processing: "bg-secondary-container text-secondary",
  success: "bg-accent text-primary",
  error: "bg-error-container text-on-error-container",
};

export function StatusCard({ variant, title, message, summary, children }: StatusCardProps) {
  return (
    <div className="flex flex-col items-center p-8 text-center sm:p-10">
      <div className={`flex h-14 w-14 items-center justify-center rounded-full ${ICON_WRAP_CLASS[variant]}`}>
        <StatusIcon variant={variant} />
      </div>

      <h1 className="mt-4 text-xl font-bold text-on-surface">{title}</h1>
      {message && <p className="mt-2 text-sm text-on-surface-variant">{message}</p>}

      {summary && (
        <div className="mt-5 w-full rounded border border-outline-variant bg-surface-container px-4 py-3">
          <p className="text-xs text-on-surface-variant">{summary.merchantName}</p>
          <p className="mt-0.5 text-lg font-semibold text-on-surface">
            {formatCurrency(summary.amount, summary.currency)}
          </p>
        </div>
      )}

      {children}
    </div>
  );
}

function StatusIcon({ variant }: { variant: StatusVariant }) {
  if (variant === "processing") {
    return (
      <span
        aria-hidden
        className="h-6 w-6 animate-spin rounded-full border-2 border-current border-t-transparent"
      />
    );
  }

  if (variant === "success" || variant === "paid") {
    return (
      <svg viewBox="0 0 24 24" fill="none" strokeWidth={2} stroke="currentColor" className="h-7 w-7">
        <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
      </svg>
    );
  }

  if (variant === "error") {
    return (
      <svg viewBox="0 0 24 24" fill="none" strokeWidth={2} stroke="currentColor" className="h-7 w-7">
        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
      </svg>
    );
  }

  if (variant === "expired") {
    return (
      <svg viewBox="0 0 24 24" fill="none" strokeWidth={2} stroke="currentColor" className="h-7 w-7">
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l2.5 2.5" />
        <circle cx="12" cy="12" r="8.25" strokeLinecap="round" />
      </svg>
    );
  }

  if (variant === "cancelled") {
    return (
      <svg viewBox="0 0 24 24" fill="none" strokeWidth={2} stroke="currentColor" className="h-7 w-7">
        <circle cx="12" cy="12" r="8.25" strokeLinecap="round" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 9l6 6M15 9l-6 6" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 24 24" fill="none" strokeWidth={2} stroke="currentColor" className="h-7 w-7">
      <circle cx="12" cy="12" r="8.25" strokeLinecap="round" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 11v5M12 8.25h.01" />
    </svg>
  );
}
