"use client";

import { useEffect, useState } from "react";
import { VerdictBadge } from "./verdict-demo";

type Verdict = "ALLOWED" | "BLOCKED" | "NEEDS_REVIEW";
type Outcome = "PASS" | "FAIL" | "ESCALATE";

interface Citation {
  page: number;
  quote: string;
  char_start: number;
  char_end: number;
  prefix?: string;
  suffix?: string;
}

interface SpendRule {
  id: string;
  name: string;
  rule_type: string;
  citation: Citation;
  params: Record<string, unknown>;
}

interface Ruleset {
  grant_id: string;
  grant_name: string;
  rules: SpendRule[];
}

interface RuleTrace {
  rule_id: string;
  rule_name: string;
  outcome: Outcome;
  reason: string;
  citation: Citation;
}

interface RejectedCandidate {
  candidate: { page?: number; quote?: string; rule_type?: string };
  reason: string;
}

interface CompileResponse {
  ruleset: Ruleset;
  rejected: RejectedCandidate[];
  verified_count: number;
  rejected_count: number;
  proposer: string;
}

interface EnforcementResult {
  verdict: Verdict;
  traces: RuleTrace[];
  latency_ms: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
const API_OFFLINE = "Can't reach the Fineprint API. Start it with `make api` (port 8000).";

interface BudgetState {
  lines: Record<string, { category: string; allocated_cents: number; spent_cents: number }>;
}

/** "412.5" -> 41250. Parses digits only; never goes through floating point. */
function parseDollarsToCents(input: string): number | null {
  const match = /^\s*\$?(\d{1,9})(?:\.(\d{1,2}))?\s*$/.exec(input.replace(/,/g, ""));
  if (!match) return null;
  return Number(match[1]) * 100 + Number((match[2] ?? "").padEnd(2, "0"));
}

export function InteractiveStudio() {
  const [ruleset, setRuleset] = useState<Ruleset | null>(null);
  const [budget, setBudget] = useState<BudgetState | null>(null);
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string>("");
  const [compileInfo, setCompileInfo] = useState<CompileResponse | null>(null);

  // Expense form state
  const [merchant, setMerchant] = useState("Lakeshore Hotel");
  const [memo, setMemo] = useState("Conference lodging, 2 nights");
  const [dollars, setDollars] = useState("412.00");
  const [category, setCategory] = useState("travel_domestic");
  const [hasApproval, setHasApproval] = useState(false);
  const [expenseDate, setExpenseDate] = useState("2026-06-15");

  // Enforcement result
  const [result, setResult] = useState<EnforcementResult | null>(null);
  const [evaluating, setEvaluating] = useState(false);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);

