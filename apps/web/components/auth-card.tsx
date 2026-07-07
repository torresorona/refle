"use client";

import { useEffect, useState } from "react";

import { ApiError, type SetupStatus, api } from "@/lib/api";

type Mode = "setup" | "login" | "request";

export function AuthCard({ onAuthed }: { onAuthed: () => void }) {
  const [setup, setSetup] = useState<SetupStatus | null>(null);
  const [mode, setMode] = useState<Mode>("login");
  const [orgName, setOrgName] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .setupStatus()
      .then((status) => {
        setSetup(status);
        setMode(status.organization_configured ? "login" : "setup");
      })
      .catch(() => {
        setError("Failed to load setup status. Is the API running?");
      });
  }, []);

  async function refreshSetup() {
    const status = await api.setupStatus();
    setSetup(status);
    return status;
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      if (mode === "setup") {
        await api.register({
          org_name: orgName,
          email,
          password,
          full_name: fullName || undefined,
        });
        onAuthed();
        return;
      }

      if (mode === "request") {
        await api.requestAccess({
          email,
          password,
          full_name: fullName || undefined,
        });
        setNotice("Access request sent for owner approval.");
        setPassword("");
        await refreshSetup();
        return;
      }

      await api.login({ email, password });
      onAuthed();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  const organizationConfigured = setup?.organization_configured ?? false;

  return (
    <div
      className={`mx-auto mt-16 px-6 ${
        organizationConfigured ? "max-w-md" : "max-w-2xl"
      }`}
    >
      <h1 className="text-2xl font-semibold tracking-tight">refle</h1>
      <p className="mt-1 text-sm text-neutral-500">AI-Powered Automated Compliance</p>

      <div
        className={`mt-8 ${
          organizationConfigured ? "" : "grid gap-6 md:grid-cols-[1.05fr_0.95fr]"
        }`}
      >
        <section className="rounded-lg border border-neutral-200 p-5 dark:border-neutral-800">
          <div className="mb-5">
            <h2 className="text-sm font-medium">
              {organizationConfigured ? "Sign in" : "Create organization"}
            </h2>
            {setup?.organization_name && (
              <p className="mt-1 text-xs text-neutral-500">{setup.organization_name}</p>
            )}
          </div>

          {organizationConfigured && (
            <div className="mb-5 flex gap-1 rounded-lg bg-neutral-100 p-1 text-sm dark:bg-neutral-900">
              {(["login", "request"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => {
                    setMode(m);
                    setError(null);
                    setNotice(null);
                  }}
                  className={`flex-1 rounded-md px-3 py-1.5 transition ${
                    mode === m
                      ? "bg-white shadow-sm dark:bg-neutral-800"
                      : "text-neutral-500"
                  }`}
                >
                  {m === "login" ? "Sign in" : "Request access"}
                </button>
              ))}
            </div>
          )}

          <form onSubmit={submit} className="space-y-3">
            {mode === "setup" && (
              <Field
                label="Organization name"
                value={orgName}
                onChange={setOrgName}
                required
                placeholder="Acme Inc."
              />
            )}
            {(mode === "setup" || mode === "request") && (
              <Field
                label="Your name"
                value={fullName}
                onChange={setFullName}
                placeholder="Jane Doe"
              />
            )}
            <Field
              label="Email"
              type="email"
              value={email}
              onChange={setEmail}
              required
              placeholder="you@company.com"
            />
            <Field
              label="Password"
              type="password"
              value={password}
              onChange={setPassword}
              required
              placeholder="At least 8 characters"
            />

            {error && (
              <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-300">
                {error}
              </p>
            )}
            {notice && (
              <p className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-700 dark:bg-green-950/40 dark:text-green-300">
                {notice}
              </p>
            )}

            <button
              type="submit"
              disabled={busy || !setup}
              className="w-full rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-neutral-700 disabled:opacity-50 dark:bg-white dark:text-neutral-900"
            >
              {busy
                ? "Working..."
                : mode === "setup"
                  ? "Create organization"
                  : mode === "request"
                    ? "Request access"
                    : "Sign in"}
            </button>
          </form>
        </section>

        {!organizationConfigured && <SetupChecklist setup={setup} />}
      </div>
    </div>
  );
}

function SetupChecklist({ setup }: { setup: SetupStatus | null }) {
  return (
    <section className="rounded-lg border border-neutral-200 p-5 dark:border-neutral-800">
      <h2 className="text-sm font-medium">Configuration</h2>
      <div className="mt-4 divide-y divide-neutral-100 dark:divide-neutral-800">
        {setup ? (
          setup.configuration.map((item) => (
            <div key={item.key} className="flex items-start justify-between gap-3 py-2">
              <div>
                <div className="text-sm font-medium">{item.label}</div>
                {item.detail && (
                  <div className="mt-0.5 text-xs text-neutral-500">{item.detail}</div>
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
          ))
        ) : (
          <p className="py-2 text-sm text-neutral-500">Loading setup status...</p>
        )}
      </div>
    </section>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  required = false,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  required?: boolean;
  placeholder?: string;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-neutral-500">{label}</span>
      <input
        type={type}
        value={value}
        required={required}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-neutral-500 dark:border-neutral-700"
      />
    </label>
  );
}
