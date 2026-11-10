// Types and helpers for the Fineprint API (served at /api, proxied by next.config.ts).

export type Verdict = "ALLOWED" | "BLOCKED" | "NEEDS_REVIEW";
export type Outcome = "PASS" | "FAIL" | "ESCALATE";

export interface Citation {
  page: number;
  quote: string;
  char_start: number;
  char_end: number;
}

export interface SpendRule {
  id: string;
  name: string;
  rule_type: string;
  citation: Citation;
  params: Record<string, unknown> & { clarifications?: { question: string; answer: string }[] };
  source: "grant" | "policy";
  status: "proposed" | "approved";
}

export interface Ruleset {
  grant_id: string;
  grant_name: string;
  rules: SpendRule[];
}

export interface Expense {
  id: string;
  amount_cents: number;
  date: string;
  merchant: string;
  category: string;
  memo?: string;
  has_receipt?: boolean;
  has_prior_approval?: boolean;
  approvals: string[];
}

export interface RuleTrace {
  rule_id: string;
  rule_name: string;
  outcome: Outcome;
  reason: string;
  citation: Citation;
  source: "grant" | "policy";
  fix: string | null;
}

export interface EnforcementResult {
  verdict: Verdict;
  traces: RuleTrace[];
  latency_ms: number;
}

export interface LoggedExpense {
  expense: Expense;
  result: EnforcementResult;
  ruleset_ids: string[];
  recorded_spend: boolean;
  spent_on: string | null;
}

export interface RuleExample {
  description: string;
  verdict: Verdict;
  reason: string;
  fix: string | null;
}

export interface RuleCard {
  rule: SpendRule;
  description: string;
  examples: RuleExample[];
  open_questions: { id: string; question: string }[];
  can_approve: boolean;
}

export interface RulesetSummary {
  id: string;
  name: string;
  kind: "grant" | "policy";
  rules: number;
  approved: number;
  open_items: number;
}

export interface BudgetLineView {
  line: string;
  label: string;
  allocated_cents: number;
  spent_cents: number;
  remaining_cents: number;
  source: string;
}

export interface GrantBudget {
  grant_id: string;
  name: string;
  lines: BudgetLineView[];
  missing: string[];
}

export interface AppState {
  rulesets: RulesetSummary[];
  budgets: GrantBudget[];
  expenses_checked: number;
  verdicts: Record<Verdict, number>;
  llm_enabled: boolean;
}

export type ClauseStatus = "rule" | "flagged" | "rejected" | "no_rule";

export interface Coverage {
  total: number;
  rules: number;
  flagged: number;
  rejected: number;
  no_rule: number;
  clauses: { page: number; text: string; status: ClauseStatus; detail: string }[];
}

export interface CompileResponse {
  ruleset: Ruleset;
  rejected: { reason: string; candidate: { quote: string; page: number } }[];
  coverage: Coverage;
  proposer: string;
}

export interface ChatOption {
  label: string;
  value: string;
  suggested?: boolean;
}

export interface ChatMessage {
  role: "assistant" | "user";
  text: string;
  gap_id: string | null;
  options: ChatOption[];
  free_text_hint: string | null;
}

export interface PolicySession {
  session_id: string;
  name: string;
  source: string;
  drafter: string;
  chat_page: number;
  ruleset: Ruleset;
  gaps: { id: string; resolved: boolean }[];
  messages: ChatMessage[];
  grant_ids: string[];
  approved: boolean;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { cache: "no-store", ...init });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = (data as { detail?: unknown }).detail;
    throw new Error(typeof detail === "string" ? detail : `Request failed (${res.status})`);
  }
  return data as T;
}

export function post<T>(path: string, body?: unknown): Promise<T> {
  return api<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
}

/** Integer cents to "$1,234" or "$1,234.50". No float math. */
export function money(cents: number): string {
  const dollars = Math.trunc(cents / 100).toLocaleString("en-US");
  const rest = String(Math.abs(cents % 100)).padStart(2, "0");
  return rest === "00" ? `$${dollars}` : `$${dollars}.${rest}`;
}

/** "1,234.5" or "$80" to integer cents, or null if it isn't an amount. */
export function toCents(value: string): number | null {
  const m = /^\s*\$?(\d{1,9})(?:\.(\d{1,2}))?\s*$/.exec(value.replace(/,/g, ""));
  return m ? Number(m[1]) * 100 + Number((m[2] ?? "").padEnd(2, "0")) : null;
}

const LABELS: Record<string, string> = {
  travel_domestic: "domestic travel",
  travel_foreign: "foreign travel",
  first_class_airfare: "first-class airfare",
  ground_transport: "taxi / rideshare",
};

export const label = (category: string) => LABELS[category] ?? category.replace(/_/g, " ");
export const roleLabel = (role: string) =>
  role.length <= 3 ? role.toUpperCase() : role.replace(/_/g, " ");
export const verdictText = (v: Verdict) =>
  ({ ALLOWED: "Allowed", NEEDS_REVIEW: "Needs review", BLOCKED: "Blocked" })[v];
