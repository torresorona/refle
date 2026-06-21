"use client";

import { useCallback, useEffect, useState } from "react";

import { type Evidence, type OrgControl, api } from "@/lib/api";

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function EvidencePanel({ canWrite }: { canWrite: boolean }) {
  const [items, setItems] = useState<Evidence[]>([]);
  const [controls, setControls] = useState<OrgControl[]>([]);
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [showLink, setShowLink] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const [ev, ctrls] = await Promise.all([api.listEvidence(), api.controls()]);
    setItems(ev);
    setControls(ctrls);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function upload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("name", name || file.name);
      if (selected.size) form.append("control_ids", Array.from(selected).join(","));
      await api.uploadEvidence(form);
      setName("");
      setFile(null);
      setSelected(new Set());
      setShowLink(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  function toggle(id: string) {
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function download(id: string) {
    const { url } = await api.evidenceDownloadUrl(id);
    window.open(url, "_blank");
  }

  return (
    <div>
      {canWrite && (
        <form
          onSubmit={upload}
          className="mb-8 rounded-xl border border-neutral-200 p-4 dark:border-neutral-800"
        >
          <h3 className="mb-3 text-sm font-medium">Upload evidence</h3>
          <div className="flex flex-col gap-3 sm:flex-row">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Name (e.g. Q2 access review)"
              className="flex-1 rounded-lg border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none dark:border-neutral-700"
            />
            <input
              type="file"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="text-sm file:mr-3 file:rounded-md file:border-0 file:bg-neutral-900 file:px-3 file:py-2 file:text-white dark:file:bg-white dark:file:text-neutral-900"
            />
            <button
              type="submit"
              disabled={busy || !file}
              className="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-neutral-900"
            >
              {busy ? "Uploading…" : "Upload"}
            </button>
          </div>

          <button
            type="button"
            onClick={() => setShowLink((v) => !v)}
            className="mt-3 text-xs text-neutral-500 underline"
          >
            {selected.size
              ? `Linked to ${selected.size} control(s)`
              : "Link to controls (optional)"}
          </button>
          {showLink && (
            <div className="mt-2 grid max-h-40 grid-cols-1 gap-1 overflow-y-auto sm:grid-cols-2">
              {controls.map((oc) => (
                <label key={oc.id} className="flex items-center gap-2 text-xs">
                  <input
                    type="checkbox"
                    checked={selected.has(oc.id)}
                    onChange={() => toggle(oc.id)}
                  />
                  <span className="font-mono text-neutral-500">{oc.control.code}</span>
                  <span className="truncate">{oc.control.title}</span>
                </label>
              ))}
            </div>
          )}
          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
        </form>
      )}

      {items.length === 0 ? (
        <p className="text-sm text-neutral-500">No evidence uploaded yet.</p>
      ) : (
        <ul className="space-y-2">
          {items.map((ev) => (
            <li
              key={ev.id}
              className="flex items-center justify-between rounded-lg border border-neutral-200 px-4 py-3 dark:border-neutral-800"
            >
              <div className="min-w-0">
                <div className="font-medium">{ev.name}</div>
                <div className="text-xs text-neutral-400">
                  {ev.filename} · {formatSize(ev.size_bytes)}
                  {ev.control_codes.length > 0 &&
                    ` · ${ev.control_codes.join(", ")}`}
                </div>
              </div>
              <button
                onClick={() => download(ev.id)}
                className="shrink-0 rounded-lg border border-neutral-300 px-3 py-1.5 text-sm transition hover:bg-neutral-100 dark:border-neutral-700 dark:hover:bg-neutral-900"
              >
                Download
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
