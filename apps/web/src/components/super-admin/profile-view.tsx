"use client";

import { useState } from "react";

import { Card } from "@/components/portal/card";
import { createClient } from "@/lib/supabase/client";

export function ProfileView({ email, fullName: initialFullName }: { email: string; fullName: string }) {
  const [fullName, setFullName] = useState(initialFullName);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  async function handleSave(event: React.FormEvent) {
    event.preventDefault();
    setSaved(false);
    setError("");

    if (!fullName.trim()) {
      setError("Full name cannot be blank.");
      return;
    }

    setSaving(true);
    const supabase = createClient();
    const { error: updateError } = await supabase.auth.updateUser({ data: { full_name: fullName.trim() } });

    if (updateError) {
      setError(updateError.message || "Something went wrong. Please try again.");
      setSaving(false);
      return;
    }

    setFullName(fullName.trim());
    setSaved(true);
    setSaving(false);
  }

  return (
    <div className="space-y-8">
      <Card id="account" className="scroll-mt-24">
        <h3 className="text-2xl font-semibold text-on-background mb-5">My Account</h3>
        <div className="grid sm:grid-cols-2 gap-5">
          <div>
            <p className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide mb-1">Email</p>
            <p className="text-sm text-on-background">{email}</p>
          </div>
          <div>
            <p className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide mb-1">Role</p>
            <p className="text-sm text-on-background">Super Admin</p>
          </div>
        </div>
      </Card>

      <Card id="profile" className="scroll-mt-24">
        <h3 className="text-2xl font-semibold text-on-background mb-5">Profile</h3>
        <form onSubmit={handleSave} className="space-y-5">
          {saved && (
            <div className="rounded-lg bg-primary-container/10 px-4 py-3 text-sm text-on-surface">
              Profile updated.
            </div>
          )}
          {error && <div className="rounded-lg bg-error/10 px-4 py-3 text-sm font-medium text-error">{error}</div>}
          <div>
            <label className="block text-sm font-medium text-on-surface-variant mb-1.5">Full Name</label>
            <input
              className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm max-w-md"
              type="text"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
            />
          </div>
          <button
            className="bg-primary-container text-on-primary text-sm font-medium py-3 px-6 rounded-lg hover:opacity-90 transition-opacity disabled:opacity-60"
            type="submit"
            disabled={saving}
          >
            {saving ? "Saving…" : "Save Profile"}
          </button>
        </form>
      </Card>
    </div>
  );
}
