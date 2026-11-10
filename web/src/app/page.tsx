const REPO_URL = "https://github.com/mihikaGarg/Fineprint";

const COMPILE_STEPS = [
  { title: "Read the agreement", body: "Every page of the grant PDF is extracted with stable character offsets." },
  { title: "Propose rules", body: "A model suggests typed rules, each with the exact clause it relies on." },
  {
    title: "Check every quote",
    body: "Code compares each quote with the PDF, character for character. Anything that doesn't match is rejected.",
  },
];

const ENFORCE_STEPS = [
  { title: "An expense comes in", body: "Amount, date, merchant, category, sign-offs and the budget so far." },
  { title: "Rules are applied", body: "Plain code, no model calls, the same answer every time. It takes under a millisecond." },
  { title: "A decision with reasons", body: "Each rule's result, the clause and page behind it, and what would clear it." },
];

const VERDICTS = [
  { name: "Allowed", tone: "allowed", body: "Every rule that applies passed. The amount comes off the grant's budget line." },
  { name: "Blocked", tone: "blocked", body: "A rule failed. You see which clause, on which page, and why." },
  {
    name: "Needs review",
    tone: "review",
    body: "A person has to decide: a missing receipt, an exception the code can't check, an unclear clause.",
  },
] as const;

const RULES = [
  {
    title: "Every rule is quoted",
    body: "Each rule carries the verbatim sentence, its page and character offsets, checked against the PDF. No quote, no rule.",
  },
  {
    title: "Models suggest, code decides",
    body: "A model can help read the contract. It never approves or blocks a payment.",
  },
  { title: "Money is whole cents", body: "Amounts are integers from end to end. Models never do arithmetic." },
  {
    title: "Unclear cases go to a person",
    body: "When a clause or an expense is ambiguous, Fineprint asks for review instead of guessing.",
  },
];

const TONE = { allowed: "bg-allowed", blocked: "bg-blocked", review: "bg-review" } as const;
const TONE_TEXT = { allowed: "text-allowed", blocked: "text-blocked", review: "text-review" } as const;

function Wordmark() {
  return (
    <span className="font-serif text-2xl">
      Fine<span className="italic">print</span>
    </span>
  );
}

