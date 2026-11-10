"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  BudgetLines,
  Button,
  Clause,
  Empty,
  ErrorText,
  Mark,
  PageHeader,
  RuleRow,
  Section,
  Subhead,
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
        Fineprint reads the agreement clause by clause. A clause becomes a rule only if its quote
        matches the PDF character for character; anything else is listed as rejected.
      </PageHeader>

      <div className="mb-10 flex flex-wrap items-center gap-3">
        <Button variant="primary" disabled={busy} onClick={() => compile(() => post("/api/compile/demo"))}>
          Load the demo grant
        </Button>
        <Button disabled={busy} onClick={() => file.current?.click()}>
          Upload a grant PDF
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
        {busy && <span className="text-sm text-ink-muted">Reading pages and checking every quote…</span>}
        {error && <ErrorText>{error}</ErrorText>}
      </div>

      {grants.length ? (
        <div className="grid gap-12">
          {grants.map((g) => (
            <GrantSection key={g.id} id={g.id} />
          ))}
        </div>
      ) : (
        <Empty>No grants yet. The demo grant is a five-page award agreement with a budget exhibit.</Empty>
      )}
    </>
  );
}

const STATUS: Record<ClauseStatus, { text: string; tone: "allowed" | "review" | "blocked" | "muted" }> = {
  rule: { text: "Rule", tone: "allowed" },
  flagged: { text: "Unclear", tone: "review" },
  rejected: { text: "Rejected", tone: "blocked" },
  no_rule: { text: "No rule", tone: "muted" },
};

function GrantSection({ id }: { id: string }) {
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

  if (!grant) return <p className="text-sm text-ink-muted">Loading…</p>;
  const c = grant.coverage;
  const proposed = cards.filter((x) => x.rule.status !== "approved").length;
  const budget = state?.budgets.find((b) => b.grant_id === id);
  const approve = async (ruleIds: string[] = []) => {
    await post(`/api/rulesets/${id}/approve`, { rule_ids: ruleIds });
    await refresh();
  };
  const width = (n: number) => `${(n / Math.max(1, c.total)) * 100}%`;

  return (
    <Section
      title={grant.ruleset.grant_name}
      meta={`${cards.length} rules, ${proposed ? `${proposed} not yet approved` : "all approved"}. Read by the ${grant.proposer} reader.`}
      aside={
        proposed > 0 && (
          <Button variant="primary" onClick={() => approve()}>
            Approve all {proposed}
          </Button>
        )
      }
    >
      <Subhead>Every clause read ({c.total})</Subhead>
      <div className="flex h-1.5 bg-rule">
        <div className="bg-allowed" style={{ width: width(c.rules) }} />
        <div className="bg-review" style={{ width: width(c.flagged) }} />
        <div className="bg-blocked" style={{ width: width(c.rejected) }} />
      </div>
      <p className="mt-2 text-sm text-ink-muted">
        {c.rules} became rules, {c.flagged} unclear, {c.rejected} rejected, {c.no_rule} with nothing to enforce.
      </p>

      <Subhead>Rules</Subhead>
      <div className="border-t border-rule pt-4">
        {cards.map((card) => (
          <RuleRow key={card.rule.id} card={card} sourceName="Grant agreement" onApprove={() => approve([card.rule.id])} />
        ))}
      </div>

      <Subhead>Approved budget</Subhead>
      <div className="max-w-xl border-t border-rule pt-3">
        <BudgetLines budget={budget ?? { grant_id: id, name: "", lines: [], missing: [] }} onChange={refresh} />
      </div>

      <div className="mt-8 border-t border-rule">
        {grant.rejected.length > 0 && (
          <Fold summary={`Rejected suggestions (${grant.rejected.length})`}>
            {grant.rejected.map((x) => (
              <div key={x.candidate.quote} className="border-b border-rule py-3 last:border-b-0">
                <p className="mb-1.5 text-sm text-blocked">{x.reason}</p>
                <Clause quote={x.candidate.quote} source={`Grant agreement, p. ${x.candidate.page}`} />
              </div>
            ))}
          </Fold>
        )}
        <Fold summary={`All ${c.total} clauses`}>
          {c.clauses.map((cl, i) => (
            <div key={i} className="grid grid-cols-[6.5rem_3rem_minmax(0,1fr)] gap-2 border-b border-rule py-2 text-sm last:border-b-0">
              <Mark tone={STATUS[cl.status].tone}>{STATUS[cl.status].text}</Mark>
              <span className="font-mono text-xs leading-5 text-ink-muted">p. {cl.page}</span>
              <div className="min-w-0">
                <span className="font-serif italic">{cl.text}</span>
                {cl.detail && <p className="text-xs text-ink-muted">{cl.detail}</p>}
              </div>
            </div>
          ))}
        </Fold>
      </div>
    </Section>
  );
}

function Fold({ summary, children }: { summary: string; children: React.ReactNode }) {
  return (
    <details className="group border-b border-rule">
      <summary className="flex cursor-pointer list-none items-center gap-2 py-2.5 text-sm text-ink-muted hover:text-ink">
        <span className="inline-block w-3 transition-transform group-open:rotate-90">›</span>
        {summary}
      </summary>
      <div className="pb-3 pl-5">{children}</div>
    </details>
  );
}
