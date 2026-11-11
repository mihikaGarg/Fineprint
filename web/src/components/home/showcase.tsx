"use client";

import { Fragment, useState } from "react";
import { Verdict, type VerdictKey } from "@/components/brand";
import { label, money, type ClauseStatus } from "@/lib/api";
import { HOME_DEMO } from "@/lib/home-demo";

const D = HOME_DEMO;
type Row = (typeof D.expenses)[number];

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

/** The 16 real decisions from the demo run, scrolling past like a feed. Hover to pause. */
export function DecisionFeed() {
  const rows = [...D.expenses, ...D.expenses];
  const counts = { ALLOWED: 0, BLOCKED: 0, NEEDS_REVIEW: 0 } as Record<VerdictKey, number>;
  D.expenses.forEach((e) => counts[e.verdict as VerdictKey]++);
  return (
    <div className="crop bg-paper-raised">
      <div className="flex items-center justify-between gap-3 border-b border-ink px-4 py-2.5">
        <span className="font-mono text-[11px]">Live decisions · demo run</span>
        <span className="hidden gap-3 font-mono text-[11px] sm:flex">
          <span className="text-allowed">{counts.ALLOWED} ok</span>
          <span className="text-review">{counts.NEEDS_REVIEW} review</span>
          <span className="text-blocked">{counts.BLOCKED} blocked</span>
        </span>
      </div>
      <div className="relative h-[22rem] overflow-hidden [mask-image:linear-gradient(to_bottom,transparent,black_12%,black_88%,transparent)]">
        <ul className="animate-ticker">
          {rows.map((e, i) => (
            <li key={i} className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 border-b border-rule px-4 py-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{e.memo}</p>
                <p className="mt-0.5 truncate text-xs text-ink-muted">
                  {e.reason ?? `Passed all ${e.rules} rules`}
                </p>
              </div>
              <div className="text-right">
                <p className="font-mono text-sm tabular-nums">{money(e.amount_cents)}</p>
                <Verdict v={e.verdict as VerdictKey} className="mt-1" />
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

/** The demo agreement as a marked-up page: rules highlighted, rejected lines struck, the rest plain. */
export function MarkedAgreement() {
  const [hover, setHover] = useState<number | null>(null);
  const shown: { page: number; text: string; status: ClauseStatus }[] = D.clauses.slice(0, 14);
  return (
    <div className="crop bg-paper-raised px-6 py-6 sm:px-8">
      <div className="mb-4 flex items-baseline justify-between border-b border-ink pb-2">
        <span className="font-mono text-[11px]">{D.grantName}</span>
        <span className="font-mono text-[11px] text-ink-muted">pp. 1–5</span>
      </div>
      <ol className="space-y-2.5 text-[15px] leading-relaxed">
        {shown.map((c, i) => (
          <li
            key={i}
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
            className="grid grid-cols-[2.25rem_minmax(0,1fr)] gap-2"
          >
            <span className="pt-1 font-mono text-[10px] text-ink-muted">p.{c.page}</span>
            <p
              className={cx(
                c.status === "no_rule" && "text-ink-muted",
                c.status === "flagged" && "underline decoration-review decoration-dotted decoration-2 underline-offset-4",
                c.status === "rejected" && "text-ink-muted line-through decoration-blocked decoration-2",
              )}
            >
              {c.status === "rule" ? <mark>{c.text}</mark> : c.text}
              {hover === i && (
                <span className="ml-2 font-mono text-[10px] text-accent">
                  {c.status === "rule"
                    ? "→ became a rule"
                    : c.status === "rejected"
                      ? "→ rejected: couldn't be checked"
                      : c.status === "flagged"
                        ? "→ unclear: left for a person"
                        : "→ nothing to enforce"}
                </span>
              )}
            </p>
          </li>
        ))}
      </ol>
      <p className="mt-4 border-t border-rule pt-3 font-mono text-[11px] text-ink-muted">
        {D.coverage.total - shown.length} more clauses on the following pages
      </p>
    </div>
  );
}

/** The real first question from the sample policy, with its real choices. */
export function TranscriptSample() {
  const [picked, setPicked] = useState<number | null>(null);
  const q = D.question;
  const text = q.text.replace(/^\(\d+ of \d+\) /, "");
  const [ask, why] = text.split("\nI'd pick the first choice. ");
  return (
    <div className="crop bg-paper-raised px-6 py-6 sm:px-8">
      <div className="mb-5 flex items-baseline justify-between border-b border-ink pb-2">
        <span className="font-mono text-[11px]">Northwind University FIN-204</span>
        <span className="font-mono text-[11px] text-ink-muted">question 1 of 13</span>
      </div>
      <Line who="Fineprint">{ask}</Line>
      {why && (
        <Line who="">
          <span className="text-ink-muted">I&apos;d pick A. {why}</span>
        </Line>
      )}
      <ol className="ml-[5.5rem] mt-3 border-t border-rule">
        {q.options.map((o, i) => (
          <li key={o.label} className="border-b border-rule">
            <button
              type="button"
              onClick={() => setPicked(i)}
              className={cx(
                "group grid w-full grid-cols-[1.5rem_minmax(0,1fr)] gap-2 py-2.5 text-left text-sm transition-colors",
                picked === i ? "bg-highlight/40" : "hover:bg-highlight/25",
              )}
            >
              <span className="font-mono text-ink-muted group-hover:text-accent">{"AB"[i]}</span>
              <span>
                {o.label}
                {o.suggested && <span className="ml-2 font-mono text-[10px] text-accent">suggested</span>}
              </span>
            </button>
          </li>
        ))}
      </ol>
      {picked !== null && (
        <Line who="Fineprint">
          {picked === 0 ? q.answer : "Got it: Any expense from $1,000 needs manager approval; without it, approved anyway."}
        </Line>
      )}
    </div>
  );
}

function Line({ who, children }: { who: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[5rem_minmax(0,1fr)] gap-2 py-1.5">
      <span className="pt-0.5 font-mono text-[10px] text-ink-muted">{who}</span>
      <p className="text-[15px] leading-relaxed">{children}</p>
    </div>
  );
}

const FILTERS: ("ALL" | VerdictKey)[] = ["ALL", "BLOCKED", "NEEDS_REVIEW", "ALLOWED"];

/** All 16 real decisions. Click a row to see the clause that decided it. */
export function ExpenseLedger() {
  const [filter, setFilter] = useState<"ALL" | VerdictKey>("ALL");
  const [open, setOpen] = useState<string | null>("NW-1004");
  const rows: readonly Row[] = filter === "ALL" ? D.expenses : D.expenses.filter((e) => e.verdict === filter);
  return (
    <div>
      <div className="flex flex-wrap gap-2 border-b border-ink pb-3">
        {FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={cx(
              "border px-3 py-1 font-mono text-xs transition-colors",
              filter === f ? "border-ink bg-ink text-paper" : "border-rule hover:border-ink",
            )}
          >
            {f === "ALL" ? "All 16" : f === "NEEDS_REVIEW" ? "Needs review" : f[0] + f.slice(1).toLowerCase()}
          </button>
        ))}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] border-collapse text-sm">
          <thead>
            <tr className="text-left font-mono text-[10px] text-ink-muted">
              <th className="py-2 pr-3 font-normal">ID</th>
              <th className="py-2 pr-3 font-normal">Expense</th>
              <th className="py-2 pr-3 text-right font-normal">Amount</th>
              <th className="py-2 pr-3 font-normal">Decision</th>
              <th className="py-2 font-normal">Decided by</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e) => (
              <Fragment key={e.id}>
                <tr
                  onClick={() => setOpen(open === e.id ? null : e.id)}
                  className={cx(
                    "cursor-pointer border-t border-rule align-top transition-colors hover:bg-highlight/20",
                    open === e.id && "bg-highlight/25",
                  )}
                >
                  <td className="py-2.5 pr-3 font-mono text-xs text-ink-muted">{e.id}</td>
                  <td className="py-2.5 pr-3">
                    {e.memo}
                    <span className="block text-xs text-ink-muted">
                      {label(e.category)} · {e.merchant}
                    </span>
                  </td>
                  <td className="py-2.5 pr-3 text-right font-mono tabular-nums">{money(e.amount_cents)}</td>
                  <td className="py-2.5 pr-3">
                    <Verdict v={e.verdict as VerdictKey} />
                  </td>
                  <td className="py-2.5">{e.reason ?? <span className="text-ink-muted">Every rule passed</span>}</td>
                </tr>
                {open === e.id && e.quote && (
                  <tr className="bg-highlight/25">
                    <td />
                    <td colSpan={4} className="pb-4 pr-3">
                      <p className="border-l-2 border-accent pl-3 text-[15px]">
                        <mark>“{e.quote}”</mark>
                        <span className="ml-2 font-mono text-[10px] text-ink-muted">{e.source}</span>
                      </p>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** Grant budget after the demo run. */
export function BudgetBoard() {
  return (
    <div className="grid gap-px bg-ink sm:grid-cols-2 lg:grid-cols-4">
      {D.budget.map((b) => {
        const pct = Math.round((b.spent_cents / b.allocated_cents) * 100);
        return (
          <div key={b.label} className="bg-paper px-5 py-5">
            <p className="text-sm font-medium">{b.label}</p>
            <p className="font-display mt-3 text-3xl tabular-nums">{money(b.allocated_cents - b.spent_cents)}</p>
            <p className="mt-1 font-mono text-[11px] text-ink-muted">
              left of {money(b.allocated_cents)}
            </p>
            <div className="mt-4 h-2 bg-rule">
              <div className="h-full bg-accent" style={{ width: `${Math.max(pct, pct ? 2 : 0)}%` }} />
            </div>
            <p className="mt-2 font-mono text-[10px] text-ink-muted">{b.source}</p>
          </div>
        );
      })}
    </div>
  );
}