function Steps({ label, steps }: { label: string; steps: typeof COMPILE_STEPS }) {
  return (
    <div className="border-t border-ink pt-3">
      <h3 className="font-serif text-2xl">{label}</h3>
      <ol className="mt-4">
        {steps.map((s, i) => (
          <li key={s.title} className="grid grid-cols-[1.75rem_1fr] gap-2 border-b border-rule py-3 last:border-b-0">
            <span className="font-mono text-sm text-ink-muted">{i + 1}.</span>
            <div>
              <p className="font-medium">{s.title}</p>
              <p className="mt-0.5 text-sm leading-relaxed text-ink-muted">{s.body}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

/** A real decision from the demo: sample expense NW-1010 against clause 5.3 of the demo grant. */
function Excerpt() {
  return (
    <figure className="border-y border-ink py-5">
      <p className="text-xs text-ink-muted">From the demo grant, page 3</p>
      <blockquote className="mt-2 font-serif text-2xl leading-snug">
        “5.3 <mark>Fundraising costs are unallowable.</mark>”
      </blockquote>
      <div className="mt-6 border-t border-rule pt-4">
        <div className="flex items-baseline justify-between gap-4">
          <div>
            <p className="font-medium">Gala table, City Gala Foundation</p>
            <p className="text-sm text-ink-muted">Development Office · fundraising · signed off by manager</p>
          </div>
          <span className="font-mono tabular-nums">$2,500</span>
        </div>
        <p className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-blocked">
          <span aria-hidden className="size-2 rounded-[1px] bg-blocked" />
          Blocked
        </p>
        <p className="mt-1 text-sm text-ink-muted">
          Category is fundraising. Not allowed in any amount under this rule; use a different funding
          source.
        </p>
      </div>
      <figcaption className="mt-4 text-xs text-ink-muted">
        Checked against 4 grant rules and 13 company rules in under a millisecond.
      </figcaption>
    </figure>
  );
}

export default function Home() {
  return (
    <div className="min-h-screen">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-4 py-5 sm:px-6">
        <Wordmark />
        <nav className="flex items-center gap-5 text-sm">
          <a href="#how" className="hidden text-ink-muted hover:text-ink sm:inline">
            How it works
          </a>
          <a href={REPO_URL} className="hidden text-ink-muted hover:text-ink sm:inline">
            Code
          </a>
          <a href="/app" className="rounded-[3px] bg-ink px-3 py-1.5 font-medium text-paper hover:bg-ink/85">
            Open the app
          </a>
        </nav>
      </header>

      <main className="mx-auto max-w-6xl px-4 sm:px-6">
        <section className="grid gap-10 border-t border-ink py-12 lg:grid-cols-[1.15fr_1fr] lg:gap-16 lg:py-16">
          <div>
            <h1 className="font-serif text-4xl leading-tight sm:text-5xl">
              Every dollar, cleared by <span className="italic">the clause.</span>
            </h1>
            <p className="mt-5 max-w-[56ch] text-lg leading-relaxed text-ink-muted">
              Fineprint reads a grant agreement and your company&apos;s expense policy, turns each
              spending limit into a rule quoted from the document, and checks every expense against
              all of them before it&apos;s paid.
            </p>
            <div className="mt-7 flex flex-wrap items-center gap-5">
              <a
                href="/app"
                className="rounded-[3px] bg-ink px-4 py-2 text-sm font-medium text-paper hover:bg-ink/85"
              >
                Open the app
              </a>
              <a href="#how" className="text-sm text-ink-muted underline underline-offset-4 hover:text-ink">
                How it works
              </a>
            </div>
          </div>
          <Excerpt />
        </section>

        <section id="how" className="border-t border-ink py-12">
          <h2 className="font-serif text-3xl">How it works</h2>
          <p className="mt-3 max-w-[62ch] text-ink-muted">
            Reading a contract can take its time. Deciding on a payment has to be fast, repeatable and
            explainable, so the two run separately.
          </p>
          <div className="mt-8 grid gap-10 md:grid-cols-2">
            <Steps label="Reading the agreement" steps={COMPILE_STEPS} />
            <Steps label="Checking an expense" steps={ENFORCE_STEPS} />
          </div>
        </section>

        <section className="border-t border-ink py-12">
          <h2 className="font-serif text-3xl">The three decisions</h2>
          <dl className="mt-6">
            {VERDICTS.map((v) => (
              <div key={v.name} className="grid gap-2 border-b border-rule py-3 last:border-b-0 sm:grid-cols-[12rem_1fr]">
                <dt className={`inline-flex items-center gap-2 font-medium ${TONE_TEXT[v.tone]}`}>
                  <span aria-hidden className={`size-2 rounded-[1px] ${TONE[v.tone]}`} />
                  {v.name}
                </dt>
                <dd className="text-ink-muted">{v.body}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section className="border-t border-ink py-12">
          <h2 className="font-serif text-3xl">Rules the code follows</h2>
          <dl className="mt-6 grid gap-x-12 sm:grid-cols-2">
            {RULES.map((r) => (
              <div key={r.title} className="border-b border-rule py-4">
                <dt className="font-medium">{r.title}</dt>
                <dd className="mt-1 leading-relaxed text-ink-muted">{r.body}</dd>
              </div>
            ))}
          </dl>
        </section>
      </main>

      <footer className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="flex flex-col gap-2 border-t border-ink py-6 text-sm text-ink-muted sm:flex-row sm:items-center sm:justify-between">
          <Wordmark />
          <p>
            Built at the Ramp × BBS hackathon ·{" "}
            <a href={REPO_URL} className="underline underline-offset-4 hover:text-ink">
              source on GitHub
            </a>
          </p>
        </div>
      </footer>
    </div>
  );
}
