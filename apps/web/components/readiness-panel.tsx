"use client";

import { useCallback, useEffect, useState } from "react";
import { type Gap, type ReadinessReport, api } from "@/lib/api";

const SEVERITY_BADGE: Record<Gap["severity"], string> = {
  high: "bg-red-100 text-red-800 dark:bg-red-950/50 dark:text-red-300",
  medium: "bg-amber-100 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300",
  low: "bg-neutral-100 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-400",
};

const SEVERITY_ORDER: Record<Gap["severity"], number> = { high: 0, medium: 1, low: 2 };

export function ReadinessPanel() {
  const [report, setReport] = useState<ReadinessReport | null>(null);
  const [gaps, setGaps] = useState<Gap[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [r, g] = await Promise.all([api.readiness(), api.gaps()]);
      setReport(r);
      setGaps([...g].sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load readiness");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function exportPackage() {
    setExporting(true);
    try {
      const blob = await api.downloadAuditPackage();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "refle-audit-package.zip";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExporting(false);
    }
  }

  if (loading) return <p className="text-sm text-neutral-500">Loading readiness…</p>;
  if (!report) return <p className="text-sm text-red-600">{error ?? "No data"}</p>;

  const fp = report.framework;

  return (
    <div className="space-y-10">
      <section>
        <div className="flex items-end justify-between">
          <h2 className="text-xs font-medium uppercase tracking-wide text-neutral-400">
            {fp.name} readiness
          </h2>
          <button
            onClick={exportPackage}
            disabled={exporting}
            className="rounded-lg bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-neutral-900"
          >
            {exporting ? "Exporting…" : "Export audit package"}
          </button>
        </div>
        <div className="mt-3 flex items-end justify-between">
          <span className="text-3xl font-semibold tabular-nums">{fp.percent_ready}%</span>
          <span className="text-sm text-neutral-500">
            {fp.passing} passing · {fp.failing} failing · {fp.not_assessed} not assessed
          </span>
        </div>
        <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-neutral-200 dark:bg-neutral-800">
          <div
            className="h-full rounded-full bg-green-500 transition-all"
            style={{ width: `${fp.percent_ready}%` }}
          />
        </div>
      </section>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <section>
        <h2 className="mb-3 text-xs font-medium uppercase tracking-wide text-neutral-400">
          Gaps ({gaps.length})
        </h2>
        {gaps.length === 0 ? (
          <p className="text-sm text-neutral-500">No open gaps. Nice.</p>
        ) : (
          <ul className="space-y-2">
            {gaps.map((g, i) => (
              <li
                key={i}
                className="flex items-start gap-3 rounded-lg border border-neutral-200 p-3 dark:border-neutral-800"
              >
                <span
                  className={`mt-0.5 rounded-full px-2 py-0.5 text-xs ${SEVERITY_BADGE[g.severity]}`}
                >
                  {g.severity}
                </span>
                <div>
                  <div className="text-sm font-medium">{g.title}</div>
                  <div className="text-xs text-neutral-500">{g.recommendation}</div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-xs font-medium uppercase tracking-wide text-neutral-400">
          Control coverage ({report.controls.length})
        </h2>
        <div className="overflow-hidden rounded-xl border border-neutral-200 dark:border-neutral-800">
          <table className="w-full text-sm">
            <thead className="bg-neutral-50 text-left text-xs uppercase tracking-wide text-neutral-400 dark:bg-neutral-900">
              <tr>
                <th className="px-4 py-2 font-medium">Code</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Evidence</th>
                <th className="px-4 py-2 font-medium">Open fixes</th>
                <th className="px-4 py-2 font-medium">Last tested</th>
              </tr>
            </thead>
            <tbody>
              {report.controls.map((c) => (
                <tr
                  key={c.control_code}
                  className="border-t border-neutral-100 dark:border-neutral-800/60"
                >
                  <td className="whitespace-nowrap px-4 py-2 font-mono text-xs text-neutral-500">
                    {c.control_code}
                  </td>
                  <td className="px-4 py-2">{c.status}</td>
                  <td className="px-4 py-2 tabular-nums">{c.evidence_count}</td>
                  <td className="px-4 py-2 tabular-nums">{c.open_remediations}</td>
                  <td className="px-4 py-2 text-xs text-neutral-500">
                    {c.last_tested_at ? new Date(c.last_tested_at).toLocaleDateString() : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
