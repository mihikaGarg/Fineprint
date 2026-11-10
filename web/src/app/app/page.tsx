"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BudgetLines, Empty, ExpenseTable, PageHeader, Section, cx } from "@/components/app/ui";
import { api, type LoggedExpense } from "@/lib/api";
import { useAppState } from "@/lib/app-state";

export default function Overview() {
  const { state, refresh } = useAppState();
  const [log, setLog] = useState<LoggedExpense[]>([]);

  useEffect(() => {
    api<LoggedExpense[]>("/api/expenses").then(setLog).catch(() => setLog([]));
  }, [state]);

  if (!state) return null;
  const grants = state.rulesets.filter((r) => r.kind === "grant");
  const policies = state.rulesets.filter((r) => r.kind === "policy");
  const total = state.rulesets.reduce((a, r) => a + r.rules, 0);
  const approved = state.rulesets.reduce((a, r) => a + r.approved, 0);

  const steps = [
    {
      title: "Add a grant agreement",
      body: "Each clause that limits spending becomes a rule, quoted with its page.",
      done: grants.length > 0,
      href: "/app/grants",
    },
    {
      title: "Set up your company policy",
      body: "Upload your expense policy and answer the questions it leaves open.",
      done: policies.length > 0 && !policies.some((p) => p.open_items),
      href: "/app/policy",
    },
    {
      title: "Approve the rules",
      body: "Nothing is enforced until a person approves it.",
      done: total > 0 && approved === total,
      href: "/app/rulebook",
    },
    {
      title: "Check expenses",
      body: "Each expense is checked against the grant and your policy together.",
      done: state.expenses_checked > 0,
      href: "/app/expenses",
    },
  ];
  const next = steps.findIndex((s) => !s.done);

  return (
    <>
      <PageHeader title="Overview" />

      <div className="grid gap-10">
        <Section title="Setup">
          <ol>
            {steps.map((s, i) => (
              <li
                key={s.title}
                className="grid grid-cols-[2rem_minmax(0,1fr)_auto] items-baseline gap-x-3 border-b border-rule py-3 first:pt-0 last:border-b-0"
              >
                <span className={cx("font-mono text-sm", s.done ? "text-allowed" : "text-ink-muted")}>
                  {s.done ? "✓" : `${i + 1}.`}
                </span>
                <div>
                  <p className={cx("font-medium", s.done && "text-ink-muted")}>{s.title}</p>
                  <p className="text-sm text-ink-muted">{s.body}</p>
                </div>
                <Link
                  href={s.href}
                  className={cx(
                    "text-sm",
                    i === next
                      ? "rounded-[3px] bg-ink px-3 py-1 font-medium text-paper hover:bg-ink/85"
                      : "text-ink-muted underline-offset-4 hover:text-ink hover:underline",
                  )}
                >
                  {s.done ? "Open" : i === next ? "Start" : "Go"}
                </Link>
              </li>
            ))}
          </ol>
        </Section>

        <dl className="grid grid-cols-1 border-y border-ink sm:grid-cols-3 sm:divide-x sm:divide-rule">
          <Figure term="Rulebooks" value={state.rulesets.length}>
            {grants.length} grant, {policies.length} company policy
          </Figure>
          <Figure term="Rules approved" value={`${approved} of ${total}`}>
            Only approved rules are enforced
          </Figure>
          <Figure term="Expenses checked" value={state.expenses_checked}>
            <span className="text-allowed">{state.verdicts.ALLOWED} allowed</span>,{" "}
            <span className="text-review">{state.verdicts.NEEDS_REVIEW} to review</span>,{" "}
            <span className="text-blocked">{state.verdicts.BLOCKED} blocked</span>
          </Figure>
        </dl>

        <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,20rem)]">
          <Section title="Recent decisions">
            {log.length ? <ExpenseTable items={log.slice(0, 6)} /> : <Empty>No expenses checked yet.</Empty>}
          </Section>
          <Section title="Grant budgets">
            {state.budgets.length ? (
              <div className="space-y-6">
                {state.budgets.map((b) => (
                  <div key={b.grant_id}>
                    {state.budgets.length > 1 && <h3 className="mb-2 text-sm font-semibold">{b.name}</h3>}
                    <BudgetLines budget={b} onChange={refresh} />
                  </div>
                ))}
              </div>
            ) : (
              <Empty>Add a grant to see its budget.</Empty>
            )}
          </Section>
        </div>
      </div>
    </>
  );
}

function Figure({ term, value, children }: { term: string; value: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="border-b border-rule py-4 last:border-b-0 sm:border-b-0 sm:px-5 sm:first:pl-0">
      <dt className="text-sm text-ink-muted">{term}</dt>
      <dd className="mt-1 font-mono text-2xl tabular-nums">{value}</dd>
      <dd className="mt-1 text-sm text-ink-muted">{children}</dd>
    </div>
  );
}
