"use client";

import { useCallback, useEffect, useState } from "react";
import {
  BudgetLines,
  Button,
  Card,
  Empty,
  ErrorText,
  ExpenseTable,
  Input,
  Label,
  PageHeader,
  TraceRow,
  VerdictPill,
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
    memo: "Dr. Lee · Earth Sciences · Boston hotel, 2 nights",
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
        Check an expense before it&apos;s paid. It&apos;s checked against every selected rulebook at
        once, and allowed spend comes off the grant budget.
      </PageHeader>

      {state && !rulebooks.length && (
        <div className="mb-6 rounded-xl border border-review/40 bg-review-bg px-4 py-3 text-sm text-review">
          No approved rules yet. Add a grant or company policy and approve its rules first.
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
        <Card title="Check an expense">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Description" className="sm:col-span-2">
              <Input value={form.memo} onChange={(e) => setForm({ ...form, memo: e.target.value })} />
            </Field>
            <Field label="Amount ($)">
              <Input
                inputMode="decimal"
                value={form.amount}
                onChange={(e) => setForm({ ...form, amount: e.target.value })}
              />
            </Field>
            <Field label="Category">
              <select
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
                className="rounded-lg border border-rule bg-paper px-3 py-2 text-sm capitalize focus:border-ink focus:outline-none"
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

          <Label>Documentation and approvals</Label>
          <div className="flex flex-wrap gap-2">
            <Toggle on={form.receipt} onClick={() => setForm({ ...form, receipt: !form.receipt })}>
              Receipt attached
            </Toggle>
            <Toggle on={form.prior} onClick={() => setForm({ ...form, prior: !form.prior })}>
              Sponsor&apos;s prior written approval
            </Toggle>
            {roles.map((r) => (
              <Toggle key={r} on={approvals.has(r)} onClick={() => setApprovals(toggle(approvals, r))}>
                Approved by {roleLabel(r)}
              </Toggle>
            ))}
          </div>

          <Label>Check against</Label>
          {rulebooks.length ? (
            <div className="flex flex-wrap gap-2">
              {rulebooks.map((r) => (
                <Toggle key={r.id} on={!unchecked.has(r.id)} onClick={() => setUnchecked(toggle(unchecked, r.id))}>
                  {r.name}
                </Toggle>
              ))}
            </div>
          ) : (
            <p className="text-sm text-ink-muted">No approved rulebooks.</p>
          )}

          <div className="mt-6 flex flex-wrap items-center gap-3">
            <Button variant="primary" disabled={!selected.length || busy} onClick={check}>
              Check expense
            </Button>
            <Button disabled={!rulebooks.length || busy} onClick={runBatch}>
              Run 16 sample expenses
            </Button>
            {error && <ErrorText>{error}</ErrorText>}
          </div>

          {result && <Result item={result} />}
        </Card>

        <Card title="Grant budgets">
          {state?.budgets.length ? (
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
      </div>

      <Card title="History" className="mt-6">
        <div className="mb-4 flex flex-wrap gap-2">
          {(["ALL", "ALLOWED", "NEEDS_REVIEW", "BLOCKED"] as Filter[]).map((k) => (
            <Toggle key={k} on={filter === k} onClick={() => setFilter(k)}>
              {k === "ALL" ? "All" : verdictText(k)} <span className="font-mono tabular-nums opacity-70">{counts[k]}</span>
            </Toggle>
          ))}
        </div>
        {shown.length ? <ExpenseTable items={shown} /> : <Empty>Nothing here yet.</Empty>}
      </Card>
    </>
  );
}

function Field({ label, className, children }: { label: string; className?: string; children: React.ReactNode }) {
  return (
    <label className={cx("grid gap-1.5", className)}>
      <span className="text-sm text-ink-muted">{label}</span>
      {children}
    </label>
  );
}

function Toggle({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={cx(
        "rounded-full border px-3 py-1.5 text-sm transition-colors",
        on ? "border-ink bg-ink text-paper" : "border-rule text-ink-muted hover:border-ink hover:text-ink",
      )}
    >
      {children}
    </button>
  );
}

function Result({ item }: { item: LoggedExpense }) {
  const { state } = useAppState();
  const r = item.result;
  const issues = r.traces.filter((t) => t.outcome !== "PASS");
  const [showAll, setShowAll] = useState(false);
  const grants = item.ruleset_ids.filter((id) => state?.rulesets.find((x) => x.id === id)?.kind === "grant");
  const spendNote = item.spent_on
    ? `Spend recorded on ${label(item.spent_on)}.`
    : r.verdict !== "ALLOWED"
      ? "No spend recorded."
      : grants.length > 1
        ? "Spend not recorded: it was checked against several grants, so select only the grant it's charged to."
        : !grants.length
          ? "Spend not recorded: no grant was checked."
          : "Spend not recorded: this grant has no budget line for that category.";

  return (
    <div
      className={cx(
        "mt-6 rounded-xl border p-4",
        r.verdict === "ALLOWED" && "border-allowed/40 bg-allowed-bg/40",
        r.verdict === "BLOCKED" && "border-blocked/40 bg-blocked-bg/40",
        r.verdict === "NEEDS_REVIEW" && "border-review/40 bg-review-bg/40",
      )}
    >
      <div className="flex flex-wrap items-center gap-3">
        <VerdictPill verdict={r.verdict} />
        <span className="font-mono text-lg tabular-nums">{money(item.expense.amount_cents)}</span>
        <span className="capitalize text-ink-muted">{label(item.expense.category)}</span>
      </div>
      <p className="mt-2 text-sm text-ink-muted">
        Checked {r.traces.length} rules from {item.ruleset_ids.length} rulebook
        {item.ruleset_ids.length === 1 ? "" : "s"} in {r.latency_ms} ms. {spendNote}
      </p>
      <div className="mt-3">
        {issues.length ? (
          issues.map((t) => <TraceRow key={t.rule_id} trace={t} />)
        ) : (
          <p className="text-sm">Every applicable rule passed.</p>
        )}
      </div>
      <button
        type="button"
        onClick={() => setShowAll(!showAll)}
        className="mt-2 text-sm text-ink-muted underline-offset-2 hover:text-ink hover:underline"
      >
        {showAll ? "Hide" : "Show"} all {r.traces.length} rules checked
      </button>
      {showAll && (
        <div className="mt-2">
          {r.traces.map((t) => (
            <TraceRow key={t.rule_id} trace={t} />
          ))}
        </div>
      )}
    </div>
  );
}
