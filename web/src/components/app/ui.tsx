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

// The app reads like a working document: ruled sections instead of boxes,
// rows instead of cards, a colored mark next to a word instead of badges.

export function cx(...classes: (string | false | null | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}

// ---------- primitives ----------

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "quiet";
  size?: "sm" | "md";
};

export function Button({ variant = "secondary", size = "md", className, ...props }: ButtonProps) {
  return (
    <button
      {...props}
      className={cx(
        "inline-flex items-center justify-center gap-2 font-semibold transition-colors",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
        "disabled:cursor-not-allowed disabled:opacity-45",
        size === "sm" ? "px-2.5 py-1 text-[13px]" : "px-3.5 py-1.5 text-sm",
        variant === "primary" && "bg-ink text-paper hover:bg-accent hover:text-accent-ink",
        variant === "secondary" && "border border-ink bg-paper-raised text-ink hover:bg-highlight hover:text-highlight-ink",
        variant === "quiet" && "px-0 text-ink-muted underline decoration-accent underline-offset-4 hover:text-ink",
        className,
      )}
    />
  );
}

/** A titled part of the page, opened by a rule across the column. */
export function Section({
  title,
  aside,
  meta,
  children,
  className,
}: {
  title: React.ReactNode;
  aside?: React.ReactNode;
  meta?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cx("border-t border-ink bg-paper pt-3", className)}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2">
        <h2 className="font-display text-xl">{title}</h2>
        {aside}
      </div>
      {meta && <p className="mt-0.5 text-sm text-ink-muted">{meta}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

export function PageHeader({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <header className="mb-8">
      <h1 className="font-display text-[clamp(2rem,3.6vw,2.75rem)]">{title}</h1>
      {children && <p className="mt-2 max-w-[62ch] text-[15px] leading-relaxed text-ink-muted">{children}</p>}
    </header>
  );
}

export function Subhead({ children }: { children: React.ReactNode }) {
  return <h3 className="mb-2 mt-7 text-sm font-semibold first:mt-0">{children}</h3>;
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="border-l-2 border-rule py-1 pl-3 text-sm text-ink-muted">{children}</p>;
}

export function ErrorText({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-blocked">{children}</p>;
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={cx(
        "border border-ink/30 bg-paper-raised px-2.5 py-1.5 text-sm text-ink",
        "placeholder:text-ink-muted/70 focus:border-accent focus:outline-none",
        props.className,
      )}
    />
  );
}

export function Check({
  checked,
  onChange,
  children,
}: {
  checked: boolean;
  onChange: () => void;
  children: React.ReactNode;
}) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2 text-sm">
      <input type="checkbox" checked={checked} onChange={onChange} className="size-4 accent-[var(--accent)]" />
      {children}
    </label>
  );
}

// ---------- marks ----------

type Tone = "allowed" | "blocked" | "review" | "muted";
const TONE_TEXT: Record<Tone, string> = {
  allowed: "text-allowed",
  blocked: "text-blocked",
  review: "text-review",
  muted: "text-ink-muted",
};
const TONE_DOT: Record<Tone, string> = {
  allowed: "bg-allowed",
  blocked: "bg-blocked",
  review: "bg-review",
  muted: "bg-ink-muted",
};

/** A small square in the verdict color, then the word. */
export function Mark({ tone, children }: { tone: Tone; children: React.ReactNode }) {
  return (
    <span className={cx("inline-flex shrink-0 items-center gap-1.5 text-sm font-medium", TONE_TEXT[tone])}>
      <span aria-hidden className={cx("size-2", TONE_DOT[tone])} />
      {children}
    </span>
  );
}

const VERDICT_TONE: Record<Verdict, Tone> = { ALLOWED: "allowed", BLOCKED: "blocked", NEEDS_REVIEW: "review" };
const OUTCOME: Record<Outcome, [Tone, string]> = {
  PASS: ["allowed", "Pass"],
  FAIL: ["blocked", "Fail"],
  ESCALATE: ["review", "Review"],
};

export const VerdictMark = ({ verdict }: { verdict: Verdict }) => (
  <Mark tone={VERDICT_TONE[verdict]}>{verdictText(verdict)}</Mark>
);
export const OutcomeMark = ({ outcome }: { outcome: Outcome }) => (
  <Mark tone={OUTCOME[outcome][0]}>{OUTCOME[outcome][1]}</Mark>
);

// ---------- clause quote ----------

export function Clause({ quote, source }: { quote: string; source: string }) {
  return (
    <figure>
      <blockquote className="text-[15px] leading-relaxed">
        <mark>“{quote}”</mark>
      </blockquote>
      <figcaption className="mt-1 font-mono text-[10px] text-ink-muted">{source}</figcaption>
    </figure>
  );
}

// ---------- budgets ----------

