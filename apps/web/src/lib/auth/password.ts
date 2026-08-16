/**
 * Password policy: min 8 chars, at least one uppercase, lowercase, number,
 * and symbol. Every violated rule is checked independently (not short
 * circuited) so the form can show all of them at once.
 */
export function validatePassword(password: string): string[] {
  const errors: string[] = [];

  if (password.length < 8) {
    errors.push("Password must be at least 8 characters.");
  }
  if (!/[A-Z]/.test(password)) {
    errors.push("Password must include at least one uppercase letter.");
  }
  if (!/[a-z]/.test(password)) {
    errors.push("Password must include at least one lowercase letter.");
  }
  if (!/[0-9]/.test(password)) {
    errors.push("Password must include at least one number.");
  }
  if (!/[^A-Za-z0-9]/.test(password)) {
    errors.push("Password must include at least one symbol.");
  }

  return errors;
}

export function isEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}
