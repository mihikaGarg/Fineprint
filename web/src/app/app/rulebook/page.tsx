"use client";

import { useEffect, useState } from "react";
import { Button, Card, Empty, PageHeader, Pill, RuleCardView } from "@/components/app/ui";
import { api, post, type RuleCard, type RulesetSummary } from "@/lib/api";
import { useAppState } from "@/lib/app-state";

export default function Rulebook() {
  const { state } = useAppState();
  return (
    <>
      <PageHeader title="Rulebook">
        Every rule from every source. Expenses are checked against all approved rules at once, and
        the strictest answer wins. The examples come from the real checker.
      </PageHeader>
      {state && !state.rulesets.length ? (
        <Empty>No rules yet. Add a grant or set up your company policy.</Empty>
      ) : (
        <div className="grid gap-6">
          {state?.rulesets.map((rs) => <RulesetCard key={rs.id} rs={rs} />)}
        </div>
      )}
    </>
  );
}

function RulesetCard({ rs }: { rs: RulesetSummary }) {
  const { state, refresh } = useAppState();
  const [cards, setCards] = useState<RuleCard[]>([]);

  useEffect(() => {
    api<RuleCard[]>(`/api/rulesets/${rs.id}/cards`).then(setCards).catch(() => setCards([]));
  }, [rs.id, state]);

  const approve = async (ruleIds: string[] = []) => {
    await post(`/api/rulesets/${rs.id}/approve`, { rule_ids: ruleIds });
    await refresh();
  };
  const pending = rs.rules - rs.approved;
  const source = rs.kind === "grant" ? "Grant agreement" : rs.name;

  return (
    <Card
      title={rs.name}
      aside={
        pending ? (
          <Button variant="primary" onClick={() => approve()}>
            Approve all
          </Button>
        ) : (
          <Pill tone="allowed">All approved</Pill>
        )
      }
    >
      <p className="-mt-2 mb-5 text-sm text-ink-muted">
        {rs.kind === "grant" ? "Grant agreement" : "Company policy"} · {rs.approved}/{rs.rules} approved
        {rs.open_items > 0 && <span className="text-review"> · {rs.open_items} open questions</span>}
      </p>
      {cards.map((c) => (
        <RuleCardView key={c.rule.id} card={c} sourceName={source} onApprove={() => approve([c.rule.id])} />
      ))}
    </Card>
  );
}
