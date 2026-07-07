"use client";

import { useEffect, useState } from "react";

import {
  ApiError,
  type AccessRequest,
  type Invitation,
  type OrgUser,
  type Role,
  type SetupStatus,
  api,
} from "@/lib/api";

const ROLE_OPTIONS: { value: Role; label: string }[] = [
  { value: "member", label: "User" },
  { value: "auditor", label: "Auditor" },
  { value: "owner", label: "Owner" },
];

function roleLabel(role: Role) {
  if (role === "member") return "User";
  if (role === "admin") return "Admin";
  return role.charAt(0).toUpperCase() + role.slice(1);
}

export function SettingsPanel({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [setup, setSetup] = useState<SetupStatus | null>(null);
  const [users, setUsers] = useState<OrgUser[]>([]);
  const [requests, setRequests] = useState<AccessRequest[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [userEmail, setUserEmail] = useState("");
  const [userName, setUserName] = useState("");
  const [userPassword, setUserPassword] = useState("");
  const [userRole, setUserRole] = useState<Role>("member");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<Role>("member");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    const [nextSetup, nextUsers, nextRequests, nextInvites] = await Promise.all([
      api.setupStatus(),
      api.users(),
      api.accessRequests(),
      api.invitations(),
    ]);
    setSetup(nextSetup);
    setUsers(nextUsers);
    setRequests(nextRequests);
    setInvitations(nextInvites);
  }

  useEffect(() => {
    if (!open) return;
    setError(null);
    setNotice(null);
    load().catch((err) =>
      setError(err instanceof ApiError ? err.message : "Could not load settings"),
    );
  }, [open]);

  if (!open) return null;

  async function createUser(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await api.createUser({
        email: userEmail,
        password: userPassword,
        full_name: userName || undefined,
        role: userRole,
      });
      setUserEmail("");
      setUserName("");
      setUserPassword("");
      setUserRole("member");
      setNotice("User created.");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create user");
    } finally {
      setBusy(false);
    }
  }

  async function createInvitation(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await api.createInvitation({ email: inviteEmail, role: inviteRole });
      setInviteEmail("");
      setInviteRole("member");
      setNotice("Invitation created.");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create invitation");
    } finally {
      setBusy(false);
    }
  }

  async function reviewAccessRequest(id: string, action: "approve" | "reject") {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      if (action === "approve") {
        await api.approveAccessRequest(id);
        setNotice("Access request approved.");
      } else {
        await api.rejectAccessRequest(id);
        setNotice("Access request rejected.");
      }
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not update request");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/40 px-4 py-6">
      <section className="mx-auto max-h-[88vh] max-w-4xl overflow-y-auto rounded-lg bg-white p-6 shadow-xl dark:bg-neutral-950">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold">Settings</h2>
            {setup?.organization_name && (
              <p className="mt-1 text-sm text-neutral-500">{setup.organization_name}</p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-neutral-300 px-3 py-1.5 text-sm transition hover:bg-neutral-100 dark:border-neutral-700 dark:hover:bg-neutral-900"
          >
            Close
          </button>
        </div>

        {error && (
          <p className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-300">
            {error}
          </p>
        )}
        {notice && (
          <p className="mt-4 rounded-md bg-green-50 px-3 py-2 text-sm text-green-700 dark:bg-green-950/40 dark:text-green-300">
            {notice}
          </p>
        )}

        <div className="mt-6 grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="space-y-8">
            <section>
              <h3 className="text-sm font-medium">Users</h3>
              <div className="mt-3 overflow-hidden rounded-lg border border-neutral-200 dark:border-neutral-800">
                <table className="w-full text-sm">
                  <thead className="bg-neutral-50 text-left text-xs uppercase tracking-wide text-neutral-400 dark:bg-neutral-900">
                    <tr>
                      <th className="px-3 py-2 font-medium">Name</th>
                      <th className="px-3 py-2 font-medium">Email</th>
                      <th className="px-3 py-2 font-medium">Role</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((user) => (
                      <tr
                        key={user.user_id}
                        className="border-t border-neutral-100 dark:border-neutral-800/60"
                      >
                        <td className="px-3 py-2">{user.full_name ?? "Unassigned"}</td>
                        <td className="px-3 py-2 text-neutral-500">{user.email}</td>
                        <td className="px-3 py-2">{roleLabel(user.role)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <form onSubmit={createUser} className="mt-4 grid gap-3 sm:grid-cols-2">
                <Field label="Email" type="email" value={userEmail} onChange={setUserEmail} required />
                <Field label="Name" value={userName} onChange={setUserName} />
                <Field
                  label="Password"
                  type="password"
                  value={userPassword}
                  onChange={setUserPassword}
                  required
                />
                <RoleSelect label="Role" value={userRole} onChange={setUserRole} />
                <button
                  type="submit"
                  disabled={busy}
                  className="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-neutral-700 disabled:opacity-50 dark:bg-white dark:text-neutral-900 sm:col-span-2"
                >
                  Create user
                </button>
              </form>
            </section>

            <section>
              <h3 className="text-sm font-medium">Access requests</h3>
              <div className="mt-3 space-y-2">
                {requests.length === 0 && (
                  <p className="text-sm text-neutral-500">No pending requests.</p>
                )}
                {requests.map((request) => (
                  <div
                    key={request.id}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-neutral-200 px-3 py-2 text-sm dark:border-neutral-800"
                  >
                    <div>
                      <div className="font-medium">{request.full_name ?? request.email}</div>
                      <div className="text-xs text-neutral-500">{request.email}</div>
                    </div>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => reviewAccessRequest(request.id, "approve")}
                        className="rounded-md border border-neutral-300 px-3 py-1 text-xs transition hover:bg-neutral-100 disabled:opacity-50 dark:border-neutral-700 dark:hover:bg-neutral-900"
                      >
                        Approve
                      </button>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => reviewAccessRequest(request.id, "reject")}
                        className="rounded-md border border-neutral-300 px-3 py-1 text-xs transition hover:bg-neutral-100 disabled:opacity-50 dark:border-neutral-700 dark:hover:bg-neutral-900"
                      >
                        Reject
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </div>

          <div className="space-y-8">
            <section>
              <h3 className="text-sm font-medium">Invitations</h3>
              <form onSubmit={createInvitation} className="mt-3 space-y-3">
                <Field
                  label="Email"
                  type="email"
                  value={inviteEmail}
                  onChange={setInviteEmail}
                  required
                />
                <RoleSelect label="Role" value={inviteRole} onChange={setInviteRole} />
                <button
                  type="submit"
                  disabled={busy}
                  className="w-full rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-neutral-700 disabled:opacity-50 dark:bg-white dark:text-neutral-900"
                >
                  Send invitation
                </button>
              </form>
              <div className="mt-4 space-y-2">
                {invitations.length === 0 && (
                  <p className="text-sm text-neutral-500">No pending invitations.</p>
                )}
                {invitations.map((invite) => (
                  <div
                    key={invite.id}
                    className="rounded-lg border border-neutral-200 px-3 py-2 text-sm dark:border-neutral-800"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{invite.email}</span>
                      <span className="text-xs text-neutral-500">{roleLabel(invite.role)}</span>
                    </div>
                    <code className="mt-2 block break-all rounded-md bg-neutral-100 px-2 py-1 text-xs dark:bg-neutral-900">
                      {invite.token}
                    </code>
                  </div>
                ))}
              </div>
            </section>

            <section>
              <h3 className="text-sm font-medium">Configuration</h3>
              <div className="mt-3 divide-y divide-neutral-100 rounded-lg border border-neutral-200 px-3 dark:divide-neutral-800 dark:border-neutral-800">
                {setup?.configuration.map((item) => (
                  <div key={item.key} className="flex items-center justify-between gap-3 py-2">
                    <div>
                      <div className="text-sm font-medium">{item.label}</div>
                      {item.detail && (
                        <div className="text-xs text-neutral-500">{item.detail}</div>
                      )}
                    </div>
                    <span
                      className={`shrink-0 rounded-full px-2 py-0.5 text-xs ${
                        item.configured
                          ? "bg-green-100 text-green-800 dark:bg-green-950/50 dark:text-green-300"
                          : "bg-amber-100 text-amber-800 dark:bg-amber-950/50 dark:text-amber-300"
                      }`}
                    >
                      {item.configured ? "Configured" : item.required ? "Required" : "Pending"}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          </div>
        </div>
      </section>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  required = false,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  required?: boolean;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-neutral-500">{label}</span>
      <input
        type={type}
        value={value}
        required={required}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-neutral-500 dark:border-neutral-700"
      />
    </label>
  );
}

function RoleSelect({
  label,
  value,
  onChange,
}: {
  label: string;
  value: Role;
  onChange: (v: Role) => void;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-neutral-500">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as Role)}
        className="w-full rounded-lg border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-neutral-500 dark:border-neutral-700"
      >
        {ROLE_OPTIONS.map((role) => (
          <option key={role.value} value={role.value}>
            {role.label}
          </option>
        ))}
      </select>
    </label>
  );
}
