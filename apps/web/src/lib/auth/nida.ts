/**
 * Tanzania NIDA (National ID) number — client-side shape check for the
 * signup form. The backend (app/core/nida.py) is the source of truth and
 * re-validates; this just gives the merchant an immediate error before
 * submit. NIDA is 20 digits, commonly written grouped with dashes.
 */

export const NIDA_DIGIT_LENGTH = 20;

export function nidaDigits(raw: string): string {
  return raw.replace(/\D/g, "");
}

export function isValidNida(raw: string): boolean {
  return nidaDigits(raw).length === NIDA_DIGIT_LENGTH;
}
