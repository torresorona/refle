"use client";

import { useCallback, useEffect, useState } from "react";
import {
  type AccessReview,
  type AccessReviewDetail,
  type ChecklistItem,
  type Person,
  type TrainingRecord,
  api,
} from "@/lib/api";

export function PeoplePanel({ canWrite }: { canWrite: boolean }) {
  const [people, setPeople] = useState<Person[]>([]);
  const [selected, setSelected] = useState<Person | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");

  const load = useCallback(async () => {
    try {
      setPeople(await api.people());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load people");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function addPerson(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.createPerson({ full_name: name, email });
      setName("");
      setEmail("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add person");
    }
  }

  return (
    <div className="space-y-10">
      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="grid gap-8 md:grid-cols-3">
        <div className="md:col-span-2">
          <h2 className="mb-3 text-xs font-medium uppercase tracking-wide text-neutral-400">
            People ({people.length})
          </h2>
          {people.length === 0 ? (
            <p className="text-sm text-neutral-500">No people yet.</p>
          ) : (
            <ul className="divide-y divide-neutral-100 rounded-xl border border-neutral-200 dark:divide-neutral-800/60 dark:border-neutral-800">
              {people.map((p) => (
                <li key={p.id}>
                  <button
                    onClick={() => setSelected(p)}
                    className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-neutral-50 dark:hover:bg-neutral-900"
                  >
                    <div>
                      <div className="font-medium">{p.full_name}</div>
                      <div className="text-xs text-neutral-400">{p.email}</div>
                    </div>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs ${
                        p.status === "terminated"
                          ? "bg-neutral-100 text-neutral-500 dark:bg-neutral-800"
                          : "bg-green-100 text-green-800 dark:bg-green-950/50 dark:text-green-300"
                      }`}
                    >
                      {p.status}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {canWrite && (
          <div>
            <h2 className="mb-3 text-xs font-medium uppercase tracking-wide text-neutral-400">
              Add person
            </h2>
            <form
              onSubmit={addPerson}
              className="space-y-3 rounded-xl border border-neutral-200 p-4 dark:border-neutral-800"
            >
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Full name"
                required
                className="w-full rounded-lg border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none dark:border-neutral-700"
              />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="email@example.com"
                required
                className="w-full rounded-lg border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none dark:border-neutral-700"
              />
              <button
                type="submit"
                className="w-full rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white dark:bg-white dark:text-neutral-900"
              >
                Add
              </button>
            </form>
          </div>
        )}
      </div>

      {selected && (
        <PersonDetail
          person={selected}
          canWrite={canWrite}
          onChanged={async () => {
            await load();
            setPeople((prev) => prev);
          }}
        />
      )}

      <AccessReviews canWrite={canWrite} people={people} />
    </div>
  );
}

function PersonDetail({
  person,
  canWrite,
  onChanged,
}: {
  person: Person;
  canWrite: boolean;
  onChanged: () => void;
}) {
  const [checklist, setChecklist] = useState<ChecklistItem[]>([]);
  const [training, setTraining] = useState<TrainingRecord[]>([]);
  const [course, setCourse] = useState("");
  const [status, setStatus] = useState(person.status);

  const load = useCallback(async () => {
    const [cl, tr] = await Promise.all([
      api.personChecklist(person.id),
      api.personTraining(person.id),
    ]);
    setChecklist(cl);
    setTraining(tr);
    setStatus(person.status);
  }, [person.id, person.status]);

  useEffect(() => {
    void load();
  }, [load]);

  async function terminate() {
    await api.updatePerson(person.id, { status: "terminated" });
    onChanged();
    await load();
  }

  async function complete(itemId: string) {
    await api.completeChecklistItem(itemId);
    await load();
  }

  async function addTraining(e: React.FormEvent) {
    e.preventDefault();
    await api.addTraining(person.id, { course });
    setCourse("");
    await load();
  }

  return (
    <section className="rounded-xl border border-neutral-200 p-5 dark:border-neutral-800">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-medium">{person.full_name}</h3>
        {canWrite && status !== "terminated" && (
          <button
            onClick={terminate}
            className="rounded-lg border border-red-300 px-3 py-1.5 text-sm text-red-700 hover:bg-red-50 dark:border-red-900/60 dark:text-red-300"
          >
            Terminate
          </button>
        )}
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div>
          <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-neutral-400">
            Checklist
          </h4>
          <ul className="space-y-1.5">
            {checklist.map((i) => (
              <li key={i.id} className="flex items-center justify-between gap-2 text-sm">
                <span className={i.done_at ? "text-neutral-400 line-through" : ""}>
                  [{i.kind === "offboarding" ? "off" : "on"}] {i.label}
                </span>
                {canWrite && !i.done_at && (
                  <button
                    onClick={() => complete(i.id)}
                    className="shrink-0 text-xs font-medium text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-200"
                  >
                    Done
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>

        <div>
          <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-neutral-400">
            Training
          </h4>
          <ul className="space-y-1 text-sm">
            {training.map((t) => (
              <li key={t.id}>
                {t.course}
                {t.expires_at && (
                  <span className="text-xs text-neutral-400"> · expires {t.expires_at}</span>
                )}
              </li>
            ))}
            {training.length === 0 && (
              <li className="text-sm text-neutral-500">No training recorded.</li>
            )}
          </ul>
          {canWrite && (
            <form onSubmit={addTraining} className="mt-3 flex gap-2">
              <input
                value={course}
                onChange={(e) => setCourse(e.target.value)}
                placeholder="Course name"
                required
                className="flex-1 rounded-lg border border-neutral-300 bg-transparent px-2 py-1 text-sm outline-none dark:border-neutral-700"
              />
              <button
                type="submit"
                className="rounded-lg border border-neutral-300 px-3 py-1 text-sm dark:border-neutral-700"
              >
                Add
              </button>
            </form>
          )}
        </div>
      </div>
    </section>
  );
}

function AccessReviews({ canWrite, people }: { canWrite: boolean; people: Person[] }) {
  const [reviews, setReviews] = useState<AccessReview[]>([]);
  const [open, setOpen] = useState<AccessReviewDetail | null>(null);
  const [name, setName] = useState("");

  const load = useCallback(async () => {
    setReviews(await api.accessReviews());
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function createReview(e: React.FormEvent) {
    e.preventDefault();
    // Seed one item per active person so reviewers have something to attest.
    const items = people
      .filter((p) => p.status === "active")
      .map((p) => ({ system: "all systems", person_id: p.id, access_detail: p.title ?? "" }));
    const detail = await api.createAccessReview({ name, items });
    setName("");
    setOpen(detail);
    await load();
  }

  async function decide(itemId: string, decision: "keep" | "revoke") {
    if (!open) return;
    await api.decideAccessReviewItem(itemId, decision);
    setOpen(await api.getAccessReview(open.id));
  }

  async function complete() {
    if (!open) return;
    setOpen(await api.completeAccessReview(open.id));
    await load();
  }

  return (
    <section>
      <h2 className="mb-3 text-xs font-medium uppercase tracking-wide text-neutral-400">
        Access reviews
      </h2>

      {canWrite && (
        <form onSubmit={createReview} className="mb-4 flex gap-2">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Q3 quarterly access review"
            required
            className="flex-1 rounded-lg border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none dark:border-neutral-700"
          />
          <button
            type="submit"
            className="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white dark:bg-white dark:text-neutral-900"
          >
            Start review
          </button>
        </form>
      )}

      <ul className="divide-y divide-neutral-100 rounded-xl border border-neutral-200 dark:divide-neutral-800/60 dark:border-neutral-800">
        {reviews.map((r) => (
          <li key={r.id}>
            <button
              onClick={async () => setOpen(await api.getAccessReview(r.id))}
              className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-neutral-50 dark:hover:bg-neutral-900"
            >
              <span className="text-sm font-medium">{r.name}</span>
              <span className="text-xs text-neutral-400">{r.status}</span>
            </button>
          </li>
        ))}
        {reviews.length === 0 && (
          <li className="px-4 py-3 text-sm text-neutral-500">No access reviews yet.</li>
        )}
      </ul>

      {open && (
        <div className="mt-4 rounded-xl border border-neutral-200 p-4 dark:border-neutral-800">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-medium">{open.name}</h3>
            {canWrite && open.status === "open" && (
              <button
                onClick={complete}
                className="rounded-lg border border-neutral-300 px-3 py-1 text-sm dark:border-neutral-700"
              >
                Complete review
              </button>
            )}
          </div>
          <ul className="space-y-1.5">
            {open.items.map((it) => (
              <li key={it.id} className="flex items-center justify-between gap-2 text-sm">
                <span>
                  {it.system}
                  {it.access_detail ? ` · ${it.access_detail}` : ""}
                </span>
                <span className="flex items-center gap-2">
                  <span className="text-xs text-neutral-400">{it.decision}</span>
                  {canWrite && open.status === "open" && it.decision === "pending" && (
                    <>
                      <button
                        onClick={() => decide(it.id, "keep")}
                        className="text-xs font-medium text-green-700 dark:text-green-400"
                      >
                        Keep
                      </button>
                      <button
                        onClick={() => decide(it.id, "revoke")}
                        className="text-xs font-medium text-red-700 dark:text-red-400"
                      >
                        Revoke
                      </button>
                    </>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
