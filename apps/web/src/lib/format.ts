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

export function formatDateTime(iso: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(iso));
}
