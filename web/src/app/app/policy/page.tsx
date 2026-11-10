"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button, Clause, PageHeader, Section, cx } from "@/components/app/ui";
import { api, post, type ChatOption, type PolicySession, type RuleCard } from "@/lib/api";
import { useAppState } from "@/lib/app-state";

interface Line {
  role: "assistant" | "user";
  text: string;
}

// "(4 of 13) ..." moves out of the message and into the progress line.
const PROGRESS = /^\((\d+) of (\d+)\) /;
const LETTERS = "ABCDEFGH";

export default function Policy() {
  const { state, refresh } = useAppState();
  const [session, setSession] = useState<PolicySession | null>(null);
  const [pending, setPending] = useState<Line[]>([]);
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

  // Keep the newest message and its choices in view.
  useEffect(() => {
    const el = log.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [session, pending, typing]);

  async function run(shown: string, request: () => Promise<PolicySession>) {
    if (typing) return;
    setPending([{ role: "user", text: shown }]);
    setTyping(true);
    try {
      const [next] = await Promise.all([request(), new Promise((r) => setTimeout(r, 300))]);
      setSession(next);
      setPending([]);
      void refresh();
    } catch (e) {
      setPending([
        { role: "user", text: shown },
        { role: "assistant", text: `That didn't work: ${(e as Error).message}` },
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
      post<PolicySession>(`/api/chat/${session.session_id}/reply`, { gap_id: openGap?.gap_id ?? null, text: value }),
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

  const welcome: Line = {
    role: "assistant",
    text:
      "Send me your expense policy as a PDF or text file. I'll turn each spending rule into a rule you can check, quoted with its page, then ask you about anything vague, missing or with an exception, one question at a time." +
      (grants.length
        ? `\n\nI'll also compare it with ${grants.map((g) => g.name).join(", ")}.`
        : "\n\nIf you add a grant first, I'll point out where the grant is stricter than your policy."),
  };
  const lines: Line[] = [...(session ? session.messages : [welcome]), ...pending].map((b) => ({
    ...b,
    text: b.text.replace(PROGRESS, ""),
  }));
  const progress = [...(session?.messages ?? [])].reverse().map((m) => PROGRESS.exec(m.text)).find(Boolean);
  const step = progress ? Number(progress[1]) : 0;
  const steps = progress ? Number(progress[2]) : 0;
  const onFinal = openGap?.gap_id === "final";
  const status = !session
    ? "Not started"
    : session.approved
      ? "Rulebook approved"
      : onFinal
        ? "All questions answered. Review and approve."
        : steps
          ? `Question ${step} of ${steps}`
          : "Reading";
  const canType = !typing && (!!session || typedStart);

  return (
    <>
      <PageHeader title="Company policy">
        Most of a policy can be read straight into rules. The rest, like limits with no amount or
        rules with exceptions, needs a decision from you.
      </PageHeader>

      <div className="grid gap-10 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <section className="flex h-[min(74vh,780px)] min-h-[460px] flex-col border-y border-ink">
          <div className="flex items-baseline justify-between gap-4 border-b border-rule py-2.5">
            <h2 className="truncate font-serif text-xl">{session ? session.name : "Setup conversation"}</h2>
            <div className="flex shrink-0 items-center gap-3">
              <span className="text-sm text-ink-muted">{status}</span>
              {steps > 0 && !session?.approved && (
                <span className="hidden h-1 w-24 bg-rule sm:block">
                  <span
                    className="block h-full bg-ink"
                    style={{ width: `${onFinal ? 100 : ((step - 1) / steps) * 100}%` }}
                  />
                </span>
              )}
            </div>
          </div>

          <div ref={log} className="flex-1 overflow-y-auto py-4 pr-2">
            {lines.map((b, i) => (
              <div key={i} className="grid grid-cols-[4.5rem_minmax(0,1fr)] gap-3 py-2">
                <span className={cx("pt-px text-xs", b.role === "user" ? "font-medium text-ink" : "text-ink-muted")}>
                  {b.role === "user" ? "You" : "Fineprint"}
                </span>
                <p
                  className={cx(
                    "max-w-[68ch] whitespace-pre-line text-[15px] leading-relaxed",
                    b.role === "user" && "font-medium",
                  )}
                >
                  {b.text}
                </p>
              </div>
            ))}
            {typing && (
              <div className="grid grid-cols-[4.5rem_minmax(0,1fr)] gap-3 py-2">
                <span className="text-xs text-ink-muted">Fineprint</span>
                <p className="text-sm text-ink-muted">Writing…</p>
              </div>
            )}
            {!typing && !pending.length && !session && (
              <Choices>
                <Choice letter="A" onClick={() => file.current?.click()}>
                  Upload my policy (PDF, .txt or .md)
                </Choice>
                <Choice
                  letter="B"
                  onClick={() => {
                    const fd = new FormData();
                    fd.append("sample", "northwind");
                    fd.append("name", "Northwind University FIN-204");
                    start(fd, "Use the sample: Northwind University travel and expense policy");
                  }}
                >
                  Use the sample: Northwind University travel and expense policy, 5 pages
                </Choice>
                <Choice
                  letter="C"
                  onClick={() => {
                    setTypedStart(true);
                    setTimeout(() => input.current?.focus(), 0);
                  }}
                >
                  Type a few rules instead
                </Choice>
              </Choices>
            )}
            {!typing && !pending.length && openGap && openGap.options.length > 0 && (
              <Choices>
                {openGap.options.map((o, i) => (
                  <Choice key={o.value} letter={LETTERS[i]} suggested={o.suggested} onClick={() => choose(o)}>
                    {o.label}
                  </Choice>
                ))}
              </Choices>
            )}
          </div>

          <form onSubmit={submit} className="flex items-center gap-3 border-t border-rule py-2.5">
            <input
              ref={input}
              value={text}
              onChange={(e) => setText(e.target.value)}
              disabled={!canType}
              placeholder={
                !session
                  ? typedStart
                    ? "For example: No alcohol. Meals up to $75."
                    : "Choose A, B or C to start"
                  : openGap
                    ? `Or type your answer, or a new rule`
                    : "Type a new rule"
              }
              className="min-w-0 flex-1 rounded-[3px] border border-ink/20 bg-paper-raised px-2.5 py-1.5 text-sm placeholder:text-ink-muted/70 focus:border-ink focus:outline-none disabled:opacity-50"
            />
            <Button type="submit" variant="primary" size="sm" disabled={!canType || !text.trim()}>
              Send
            </Button>
            <Button
              type="button"
              variant="quiet"
              size="sm"
              disabled={!session?.messages.some((m) => m.role === "user") || typing}
              onClick={undo}
            >
              Undo last answer
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
              start(fd, `Uploaded ${f.name}`);
            }}
          />
        </section>

        <Section
          title="Rules so far"
          meta={
            session
              ? `${cards.length} rules${session.grant_ids.length ? ", compared with your grant" : ""}`
              : undefined
          }
          className="xl:max-h-[min(74vh,780px)] xl:overflow-y-auto"
        >
          {session ? (
            <ul>
              {cards.map(({ rule: r, description }) => (
                <li key={r.id} className="border-b border-rule py-3 first:pt-0 last:border-b-0">
                  <p className="text-sm font-medium leading-snug">{description}</p>
                  {r.status !== "approved" && <p className="mt-0.5 text-xs text-ink-muted">Not enforced yet</p>}
                  <div className="mt-2">
                    <Clause
                      quote={r.citation.quote}
                      source={r.citation.page === session.chat_page ? "Your answer here" : `${session.name}, p. ${r.citation.page}`}
                    />
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-muted">Rules appear here as the policy is read.</p>
          )}
        </Section>
      </div>
    </>
  );
}

function Choices({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[4.5rem_minmax(0,1fr)] gap-3 pt-2">
      <span />
      <ol className="max-w-[68ch] border-t border-rule">{children}</ol>
    </div>
  );
}

function Choice({
  letter,
  suggested,
  onClick,
  children,
}: {
  letter: string;
  suggested?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <li className="border-b border-rule">
      <button
        type="button"
        onClick={onClick}
        className="group grid w-full grid-cols-[1.5rem_minmax(0,1fr)] items-baseline gap-2 py-2.5 text-left text-[15px] hover:bg-paper-raised focus-visible:outline-2 focus-visible:outline-ink"
      >
        <span className="font-mono text-sm text-ink-muted group-hover:text-ink">{letter}</span>
        <span>
          {children}
          {suggested && <span className="ml-2 text-sm text-allowed">Suggested</span>}
        </span>
      </button>
    </li>
  );
}
