"use client";

import { useEffect, useState } from "react";
import { Button, Empty, PageHeader, RuleRow, Section } from "@/components/app/ui";
import { api, post, type RuleCard, type RulesetSummary } from "@/lib/api";
import { useAppState } from "@/lib/app-state";

export default function Rulebook() {
  const { state } = useAppState();
  return (
    <>
      <PageHeader title="Rulebook">
        Every rule from every source, each next to the sentence it came from. An expense is checked
        against all approved rules at once and the strictest answer wins. The examples are run
        through the real checker.
      </PageHeader>
      {state && !state.rulesets.length ? (
        <Empty>No rules yet. Add a grant or set up your company policy.</Empty>
      ) : (
        <div className="grid gap-12">
          {state?.rulesets.map((rs) => <RulesetSection key={rs.id} rs={rs} />)}
        </div>
      )}
    </>
  );
}

function RulesetSection({ rs }: { rs: RulesetSummary }) {
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
  const open = rs.open_items ? `, ${rs.open_items} questions still open` : "";

  return (
    <Section
      title={rs.name}
      meta={`${rs.kind === "grant" ? "Grant agreement" : "Company policy"}. ${rs.approved} of ${rs.rules} approved${open}.`}
      aside={
        pending > 0 && (
          <Button variant="primary" onClick={() => approve()}>
            Approve all
          </Button>
        )
      }
    >
      <div className="hidden grid-cols-2 gap-8 border-b border-rule pb-2 text-xs text-ink-muted md:grid">
        <span>What it does</span>
        <span>Where it comes from</span>
      </div>
      <div className="pt-4">
        {cards.map((c) => (
          <RuleRow key={c.rule.id} card={c} sourceName={source} onApprove={() => approve([c.rule.id])} />
        ))}
      </div>
    </Section>
  );
}
