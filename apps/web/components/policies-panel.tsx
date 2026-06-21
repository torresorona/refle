"use client";

import { useCallback, useEffect, useState } from "react";

import { type Policy, api } from "@/lib/api";

export function PoliciesPanel({ canAdmin }: { canAdmin: boolean }) {
  const [items, setItems] = useState<Policy[]>([]);
  const [name, setName] = useState("");
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setItems(await api.listPolicies());
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.createPolicy({ name, body });
      setName("");
      setBody("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create policy");
    } finally {
      setBusy(false);
    }
  }

  async function accept(id: string) {
    await api.acceptPolicy(id);
    await load();
  }

  return (
    <div>
      {canAdmin && (
        <form
          onSubmit={create}
          className="mb-8 rounded-xl border border-neutral-200 p-4 dark:border-neutral-800"
        >
          <h3 className="mb-3 text-sm font-medium">New policy</h3>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            placeholder="Policy name (e.g. Information Security Policy)"
            className="mb-2 w-full rounded-lg border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none dark:border-neutral-700"
          />
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            required
            rows={4}
            placeholder="Policy body (markdown)…"
            className="w-full rounded-lg border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none dark:border-neutral-700"
          />
          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
          <button
            type="submit"
            disabled={busy}
            className="mt-2 rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-neutral-900"
          >
            {busy ? "Creating…" : "Create policy"}
          </button>
        </form>
      )}

      {items.length === 0 ? (
        <p className="text-sm text-neutral-500">No policies yet.</p>
      ) : (
        <ul className="space-y-2">
          {items.map((p) => (
            <li
              key={p.id}
              className="flex items-center justify-between rounded-lg border border-neutral-200 px-4 py-3 dark:border-neutral-800"
            >
              <div>
                <div className="font-medium">{p.name}</div>
                <div className="text-xs text-neutral-400">
                  v{p.latest_version ?? "—"} · {p.accepted_count} accepted
                </div>
              </div>
              {p.accepted_by_me ? (
                <span className="shrink-0 rounded-full bg-green-100 px-3 py-1 text-xs text-green-800 dark:bg-green-950/50 dark:text-green-300">
                  Accepted ✓
                </span>
              ) : (
                <button
                  onClick={() => accept(p.id)}
                  className="shrink-0 rounded-lg border border-neutral-300 px-3 py-1.5 text-sm transition hover:bg-neutral-100 dark:border-neutral-700 dark:hover:bg-neutral-900"
                >
                  Accept latest
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
