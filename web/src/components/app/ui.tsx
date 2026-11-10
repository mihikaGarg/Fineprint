"use client";

import { useState } from "react";
import {
  label,
  money,
  post,
  roleLabel,
  toCents,
  verdictText,
  type GrantBudget,
  type LoggedExpense,
  type Outcome,
  type RuleCard,
  type RuleTrace,
  type Verdict,
} from "@/lib/api";

export function cx(...classes: (string | false | null | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}

// ---------- primitives ----------

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md";
};

export function Button({ variant = "secondary", size = "md", className, ...props }: ButtonProps) {
  return (
    <button
      {...props}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink",
        "disabled:cursor-not-allowed disabled:opacity-50",
        size === "sm" ? "px-3 py-1.5 text-sm" : "px-4 py-2 text-sm",
        variant === "primary" && "bg-ink text-paper hover:bg-ink/85",
        variant === "secondary" && "border border-rule bg-paper-raised text-ink hover:bg-paper",
        variant === "ghost" && "text-ink-muted hover:bg-paper-raised hover:text-ink",
        className,
      )}
    />
  );
}

export function Card({
  children,
  className,
  title,
  aside,
}: {
  children: React.ReactNode;
  className?: string;
  title?: React.ReactNode;
  aside?: React.ReactNode;
}) {
  return (
    <section className={cx("rounded-2xl border border-rule bg-paper-raised p-5 sm:p-6", className)}>
      {(title || aside) && (
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          {title && <h2 className="font-serif text-2xl leading-tight">{title}</h2>}
          {aside}
        </div>
      )}
      {children}
    </section>
  );
}

export function PageHeader({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <header className="mb-8 max-w-2xl">
      <h1 className="font-serif text-4xl tracking-tight sm:text-5xl">{title}</h1>
      {children && <p className="mt-3 leading-relaxed text-ink-muted">{children}</p>}
    </header>
  );
}

export function Label({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mb-3 mt-6 font-mono text-xs uppercase tracking-wider text-ink-muted first:mt-0">
      {children}
    </h3>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-rule p-8 text-center text-ink-muted">
      {children}
    </div>
  );
}