export function BudgetLines({ budget, onChange }: { budget: GrantBudget; onChange: () => void }) {
  if (!budget.lines.length && !budget.missing.length) {
    return <Empty>No budget table found in this agreement.</Empty>;
  }
  return (
    <div>
      {budget.lines.map((l) => {
        const pct = l.allocated_cents ? Math.min(100, Math.round((l.spent_cents / l.allocated_cents) * 100)) : 0;
        return (
          <div key={l.line} className="border-b border-rule py-2.5 first:pt-0 last:border-b-0">
            <div className="flex items-baseline justify-between gap-4">
              <span className="text-sm font-medium">{l.label}</span>
              <span className="font-mono text-sm tabular-nums">
                {money(l.remaining_cents)}
                <span className="text-ink-muted"> left</span>
              </span>
            </div>
            <div className="mt-1.5 h-1 bg-rule">
              <div className={cx("h-full", pct > 90 ? "bg-blocked" : "bg-accent")} style={{ width: `${pct}%` }} />
            </div>
            <div className="mt-1 flex flex-wrap justify-between gap-x-4 text-xs text-ink-muted">
              <span className="font-mono tabular-nums">
                {money(l.spent_cents)} of {money(l.allocated_cents)} spent
              </span>
              <span>{l.source}</span>
            </div>
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
    <div className="border-l-2 border-review py-1 pl-3">
      <p className="text-sm">
        <span className="font-medium capitalize">{label(line)}</span>
        <span className="text-ink-muted">: a rule refers to this budget line, but the agreement gives no amount.</span>
      </p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <Input value={value} onChange={(e) => setValue(e.target.value)} placeholder="$5,000" className="w-28" />
        <Button size="sm" variant="primary" onClick={save}>
          Save amount
        </Button>
        {error && <ErrorText>{error}</ErrorText>}
      </div>
    </div>
  );
}

// ---------- rules ----------

/** One rule as a row: what it does and its examples on the left, the clause on the right. */
export function RuleRow({
  card,
  sourceName,
  onApprove,
}: {
  card: RuleCard;
  sourceName: string;
  onApprove?: () => void;
}) {
  const r = card.rule;
  const proposed = r.status !== "approved";
  return (
    <article className="-mx-3 grid gap-x-8 gap-y-3 border-b border-rule px-3 py-4 transition-colors last:border-b-0 hover:bg-paper-raised md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <div className="min-w-0">
        <p className="font-medium leading-snug">{card.description}</p>
        {card.open_questions.length > 0 ? (
          <p className="mt-1.5 text-sm text-review">Waiting on an answer in Company policy.</p>
        ) : (
          card.examples.length > 0 && (
            <ul className="mt-2 space-y-1">
              {card.examples.map((e) => (
                <li key={e.description} className="grid grid-cols-[7.5rem_1fr] gap-2 text-sm">
                  <VerdictMark verdict={e.verdict} />
                  <span className="text-ink-muted">{e.description}</span>
                </li>
              ))}
            </ul>
          )
        )}
        {proposed && (
          <div className="mt-3 flex items-center gap-3">
            <span className="text-xs text-ink-muted">Not enforced yet.</span>
            {card.can_approve && onApprove && (
              <Button size="sm" onClick={onApprove}>
                Approve
              </Button>
            )}
          </div>
        )}
      </div>
      <Clause quote={r.citation.quote} source={`${sourceName}, p. ${r.citation.page}`} />
    </article>
  );
}

// ---------- expenses ----------

export function TraceRow({ trace }: { trace: RuleTrace }) {
  const source = trace.source === "grant" ? `Grant agreement, p. ${trace.citation.page}` : "Company policy";
  return (
    <div className="grid gap-x-6 gap-y-2 border-b border-rule py-3 last:border-b-0 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <div>
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <OutcomeMark outcome={trace.outcome} />
          <span className="text-sm">{trace.reason}</span>
        </div>
        {trace.fix && <p className="mt-1 text-sm text-ink-muted">To clear it: {trace.fix}</p>}
      </div>
      <Clause quote={trace.citation.quote} source={source} />
    </div>
  );
}

export function ExpenseTable({ items }: { items: LoggedExpense[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[680px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-ink text-left text-xs text-ink-muted">
            <th className="py-2 pr-4 font-medium">Expense</th>
            <th className="py-2 pr-4 text-right font-medium">Amount</th>
            <th className="py-2 pr-4 font-medium">Decision</th>
            <th className="py-2 font-medium">Why</th>
          </tr>
        </thead>
        <tbody>
          {items.map(({ expense: e, result: r }) => {
            const issues = r.traces.filter((t) => t.outcome !== "PASS");
            return (
              <tr key={e.id} className="border-b border-rule align-top transition-colors hover:bg-highlight/20">
                <td className="py-2.5 pr-4">
                  <div>{e.memo || e.merchant}</div>
                  <div className="mt-0.5 text-xs text-ink-muted">
                    <span className="font-mono">{e.id}</span> · {label(e.category)} · {e.merchant}
                    {e.approvals.length > 0 && ` · signed off by ${e.approvals.map(roleLabel).join(", ")}`}
                  </div>
                </td>
                <td className="py-2.5 pr-4 text-right font-mono tabular-nums">{money(e.amount_cents)}</td>
                <td className="py-2.5 pr-4">
                  <VerdictMark verdict={r.verdict} />
                </td>
                <td className="py-2.5">
                  {issues.length ? (
                    issues.map((t) => (
                      <div key={t.rule_id} className="mb-1 last:mb-0">
                        <span className="text-ink-muted">
                          {t.source === "grant" ? `Grant p. ${t.citation.page}` : "Policy"}:
                        </span>{" "}
                        {t.reason}
                      </div>
                    ))
                  ) : (
                    <span className="text-ink-muted">Every rule passed</span>
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
