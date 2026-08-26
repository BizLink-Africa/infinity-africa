"use client";

import { useEffect, useState } from "react";

import { Card, tdClass, thClass } from "@/components/portal/card";
import { EmptyState } from "@/components/portal/empty-state";
import { PageHeader } from "@/components/portal/page-header";
import { StatusBadge } from "@/components/portal/status-badge";
import { formatDateTime } from "@/lib/format";
import { createMerchantUser, deactivateMerchantUser, listMerchantUsers, updateMerchantUser } from "@/lib/portal/api";
import { MERCHANT_ROLES, UserRole, USER_ROLE_LABELS } from "@/lib/portal/roles";
import type { MerchantUser } from "@/lib/portal/types";

const STATUS_TONE: Record<MerchantUser["status"], "positive" | "pending" | "neutral"> = {
  active: "positive",
  invited: "pending",
  suspended: "neutral",
};

const STATUS_LABEL: Record<MerchantUser["status"], string> = {
  active: "Active",
  invited: "Invited",
  suspended: "Deactivated",
};

function initials(name: string | null): string {
  if (!name) return "?";
  return name
    .split(" ")
    .filter(Boolean)
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

export function UsersView() {
  const [users, setUsers] = useState<MerchantUser[]>([]);
  const [loading, setLoading] = useState(true);

  const [formOpen, setFormOpen] = useState(false);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<MerchantUser["role"]>(UserRole.MERCHANT_STAFF);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const [createSuccess, setCreateSuccess] = useState("");

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingRole, setEditingRole] = useState<MerchantUser["role"]>(UserRole.MERCHANT_STAFF);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [deactivatingId, setDeactivatingId] = useState<string | null>(null);
  const [rowError, setRowError] = useState("");

  useEffect(() => {
    listMerchantUsers()
      .then(setUsers)
      .finally(() => setLoading(false));
  }, []);

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault();
    if (!fullName.trim() || !email.trim()) return;

    setCreating(true);
    setCreateError("");
    setCreateSuccess("");
    try {
      const user = await createMerchantUser({ full_name: fullName.trim(), email: email.trim(), role });
      setUsers((prev) => [user, ...prev]);
      setFormOpen(false);
      setFullName("");
      setEmail("");
      setRole(UserRole.MERCHANT_STAFF);
      setCreateSuccess("Invitation email sent.");
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Couldn't invite this person. Please try again.");
    } finally {
      setCreating(false);
    }
  }

  function startEditing(user: MerchantUser) {
    setEditingId(user.id);
    setEditingRole(user.role);
    setRowError("");
  }

  async function handleSaveRole(userId: string) {
    setSavingId(userId);
    setRowError("");
    try {
      const updated = await updateMerchantUser(userId, { role: editingRole });
      setUsers((prev) => prev.map((u) => (u.id === userId ? updated : u)));
      setEditingId(null);
    } catch (err) {
      setRowError(err instanceof Error ? err.message : "Couldn't update this teammate's role.");
    } finally {
      setSavingId(null);
    }
  }

  async function handleDeactivate(user: MerchantUser) {
    if (!window.confirm(`Deactivate ${user.full_name ?? user.email ?? "this user"}? They will lose portal access.`)) {
      return;
    }
    setDeactivatingId(user.id);
    setRowError("");
    try {
      const updated = await deactivateMerchantUser(user.id);
      setUsers((prev) => prev.map((u) => (u.id === user.id ? updated : u)));
    } catch (err) {
      setRowError(err instanceof Error ? err.message : "Couldn't deactivate this teammate.");
    } finally {
      setDeactivatingId(null);
    }
  }

  if (loading) {
    return (
      <div className="space-y-8">
        <PageHeader title="Team" description="Manage who has access to your merchant portal." />
        <Card>
          <p className="text-sm text-on-surface-variant">Loading your team…</p>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title="Team"
        description="Manage who has access to your merchant portal."
        action={
          !formOpen && (
            <button
              type="button"
              onClick={() => {
                setCreateSuccess("");
                setFormOpen(true);
              }}
              className="bg-primary-container text-on-primary text-sm font-medium py-2.5 px-5 rounded-lg hover:opacity-90 transition-opacity"
            >
              Add User
            </button>
          )
        }
      />

      {createSuccess && !formOpen && (
        <div className="rounded-lg bg-primary-container/10 px-4 py-3 text-sm font-medium text-primary">
          {createSuccess}
        </div>
      )}

      {formOpen && (
        <Card>
          <form onSubmit={handleCreate} className="space-y-5">
            <h3 className="text-2xl font-semibold text-on-background">Add User</h3>
            {createError && (
              <div className="rounded-lg bg-error/10 px-4 py-3 text-sm font-medium text-error">{createError}</div>
            )}
            <div className="grid sm:grid-cols-2 gap-5">
              <div>
                <label className="block text-sm font-medium text-on-surface-variant mb-1.5">Full Name</label>
                <input
                  className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm"
                  placeholder="e.g. David Komba"
                  type="text"
                  value={fullName}
                  onChange={(event) => setFullName(event.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-on-surface-variant mb-1.5">Email</label>
                <input
                  className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm"
                  placeholder="e.g. david@merchant.co.tz"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-on-surface-variant mb-1.5">Role</label>
                <select
                  className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm"
                  value={role}
                  onChange={(event) => setRole(event.target.value as MerchantUser["role"])}
                >
                  {MERCHANT_ROLES.map((option) => (
                    <option key={option} value={option}>
                      {USER_ROLE_LABELS[option]}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <p className="text-xs text-on-surface-variant">
              We&apos;ll email this person an invite to set their own password and join your merchant portal.
            </p>
            <div className="flex items-center gap-3">
              <button
                type="submit"
                disabled={creating || !fullName.trim() || !email.trim()}
                className="bg-primary-container text-on-primary text-sm font-medium py-2.5 px-5 rounded-lg hover:opacity-90 transition-opacity disabled:opacity-60"
              >
                {creating ? "Inviting…" : "Send Invite"}
              </button>
              <button
                type="button"
                onClick={() => setFormOpen(false)}
                className="text-sm font-medium text-on-surface-variant hover:text-on-background"
              >
                Cancel
              </button>
            </div>
          </form>
        </Card>
      )}

      {rowError && <div className="rounded-lg bg-error/10 px-4 py-3 text-sm font-medium text-error">{rowError}</div>}

      {users.length === 0 ? (
        <Card>
          <EmptyState
            icon="group_add"
            heading="No teammates yet"
            body="Invite a staff member or developer to help manage your merchant portal."
            actionLabel="Add User"
            onAction={() => setFormOpen(true)}
          />
        </Card>
      ) : (
        <Card padded={false}>
          <div className="overflow-x-auto">
            <table className="w-full text-left min-w-[760px]">
              <thead>
                <tr className="text-on-surface-variant text-xs font-semibold border-t border-surface-container-highest">
                  <th className={thClass}>Name</th>
                  <th className={thClass}>Email</th>
                  <th className={thClass}>Role</th>
                  <th className={thClass}>Status</th>
                  <th className={thClass}>Joined</th>
                  <th className={`${thClass} text-right`}>Actions</th>
                </tr>
              </thead>
              <tbody className="text-sm">
                {users.map((user) => (
                  <tr key={user.id} className="border-t border-surface-container-highest">
                    <td className={tdClass}>
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-full bg-primary-container/15 text-primary flex items-center justify-center font-bold text-xs shrink-0">
                          {initials(user.full_name)}
                        </div>
                        <span className="font-medium text-on-background">{user.full_name ?? "—"}</span>
                      </div>
                    </td>
                    <td className={`${tdClass} text-on-surface-variant`}>{user.email ?? "—"}</td>
                    <td className={tdClass}>
                      {editingId === user.id ? (
                        <select
                          className="px-2.5 py-1.5 bg-surface-container-low border border-surface-container-highest rounded-lg text-xs font-semibold"
                          value={editingRole}
                          onChange={(event) => setEditingRole(event.target.value as MerchantUser["role"])}
                        >
                          {MERCHANT_ROLES.map((option) => (
                            <option key={option} value={option}>
                              {USER_ROLE_LABELS[option]}
                            </option>
                          ))}
                        </select>
                      ) : (
                        USER_ROLE_LABELS[user.role]
                      )}
                    </td>
                    <td className={tdClass}>
                      <StatusBadge label={STATUS_LABEL[user.status]} tone={STATUS_TONE[user.status]} dot />
                    </td>
                    <td className={`${tdClass} text-on-surface-variant text-xs`}>{formatDateTime(user.created_at)}</td>
                    <td className={`${tdClass} text-right`}>
                      {user.status !== "suspended" && (
                        <div className="flex items-center justify-end gap-3">
                          {editingId === user.id ? (
                            <>
                              <button
                                type="button"
                                onClick={() => handleSaveRole(user.id)}
                                disabled={savingId === user.id}
                                className="text-primary text-xs font-semibold hover:underline disabled:opacity-60"
                              >
                                {savingId === user.id ? "Saving…" : "Save"}
                              </button>
                              <button
                                type="button"
                                onClick={() => setEditingId(null)}
                                className="text-on-surface-variant text-xs font-semibold hover:underline"
                              >
                                Cancel
                              </button>
                            </>
                          ) : (
                            <button
                              type="button"
                              onClick={() => startEditing(user)}
                              className="text-primary text-xs font-semibold hover:underline"
                            >
                              Edit
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => handleDeactivate(user)}
                            disabled={deactivatingId === user.id}
                            className="text-error text-xs font-semibold hover:underline disabled:opacity-60"
                          >
                            {deactivatingId === user.id ? "Deactivating…" : "Deactivate"}
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
