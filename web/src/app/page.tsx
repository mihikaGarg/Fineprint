import Link from "next/link";
import { RegMark, Wordmark } from "@/components/brand";
import { BudgetBoard, DecisionFeed, ExpenseLedger, MarkedAgreement, TranscriptSample } from "@/components/home/showcase";
import { HOME_DEMO } from "@/lib/home-demo";

const REPO_URL = "https://github.com/mihikaGarg/Fineprint";

const slowest = Math.max(...HOME_DEMO.expenses.map((e) => e.latency_ms));
const FIGURES = [
  [String(HOME_DEMO.coverage.total), "clauses read in the demo grant"],
  [`${HOME_DEMO.coverage.rules} + ${HOME_DEMO.policyRules}`, "grant rules and company rules"],
  [String(HOME_DEMO.expenses.length), "sample expenses decided"],
  [`${slowest < 1 ? "<1" : slowest.toFixed(1)} ms`, "for the slowest decision"],
];

const PRINCIPLES = [
  [
    "No quote, no rule",
    "Every rule carries the exact sentence it came from, with its page and character offsets. Code checks the quote against the PDF; a model's paraphrase never becomes a rule.",
  ],
  [
    "A model never moves money",
    "Models can help read a contract. Whether an expense is allowed is decided by plain code, which gives the same answer every time and can say why.",
  ],
  [
    "Unclear goes to a person",
    "If the code can't tell whether an exception applies, say a first-class flight over six hours, the expense waits for a reviewer instead of being guessed at.",
  ],
  [
    "Whole cents only",
    "Every amount is an integer number of cents from the PDF to the budget line. Nothing is rounded and no model does arithmetic.",
  ],
];

function OpenApp({ tone = "accent" }: { tone?: "accent" | "ink" }) {
  return (
    <Link
      href="/app"
      className={
        "inline-flex items-center gap-2 border-2 border-ink px-5 py-2.5 text-sm font-semibold shadow-[4px_4px_0_var(--ink)] transition-all hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0_var(--ink)] " +
        (tone === "accent" ? "bg-accent text-accent-ink" : "bg-ink text-paper shadow-[4px_4px_0_var(--paper)]")
      }
    >
      Open the app <span aria-hidden>→</span>
    </Link>
  );
}

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="flex items-center gap-2 font-mono text-xs text-accent">
        <RegMark className="size-3.5" /> Step {n}
      </p>
      <h2 className="font-display mt-3 text-[clamp(2rem,4vw,3.25rem)]">{title}</h2>
      <div className="mt-5 max-w-[46ch] space-y-3 text-[17px] leading-relaxed text-ink-muted">{children}</div>
    </div>
  );
}