export function ErrorText({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-blocked">{children}</p>;
}

// ---------- pills ----------

const TONE = {
  allowed: "bg-allowed-bg text-allowed",
  blocked: "bg-blocked-bg text-blocked",
  review: "bg-review-bg text-review",
  neutral: "bg-paper text-ink-muted border border-rule",
} as const;

export function Pill({ tone, children }: { tone: keyof typeof TONE; children: React.ReactNode }) {
  return (
    <span
      className={cx(
        "inline-flex shrink-0 items-center rounded-full px-2 py-0.5 font-mono text-[11px] font-medium uppercase tracking-wide",
        TONE[tone],
      )}
    >
      {children}
    </span>
  );
}

const VERDICT_TONE: Record<Verdict, keyof typeof TONE> = {
  ALLOWED: "allowed",
  BLOCKED: "blocked",
  NEEDS_REVIEW: "review",
};
const OUTCOME_TONE: Record<Outcome, keyof typeof TONE> = {
  PASS: "allowed",
  FAIL: "blocked",
  ESCALATE: "review",
};

export const VerdictPill = ({ verdict }: { verdict: Verdict }) => (
  <Pill tone={VERDICT_TONE[verdict]}>{verdictText(verdict)}</Pill>
);
export const OutcomePill = ({ outcome }: { outcome: Outcome }) => (
  <Pill tone={OUTCOME_TONE[outcome]}>{{ PASS: "Pass", FAIL: "Fail", ESCALATE: "Review" }[outcome]}</Pill>
);

// ---------- clause quote ----------

export function Clause({ quote, source }: { quote: string; source: string }) {
  return (
    <blockquote className="mt-2 border-l-2 border-rule pl-3">
      <p className="font-serif text-[15px] italic leading-snug text-ink/80">“{quote}”</p>
      <p className="mt-1 font-mono text-[11px] uppercase tracking-wide text-ink-muted">{source}</p>
    </blockquote>
  );
}

// ---------- budgets ----------

export function BudgetLines({ budget, onChange }: { budget: GrantBudget; onChange: () => void }) {
  if (!budget.lines.length && !budget.missing.length) {
    return <p className="text-sm text-ink-muted">No budget table found in this agreement.</p>;
  }
  return (
    <div className="space-y-5">
      {budget.lines.map((l) => {
        const pct = l.allocated_cents
          ? Math.min(100, Math.round((l.spent_cents / l.allocated_cents) * 100))
          : 0;
        return (
          <div key={l.line}>
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <span className="font-medium">{l.label}</span>
              <span className="font-mono text-sm tabular-nums text-ink-muted">
                {money(l.spent_cents)} <span className="opacity-60">of</span> {money(l.allocated_cents)}
                <span className="ml-3 text-ink">{money(l.remaining_cents)} left</span>
              </span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-paper">
              <div
                className={cx("h-full rounded-full", pct > 90 ? "bg-blocked" : "bg-allowed")}
                style={{ width: `${pct}%` }}
              />
            </div>
            <p className="mt-1.5 font-mono text-[11px] text-ink-muted">{l.source}</p>
          </div>
        );
      })}
      {budget.missing.map((line) => (
        <MissingLine key={line} grantId={budget.grant_id} line={line} onSaved={onChange} />
      ))}
    </div>
  );
}

function MissingLine({ grantId, line, onSaved }: { grantId: string; line: string; onSaved: () => void }) {
  const [value, setValue] = useState("");
  const [error, setError] = useState("");
  async function save() {
    const cents = toCents(value);
    if (!cents) return setError("Enter an amount like 5,000");
    await post(`/api/grants/${grantId}/budget`, { line, allocated_cents: cents });
    onSaved();
  }
  return (
    <div className="rounded-xl border border-dashed border-review/50 bg-review-bg/40 p-4">
      <p className="text-sm">
        <span className="font-medium capitalize">{label(line)}</span>
        <span className="text-ink-muted">: a rule refers to this budget line, but the agreement gives no amount.</span>
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="text-sm text-ink-muted">Approved amount</span>
        <Input value={value} onChange={(e) => setValue(e.target.value)} placeholder="$5,000" className="w-32" />
        <Button size="sm" variant="primary" onClick={save}>
          Save
        </Button>
        {error && <ErrorText>{error}</ErrorText>}
      </div>
    </div>
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={cx(
        "rounded-lg border border-rule bg-paper px-3 py-2 text-sm text-ink placeholder:text-ink-muted/70",
        "focus:border-ink focus:outline-none",
        props.className,
      )}
    />
  );
}

// ---------- rules ----------

export function RuleCardView({
  card,
  sourceName,
  onApprove,
}: {
  card: RuleCard;
  sourceName: string;
  onApprove?: () => void;
}) {
  const r = card.rule;
  const approved = r.status === "approved";
  return (
    <article className="border-t border-rule py-4 first:border-t-0 first:pt-0">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Pill tone={approved ? "allowed" : "neutral"}>{approved ? "Approved" : "Proposed"}</Pill>
            <p className="font-medium">{card.description}</p>
          </div>
          <Clause quote={r.citation.quote} source={`${sourceName} · p. ${r.citation.page}`} />
        </div>
        {!approved && card.can_approve && onApprove && (
          <Button size="sm" onClick={onApprove}>
            Approve
          </Button>
        )}
      </div>
      {card.open_questions.length > 0 && (
        <p className="mt-2 text-sm text-review">Has an open question. Answer it in Company policy.</p>
      )}
      {card.examples.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
          {card.examples.map((e) => (
            <li key={e.description} className="flex items-center gap-1.5 text-sm text-ink-muted">
              <VerdictPill verdict={e.verdict} />
              {e.description}
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}

// ---------- expenses ----------

export function TraceRow({ trace }: { trace: RuleTrace }) {
  const source = trace.source === "grant" ? `Grant agreement · p. ${trace.citation.page}` : "Company policy";
  return (
    <div className="border-t border-rule py-3 first:border-t-0">
      <div className="flex flex-wrap items-center gap-2">
        <OutcomePill outcome={trace.outcome} />
        <span className="text-sm">{trace.reason}</span>
      </div>
      <Clause quote={trace.citation.quote} source={source} />
      {trace.fix && (
        <p className="mt-2 text-sm">
          <span className="text-ink-muted">What would make it OK: </span>
          {trace.fix}
        </p>
      )}
    </div>
  );
}

export function ExpenseTable({ items }: { items: LoggedExpense[] }) {
  return (
    <div className="-mx-5 overflow-x-auto sm:-mx-6">
      <table className="w-full min-w-[640px] text-sm">
        <thead>
          <tr className="border-b border-rule text-left font-mono text-[11px] uppercase tracking-wider text-ink-muted">
            <th className="px-5 pb-2 font-normal sm:px-6">Expense</th>
            <th className="pb-2 font-normal">Verdict</th>
            <th className="px-5 pb-2 font-normal sm:px-6">Decided by</th>
          </tr>
        </thead>
        <tbody>
          {items.map(({ expense: e, result: r }) => {
            const issues = r.traces.filter((t) => t.outcome !== "PASS");
            return (
              <tr key={e.id} className="border-b border-rule align-top last:border-b-0">
                <td className="px-5 py-3 sm:px-6">
                  <div>
                    <span className="font-mono font-medium tabular-nums">{money(e.amount_cents)}</span>{" "}
                    {e.memo || e.merchant}
                  </div>
                  <div className="mt-0.5 text-xs text-ink-muted">
                    {e.id} · {label(e.category)} · {e.merchant}
                    {e.approvals.length > 0 && ` · approved by ${e.approvals.map(roleLabel).join(", ")}`}
                  </div>
                </td>
                <td className="py-3">
                  <VerdictPill verdict={r.verdict} />
                </td>
                <td className="px-5 py-3 sm:px-6">
                  {issues.length ? (
                    issues.map((t) => (
                      <div key={t.rule_id} className="mb-1.5 last:mb-0">
                        <span className="font-medium">
                          {t.source === "grant" ? `Grant p. ${t.citation.page}` : "Policy"}:
                        </span>{" "}
                        {t.reason}
                        {t.fix && <div className="text-xs text-ink-muted">Fix: {t.fix}</div>}
                      </div>
                    ))
                  ) : (
                    <span className="text-ink-muted">All rules passed</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
