import { apiBaseUrl, getMeta } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function Home() {
  const meta = await getMeta();

  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <header>
        <h1 className="text-3xl font-semibold tracking-tight">refle</h1>
        <p className="mt-1 text-neutral-500">
          AI-Powered Automated Compliance for your Business
        </p>
      </header>

      {meta ? (
        <section className="mt-10">
          <h2 className="text-xs font-medium uppercase tracking-wide text-neutral-400">
            Deployment status
          </h2>
          <dl className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Stat label="Version" value={meta.version} />
            <Stat label="License tier" value={meta.license.tier} />
            <Stat label="AI provider" value={meta.ai.provider} />
            <Stat label="AI model" value={meta.ai.model} />
            <Stat
              label="Sovereign mode"
              value={meta.ai.sovereign ? "on (local)" : "off (cloud)"}
            />
            <Stat
              label="Connectors"
              value={
                meta.connectors.length
                  ? meta.connectors.join(", ")
                  : "none yet (Phase 2)"
              }
            />
          </dl>
        </section>
      ) : (
        <section className="mt-10 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
          Couldn&apos;t reach the API at{" "}
          <code className="font-mono">{apiBaseUrl}</code>. Start it with{" "}
          <code className="font-mono">make api</code>.
        </section>
      )}
    </main>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
      <dt className="text-xs uppercase tracking-wide text-neutral-400">
        {label}
      </dt>
      <dd className="mt-1 text-lg font-medium">{value}</dd>
    </div>
  );
}
