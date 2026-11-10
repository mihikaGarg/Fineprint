"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  BudgetLines,
  Button,
  Card,
  Clause,
  Empty,
  ErrorText,
  Label,
  PageHeader,
  Pill,
  RuleCardView,
  cx,
} from "@/components/app/ui";
import { api, post, type ClauseStatus, type CompileResponse, type RuleCard } from "@/lib/api";
import { useAppState } from "@/lib/app-state";

export default function Grants() {
  const { state, refresh } = useAppState();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const file = useRef<HTMLInputElement>(null);

  async function compile(request: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await request();
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const grants = state?.rulesets.filter((r) => r.kind === "grant") ?? [];

  return (
    <>
      <PageHeader title="Grants">
        Upload a grant agreement. Fineprint reads every clause, proposes rules tied to the exact
        sentence and page, and rejects anything it can&apos;t verify against the PDF.
      </PageHeader>

      <div className="mb-8 flex flex-wrap items-center gap-3">
        <Button variant="primary" disabled={busy} onClick={() => compile(() => post("/api/compile/demo"))}>
          Load demo grant (5 pages)
        </Button>
        <Button disabled={busy} onClick={() => file.current?.click()}>
          Upload grant PDF
        </Button>
        <input
          ref={file}
          type="file"
          accept=".pdf"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0];
            e.target.value = "";
            if (!f) return;
            const fd = new FormData();
            fd.append("file", f);
            void compile(() => api("/api/compile", { method: "POST", body: fd }));
          }}
        />
        {busy && (
          <span className="text-sm text-ink-muted">
            Reading pages, finding rules, verifying every quote against the PDF…
          </span>
        )}
        {error && <ErrorText>{error}</ErrorText>}
      </div>

      {grants.length ? (
        <div className="grid gap-6">
          {grants.map((g) => (
            <GrantCard key={g.id} id={g.id} />
          ))}
        </div>
      ) : (
        <Empty>No grants yet. Load the demo grant to see how it works.</Empty>
      )}
    </>
  );
}

const STATUS: Record<ClauseStatus, { text: string; tone: "allowed" | "review" | "blocked" | "neutral" }> = {
  rule: { text: "Rule", tone: "allowed" },
  flagged: { text: "Flagged", tone: "review" },
  rejected: { text: "Rejected", tone: "blocked" },
  no_rule: { text: "No rule", tone: "neutral" },
};

function GrantCard({ id }: { id: string }) {
  const { state, refresh } = useAppState();
  const [grant, setGrant] = useState<CompileResponse | null>(null);
  const [cards, setCards] = useState<RuleCard[]>([]);

  const load = useCallback(async () => {
    const [g, c] = await Promise.all([
      api<CompileResponse>(`/api/grants/${id}`),
      api<RuleCard[]>(`/api/rulesets/${id}/cards`),
    ]);
    setGrant(g);
    setCards(c);
  }, [id]);

  useEffect(() => {
    void load();
  }, [load, state]);

  if (!grant) return <Card>Loading…</Card>;
  const c = grant.coverage;
  const proposed = cards.filter((x) => x.rule.status !== "approved").length;
  const budget = state?.budgets.find((b) => b.grant_id === id);
  const approve = async (ruleIds: string[] = []) => {
    await post(`/api/rulesets/${id}/approve`, { rule_ids: ruleIds });
    await refresh();
  };
  const width = (n: number) => `${(n / Math.max(1, c.total)) * 100}%`;

  return (
    <Card
      title={grant.ruleset.grant_name}
      aside={
        proposed ? (
          <Button variant="primary" onClick={() => approve()}>
            Approve all {proposed}
          </Button>
        ) : (
          <Pill tone="allowed">All approved</Pill>
        )
      }
    >
      <p className="-mt-2 mb-6 text-sm text-ink-muted">
        Read by {grant.proposer} · {cards.length} rules · {proposed} awaiting approval
      </p>

      <Label>Coverage: read all {c.total} clauses</Label>
      <div className="flex h-2 overflow-hidden rounded-full bg-paper">
        <div className="bg-allowed" style={{ width: width(c.rules) }} />
        <div className="bg-review" style={{ width: width(c.flagged) }} />
        <div className="bg-blocked" style={{ width: width(c.rejected) }} />
      </div>
      <p className="mt-2 text-sm text-ink-muted">
        <span className="text-allowed">{c.rules} became rules</span> · {c.flagged} flagged as ambiguous ·{" "}
        <span className="text-blocked">{c.rejected} rejected</span> · {c.no_rule} with no spending rule
      </p>

      <Label>Rules</Label>
      {cards.map((card) => (
        <RuleCardView
          key={card.rule.id}
          card={card}
          sourceName="Grant agreement"
          onApprove={() => approve([card.rule.id])}
        />
      ))}

      <Label>Approved budget</Label>
      <BudgetLines budget={budget ?? { grant_id: id, name: "", lines: [], missing: [] }} onChange={refresh} />

      <div className="mt-6 space-y-2">
        {grant.rejected.length > 0 && (
          <Disclosure summary={`Rejected suggestions (${grant.rejected.length}): never became rules`}>
            {grant.rejected.map((x) => (
              <div key={x.candidate.quote} className="border-t border-rule py-3 first:border-t-0">
                <ErrorText>{x.reason}</ErrorText>
                <Clause quote={x.candidate.quote} source={`p. ${x.candidate.page}`} />
              </div>
            ))}
          </Disclosure>
        )}
        <Disclosure summary={`Every clause (${c.total})`}>
          {c.clauses.map((cl, i) => (
            <div key={i} className="flex gap-3 border-t border-rule py-2.5 text-sm first:border-t-0">
              <span className="w-20 shrink-0">
                <Pill tone={STATUS[cl.status].tone}>{STATUS[cl.status].text}</Pill>
              </span>
              <div className="min-w-0">
                <span className="font-mono text-xs text-ink-muted">p. {cl.page} </span>
                <span className="font-serif italic">{cl.text}</span>
                {cl.detail && <p className="text-xs text-ink-muted">{cl.detail}</p>}
              </div>
            </div>
          ))}
        </Disclosure>
      </div>
    </Card>
  );
}

function Disclosure({ summary, children }: { summary: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-xl border border-rule">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-3 text-left text-sm text-ink-muted hover:text-ink"
      >
        {summary}
        <span className={cx("transition-transform", open && "rotate-90")}>›</span>
      </button>
      {open && <div className="px-4 pb-3">{children}</div>}
    </div>
  );
}
