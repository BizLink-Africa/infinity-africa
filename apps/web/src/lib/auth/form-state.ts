export type FormState = {
  errors: Record<string, string[]>;
  formError?: string;
  values?: Record<string, string>;
} | null;
