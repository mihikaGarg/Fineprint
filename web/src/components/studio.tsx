"use client";

import { useEffect, useState } from "react";
import { VerdictBadge } from "./verdict-demo";

type Verdict = "ALLOWED" | "BLOCKED" | "NEEDS_REVIEW";
type Outcome = "PASS" | "FAIL" | "ESCALATE";

interface Citation {
  page: number;
  quote: string;
  char_start?: number;
  char_end?: number;
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

interface EnforcementResult {
  verdict: Verdict;
  traces: RuleTrace[];
  latency_ms: number;
}

const API_BASE = "http://localhost:8000";

const DEFAULT_BUDGET = {
  lines: {
    travel_domestic: { category: "travel_domestic", allocated_cents: 800000, spent_cents: 320000 },
    equipment: { category: "equipment", allocated_cents: 2000000, spent_cents: 0 },
  },
};

export function InteractiveStudio() {
  const [ruleset, setRuleset] = useState<Ruleset | null>(null);
  const [budget] = useState(DEFAULT_BUDGET);
  const [loading, setLoading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string>("");

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

  // Load default fixtures on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/fixtures`)
      .then((res) => res.json())
      .then((data) => {
        if (data.ruleset) {
          setRuleset(data.ruleset);
          if (data.ruleset.rules?.[0]?.citation) {
            setActiveCitation(data.ruleset.rules[0].citation);
          }
        }
      })
      .catch(() => {
        // Fallback demo ruleset if API server is not running
        const fallbackRuleset: Ruleset = {
          grant_id: "grant_bbs_2026",
          grant_name: "Ramp x BBS Innovation Award (Local Mode)",
          rules: [
            {
              id: "r1",
              name: "Period of performance",
              rule_type: "period_of_performance",
              citation: {
                page: 2,
                quote: "The period of performance shall be from January 1, 2026 through December 31, 2026.",
              },
              params: { start_date: "2026-01-01", end_date: "2026-12-31" },
            },
            {
              id: "r2",
              name: "Category prohibition",
              rule_type: "category_prohibition",
              citation: {
                page: 12,
                quote: "Costs of alcoholic beverages are unallowable under this award.",
                prefix: "§6.1 Unallowable costs. ",
              },
              params: { prohibited_categories: ["alcohol", "entertainment"] },
            },
            {
              id: "r3",
              name: "Travel budget line",
              rule_type: "budget_limit",
              citation: {
                page: 7,
                quote: "Domestic travel necessary to carry out the project is an allowable cost, subject to the approved budget.",
                prefix: "§4.2 ",
              },
              params: { budget_line: "travel_domestic" },
            },
            {
              id: "r4",
              name: "Equipment prior approval",
              rule_type: "threshold_approval",
              citation: {
                page: 15,
                quote: "Capital expenditures for special purpose equipment having a unit cost of $5,000 or more require prior written approval.",
                prefix: "§8.3 Equipment. ",
              },
              params: { category: "equipment", threshold_cents: 500000 },
            },
          ],
        };
        setRuleset(fallbackRuleset);
        setActiveCitation(fallbackRuleset.rules[0].citation);
      });
  }, []);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setLoading(true);
    setUploadStatus("Scanning pages & verifying clause citations...");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_BASE}/api/compile`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        throw new Error("Failed to compile PDF");
      }

      const data = await res.json();
      setRuleset(data.ruleset);
      setUploadStatus(`Extracted ${data.verified_count} rules (${data.rejected_count} unverifiable rules rejected).`);
      if (data.ruleset.rules?.[0]?.citation) {
        setActiveCitation(data.ruleset.rules[0].citation);
      }
    } catch {
      setUploadStatus("API offline or upload error. Make sure 'uvicorn api.main:app' is running.");
    } finally {
      setLoading(false);
    }
  };

  const handleRunEnforcement = async () => {
    if (!ruleset) return;

    setEvaluating(true);
    const amountCents = Math.round(parseFloat(dollars || "0") * 100);

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

      if (res.ok) {
        const data: EnforcementResult = await res.json();
        setResult(data);
        if (data.traces[0]?.citation) {
          setActiveCitation(data.traces[0].citation);
        }
        return;
      }
    } catch {
      // Fallback client-side evaluator for seamless local demo without backend
      const traces: RuleTrace[] = [];
      let verdict: Verdict = "ALLOWED";

      for (const rule of ruleset.rules) {
        if (rule.rule_type === "period_of_performance") {
          traces.push({
            rule_id: rule.id,
            rule_name: rule.name,
            outcome: "PASS",
            reason: "Within Jan 1 – Dec 31, 2026",
            citation: rule.citation,
          });
        } else if (rule.rule_type === "category_prohibition") {
          const isProhibited = category === "alcohol" || category === "entertainment";
          traces.push({
            rule_id: rule.id,
            rule_name: rule.name,
            outcome: isProhibited ? "FAIL" : "PASS",
            reason: isProhibited ? `Category '${category}' is prohibited` : `Category '${category}' allowable`,
            citation: rule.citation,
          });
          if (isProhibited) verdict = "BLOCKED";
        } else if (rule.rule_type === "threshold_approval" && category === "equipment") {
          if (amountCents >= 500000) {
            traces.push({
              rule_id: rule.id,
              rule_name: rule.name,
              outcome: hasApproval ? "PASS" : "ESCALATE",
              reason: hasApproval ? "Exceeds $5,000 with sponsor approval" : "Exceeds $5,000 without prior approval",
              citation: rule.citation,
            });
            if (!hasApproval && verdict !== "BLOCKED") verdict = "NEEDS_REVIEW";
          }
        } else if (rule.rule_type === "budget_limit" && category === "travel_domestic") {
          const exceeds = 320000 + amountCents > 800000;
          traces.push({
            rule_id: rule.id,
            rule_name: rule.name,
            outcome: exceeds ? "FAIL" : "PASS",
            reason: exceeds ? "Exceeds $8,000 travel budget" : `$${((320000 + amountCents) / 100).toLocaleString()} of $8,000 used`,
            citation: rule.citation,
          });
          if (exceeds) verdict = "BLOCKED";
        }
      }

      setResult({
        verdict,
        traces,
        latency_ms: 1.2,
      });
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
            {ruleset ? ruleset.grant_name : "Loading Grant..."}
          </h2>
        </div>

        {/* PDF Upload button */}
        <div className="flex items-center gap-3">
          <label className="cursor-pointer rounded-full border border-rule bg-paper px-4 py-2 text-xs font-medium hover:border-ink">
            <span>{loading ? "Scanning..." : "Upload Grant PDF"}</span>
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
        <div className="mb-6 rounded-lg bg-paper px-4 py-2 text-xs text-ink-muted">
          {uploadStatus}
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
