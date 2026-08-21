"use client";

import { useState, useTransition } from "react";

import {
  approveOnboardingAction,
  rejectOnboardingAction,
  requestInfoOnboardingAction,
} from "./admin-actions";

export interface ReviewOutcome {
  type: "success" | "error";
  message: string;
}

/** Drives the Approve/Reject/Request Info actions for one onboarding
 * submission — used by both the review-queue table row and the submission
 * detail page (same three server actions, same note field, same
 * success/error feedback need). Runs each action via useTransition rather
 * than a native <form formAction>, so a result — success or failure — is
 * always visible here instead of only a silent revalidatePath: approving
 * an already-verified submission, for instance, succeeds but changes
 * nothing visible in the table, which previously looked exactly like a
 * broken button. */
export function useOnboardingReviewAction(id: string) {
  const [note, setNote] = useState("");
  const [outcome, setOutcome] = useState<ReviewOutcome | null>(null);
  const [isPending, startTransition] = useTransition();

  function run(action: () => Promise<void>, successMessage: string, failureMessage: string) {
    setOutcome(null);
    startTransition(async () => {
      try {
        await action();
        setOutcome({ type: "success", message: successMessage });
        setNote("");
      } catch (err) {
        setOutcome({ type: "error", message: err instanceof Error ? err.message : failureMessage });
      }
    });
  }

  const approve = () => run(() => approveOnboardingAction(id), "Approved.", "Couldn't approve — try again.");
  const reject = () =>
    run(() => rejectOnboardingAction(id, note.trim() || null), "Rejected.", "Couldn't reject — try again.");
  const requestInfo = () =>
    run(
      () => requestInfoOnboardingAction(id, note.trim() || null),
      "Requested more information.",
      "Couldn't send the request — try again.",
    );

  return { note, setNote, outcome, isPending, approve, reject, requestInfo };
}