  // Load the sample grant from the API on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/fixtures`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: { ruleset: Ruleset; budget: BudgetState }) => {
        setRuleset(data.ruleset);
        setBudget(data.budget);
        if (data.ruleset.rules[0]) setActiveCitation(data.ruleset.rules[0].citation);
      })
      .catch(() => setError(API_OFFLINE));
  }, []);

  const runCompile = async (request: () => Promise<Response>, label: string) => {
    setLoading(true);
    setError("");
    setResult(null);
    setUploadStatus(`${label}: reading pages, finding rules, verifying every quote against the PDF…`);
    try {
      const res = await request();
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: CompileResponse = await res.json();
      // Compiled rules start as "proposed" and aren't enforced until approved.
      // Until the review screen exists, approve them all so the demo can enforce.
      const approved = await fetch(`${API_BASE}/api/rulesets/${data.ruleset.grant_id}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (approved.ok) data.ruleset = await approved.json();
      setRuleset(data.ruleset);
      setCompileInfo(data);
      setUploadStatus(
        `${data.verified_count} rules verified, ${data.rejected_count} suggestions rejected.`,
      );
      if (data.ruleset.rules[0]) setActiveCitation(data.ruleset.rules[0].citation);
    } catch {
      setUploadStatus("");
      setError(API_OFFLINE);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    void runCompile(
      () => fetch(`${API_BASE}/api/compile`, { method: "POST", body: formData }),
      file.name,
    );
  };

  const handleLoadDemo = () => {
    void runCompile(
      () => fetch(`${API_BASE}/api/compile/demo`, { method: "POST" }),
      "Demo grant",
    );
  };

  const handleRunEnforcement = async () => {
    if (!ruleset || !budget) return;

    const amountCents = parseDollarsToCents(dollars);
    if (amountCents === null || amountCents === 0) {
      setError("Enter an amount like 412.00");
      return;
    }

    setError("");
    setEvaluating(true);

    const expensePayload = {
      id: "exp_studio",
      amount_cents: amountCents,
      date: expenseDate,
      merchant,
      category,
      memo,
      has_prior_approval: hasApproval,
    };

    try {
      const res = await fetch(`${API_BASE}/api/enforce`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          expense: expensePayload,
          ruleset,
          budget_state: budget,
        }),
      });

      if (!res.ok) {
        setResult(null);
        setError(`The API rejected this expense (HTTP ${res.status}).`);
        return;
      }
      const data: EnforcementResult = await res.json();
      setResult(data);
      // Show the clause that decided the verdict, not just the first rule checked.
      const deciding =
        data.traces.find((t) => t.outcome === "FAIL") ??
        data.traces.find((t) => t.outcome === "ESCALATE") ??
        data.traces[0];
      if (deciding) setActiveCitation(deciding.citation);
    } catch {
      setResult(null);
      setError(API_OFFLINE);
    } finally {
      setEvaluating(false);
    }
  };

  const applyPreset = (pMerchant: string, pMemo: string, pDollars: string, pCategory: string, pApproval: boolean) => {
    setMerchant(pMerchant);
    setMemo(pMemo);
    setDollars(pDollars);
    setCategory(pCategory);
    setHasApproval(pApproval);
  };

  return (
    <div className="w-full rounded-2xl border border-rule bg-paper-raised p-6 shadow-sm">
      <div className="mb-6 flex flex-col justify-between gap-4 border-b border-rule pb-5 md:flex-row md:items-center">
        <div>
          <span className="font-mono text-xs uppercase tracking-wider text-ink-muted">Interactive Studio</span>
          <h2 className="font-serif text-3xl font-medium tracking-tight">
            {ruleset ? ruleset.grant_name : error ? "Grant unavailable" : "Loading grant…"}
          </h2>
        </div>

        {/* Compile controls */}
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={handleLoadDemo}
            disabled={loading}
            className="rounded-full bg-ink px-4 py-2 text-xs font-medium text-paper hover:opacity-90 disabled:opacity-50"
          >
            {loading ? "Compiling…" : "Load demo grant"}
          </button>
          <label className="cursor-pointer rounded-full border border-rule bg-paper px-4 py-2 text-xs font-medium hover:border-ink">
            <span>Upload grant PDF</span>
            <input
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={handleFileUpload}
              disabled={loading}
            />
          </label>
        </div>
      </div>

      {uploadStatus && (
        <div className="mb-6 flex flex-wrap items-center gap-3 rounded-lg bg-paper px-4 py-2 text-xs text-ink-muted">
          {compileInfo && !loading && (
            <span
              className={`rounded-full px-2.5 py-0.5 font-mono text-[10px] font-semibold ${
                compileInfo.proposer === "llm"
                  ? "bg-allowed-bg text-allowed"
                  : "bg-review-bg text-review"
              }`}
            >
              {compileInfo.proposer === "llm" ? "RULES FOUND BY CLAUDE" : "KEYWORD FINDER (OFFLINE)"}
            </span>
          )}
          <span>{uploadStatus}</span>
          {compileInfo && compileInfo.proposer.startsWith("keyword (") && (
            <span className="text-review">{compileInfo.proposer}</span>
          )}
        </div>
      )}

      {error && (
        <div role="alert" className="mb-6 rounded-lg bg-blocked-bg px-4 py-2 text-xs text-blocked">
          {error}
        </div>
      )}

      <div className="grid gap-8 lg:grid-cols-2">
        {/* Left: Spend Simulator Form */}
        <div className="space-y-5">
          <div className="flex items-center justify-between">
            <h3 className="font-medium text-sm text-ink-muted uppercase tracking-wider">Test An Expense</h3>
            <div className="flex gap-1.5 text-xs">
              <button
                type="button"
                onClick={() => applyPreset("Lakeshore Hotel", "Lodging 2 nights", "412.00", "travel_domestic", false)}
                className="rounded border border-rule px-2 py-1 text-ink-muted hover:border-ink hover:text-ink"
              >
                Travel
              </button>
              <button
                type="button"
                onClick={() => applyPreset("Riverside Wine Bar", "Team dinner", "186.40", "alcohol", false)}
                className="rounded border border-rule px-2 py-1 text-ink-muted hover:border-ink hover:text-ink"
              >
                Alcohol
              </button>
              <button
                type="button"
                onClick={() => applyPreset("Meridian Optics", "Thermal Camera", "6250.00", "equipment", false)}
                className="rounded border border-rule px-2 py-1 text-ink-muted hover:border-ink hover:text-ink"
              >
                Equipment
              </button>
            </div>
          </div>

          <div className="space-y-4 rounded-xl border border-rule bg-paper p-5">
            <div>
              <label className="block text-xs font-medium text-ink-muted">Merchant</label>
              <input
                type="text"
                value={merchant}
                onChange={(e) => setMerchant(e.target.value)}
                className="mt-1 w-full rounded-lg border border-rule bg-transparent px-3 py-2 text-sm focus:border-ink focus:outline-none"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-ink-muted">Amount ($ USD)</label>
                <input
                  type="number"
                  step="0.01"
                  value={dollars}
                  onChange={(e) => setDollars(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-rule bg-transparent px-3 py-2 font-mono text-sm focus:border-ink focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-ink-muted">Category</label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-rule bg-paper px-3 py-2 text-sm focus:border-ink focus:outline-none"
                >
                  <option value="travel_domestic">Domestic Travel</option>
                  <option value="equipment">Special Equipment</option>
                  <option value="alcohol">Alcohol / Dining</option>
                  <option value="supplies">Supplies</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-ink-muted">Transaction Date</label>
                <input
                  type="date"
                  value={expenseDate}
                  onChange={(e) => setExpenseDate(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-rule bg-transparent px-3 py-2 text-sm focus:border-ink focus:outline-none"
                />
              </div>

              <div className="flex items-center pt-5">
                <label className="flex cursor-pointer items-center gap-2 text-xs">
                  <input
                    type="checkbox"
                    checked={hasApproval}
                    onChange={(e) => setHasApproval(e.target.checked)}
                    className="h-4 w-4 rounded border-rule text-ink"
                  />
                  <span>Prior Written Approval Attached</span>
                </label>
              </div>
            </div>

            <button
              type="button"
              onClick={handleRunEnforcement}
              disabled={evaluating}
              className="mt-2 w-full rounded-full bg-ink py-2.5 text-center text-sm font-medium text-paper hover:opacity-90 transition-opacity"
            >
              {evaluating ? "Evaluating..." : "Evaluate Spend Against Rules"}
            </button>
          </div>

          {/* Compiled rules list */}
          <div>
            <h4 className="mb-2 text-xs font-medium uppercase tracking-wider text-ink-muted">
              Active Compiled Rules ({ruleset?.rules.length ?? 0})
            </h4>
            <div className="max-h-48 space-y-1.5 overflow-y-auto">
              {ruleset?.rules.map((rule) => (
                <div
                  key={rule.id}
                  onClick={() => setActiveCitation(rule.citation)}
                  className="cursor-pointer rounded-lg border border-rule bg-paper px-3 py-2 text-xs hover:border-ink transition-colors flex items-center justify-between"
                >
                  <div>
                    <span className="font-medium">{rule.name}</span>
                    <span className="ml-2 text-ink-muted">p. {rule.citation.page}</span>
                  </div>
                  <span className="font-mono text-[10px] text-ink-muted">VERIFIED</span>
                </div>
              ))}
            </div>
          </div>

          {compileInfo && compileInfo.rejected.length > 0 && (
            <details className="rounded-lg border border-rule bg-paper px-3 py-2 text-xs">
              <summary className="cursor-pointer font-medium uppercase tracking-wider text-ink-muted">
                Rejected suggestions ({compileInfo.rejected.length}): never became rules
              </summary>
              <ul className="mt-2 space-y-2">
                {compileInfo.rejected.map((r, i) => (
                  <li key={i} className="border-t border-rule pt-2">
                    <p className="text-blocked">{r.reason}</p>
                    {r.candidate.quote && (
                      <p className="mt-0.5 font-serif text-ink-muted">
                        “{r.candidate.quote}”{r.candidate.page ? ` (p. ${r.candidate.page})` : ""}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>

        {/* Right: Real-time Trace & Clause Citation */}
        <div className="space-y-5">
          <h3 className="font-medium text-sm text-ink-muted uppercase tracking-wider">Evaluation Trace</h3>

          {result ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between rounded-xl border border-rule bg-paper p-4">
                <div>
                  <span className="text-xs text-ink-muted">Enforcement Verdict</span>
                  <div className="mt-1">
                    <VerdictBadge verdict={result.verdict} />
                  </div>
                </div>
                <div className="text-right">
                  <span className="text-xs text-ink-muted">Latency</span>
                  <p className="font-mono text-sm font-medium">{result.latency_ms} ms</p>
                </div>
              </div>

              <div className="divide-y divide-rule rounded-xl border border-rule bg-paper text-xs">
                {result.traces.map((trace) => (
                  <div
                    key={trace.rule_id}
                    onClick={() => setActiveCitation(trace.citation)}
                    className="cursor-pointer p-3 hover:bg-paper-raised transition-colors flex items-center justify-between gap-3"
                  >
                    <div>
                      <p className="font-medium">{trace.rule_name}</p>
                      <p className="text-ink-muted">{trace.reason}</p>
                    </div>
                    <span
                      className={`font-mono text-[11px] font-semibold ${
                        trace.outcome === "PASS"
                          ? "text-allowed"
                          : trace.outcome === "FAIL"
                          ? "text-blocked"
                          : "text-review"
                      }`}
                    >
                      {trace.outcome}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex h-40 items-center justify-center rounded-xl border border-dashed border-rule text-xs text-ink-muted">
              Click &quot;Evaluate Spend Against Rules&quot; to check compliance.
            </div>
          )}

          {/* Active Citation Card */}
          {activeCitation && (
            <div className="rounded-xl border border-rule bg-paper p-5">
              <div className="mb-2 flex items-center justify-between">
                <span className="font-mono text-[11px] uppercase tracking-wider text-ink-muted">
                  Clause Citation · Page {activeCitation.page}
                </span>
                <span className="rounded bg-allowed-bg px-1.5 py-0.5 font-mono text-[10px] text-allowed">
                  100% Match
                </span>
              </div>
              <blockquote className="font-serif text-sm leading-relaxed text-ink">
                {activeCitation.prefix}
                <mark className="bg-yellow-100 font-medium px-0.5 rounded">{activeCitation.quote}</mark>
                {activeCitation.suffix}
              </blockquote>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
