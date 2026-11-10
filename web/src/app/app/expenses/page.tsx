"use client";

import { useCallback, useEffect, useState } from "react";
import {
  BudgetLines,
  Button,
  Check,
  Empty,
  ErrorText,
  ExpenseTable,
  Input,
  PageHeader,
  Section,
  Subhead,
  TraceRow,
  cx,
} from "@/components/app/ui";
import {
  api,
  label,
  money,
  post,
  roleLabel,
  toCents,
  verdictText,
  type LoggedExpense,
  type Ruleset,
  type Verdict,
} from "@/lib/api";
import { useAppState } from "@/lib/app-state";

type Filter = "ALL" | Verdict;

export default function Expenses() {
  const { state, refresh } = useAppState();
  const [categories, setCategories] = useState<string[]>([]);
  const [roles, setRoles] = useState<string[]>([]);
  const [form, setForm] = useState({
    memo: "Dr. Lee, Earth Sciences: Boston hotel, 2 nights",
    amount: "640.00",
    category: "lodging",
    merchant: "Harborview Hotel Boston",
    date: "2026-06-12",
    receipt: true,
    prior: false,
  });
  const [approvals, setApprovals] = useState<Set<string>>(new Set());
  const [unchecked, setUnchecked] = useState<Set<string>>(new Set());
  const [result, setResult] = useState<LoggedExpense | null>(null);
  const [error, setError] = useState("");
  const [log, setLog] = useState<LoggedExpense[]>([]);
  const [filter, setFilter] = useState<Filter>("ALL");
  const [busy, setBusy] = useState(false);

  const rulebooks = state?.rulesets.filter((r) => r.approved > 0) ?? [];
  const selected = rulebooks.filter((r) => !unchecked.has(r.id)).map((r) => r.id);

  const loadLog = useCallback(async () => {
    setLog(await api<LoggedExpense[]>("/api/expenses").catch(() => []));
  }, []);

  useEffect(() => {
    api<string[]>("/api/categories").then(setCategories).catch(() => {});
    void loadLog();
  }, [loadLog]);

  useEffect(() => {
    if (!state) return;
    Promise.all(state.rulesets.map((rs) => api<Ruleset>(`/api/rulesets/${rs.id}`)))
      .then((all) => {
        const found = new Set<string>();
        all.forEach((rs) =>
          rs.rules.forEach((r) => {
            if (typeof r.params.approver_role === "string") found.add(r.params.approver_role);
          }),
        );
        setRoles([...found].sort());
      })
      .catch(() => {});
  }, [state]);

  async function check() {
    const cents = toCents(form.amount);
    if (cents === null) return setError("Enter an amount like 640.00");
    setError("");
    setBusy(true);
    try {
      const item = await post<LoggedExpense>("/api/expenses/check", {
        expense: {
          id: `EXP-${Date.now().toString().slice(-5)}`,
          memo: form.memo,
          amount_cents: cents,
          date: form.date,
          merchant: form.merchant || "Unknown",
          category: form.category,
          has_receipt: form.receipt,
          has_prior_approval: form.prior,
          approvals: [...approvals],
        },
        ruleset_ids: selected,
      });
      setResult(item);
      await Promise.all([refresh(), loadLog()]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function runBatch() {
    setBusy(true);
    await post("/api/expenses/sample-batch", {});
    await Promise.all([refresh(), loadLog()]);
    setBusy(false);
  }

  const counts: Record<Filter, number> = { ALL: log.length, ALLOWED: 0, NEEDS_REVIEW: 0, BLOCKED: 0 };
  log.forEach((i) => counts[i.result.verdict]++);
  const shown = filter === "ALL" ? log : log.filter((i) => i.result.verdict === filter);
  const toggle = (set: Set<string>, value: string) => {
    const next = new Set(set);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    return next;
  };

  return (
    <>
      <PageHeader title="Expenses">
        Check an expense before it&apos;s paid. It&apos;s run against every rulebook you tick, and if
        it&apos;s allowed the amount comes off the grant&apos;s budget.
      </PageHeader>

      {state && !rulebooks.length && (
        <p className="mb-8 border-l-2 border-review py-1 pl-3 text-sm">
          No rules are approved yet. Add a grant or a company policy and approve its rules first.
        </p>
      )}

      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,20rem)]">
        <Section title="Check an expense">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Description" className="sm:col-span-2">
              <Input value={form.memo} onChange={(e) => setForm({ ...form, memo: e.target.value })} />
            </Field>
            <Field label="Amount (USD)">
              <Input
                inputMode="decimal"
                value={form.amount}
                onChange={(e) => setForm({ ...form, amount: e.target.value })}
                className="font-mono"
              />
            </Field>
            <Field label="Category">
              <select
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
                className="border border-ink/30 bg-paper-raised px-2.5 py-1.5 text-sm capitalize focus:border-accent focus:outline-none"
              >
                {categories.map((c) => (
                  <option key={c} value={c}>
                    {label(c)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Merchant">
              <Input value={form.merchant} onChange={(e) => setForm({ ...form, merchant: e.target.value })} />
            </Field>
            <Field label="Date">
              <Input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
            </Field>
          </div>

          <Subhead>Paperwork</Subhead>
          <div className="flex flex-wrap gap-x-6 gap-y-2">
            <Check checked={form.receipt} onChange={() => setForm({ ...form, receipt: !form.receipt })}>
              Receipt attached
            </Check>
            <Check checked={form.prior} onChange={() => setForm({ ...form, prior: !form.prior })}>
              Sponsor&apos;s prior written approval
            </Check>
          </div>
          {roles.length > 0 && (
            <>
              <Subhead>Signed off by</Subhead>
              <div className="flex flex-wrap gap-x-6 gap-y-2">
                {roles.map((r) => (
                  <Check key={r} checked={approvals.has(r)} onChange={() => setApprovals(toggle(approvals, r))}>
                    <span className="capitalize">{roleLabel(r)}</span>
                  </Check>
                ))}
              </div>
            </>
          )}

          <Subhead>Check against</Subhead>
          {rulebooks.length ? (
            <div className="flex flex-wrap gap-x-6 gap-y-2">
              {rulebooks.map((r) => (
                <Check key={r.id} checked={!unchecked.has(r.id)} onChange={() => setUnchecked(toggle(unchecked, r.id))}>
                  {r.name}
                </Check>
              ))}
            </div>
          ) : (
            <p className="text-sm text-ink-muted">No approved rulebooks yet.</p>
          )}

          <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-rule pt-4">
            <Button variant="primary" disabled={!selected.length || busy} onClick={check}>
              Check this expense
            </Button>
            <Button disabled={!rulebooks.length || busy} onClick={runBatch}>
              Run the 16 sample expenses
            </Button>
            {error && <ErrorText>{error}</ErrorText>}
          </div>

          {result && <Result item={result} />}
        </Section>

        <Section title="Grant budgets">
          {state?.budgets.length ? (
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

      <Section title="History" className="mt-12">
        <div className="mb-3 flex flex-wrap gap-x-5 border-b border-rule" role="tablist">
          {(["ALL", "ALLOWED", "NEEDS_REVIEW", "BLOCKED"] as Filter[]).map((k) => (
            <button
              key={k}
              type="button"
              role="tab"
              aria-selected={filter === k}
              onClick={() => setFilter(k)}
              className={cx(
                "-mb-px border-b-2 pb-2 text-sm",
                filter === k ? "border-ink font-medium text-ink" : "border-transparent text-ink-muted hover:text-ink",
              )}
            >
              {k === "ALL" ? "All" : verdictText(k)}{" "}
              <span className="font-mono text-xs tabular-nums text-ink-muted">{counts[k]}</span>
            </button>
          ))}
        </div>
        {shown.length ? <ExpenseTable items={shown} /> : <Empty>Nothing here yet.</Empty>}
      </Section>
    </>
  );
}

function Field({ label, className, children }: { label: string; className?: string; children: React.ReactNode }) {
  return (
    <label className={cx("grid gap-1", className)}>
      <span className="text-sm text-ink-muted">{label}</span>
      {children}
    </label>
  );
}

const RULE_COLOR: Record<Verdict, string> = {
  ALLOWED: "border-allowed",
  BLOCKED: "border-blocked",
  NEEDS_REVIEW: "border-review",
};

function Result({ item }: { item: LoggedExpense }) {
  const { state } = useAppState();
  const r = item.result;
  const issues = r.traces.filter((t) => t.outcome !== "PASS");
  const grants = item.ruleset_ids.filter((id) => state?.rulesets.find((x) => x.id === id)?.kind === "grant");
  const spendNote = item.spent_on
    ? `Charged to ${label(item.spent_on)}.`
    : r.verdict !== "ALLOWED"
      ? "Nothing was charged to the budget."
      : grants.length > 1
        ? "Not charged: it was checked against more than one grant. Tick only the grant it belongs to."
        : !grants.length
          ? "Not charged: no grant was ticked."
          : "Not charged: this grant has no budget line for that category.";

  return (
    <div className={cx("mt-6 border-l-4 pl-4", RULE_COLOR[r.verdict])}>
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <span className="font-display text-2xl">{verdictText(r.verdict)}</span>
        <span className="font-mono tabular-nums">{money(item.expense.amount_cents)}</span>
        <span className="capitalize text-ink-muted">{label(item.expense.category)}</span>
      </div>
      <p className="mt-1 text-sm text-ink-muted">
        {r.traces.length} rules applied, from {item.ruleset_ids.length} rulebook
        {item.ruleset_ids.length === 1 ? "" : "s"}, in {r.latency_ms} ms. {spendNote}
      </p>
      <div className="mt-3 border-t border-rule">
        {issues.length ? (
          issues.map((t) => <TraceRow key={t.rule_id} trace={t} />)
        ) : (
          <p className="py-3 text-sm">Every rule that applies passed.</p>
        )}
      </div>
      <details className="group mt-1">
        <summary className="cursor-pointer list-none py-1 text-sm text-ink-muted hover:text-ink">
          <span className="inline-block w-3 transition-transform group-open:rotate-90">›</span>
          All {r.traces.length} rules applied
        </summary>
        <div className="border-t border-rule">
          {r.traces.map((t) => (
            <TraceRow key={t.rule_id} trace={t} />
          ))}
        </div>
      </details>
    </div>
  );
}
