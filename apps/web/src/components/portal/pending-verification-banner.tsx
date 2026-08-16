import { Icon } from "./icon";

/** Shown across the merchant portal while account_status is
 * PENDING_VERIFICATION — the portal stays fully browsable, this just sets
 * the right expectation. */
export function PendingVerificationBanner() {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      <Icon name="hourglass_top" className="text-[20px] text-amber-600" />
      <p>
        <span className="font-semibold">Your account is pending verification.</span> You can explore the portal now
        — some actions may be limited until your documents are reviewed.
      </p>
    </div>
  );
}
