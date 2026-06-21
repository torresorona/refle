"use client";

import { useCallback, useEffect, useState } from "react";
import Markdown from "react-markdown";
import { type Policy, type PolicyDetail, type PolicyTemplate, type Evidence, api } from "@/lib/api";

function DraftPolicyModal({
  onClose,
  onDraft,
}: {
  onClose: () => void;
  onDraft: (data: { name: string; instructions?: string; template_id?: string; evidence_id?: string }) => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [instructions, setInstructions] = useState("");
  const [sourceType, setSourceType] = useState<"template" | "evidence" | "upload" | "none">("none");
  const [templateId, setTemplateId] = useState("");
  const [evidenceId, setEvidenceId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  
  const [templates, setTemplates] = useState<PolicyTemplate[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listTemplates().then(setTemplates).catch(() => setTemplates([]));
    api.listEvidence().then(setEvidence).catch(() => setEvidence([]));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      let finalEvidenceId = evidenceId;
      if (sourceType === "upload" && file) {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("name", file.name);
        formData.append("source", "hot_template_upload");
        const uploaded = await api.uploadEvidence(formData);
        finalEvidenceId = uploaded.id;
      }
      
      await onDraft({
        name,
        instructions,
        template_id: sourceType === "template" && templateId ? templateId : undefined,
        evidence_id: (sourceType === "evidence" && finalEvidenceId) || (sourceType === "upload" && finalEvidenceId) ? finalEvidenceId : undefined,
      });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to draft policy");
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800">
        <h2 className="text-xl font-semibold mb-4">✨ Draft Policy with AI</h2>
        <form onSubmit={handleSubmit}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Policy Name</label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                className="w-full rounded-lg border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none dark:border-neutral-700"
                placeholder="e.g. Data Classification Policy"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Source Material</label>
              <select
                value={sourceType}
                onChange={(e) => setSourceType(e.target.value as any)}
                className="w-full rounded-lg border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none dark:border-neutral-700 mb-2"
              >
                <option value="none">None (Generate from scratch)</option>
                <option value="template">Use a Template</option>
                <option value="evidence">Use Existing Evidence</option>
                <option value="upload">Upload Hot Template</option>
              </select>

              {sourceType === "template" && (
                <select
                  value={templateId}
                  onChange={(e) => setTemplateId(e.target.value)}
                  required
                  className="w-full rounded-lg border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none dark:border-neutral-700"
                >
                  <option value="" disabled>Select a template...</option>
                  {templates.map(t => (
                    <option key={t.id} value={t.id}>{t.name} ({t.type})</option>
                  ))}
                </select>
              )}

              {sourceType === "evidence" && (
                <select
                  value={evidenceId}
                  onChange={(e) => setEvidenceId(e.target.value)}
                  required
                  className="w-full rounded-lg border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none dark:border-neutral-700"
                >
                  <option value="" disabled>Select existing evidence...</option>
                  {evidence.map(e => (
                    <option key={e.id} value={e.id}>{e.name}</option>
                  ))}
                </select>
              )}

              {sourceType === "upload" && (
                <input
                  type="file"
                  required
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  className="w-full text-sm text-neutral-500 file:mr-4 file:rounded-full file:border-0 file:bg-neutral-100 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-neutral-700 hover:file:bg-neutral-200 dark:file:bg-neutral-800 dark:file:text-neutral-300"
                />
              )}
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Special Instructions (Optional)</label>
              <textarea
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
                rows={2}
                className="w-full rounded-lg border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none dark:border-neutral-700"
                placeholder="e.g. Make it strict and align with ISO 27001"
              />
            </div>
          </div>
          
          {error && <p className="mt-4 text-sm text-red-600">{error}</p>}
          
          <div className="mt-6 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={busy}
              className="rounded-lg px-4 py-2 text-sm font-medium transition hover:bg-neutral-100 dark:hover:bg-neutral-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={busy || (sourceType === "upload" && !file)}
              className="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-neutral-900"
            >
              {busy ? "Drafting..." : "Draft Policy"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function PolicyDetailModal({
  policyId,
  onClose,
  onUpdate,
}: {
  policyId: string;
  onClose: () => void;
  onUpdate: () => void;
}) {
  const [policy, setPolicy] = useState<PolicyDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const [editing, setEditing] = useState(false);
  const [editBody, setEditBody] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.getPolicy(policyId).then((p) => {
      setPolicy(p);
      setLoading(false);
    }).catch((e) => {
      setError(e instanceof Error ? e.message : "Failed to load");
      setLoading(false);
    });
  }, [policyId]);

  if (loading) return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"><div className="rounded-xl bg-white p-6 shadow-xl dark:bg-neutral-900 text-sm">Loading policy...</div></div>;
  if (error || !policy) return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"><div className="rounded-xl bg-white p-6 shadow-xl dark:bg-neutral-900 text-red-500 text-sm">{error || "Not found"} <button onClick={onClose} className="ml-4 underline">Close</button></div></div>;

  const latestVer = policy.versions[0];
  const isDraft = latestVer?.status === "draft";

  async function handleSaveEdit() {
    if (!policy || !latestVer) return;
    setSaving(true);
    try {
      await api.updatePolicyVersion(policy.id, latestVer.version, { body: editBody });
      const updated = await api.getPolicy(policy.id);
      setPolicy(updated);
      setEditing(false);
    } catch (e: any) {
      alert(e.message);
    }
    setSaving(false);
  }

  async function handlePublish() {
    if (!policy || !latestVer) return;
    setSaving(true);
    try {
      await api.publishPolicyVersion(policy.id, latestVer.version);
      const updated = await api.getPolicy(policy.id);
      setPolicy(updated);
      onUpdate();
    } catch (e: any) {
      alert(e.message);
    }
    setSaving(false);
  }

  async function handleAccept() {
    if (!policy) return;
    setSaving(true);
    try {
      await api.acceptPolicy(policy.id);
      const updated = await api.getPolicy(policy.id);
      setPolicy(updated);
      onUpdate();
    } catch (e: any) {
      alert(e.message);
    }
    setSaving(false);
  }

  function handleDownload() {
    if (!policy || !latestVer) return;
    const blob = new Blob([latestVer.body], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${policy.slug}-v${latestVer.version}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="flex h-full max-h-[90vh] w-full max-w-4xl flex-col rounded-2xl bg-white shadow-xl dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800">
        <div className="flex items-center justify-between border-b border-neutral-200 p-4 dark:border-neutral-800 shrink-0">
          <div>
            <h2 className="text-xl font-semibold">{policy.name}</h2>
            <div className="flex items-center gap-2 text-sm text-neutral-500 mt-1">
              <span>Version {latestVer?.version || "—"}</span>
              <span className={`rounded px-1.5 py-0.5 text-xs ${isDraft ? "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400" : "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"}`}>
                {latestVer?.status || "Unknown"}
              </span>
            </div>
          </div>
          <div className="flex gap-2">
            {latestVer && (
               <button onClick={handleDownload} className="rounded-lg border border-neutral-300 px-3 py-1.5 text-sm transition hover:bg-neutral-100 dark:border-neutral-700 dark:hover:bg-neutral-800">
                 Download (.md)
               </button>
            )}
            <button onClick={onClose} className="rounded-lg bg-neutral-100 px-3 py-1.5 text-sm transition hover:bg-neutral-200 dark:bg-neutral-800 dark:hover:bg-neutral-700">Close</button>
          </div>
        </div>

        <div className="flex-1 overflow-auto p-6">
          {editing ? (
             <textarea 
               value={editBody} 
               onChange={e => setEditBody(e.target.value)} 
               className="h-full min-h-[400px] w-full resize-none rounded-lg border border-neutral-300 bg-neutral-50 p-4 font-mono text-sm dark:border-neutral-700 dark:bg-neutral-950 outline-none"
             />
          ) : (
             <article className="prose prose-neutral dark:prose-invert max-w-none">
               <Markdown>{latestVer?.body || "*No content*"}</Markdown>
             </article>
          )}
        </div>

        <div className="border-t border-neutral-200 p-4 dark:border-neutral-800 flex justify-between bg-neutral-50 dark:bg-neutral-950/50 rounded-b-2xl shrink-0">
          <div>
             {isDraft && (
               editing ? (
                 <div className="flex gap-2">
                   <button disabled={saving} onClick={handleSaveEdit} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">Save Edits</button>
                   <button disabled={saving} onClick={() => setEditing(false)} className="rounded-lg border border-neutral-300 px-4 py-2 text-sm font-medium hover:bg-neutral-100 dark:border-neutral-700 dark:hover:bg-neutral-800">Cancel</button>
                 </div>
               ) : (
                 <button onClick={() => { setEditBody(latestVer.body); setEditing(true); }} className="rounded-lg border border-neutral-300 px-4 py-2 text-sm font-medium hover:bg-neutral-100 dark:border-neutral-700 dark:hover:bg-neutral-800">Edit Draft</button>
               )
             )}
          </div>
          <div className="flex gap-2 items-center">
             {isDraft ? (
               <button disabled={saving} onClick={handlePublish} className="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800 dark:bg-white dark:text-neutral-900 dark:hover:bg-neutral-200">
                 Publish Policy
               </button>
             ) : (
               !policy.accepted_by_me && (
                 <button disabled={saving} onClick={handleAccept} className="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800 dark:bg-white dark:text-neutral-900 dark:hover:bg-neutral-200">
                   Accept Policy
                 </button>
               )
             )}
             {policy.accepted_by_me && !isDraft && (
               <span className="flex items-center text-sm text-green-600 dark:text-green-400 font-medium">✓ You have accepted this policy</span>
             )}
          </div>
        </div>
      </div>
    </div>
  );
}

export function PoliciesPanel({ canAdmin }: { canAdmin: boolean }) {
  const [items, setItems] = useState<Policy[]>([]);
  const [name, setName] = useState("");
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showAiModal, setShowAiModal] = useState(false);
  const [viewingPolicyId, setViewingPolicyId] = useState<string | null>(null);

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

  async function handleDraft(data: { name: string; instructions?: string; template_id?: string; evidence_id?: string }) {
    await api.draftPolicy(data);
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
          <div className="mt-2 flex gap-2">
            <button
              type="submit"
              disabled={busy}
              className="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-neutral-900"
            >
              {busy ? "Creating…" : "Create policy"}
            </button>
            <button
              type="button"
              onClick={() => setShowAiModal(true)}
              className="rounded-lg border border-neutral-300 px-4 py-2 text-sm font-medium transition hover:bg-neutral-100 dark:border-neutral-700 dark:hover:bg-neutral-900"
            >
              ✨ Draft with AI
            </button>
          </div>
        </form>
      )}

      {items.length === 0 ? (
        <p className="text-sm text-neutral-500">No policies yet.</p>
      ) : (
        <ul className="space-y-2">
          {items.map((p) => (
            <li
              key={p.id}
              onClick={() => setViewingPolicyId(p.id)}
              className="flex cursor-pointer items-center justify-between rounded-lg border border-neutral-200 px-4 py-3 transition hover:bg-neutral-50 dark:border-neutral-800 dark:hover:bg-neutral-900/50"
            >
              <div>
                <div className="font-medium">{p.name}</div>
                <div className="text-xs text-neutral-400">
                  {p.latest_version === null ? "Draft" : `v${p.latest_version}`} · {p.accepted_count} accepted
                </div>
              </div>
              <div className="flex items-center gap-4">
                {p.accepted_by_me ? (
                  <span className="shrink-0 rounded-full bg-green-100 px-3 py-1 text-xs text-green-800 dark:bg-green-950/50 dark:text-green-300">
                    Accepted ✓
                  </span>
                ) : p.latest_version !== null ? (
                  <span className="shrink-0 rounded-full bg-neutral-100 px-3 py-1 text-xs text-neutral-800 dark:bg-neutral-800 dark:text-neutral-300">
                    Needs Acceptance
                  </span>
                ) : null}
                <span className="text-neutral-400">→</span>
              </div>
            </li>
          ))}
        </ul>
      )}
      
      {showAiModal && (
        <DraftPolicyModal
          onClose={() => setShowAiModal(false)}
          onDraft={handleDraft}
        />
      )}
      
      {viewingPolicyId && (
        <PolicyDetailModal
          policyId={viewingPolicyId}
          onClose={() => setViewingPolicyId(null)}
          onUpdate={load}
        />
      )}
    </div>
  );
}
