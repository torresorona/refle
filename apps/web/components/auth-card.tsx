"use client";

import { useState } from "react";

import { ApiError, api } from "@/lib/api";

export function AuthCard({ onAuthed }: { onAuthed: () => void }) {
  const [mode, setMode] = useState<"register" | "login">("register");
  const [orgName, setOrgName] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "register") {
        await api.register({
          org_name: orgName,
          email,
          password,
          full_name: fullName || undefined,
        });
      } else {
        await api.login({ email, password });
      }
      onAuthed();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto mt-24 max-w-md px-6">
      <h1 className="text-2xl font-semibold tracking-tight">refle</h1>
      <p className="mt-1 text-sm text-neutral-500">
        AI-Powered Automated Compliance
      </p>

      <div className="mt-8 rounded-xl border border-neutral-200 p-6 dark:border-neutral-800">
        <div className="mb-5 flex gap-1 rounded-lg bg-neutral-100 p-1 text-sm dark:bg-neutral-900">
          {(["register", "login"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`flex-1 rounded-md px-3 py-1.5 capitalize transition ${
                mode === m
                  ? "bg-white shadow-sm dark:bg-neutral-800"
                  : "text-neutral-500"
              }`}
            >
              {m === "register" ? "Create organization" : "Sign in"}
            </button>
          ))}
        </div>

        <form onSubmit={submit} className="space-y-3">
          {mode === "register" && (
            <>
              <Field
                label="Organization name"
                value={orgName}
                onChange={setOrgName}
                required
                placeholder="Acme Inc."
              />
              <Field
                label="Your name"
                value={fullName}
                onChange={setFullName}
                placeholder="Jane Doe"
              />
            </>
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

          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-neutral-700 disabled:opacity-50 dark:bg-white dark:text-neutral-900"
          >
            {busy
              ? "Working…"
              : mode === "register"
                ? "Create organization"
                : "Sign in"}
          </button>
        </form>
      </div>
    </div>
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
      <span className="mb-1 block text-xs font-medium text-neutral-500">
        {label}
      </span>
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