export default function Home() {
  return (
    <div className="min-h-screen overflow-x-hidden">
      <header className="sticky top-0 z-20 border-b border-ink bg-paper/95 backdrop-blur-[2px]">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
          <Wordmark />
          <nav className="flex items-center gap-6 text-sm">
            <a href="#mission" className="hidden hover:text-accent sm:inline">
              Mission
            </a>
            <a href="#product" className="hidden hover:text-accent sm:inline">
              Product
            </a>
            <a href="#principles" className="hidden hover:text-accent md:inline">
              Principles
            </a>
            <Link href="/app" className="bg-ink px-3 py-1.5 font-semibold text-paper hover:bg-accent hover:text-accent-ink">
              Open the app
            </Link>
          </nav>
        </div>
      </header>

      <main>
        {/* Hero */}
        <section className="border-b border-ink">
          <div className="mx-auto grid max-w-7xl gap-14 px-4 py-12 sm:px-6 lg:grid-cols-[1.15fr_1fr] lg:py-16">
            <div className="flex flex-col justify-center">
              <p className="font-mono text-xs text-ink-muted">Spend controls for grant-funded teams</p>
              <h1 className="font-display mt-5 text-[clamp(2.6rem,5.4vw,4.9rem)]">
                Every dollar, cleared by the <mark>clause.</mark>
              </h1>
              <p className="mt-6 max-w-[52ch] text-lg leading-relaxed text-ink-muted">
                The limits on grant money live in single sentences buried in the agreement: no
                alcohol, nothing outside the award dates, equipment over $10,000 needs the program
                officer&apos;s sign-off. Fineprint turns those sentences into rules and checks every
                expense against them before it&apos;s paid.
              </p>
              <div className="mt-8 flex flex-wrap items-center gap-6">
                <OpenApp />
                <a href="#product" className="text-sm font-medium underline decoration-accent decoration-2 underline-offset-4">
                  See it on real expenses
                </a>
              </div>
            </div>
            <DecisionFeed />
          </div>
          <dl className="mx-auto grid max-w-7xl grid-cols-2 border-t border-ink lg:grid-cols-4">
            {FIGURES.map(([value, text]) => (
              <div key={text} className="border-b border-rule px-4 py-5 even:border-l lg:border-b-0 lg:border-l lg:first:border-l-0 sm:px-6">
                <dt className="font-display text-3xl tabular-nums">{value}</dt>
                <dd className="mt-1 text-sm text-ink-muted">{text}</dd>
              </div>
            ))}
          </dl>
        </section>

        {/* Mission */}
        <section id="mission" className="border-b border-ink bg-[#caf0f8]">
          <div className="mx-auto grid max-w-7xl gap-12 px-4 py-20 sm:px-6 lg:grid-cols-[1.1fr_1fr]">
            <h2 className="font-display text-[clamp(2.25rem,4.6vw,4rem)]">
              Grant money comes with conditions. Most teams learn they broke one at the audit.
            </h2>
            <div className="space-y-5 text-[17px] leading-relaxed text-ink-muted">
              <p>
                A research lab spends against an award agreement and the university&apos;s own expense
                policy at the same time. The rules that matter are scattered across both: a cap on
                meals here, a banned category there, an approval that kicks in at $10,000.
              </p>
              <p>
                Today someone remembers them, or a spreadsheet does. When a charge slips through, the
                money comes back out of the department&apos;s budget months later.
              </p>
              <p className="font-medium text-ink">
                Our mission is to check every dollar against the exact words it&apos;s bound by, before
                it moves, and to show the sentence that decided it.
              </p>
            </div>
          </div>
        </section>

        {/* Product */}
        <div id="product">
          <section className="border-b border-ink">
            <div className="mx-auto grid max-w-7xl items-center gap-16 px-4 py-20 sm:px-6 lg:grid-cols-2">
              <Step n={1} title="Read the agreement">
                <p>
                  Upload the grant PDF. Fineprint reads it clause by clause and turns each spending
                  limit into a typed rule: a date range, a banned category, a budget line, an approval
                  threshold.
                </p>
                <p>
                  A clause only becomes a rule if its quote matches the PDF character for character.
                  Hover the page to see what happened to each line.
                </p>
              </Step>
              <MarkedAgreement />
            </div>
          </section>

          <section className="border-b border-ink">
            <div className="mx-auto grid max-w-7xl items-center gap-16 px-4 py-20 sm:px-6 lg:grid-cols-2">
              <div className="order-2 lg:order-1">
                <TranscriptSample />
              </div>
              <div className="order-1 lg:order-2">
                <Step n={2} title="Answer what the policy leaves open">
                  <p>
                    Your company policy goes in next. Most of it reads straight into rules. The rest,
                    a limit with no consequence, a rule with an exception, &ldquo;modest&rdquo;
                    entertainment, comes back as a question.
                  </p>
                  <p>
                    Each question suggests an answer from your own policy&apos;s wording and quotes
                    the line it&apos;s based on. Try picking one.
                  </p>
                </Step>
              </div>
            </div>
          </section>

          <section className="border-b border-ink">
            <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6">
              <div className="grid gap-8 lg:grid-cols-[1fr_1.4fr] lg:items-end">
                <Step n={3} title="Check every expense">
                  <p>
                    Each expense runs against the grant and the policy together. The strictest answer
                    wins, and every decision cites the clause behind it.
                  </p>
                </Step>
                <p className="max-w-[52ch] text-sm text-ink-muted lg:justify-self-end">
                  These are the 16 sample expenses from the demo, decided by the real checker. Click a
                  row to see the sentence that decided it.
                </p>
              </div>
              <div className="mt-10">
                <ExpenseLedger />
              </div>
            </div>
          </section>

          <section className="border-b border-ink">
            <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6">
              <Step n={4} title="Keep the budget honest">
                <p>
                  Budget lines are read from the agreement&apos;s own budget table, each one cited. Allowed
                  spend comes off the right line as it&apos;s approved, so you see what&apos;s left before
                  anyone over-commits.
                </p>
              </Step>
              <div className="mt-10 border border-ink">
                <BudgetBoard />
              </div>
            </div>
          </section>
        </div>

        {/* Principles */}
        <section id="principles" className="border-b border-ink">
          <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6">
            <h2 className="font-display text-[clamp(2rem,4vw,3.25rem)]">Four rules the code never breaks</h2>
            <ol className="mt-12 grid gap-x-16 md:grid-cols-2">
              {PRINCIPLES.map(([title, body], i) => (
                <li key={title} className="grid grid-cols-[3.5rem_minmax(0,1fr)] border-t border-ink py-6">
                  <span className="font-display text-3xl text-accent">{i + 1}</span>
                  <div>
                    <h3 className="text-lg font-semibold">{title}</h3>
                    <p className="mt-2 leading-relaxed text-ink-muted">{body}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* Try it */}
        <section className="bg-accent text-accent-ink">
          <div className="mx-auto flex max-w-7xl flex-col gap-8 px-4 py-16 sm:px-6 md:flex-row md:items-center md:justify-between">
            <p className="font-display max-w-[22ch] text-[clamp(1.75rem,3.4vw,2.75rem)]">
              Load the demo grant and check your first expense in a minute.
            </p>
            <OpenApp tone="ink" />
          </div>
        </section>
      </main>

      <footer className="border-t border-ink">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-6 text-sm sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <Wordmark />
          <p className="text-ink-muted">
            Built at the Ramp × BBS hackathon ·{" "}
            <a href={REPO_URL} className="underline decoration-accent underline-offset-4 hover:text-ink">
              source on GitHub
            </a>
          </p>
        </div>
      </footer>
    </div>
  );
}
