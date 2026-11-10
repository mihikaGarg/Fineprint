"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BudgetLines, Card, Empty, ExpenseTable, PageHeader, cx } from "@/components/app/ui";
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
      body: "Fineprint reads it into rules, each tied to its clause and page.",
      done: grants.length > 0,
      href: "/app/grants",
    },
    {
      title: "Set up your company policy",
      body: "Upload your expense policy. The assistant fills the gaps with you.",
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
      body: "Every expense is checked against the grant and your policy at once.",
      done: state.expenses_checked > 0,
      href: "/app/expenses",
    },
  ];
  const next = steps.findIndex((s) => !s.done);

  return (
    <>
      <PageHeader title="Overview">Every dollar, cleared by the clause.</PageHeader>

      <div className="grid gap-6">
        <Card title="Get set up">
          <ol className="divide-y divide-rule">
            {steps.map((s, i) => (
              <li key={s.title} className="flex items-center gap-4 py-3 first:pt-0 last:pb-0">
                <span
                  className={cx(
                    "grid size-8 shrink-0 place-items-center rounded-full font-mono text-sm",
                    s.done ? "bg-allowed-bg text-allowed" : "border border-rule text-ink-muted",
                  )}
                >
                  {s.done ? "✓" : i + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{s.title}</p>
                  <p className="text-sm text-ink-muted">{s.body}</p>
                </div>
                <Link
                  href={s.href}
                  className={cx(
                    "shrink-0 rounded-lg px-3 py-1.5 text-sm font-medium",
                    i === next ? "bg-ink text-paper" : "border border-rule hover:bg-paper",
                  )}
                >
                  {s.done ? "Open" : "Start"}
                </Link>
              </li>
            ))}
          </ol>
        </Card>

        <div className="grid gap-4 sm:grid-cols-3">
          <Stat label="Rulebooks" value={state.rulesets.length}>
            {grants.length} grant · {policies.length} policy
          </Stat>
          <Stat label="Rules approved" value={`${approved}/${total}`}>
            only approved rules are enforced
          </Stat>
          <Stat label="Expenses checked" value={state.expenses_checked}>
            <span className="text-allowed">{state.verdicts.ALLOWED} allowed</span> ·{" "}
            <span className="text-review">{state.verdicts.NEEDS_REVIEW} review</span> ·{" "}
            <span className="text-blocked">{state.verdicts.BLOCKED} blocked</span>
          </Stat>
        </div>

        <Card title="Grant budgets">
          {state.budgets.length ? (
            <div className="space-y-8">
              {state.budgets.map((b) => (
                <div key={b.grant_id}>
                  {state.budgets.length > 1 && <h3 className="mb-3 font-medium">{b.name}</h3>}
                  <BudgetLines budget={b} onChange={refresh} />
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-ink-muted">Add a grant to see its budget.</p>
          )}
        </Card>

        <Card title="Recent decisions">
          {log.length ? (
            <ExpenseTable items={log.slice(0, 6)} />
          ) : (
            <Empty>No expenses checked yet.</Empty>
          )}
        </Card>
      </div>
    </>
  );
}

function Stat({ label, value, children }: { label: string; value: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-rule bg-paper-raised p-5">
      <p className="font-mono text-[11px] uppercase tracking-wider text-ink-muted">{label}</p>
      <p className="mt-2 font-serif text-4xl tabular-nums">{value}</p>
      <p className="mt-1 text-sm text-ink-muted">{children}</p>
    </div>
  );
}
