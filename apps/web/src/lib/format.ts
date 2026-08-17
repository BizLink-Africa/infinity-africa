/** Amounts from the API arrive as strings (Decimal) — never numbers, to avoid
 * float precision surprises in transit. Accepts either here regardless. */
export function formatCurrency(amount: string | number, currency: string): string {
  const value = typeof amount === "string" ? Number(amount) : amount;

  try {
    return new Intl.NumberFormat("en-TZ", {
      style: "currency",
      currency,
      currencyDisplay: "code",
      maximumFractionDigits: 2,
    }).format(value);
  } catch {
    return `${currency} ${value.toLocaleString()}`;
  }
}

/** Masks a phone number or account number for display in the Super Admin
 * withdrawal approval queue — shows only the last 4 characters, e.g.
 * "+255700000000" -> "•••• 0000". Presentation-only: the raw value is never
 * withheld from the API response, only from what's rendered on screen. */
export function maskAccountIdentifier(identifier: string): string {
  const digits = identifier.trim();
  if (digits.length <= 4) return digits;
  return `•••• ${digits.slice(-4)}`;
}

export function formatDateTime(iso: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(iso));
}
