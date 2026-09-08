export type FormState = {
  errors: Record<string, string[]>;
  formError?: string;
  /** A non-error, informational message — e.g. "check your email to
   * verify your account". Rendered in a neutral/positive style, never the
   * red error style `formError` uses. */
  notice?: string;
  /** Set when a Supabase sign-up succeeded but the account still needs
   * email confirmation before a session exists. The form uses this to
   * switch to its "check your email" state and offer a resend control. */
  awaitingEmailVerification?: boolean;
  values?: Record<string, string>;
} | null;
