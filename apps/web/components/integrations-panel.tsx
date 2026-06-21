"use client";

import { useCallback, useEffect, useState } from "react";

import {
  type Connection,
  type ConnectorInfo,
  type RemediationTaskRow,
  api,
} from "@/lib/api";

const STATUS_BADGE: Record<Connection["status"], string> = {
  connected:
    "bg-green-100 text-green-800 dark:bg-green-950/50 dark:text-green-300",
  error: "bg-red-100 text-red-800 dark:bg-red-950/50 dark:text-red-300",
  never_synced:
    "bg-neutral-100 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-400",
};

export function IntegrationsPanel({
  canAdmin,
  onChanged,
}: {
  canAdmin: boolean;
  onChanged: () => void;
}) {
  const [connectors, setConnectors] = useState<ConnectorInfo[]>([]);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [tasks, setTasks] = useState<RemediationTaskRow[]>([]);
  const [provider, setProvider] = useState("");
  const [label, setLabel] = useState("");
  const [creds, setCreds] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [cons, conns, ts] = await Promise.all([
      api.connectors(),
      api.connections(),
      api.remediationTasks(),
    ]);
    setConnectors(cons);
    setConnections(conns);
    setTasks(ts);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const selected = connectors.find((c) => c.key === provider);

  async function addConnection(e: React.FormEvent) {
    e.preventDefault();
    if (!provider) return;
    setBusy("add");
    setError(null);
    try {
      await api.createConnection({
        provider,
        label: label || selected?.name || provider,
        credentials: creds,
      });
      setProvider("");
      setLabel("");
      setCreds({});
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to connect");
    } finally {
      setBusy(null);
    }
  }

  async function sync(id: string) {
    setBusy(id);
    setError(null);
    try {
      const result = await api.syncConnection(id);
      if (!result.ok) setError(result.error ?? "Sync failed");
      await load();
      onChanged(); // refresh posture/controls on the Controls tab
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      {canAdmin && (
        <form
          onSubmit={addConnection}
          className="mb-8 rounded-xl border border-neutral-200 p-4 dark:border-neutral-800"
        >
          <h3 className="mb-3 text-sm font-medium">Connect an integration</h3>
          <div className="flex flex-col gap-3 sm:flex-row">
            <select
              value={provider}
              onChange={(e) => {
                setProvider(e.target.value);
                setCreds({});
              }}
              className="rounded-lg border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none dark:border-neutral-700"
            >
              <option value="">Select connector…</option>
              {connectors.map((c) => (
                <option key={c.key} value={c.key}>
                  {c.name}
                </option>
              ))}
            </select>
            <input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Label (e.g. Production)"
              className="flex-1 rounded-lg border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none dark:border-neutral-700"
            />
          </div>

          {selected && selected.credential_fields.length > 0 && (
            <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
              {selected.credential_fields.map((field) => (
                <input
                  key={field}
                  value={creds[field] ?? ""}
                  onChange={(e) =>
                    setCreds((c) => ({ ...c, [field]: e.target.value }))
                  }
                  placeholder={field}
                  className="rounded-lg border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none dark:border-neutral-700"
                />
              ))}
            </div>
          )}
          {selected && (
            <p className="mt-2 text-xs text-neutral-400">{selected.description}</p>
          )}
          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
          <button
            type="submit"
            disabled={busy === "add" || !provider}
            className="mt-3 rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-neutral-900"
          >
            {busy === "add" ? "Connecting…" : "Connect"}
          </button>
        </form>
      )}

      <h3 className="mb-3 text-xs font-medium uppercase tracking-wide text-neutral-400">
        Connections ({connections.length})
      </h3>
      {connections.length === 0 ? (
        <p className="text-sm text-neutral-500">
          No integrations connected. Connect the <strong>Demo</strong> connector to
          see automated control tests run.
        </p>
      ) : (
        <ul className="space-y-2">
          {connections.map((c) => (
            <li
              key={c.id}
              className="flex items-center justify-between rounded-lg border border-neutral-200 px-4 py-3 dark:border-neutral-800"
            >
              <div>
                <div className="font-medium">{c.label}</div>
                <div className="text-xs text-neutral-400">
                  {c.provider}
                  {c.last_synced_at
                    ? ` · synced ${new Date(c.last_synced_at).toLocaleString()}`
                    : " · never synced"}
                  {c.last_error ? ` · ${c.last_error}` : ""}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span
                  className={`rounded-full px-2 py-0.5 text-xs ${STATUS_BADGE[c.status]}`}
                >
                  {c.status.replace("_", " ")}
                </span>
                {canAdmin && (
                  <button
                    onClick={() => sync(c.id)}
                    disabled={busy === c.id}
                    className="rounded-lg border border-neutral-300 px-3 py-1.5 text-sm transition hover:bg-neutral-100 disabled:opacity-50 dark:border-neutral-700 dark:hover:bg-neutral-900"
                  >
                    {busy === c.id ? "Syncing…" : "Sync now"}
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {tasks.length > 0 && (
        <section className="mt-8">
          <h3 className="mb-3 text-xs font-medium uppercase tracking-wide text-neutral-400">
            Open remediation tasks ({tasks.length})
          </h3>
          <ul className="space-y-2">
            {tasks.map((t) => (
              <li
                key={t.id}
                className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-200"
              >
                <span className="font-medium">{t.title}</span>
                {t.detail ? ` — ${t.detail}` : ""}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
