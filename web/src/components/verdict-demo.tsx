"use client";

import { useEffect, useState } from "react";

type Verdict = "ALLOWED" | "BLOCKED" | "NEEDS_REVIEW";
type Outcome = "PASS" | "FAIL" | "ESCALATE";

type Example = {
  merchant: string;
  memo: string;
  amountCents: number;
  category: string;
  verdict: Verdict;
  latencyMs: number;
  clause: { page: number; before: string; quote: string; after: string };
  trace: { rule: string; outcome: Outcome; reason: string }[];
};

// Illustrative sample grant, not a real agreement.
const EXAMPLES: Example[] = [
  {
    merchant: "Lakeshore Hotel",
    memo: "Conference lodging, 2 nights",
    amountCents: 41_200,
    category: "travel_domestic",
    verdict: "ALLOWED",
    latencyMs: 4,
    clause: {
      page: 7,
      before: "§4.2 ",
      quote: "Domestic travel necessary to carry out the project is an allowable cost",
      after: ", subject to the approved budget.",
    },
    trace: [
      { rule: "Period of performance", outcome: "PASS", reason: "Within Jan 1 – Dec 31" },
      { rule: "Travel budget line", outcome: "PASS", reason: "$3,612 of $8,000 used" },
    ],
  },
  {
    merchant: "Riverside Wine Bar",
    memo: "Team dinner",
    amountCents: 18_640,
    category: "alcohol",
    verdict: "BLOCKED",
    latencyMs: 3,
    clause: {
      page: 12,
      before: "§6.1 Unallowable costs. ",
      quote: "Costs of alcoholic beverages are unallowable",
      after: " under this award.",
    },
    trace: [
      { rule: "Period of performance", outcome: "PASS", reason: "Within Jan 1 – Dec 31" },
      { rule: "Category prohibition", outcome: "FAIL", reason: "Category is alcohol" },
    ],
  },
  {
    merchant: "Meridian Optics",
    memo: "Thermal imaging camera",
    amountCents: 625_000,
    category: "equipment",
    verdict: "NEEDS_REVIEW",
    latencyMs: 5,
    clause: {
      page: 9,
      before: "§5.3 ",
      quote: "Equipment with a unit cost of $5,000 or more requires prior written approval",
      after: " from the Program Officer.",
    },
    trace: [
      { rule: "Period of performance", outcome: "PASS", reason: "Within Jan 1 – Dec 31" },
      { rule: "Per-item threshold", outcome: "ESCALATE", reason: "$6,250 ≥ $5,000, no approval on file" },
    ],
  },
];

const VERDICT_STYLE: Record<Verdict, string> = {
  ALLOWED: "bg-allowed-bg text-allowed",
  BLOCKED: "bg-blocked-bg text-blocked",
  NEEDS_REVIEW: "bg-review-bg text-review",
};

const OUTCOME_STYLE: Record<Outcome, string> = {
  PASS: "text-allowed",
  FAIL: "text-blocked",
  ESCALATE: "text-review",
};

function formatCents(cents: number): string {
  const dollars = Math.trunc(cents / 100).toLocaleString("en-US");
  return `$${dollars}.${String(cents % 100).padStart(2, "0")}`;
}

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 font-mono text-[11px] font-semibold tracking-wide ${VERDICT_STYLE[verdict]}`}
    >
      {verdict.replace("_", " ")}
    </span>
  );
}

export function VerdictDemo() {
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (paused || reduce) return;
    const id = window.setInterval(() => setIndex((i) => (i + 1) % EXAMPLES.length), 4200);
    return () => window.clearInterval(id);
  }, [paused]);

  const ex = EXAMPLES[index];

  return (
    <div
      className="w-full rounded-2xl border border-rule bg-paper-raised shadow-[0_1px_0_var(--rule),0_24px_48px_-24px_rgba(22,24,29,0.25)]"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <div className="flex gap-1 border-b border-rule p-2" role="tablist" aria-label="Sample expenses">
        {EXAMPLES.map((e, i) => (
          <button
            key={e.merchant}
            role="tab"
            aria-selected={i === index}
            onClick={() => {
              setIndex(i);
              setPaused(true);
            }}
            className={`flex-1 truncate rounded-lg px-2 py-1.5 text-xs transition-colors ${
              i === index ? "bg-paper font-medium text-ink" : "text-ink-muted hover:text-ink"
            }`}
          >
            {e.merchant}
          </button>
        ))}
      </div>

      <div className="space-y-5 p-5 sm:p-6" aria-live="polite">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="truncate font-medium">{ex.merchant}</p>
            <p className="truncate text-sm text-ink-muted">{ex.memo}</p>
          </div>
          <p className="shrink-0 font-mono text-lg tabular-nums">{formatCents(ex.amountCents)}</p>
        </div>

        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <VerdictBadge verdict={ex.verdict} />
          <span className="font-mono text-xs text-ink-muted">
            category: {ex.category} · cleared in {ex.latencyMs}ms
          </span>
        </div>

        <ul className="divide-y divide-rule rounded-lg border border-rule text-sm">
          {ex.trace.map((t) => (
            <li key={t.rule} className="flex items-baseline justify-between gap-3 px-3 py-2">
              <span className="min-w-0">
                <span className="font-medium">{t.rule}</span>
                <span className="block truncate text-xs text-ink-muted">{t.reason}</span>
              </span>
              <span className={`shrink-0 font-mono text-[11px] font-semibold ${OUTCOME_STYLE[t.outcome]}`}>
                {t.outcome}
              </span>
            </li>
          ))}
        </ul>

        <figure className="rounded-lg bg-paper px-4 py-3">
          <figcaption className="mb-1.5 font-mono text-[11px] uppercase tracking-wider text-ink-muted">
            Sample grant agreement · p. {ex.clause.page}
          </figcaption>
          <blockquote className="font-serif text-[17px] leading-snug">
            {ex.clause.before}
            <mark>{ex.clause.quote}</mark>
            {ex.clause.after}
          </blockquote>
        </figure>
      </div>
    </div>
  );
}
