"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { type AIStatus, type Citation, api } from "@/lib/api";

type Turn = {
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
  generated?: boolean;
};

export function AssistantPanel({ canAdmin }: { canAdmin: boolean }) {
  const [status, setStatus] = useState<AIStatus | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  const loadStatus = useCallback(async () => {
    setStatus(await api.aiStatus());
  }, []);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  async function ask(e: React.FormEvent) {
    e.preventDefault();
    const q = question.trim();
    if (!q) return;
    setQuestion("");
    setTurns((t) => [...t, { role: "user", text: q }]);
    setBusy(true);
    try {
      const res = await api.aiChat(q);
      setTurns((t) => [
        ...t,
        {
          role: "assistant",
          text: res.answer,
          citations: res.citations,
          generated: res.generated,
        },
      ]);
      void loadStatus();
    } catch {
      setTurns((t) => [
        ...t,
        { role: "assistant", text: "Something went wrong reaching the assistant." },
      ]);
    } finally {
      setBusy(false);
    }
  }

  async function reindex() {
    setBusy(true);
    try {
      await api.aiReindex();
      await loadStatus();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between text-xs text-neutral-400">
        <span>
          {status
            ? `Model ${status.model} · embeddings ${status.embedding_provider} · ${status.indexed_chunks} indexed`
            : "…"}
        </span>
        {canAdmin && (
          <button
            onClick={reindex}
            disabled={busy}
            className="rounded-md border border-neutral-300 px-2 py-1 transition hover:bg-neutral-100 disabled:opacity-50 dark:border-neutral-700 dark:hover:bg-neutral-900"
          >
            Reindex
          </button>
        )}
      </div>

      <div className="min-h-[320px] space-y-4 rounded-xl border border-neutral-200 p-4 dark:border-neutral-800">
        {turns.length === 0 ? (
          <p className="text-sm text-neutral-500">
            Ask about your SOC 2 controls, policies, or evidence — e.g.{" "}
            <em>“What does CC6.1 require and are we meeting it?”</em>
          </p>
        ) : (
          turns.map((t, i) => (
            <div key={i} className={t.role === "user" ? "text-right" : ""}>
              <div
                className={`inline-block max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm ${
                  t.role === "user"
                    ? "bg-neutral-900 text-white dark:bg-white dark:text-neutral-900"
                    : "bg-neutral-100 dark:bg-neutral-900"
                }`}
              >
                {t.text}
                {t.role === "assistant" && t.citations && t.citations.length > 0 && (
                  <div className="mt-2 border-t border-neutral-200 pt-2 text-xs text-neutral-500 dark:border-neutral-700">
                    {t.generated === false && (
                      <div className="mb-1 text-amber-600 dark:text-amber-400">
                        retrieval-only (no model key)
                      </div>
                    )}
                    Sources:{" "}
                    {t.citations.map((c) => (
                      <span key={c.n} className="mr-2 font-mono">
                        [{c.n}] {c.source_id !== c.title ? c.source_id : c.title}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))
        )}
        <div ref={endRef} />
      </div>

      <form onSubmit={ask} className="mt-3 flex gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask the compliance assistant…"
          className="flex-1 rounded-lg border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-neutral-500 dark:border-neutral-700"
        />
        <button
          type="submit"
          disabled={busy || !question.trim()}
          className="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-neutral-900"
        >
          {busy ? "…" : "Ask"}
        </button>
      </form>
    </div>
  );
}
