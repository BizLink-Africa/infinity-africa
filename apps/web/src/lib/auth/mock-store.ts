import "server-only";

import { randomBytes, randomUUID, scryptSync, timingSafeEqual } from "crypto";

/**
 * Fallback merchant identity store used when Supabase Auth isn't reachable
 * (see supabase-status.ts). Same in-memory-singleton pattern as
 * lib/admin/api.ts's `store` — persists for the life of the dev server
 * process, resets on restart. This is explicitly a mock/demo path, not a
 * production auth store: passwords are salted+hashed with scrypt (adequate
 * for a local fallback), but there is no rate limiting, no email
 * verification, and the session cookie (see mock-session.ts) is an
 * unsigned user id.
 */

export interface MockUser {
  id: string;
  email: string;
  fullName: string;
  phone: string;
  passwordHash: string;
  salt: string;
  createdAt: string;
}

const store: { users: MockUser[] } = { users: [] };

function hashPassword(password: string, salt: string): string {
  return scryptSync(password, salt, 64).toString("hex");
}

export function findByEmail(email: string): MockUser | undefined {
  const normalized = email.trim().toLowerCase();
  return store.users.find((u) => u.email === normalized);
}

export function findById(id: string): MockUser | undefined {
  return store.users.find((u) => u.id === id);
}

export function createUser(input: { fullName: string; email: string; phone: string; password: string }): MockUser {
  const salt = randomBytes(16).toString("hex");
  const user: MockUser = {
    id: `mock-${randomUUID()}`,
    email: input.email.trim().toLowerCase(),
    fullName: input.fullName.trim(),
    phone: input.phone.trim(),
    passwordHash: hashPassword(input.password, salt),
    salt,
    createdAt: new Date().toISOString(),
  };
  store.users.push(user);
  return user;
}

export function verifyPassword(user: MockUser, password: string): boolean {
  const candidate = hashPassword(password, user.salt);
  const a = Buffer.from(candidate, "hex");
  const b = Buffer.from(user.passwordHash, "hex");
  return a.length === b.length && timingSafeEqual(a, b);
}
