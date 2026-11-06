import { VerdictBadge, VerdictDemo } from "@/components/verdict-demo";

const REPO_URL = "https://github.com/mihikaGarg/Fineprint";

const COMPILE_STEPS = [
  { title: "Read the agreement", body: "Extract every page of the grant PDF with stable character offsets." },
  { title: "Propose rules", body: "An LLM proposes typed rules, each with the exact clause it relies on." },
  { title: "Verify every citation", body: "Code checks each quote against the PDF, character for character. Anything that doesn't match is rejected." },
];

const ENFORCE_STEPS = [
  { title: "Expense arrives", body: "Amount, date, merchant, category, and current budget state." },
  { title: "Rules evaluate", body: "Plain deterministic code. No model calls, no randomness, built to answer in under 100ms." },
  { title: "Verdict with a trace", body: "Every rule's outcome, linked back to the clause and page it came from." },
];

const GUARANTEES = [
  {
    title: "Cited to the character",
    body: "Every rule carries a verbatim quote, page number, and character offsets, verified against the source PDF. No citation, no rule.",
  },
  {
    title: "Agents propose, code disposes",
    body: "Models help read the contract. They never approve or block a payment. That decision is always deterministic.",
  },
  {
    title: "Cents, never floats",
    body: "All money is integer cents end to end. Models never do arithmetic.",
  },
  {
    title: "Ambiguity escalates",
    body: "When a clause or an expense is unclear, Fineprint sends it to a person. It never guesses.",
  },
];

const VERDICTS = [
  { verdict: "ALLOWED" as const, body: "Every applicable rule passed. Spend recorded against the budget line." },
  { verdict: "BLOCKED" as const, body: "A rule failed. The trace shows which clause, on which page, and why." },
  { verdict: "NEEDS_REVIEW" as const, body: "Something needs a human: a missing approval, an unknown category, an unclear clause." },
];

function Wordmark() {
  return (
    <span className="font-serif text-2xl tracking-tight">
      Fine<span className="italic">print</span>
    </span>
  );
}

function Steps({ label, tag, steps }: { label: string; tag: string; steps: typeof COMPILE_STEPS }) {
  return (
    <div className="rounded-2xl border border-rule bg-paper-raised p-6 sm:p-8">
      <div className="mb-6 flex items-baseline justify-between gap-4">
        <h3 className="font-serif text-3xl">{label}</h3>
        <span className="font-mono text-xs uppercase tracking-wider text-ink-muted">{tag}</span>
      </div>
      <ol className="space-y-5">
        {steps.map((s, i) => (
          <li key={s.title} className="grid grid-cols-[2rem_1fr] gap-3">
            <span className="font-mono text-sm text-ink-muted tabular-nums">0{i + 1}</span>
            <div>
              <p className="font-medium">{s.title}</p>
              <p className="mt-1 text-sm leading-relaxed text-ink-muted">{s.body}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
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
          <a href="#guarantees" className="hidden text-ink-muted hover:text-ink sm:inline">
            Guarantees
          </a>
          <a
            href={REPO_URL}
            className="rounded-full border border-rule px-4 py-1.5 font-medium hover:border-ink"
          >
            GitHub
          </a>
        </nav>
      </header>

      <main>
        <section className="mx-auto grid max-w-6xl items-center gap-12 px-4 pb-20 pt-10 sm:px-6 lg:grid-cols-[1.1fr_1fr] lg:pt-20">
          <div>
            <p className="mb-5 font-mono text-xs uppercase tracking-[0.18em] text-ink-muted">
              Grant compliance, compiled
            </p>
            <h1 className="font-serif text-5xl leading-[1.02] tracking-tight sm:text-6xl lg:text-7xl">
              Every dollar, cleared by <span className="italic">the clause.</span>
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-ink-muted">
              Fineprint turns a grant agreement into enforceable spend rules, then checks every
              expense against them. Each verdict points to the exact sentence in the contract that
              decided it.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <a
                href="#how"
                className="rounded-full bg-ink px-6 py-3 text-sm font-medium text-paper hover:opacity-90"
              >
                See how it works
              </a>
              <a
                href={REPO_URL}
                className="rounded-full border border-rule px-6 py-3 text-sm font-medium hover:border-ink"
              >
                View the code
              </a>
            </div>
          </div>
          <VerdictDemo />
        </section>

        <section id="how" className="border-t border-rule py-20">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <h2 className="max-w-2xl font-serif text-4xl leading-tight sm:text-5xl">
              Read slowly once. <span className="italic">Decide instantly forever.</span>
            </h2>
            <p className="mt-4 max-w-2xl text-ink-muted">
              Two paths, kept apart on purpose. Compiling the contract can take its time. Checking
              a payment has to be fast, repeatable, and explainable.
            </p>
            <div className="mt-12 grid gap-6 md:grid-cols-2">
              <Steps label="Compile" tag="PDF → rules" steps={COMPILE_STEPS} />
              <Steps label="Enforce" tag="expense → verdict" steps={ENFORCE_STEPS} />
            </div>
          </div>
        </section>

        <section className="border-t border-rule py-20">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <h2 className="font-serif text-4xl sm:text-5xl">Three answers. No maybes.</h2>
            <div className="mt-10 grid gap-6 md:grid-cols-3">
              {VERDICTS.map((v) => (
                <div key={v.verdict} className="border-t-2 border-ink pt-5">
                  <VerdictBadge verdict={v.verdict} />
                  <p className="mt-4 leading-relaxed text-ink-muted">{v.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="guarantees" className="border-t border-rule py-20">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <h2 className="font-serif text-4xl sm:text-5xl">What we won&apos;t compromise on</h2>
            <dl className="mt-12 grid gap-x-12 gap-y-10 sm:grid-cols-2">
              {GUARANTEES.map((g, i) => (
                <div key={g.title} className="grid grid-cols-[2.5rem_1fr]">
                  <span className="font-serif text-2xl italic text-ink-muted">§{i + 1}</span>
                  <div>
                    <dt className="text-lg font-medium">{g.title}</dt>
                    <dd className="mt-2 leading-relaxed text-ink-muted">{g.body}</dd>
                  </div>
                </div>
              ))}
            </dl>
          </div>
        </section>

        <section className="border-t border-rule py-24">
          <div className="mx-auto max-w-3xl px-4 text-center sm:px-6">
            <h2 className="font-serif text-4xl leading-tight sm:text-5xl">
              Spend with the contract <span className="italic">open.</span>
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-ink-muted">
              Fineprint is in early development. Follow along, or read how it&apos;s built.
            </p>
            <a
              href={REPO_URL}
              className="mt-8 inline-block rounded-full bg-ink px-6 py-3 text-sm font-medium text-paper hover:opacity-90"
            >
              Follow on GitHub
            </a>
          </div>
        </section>
      </main>

      <footer className="border-t border-rule">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-8 text-sm text-ink-muted sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <Wordmark />
          <p>Built at the Ramp × BBS hackathon.</p>
        </div>
      </footer>
    </div>
  );
}
