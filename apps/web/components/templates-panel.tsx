"use client";

import { useCallback, useEffect, useState } from "react";
import { type PolicyTemplate, type PolicyTemplateDetail, api } from "@/lib/api";

export function TemplatesPanel({ canAdmin }: { canAdmin: boolean }) {
  const [items, setItems] = useState<PolicyTemplate[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [previewTemplate, setPreviewTemplate] = useState<PolicyTemplateDetail | null>(null);

  const load = useCallback(async () => {
    try {
      setItems(await api.listTemplates());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load templates");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.createTemplate({ name, description, body });
      setName("");
      setDescription("");
      setBody("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create template");
    } finally {
      setBusy(false);
    }
  }

  async function viewTemplate(t: PolicyTemplate) {
    try {
      const detail = await api.getTemplate(t.id);
      setPreviewTemplate(detail);
    } catch (err) {
      setError("Failed to fetch template body");
    }
  }

  function downloadTemplate(t: PolicyTemplateDetail) {
    const blob = new Blob([t.body], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${t.name.replace(/\\s+/g, "_")}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  return (
    <div>
      {canAdmin && (
        <form
          onSubmit={create}
          className="mb-8 rounded-xl border border-neutral-200 p-4 dark:border-neutral-800"
        >
          <h3 className="mb-3 text-sm font-medium">New Custom Template</h3>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            placeholder="Template name (e.g. Acme Remote Work Policy)"
            className="mb-2 w-full rounded-lg border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none dark:border-neutral-700"
          />
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Description (optional)"
            className="mb-2 w-full rounded-lg border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none dark:border-neutral-700"
          />
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            required
            rows={4}
            placeholder="Template body (markdown)…"
            className="w-full rounded-lg border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none dark:border-neutral-700"
          />
          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
          <div className="mt-2">
            <button
              type="submit"
              disabled={busy}
              className="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-neutral-900"
            >
              {busy ? "Saving…" : "Save Custom Template"}
            </button>
          </div>
        </form>
      )}

      {items.length === 0 ? (
        <p className="text-sm text-neutral-500">No templates available.</p>
      ) : (
        <ul className="space-y-2">
          {items.map((t) => (
            <li
              key={t.id}
              className="rounded-lg border border-neutral-200 px-4 py-3 dark:border-neutral-800"
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="font-medium flex items-center gap-2">
                    {t.name}
                    {t.type === "builtin" && (
                      <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[10px] uppercase font-bold text-blue-800 dark:bg-blue-900/50 dark:text-blue-300">
                        Built-in
                      </span>
                    )}
                  </div>
                  {t.description && (
                    <div className="text-sm text-neutral-500 mt-1">{t.description}</div>
                  )}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => viewTemplate(t)}
                    className="text-xs text-neutral-500 hover:text-neutral-900 dark:hover:text-white"
                  >
                    Preview & Download
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}

      {previewTemplate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="flex max-h-full w-full max-w-3xl flex-col rounded-xl bg-white shadow-2xl dark:bg-neutral-900">
            <div className="flex items-center justify-between border-b border-neutral-200 p-4 dark:border-neutral-800">
              <h2 className="font-semibold">{previewTemplate.name}</h2>
              <button
                onClick={() => setPreviewTemplate(null)}
                className="text-neutral-500 hover:text-neutral-900 dark:hover:text-white"
              >
                Close
              </button>
            </div>
            <div className="flex-1 overflow-auto p-4 text-sm font-mono whitespace-pre-wrap">
              {previewTemplate.body}
            </div>
            <div className="border-t border-neutral-200 p-4 dark:border-neutral-800 flex justify-end">
              <button
                onClick={() => downloadTemplate(previewTemplate)}
                className="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800 dark:bg-white dark:text-neutral-900 dark:hover:bg-neutral-100"
              >
                Download as .md
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
