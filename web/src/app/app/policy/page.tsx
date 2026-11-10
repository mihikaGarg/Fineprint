"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button, Card, Clause, PageHeader, Pill, cx } from "@/components/app/ui";
import { api, post, type ChatOption, type PolicySession, type RuleCard } from "@/lib/api";
import { useAppState } from "@/lib/app-state";

interface Bubble {
  role: "assistant" | "user";
  text: string;
}

export default function Policy() {
  const { state, refresh } = useAppState();
  const [session, setSession] = useState<PolicySession | null>(null);
  const [pending, setPending] = useState<Bubble[]>([]);
  const [typing, setTyping] = useState(false);
  const [typedStart, setTypedStart] = useState(false);
  const [text, setText] = useState("");
  const [cards, setCards] = useState<RuleCard[]>([]);
  const [loaded, setLoaded] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  const log = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);

  const grants = state?.rulesets.filter((r) => r.kind === "grant") ?? [];
  const policyId = state?.rulesets.find((r) => r.kind === "policy")?.id;

  // Pick up an existing setup chat when the page opens.
  useEffect(() => {
    if (!state || loaded) return;
    setLoaded(true);
    if (policyId) api<PolicySession>(`/api/chat/${policyId}`).then(setSession).catch(() => {});
  }, [state, loaded, policyId]);

  const loadCards = useCallback(async (id: string) => {
    setCards(await api<RuleCard[]>(`/api/rulesets/${id}/cards`).catch(() => []));
  }, []);

  useEffect(() => {
    if (session) void loadCards(session.session_id);
  }, [session, loadCards]);

  useEffect(() => {
    log.current?.scrollTo({ top: log.current.scrollHeight, behavior: "smooth" });
  }, [session, pending, typing]);

  async function run(shown: string, request: () => Promise<PolicySession>) {
    if (typing) return;
    setPending([{ role: "user", text: shown }]);
    setTyping(true);
    try {
      const [next] = await Promise.all([request(), new Promise((r) => setTimeout(r, 350))]);
      setSession(next);
      setPending([]);
      void refresh();
    } catch (e) {
      setPending([
        { role: "user", text: shown },
        { role: "assistant", text: `Sorry, that didn't work: ${(e as Error).message}` },
      ]);
    } finally {
      setTyping(false);
    }
  }

  function start(fd: FormData, shown: string) {
    fd.append("grant_ids", grants.map((g) => g.id).join(","));
    void run(shown, () => api<PolicySession>("/api/chat/start", { method: "POST", body: fd }));
  }

  const last = session?.messages.at(-1);
  const openGap =
    last && last.role === "assistant" && last.gap_id && !session?.gaps.find((g) => g.id === last.gap_id)?.resolved
      ? last
      : null;

  function choose(option: ChatOption) {
    if (!session || !openGap) return;
    void run(option.label, () =>
      post<PolicySession>(`/api/chat/${session.session_id}/reply`, { gap_id: openGap.gap_id, value: option.value }),
    );
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const value = text.trim();
    if (!value) return;
    setText("");
    if (!session) {
      if (!typedStart) return;
      const fd = new FormData();
      fd.append("text", value);
      start(fd, value);
      return;
    }
    void run(value, () =>
      post<PolicySession>(`/api/chat/${session.session_id}/reply`, {
        gap_id: openGap?.gap_id ?? null,
        text: value,
      }),
    );
  }

  async function undo() {
    if (!session || typing) return;
    try {
      setSession(await post<PolicySession>(`/api/chat/${session.session_id}/undo`));
      void refresh();
    } catch {
      setPending([{ role: "assistant", text: "There's nothing to undo yet." }]);
    }
  }

  const welcome: Bubble = {
    role: "assistant",
    text:
      "Hi! Let's set up your company's expense rules.\n\nUpload your expense policy (PDF or text) and I'll read it into rules, each linked to the page it came from. Then we'll go through anything vague, missing or with exceptions, one question at a time." +
      (grants.length
        ? `\n\nI'll also check it against your grant: ${grants.map((g) => g.name).join(", ")}.`
        : "\n\nTip: add a grant first and I'll flag where it's stricter than your policy."),
  };
  const bubbles: Bubble[] = [...(session ? session.messages : [welcome]), ...pending];
  const canType = !typing && (!!session || typedStart);

  return (
    <>
      <PageHeader title="Company policy">
        Upload your existing expense policy. The assistant reads it into rules, then walks you
        through anything vague, missing or with exceptions.
      </PageHeader>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <section className="flex h-[min(72vh,760px)] min-h-[480px] flex-col overflow-hidden rounded-2xl border border-rule bg-paper-raised">
          <div ref={log} className="flex-1 space-y-3 overflow-y-auto p-4 sm:p-6">
            {bubbles.map((b, i) => (
              <div
                key={i}
                className={cx(
                  "max-w-[85%] whitespace-pre-line rounded-2xl px-4 py-3 text-[15px] leading-relaxed",
                  b.role === "user"
                    ? "ml-auto rounded-br-md bg-ink text-paper"
                    : "rounded-bl-md border border-rule bg-paper",
                )}
              >
                {b.text}
              </div>
            ))}
            {typing && (
              <div className="w-fit rounded-2xl rounded-bl-md border border-rule bg-paper px-4 py-3">
                <span className="inline-flex gap-1">
                  {[0, 1, 2].map((d) => (
                    <span
                      key={d}
                      className="size-1.5 animate-bounce rounded-full bg-ink-muted"
                      style={{ animationDelay: `${d * 120}ms` }}
                    />
                  ))}
                </span>
              </div>
            )}
            {!typing && !pending.length && !session && (
              <div className="flex flex-wrap gap-2 pt-1">
                <Button variant="primary" onClick={() => file.current?.click()}>
                  Upload policy
                </Button>
                <Button
                  onClick={() => {
                    const fd = new FormData();
                    fd.append("sample", "northwind");
                    fd.append("name", "Northwind University FIN-204");
                    start(fd, "Use the sample: Northwind University travel & expense policy (5 pages)");
                  }}
                >
                  Use a sample policy
                </Button>
                <Button
                  onClick={() => {
                    setTypedStart(true);
                    setTimeout(() => input.current?.focus(), 0);
                  }}
                >
                  Type rules instead
                </Button>
              </div>
            )}
            {!typing && !pending.length && openGap && openGap.options.length > 0 && (
              <div className="flex flex-col items-start gap-2 pt-1">
                {openGap.options.map((o) => (
                  <button
                    key={o.value}
                    type="button"
                    onClick={() => choose(o)}
                    className={cx(
                      "max-w-full rounded-xl border px-4 py-2 text-left text-sm transition-colors",
                      o.suggested || o.value === "approve"
                        ? "border-ink bg-ink text-paper hover:bg-ink/85"
                        : "border-rule bg-paper-raised hover:border-ink",
                    )}
                  >
                    {o.suggested && (
                      <span className="mr-2 font-mono text-[10px] uppercase tracking-wider opacity-70">
                        Suggested
                      </span>
                    )}
                    {o.label}
                  </button>
                ))}
              </div>
            )}
          </div>
          <form onSubmit={submit} className="flex items-center gap-2 border-t border-rule p-3">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={!session?.messages.some((m) => m.role === "user") || typing}
              onClick={undo}
            >
              Undo
            </Button>
            <input
              ref={input}
              value={text}
              onChange={(e) => setText(e.target.value)}
              disabled={!canType}
              placeholder={
                !session
                  ? typedStart
                    ? "Type your rules, e.g. No alcohol. Meals up to $75."
                    : "Pick an option above to start"
                  : openGap
                    ? (openGap.free_text_hint ?? "Type a reply…")
                    : "Type a new rule…"
              }
              className="min-w-0 flex-1 rounded-lg border border-rule bg-paper px-3 py-2 text-sm placeholder:text-ink-muted/70 focus:border-ink focus:outline-none disabled:opacity-60"
            />
            <Button type="submit" variant="primary" size="sm" disabled={!canType || !text.trim()}>
              Send
            </Button>
          </form>
          <input
            ref={file}
            type="file"
            accept=".pdf,.txt,.md"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              e.target.value = "";
              if (!f) return;
              const fd = new FormData();
              fd.append("file", f);
              fd.append("name", f.name.replace(/\.[^.]+$/, ""));
              start(fd, `📎 ${f.name}`);
            }}
          />
        </section>

        <Card title="Policy rules" className="xl:max-h-[min(72vh,760px)] xl:overflow-y-auto">
          {session ? (
            <>
              <p className="-mt-2 mb-4 text-sm text-ink-muted">
                {cards.length} rules · read by {session.drafter}
                {session.grant_ids.length > 0 && ` · checked against ${session.grant_ids.length} grant`}
              </p>
              <ul className="space-y-4">
                {cards.map(({ rule: r, description }) => (
                  <li key={r.id} className="border-t border-rule pt-4 first:border-t-0 first:pt-0">
                    <div className="flex items-start gap-2">
                      <Pill tone={r.status === "approved" ? "allowed" : "neutral"}>
                        {r.status === "approved" ? "Approved" : "Proposed"}
                      </Pill>
                      <p className="text-sm font-medium">{description}</p>
                    </div>
                    <Clause
                      quote={r.citation.quote}
                      source={r.citation.page === session.chat_page ? "From this chat" : `${session.source} · p. ${r.citation.page}`}
                    />
                    {(r.params.clarifications ?? []).map((c, i) => (
                      <p key={i} className="mt-1 text-xs text-ink-muted">
                        ↳ {c.answer}
                      </p>
                    ))}
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="text-sm text-ink-muted">Rules will appear here as the assistant reads your policy.</p>
          )}
        </Card>
      </div>
    </>
  );
}
