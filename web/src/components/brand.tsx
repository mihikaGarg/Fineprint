import Link from "next/link";

/** A printer's registration mark: the crosshair used to line up plates on a press sheet. */
export function RegMark({ className = "size-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="12" cy="12" r="6.5" />
      <circle cx="12" cy="12" r="2.5" fill="currentColor" stroke="none" />
      <path d="M12 1.5v21M1.5 12h21" />
    </svg>
  );
}

export function Wordmark({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="group inline-flex items-center gap-2">
      <RegMark className="size-5 text-accent transition-transform duration-500 group-hover:rotate-90" />
      <span className="font-display text-xl tracking-tight">Fineprint</span>
    </Link>
  );
}

const TONE = {
  ALLOWED: ["bg-allowed", "text-allowed", "Allowed"],
  BLOCKED: ["bg-blocked", "text-blocked", "Blocked"],
  NEEDS_REVIEW: ["bg-review", "text-review", "Needs review"],
} as const;

export type VerdictKey = keyof typeof TONE;

export function Verdict({ v, className = "" }: { v: VerdictKey; className?: string }) {
  const [dot, text, word] = TONE[v];
  return (
    <span className={`inline-flex shrink-0 items-center gap-1.5 font-mono text-xs font-medium ${text} ${className}`}>
      <span aria-hidden className={`size-2 ${dot}`} />
      {word}
    </span>
  );
}
