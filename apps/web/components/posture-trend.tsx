"use client";

import { useEffect, useState } from "react";
import { type PostureSnapshot, api } from "@/lib/api";

/** A tiny inline SVG sparkline of percent-ready over time (no chart lib). */
export function PostureTrend() {
  const [snaps, setSnaps] = useState<PostureSnapshot[]>([]);

  useEffect(() => {
    api.postureHistory(30).then(setSnaps).catch(() => {});
  }, []);

  if (snaps.length < 2) return null;

  const W = 320;
  const H = 40;
  const pts = snaps.map((s, i) => {
    const x = (i / (snaps.length - 1)) * W;
    const y = H - (s.percent_ready / 100) * H;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const latest = snaps[snaps.length - 1]?.percent_ready ?? 0;

  return (
    <div className="mt-4">
      <div className="mb-1 text-xs uppercase tracking-wide text-neutral-400">
        Readiness trend ({snaps.length} snapshots)
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-10 w-full" preserveAspectRatio="none">
        <polyline
          points={pts.join(" ")}
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          className="text-green-500"
        />
      </svg>
      <div className="mt-1 text-right text-xs tabular-nums text-neutral-400">
        now {latest}%
      </div>
    </div>
  );
}
