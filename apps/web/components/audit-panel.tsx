"use client";

import { useEffect, useState } from "react";
import { type AuditLog, api } from "@/lib/api";

export function AuditPanel() {
  const [entries, setEntries] = useState<AuditLog[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .auditLog()
      .then(setEntries)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load audit log"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-sm text-neutral-500">Loading audit log…</p>;
  if (error) return <p className="text-sm text-red-600">{error}</p>;

  return (
    <section>
      <h2 className="mb-3 text-xs font-medium uppercase tracking-wide text-neutral-400">
        Audit log ({entries.length})
      </h2>
      {entries.length === 0 ? (
        <p className="text-sm text-neutral-500">No activity recorded yet.</p>
      ) : (
        <ul className="divide-y divide-neutral-100 rounded-xl border border-neutral-200 dark:divide-neutral-800/60 dark:border-neutral-800">
          {entries.map((e) => (
            <li key={e.id} className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm">
              <span>
                <span className="font-mono text-xs text-neutral-500">{e.action}</span>
                {e.summary ? <span className="ml-2">{e.summary}</span> : null}
                {e.target_id ? (
                  <span className="ml-2 text-xs text-neutral-400">({e.target_id})</span>
                ) : null}
              </span>
              <span className="shrink-0 text-xs text-neutral-400">
                {new Date(e.created_at).toLocaleString()}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
