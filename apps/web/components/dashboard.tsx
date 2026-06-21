"use client";

import { useCallback, useEffect, useState } from "react";

import { EvidencePanel } from "@/components/evidence-panel";
import { IntegrationsPanel } from "@/components/integrations-panel";
import { PoliciesPanel } from "@/components/policies-panel";
import {
  type ControlStatus,
  type Me,
  type OrgControl,
  type Posture,
  api,
} from "@/lib/api";

const STATUS_LABEL: Record<ControlStatus, string> = {
  passing: "Passing",
  failing: "Failing",
  not_assessed: "Not assessed",
};

const STATUS_BADGE: Record<ControlStatus, string> = {
  passing: "bg-green-100 text-green-800 dark:bg-green-950/50 dark:text-green-300",
  failing: "bg-red-100 text-red-800 dark:bg-red-950/50 dark:text-red-300",
  not_assessed:
    "bg-neutral-100 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-400",
};

type Tab = "controls" | "evidence" | "policies" | "integrations";

export function Dashboard({ onSignOut }: { onSignOut: () => void }) {
  const [me, setMe] = useState<Me | null>(null);
  const [posture, setPosture] = useState<Posture | null>(null);
  const [controls, setControls] = useState<OrgControl[]>([]);
  const [tab, setTab] = useState<Tab>("controls");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const m = await api.me();
      const c = await api.controls(); // bootstraps org controls on first call
      const p = await api.posture();
      setMe(m);
      setControls(c);
      setPosture(p);
    } catch {
      setError("Failed to load. Is the API running?");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const canEdit = me?.role === "owner" || me?.role === "admin";
  const canWrite = me?.role !== "auditor";

  async function changeStatus(oc: OrgControl, status: ControlStatus) {
    const prev = controls;
    setControls((cs) => cs.map((c) => (c.id === oc.id ? { ...c, status } : c)));
    try {
      await api.updateControl(oc.id, { status });
      setPosture(await api.posture());
    } catch {
      setControls(prev);
    }
  }

  async function signOut() {
    try {
      await api.logout();
    } finally {
      onSignOut();
    }
  }

  if (loading) {
    return <p className="p-10 text-sm text-neutral-500">Loading…</p>;
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">refle</h1>
          {me && (
            <p className="text-sm text-neutral-500">
              {me.memberships[0]?.organization.name ?? "Your organization"} ·{" "}
              {me.email} ({me.role})
            </p>
          )}
        </div>
        <button
          onClick={signOut}
          className="rounded-lg border border-neutral-300 px-3 py-1.5 text-sm transition hover:bg-neutral-100 dark:border-neutral-700 dark:hover:bg-neutral-900"
        >
          Sign out
        </button>
      </header>

      {error && (
        <p className="mt-6 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </p>
      )}

      <nav className="mt-8 flex gap-1 border-b border-neutral-200 dark:border-neutral-800">
        {(["controls", "evidence", "policies", "integrations"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm capitalize transition ${
              tab === t
                ? "border-neutral-900 font-medium dark:border-white"
                : "border-transparent text-neutral-500"
            }`}
          >
            {t}
          </button>
        ))}
      </nav>

      <div className="mt-8">
        {tab === "controls" && (
          <>
            {posture && (
              <section>
                <div className="flex items-end justify-between">
                  <h2 className="text-xs font-medium uppercase tracking-wide text-neutral-400">
                    SOC 2 posture
                  </h2>
                  <span className="text-3xl font-semibold tabular-nums">
                    {posture.percent_passing}%
                  </span>
                </div>
                <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-neutral-200 dark:bg-neutral-800">
                  <div
                    className="h-full rounded-full bg-green-500 transition-all"
                    style={{ width: `${posture.percent_passing}%` }}
                  />
                </div>
                <div className="mt-3 grid grid-cols-3 gap-3 text-sm">
                  <Stat label="Passing" value={posture.passing} />
                  <Stat label="Failing" value={posture.failing} />
                  <Stat label="Not assessed" value={posture.not_assessed} />
                </div>
              </section>
            )}

            <section className="mt-10">
              <h2 className="mb-3 text-xs font-medium uppercase tracking-wide text-neutral-400">
                Controls ({controls.length})
              </h2>
              <div className="overflow-hidden rounded-xl border border-neutral-200 dark:border-neutral-800">
                <table className="w-full text-sm">
                  <thead className="bg-neutral-50 text-left text-xs uppercase tracking-wide text-neutral-400 dark:bg-neutral-900">
                    <tr>
                      <th className="px-4 py-2 font-medium">Code</th>
                      <th className="px-4 py-2 font-medium">Control</th>
                      <th className="px-4 py-2 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {controls.map((oc) => (
                      <tr
                        key={oc.id}
                        className="border-t border-neutral-100 dark:border-neutral-800/60"
                      >
                        <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-neutral-500">
                          {oc.control.code}
                        </td>
                        <td className="px-4 py-3">
                          <div className="font-medium">{oc.control.title}</div>
                          {oc.control.category && (
                            <div className="text-xs text-neutral-400">
                              {oc.control.category}
                            </div>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          {canEdit ? (
                            <select
                              value={oc.status}
                              onChange={(e) =>
                                changeStatus(oc, e.target.value as ControlStatus)
                              }
                              className="rounded-md border border-neutral-300 bg-transparent px-2 py-1 text-xs outline-none dark:border-neutral-700"
                            >
                              {(
                                [
                                  "passing",
                                  "failing",
                                  "not_assessed",
                                ] as ControlStatus[]
                              ).map((s) => (
                                <option key={s} value={s}>
                                  {STATUS_LABEL[s]}
                                </option>
                              ))}
                            </select>
                          ) : (
                            <span
                              className={`rounded-full px-2 py-0.5 text-xs ${STATUS_BADGE[oc.status]}`}
                            >
                              {STATUS_LABEL[oc.status]}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}

        {tab === "evidence" && <EvidencePanel canWrite={canWrite} />}
        {tab === "policies" && <PoliciesPanel canAdmin={!!canEdit} />}
        {tab === "integrations" && (
          <IntegrationsPanel canAdmin={!!canEdit} onChanged={load} />
        )}
      </div>
    </main>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-neutral-200 p-3 dark:border-neutral-800">
      <div className="text-xs uppercase tracking-wide text-neutral-400">{label}</div>
      <div className="mt-0.5 text-xl font-semibold tabular-nums">{value}</div>
    </div>
  );
}
