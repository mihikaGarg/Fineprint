"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { post } from "@/lib/api";
import { AppStateProvider, useAppState } from "@/lib/app-state";
import { Wordmark } from "@/components/brand";
import { cx } from "./ui";

const NAV = [
  { href: "/app", label: "Overview" },
  { href: "/app/grants", label: "Grants" },
  { href: "/app/policy", label: "Company policy" },
  { href: "/app/rulebook", label: "Rulebook" },
  { href: "/app/expenses", label: "Expenses" },
] as const;

function useBadges(): Record<string, string> {
  const { state } = useAppState();
  if (!state) return {};
  const grants = state.rulesets.filter((r) => r.kind === "grant");
  const policies = state.rulesets.filter((r) => r.kind === "policy");
  const total = state.rulesets.reduce((a, r) => a + r.rules, 0);
  const approved = state.rulesets.reduce((a, r) => a + r.approved, 0);
  return {
    "/app/grants": grants.length ? String(grants.length) : "",
    "/app/policy": policies.length ? (policies.some((p) => p.open_items) ? "open" : "done") : "",
    "/app/rulebook": total ? `${approved}/${total}` : "",
    "/app/expenses": state.expenses_checked ? String(state.expenses_checked) : "",
  };
}

function ResetButton() {
  const [confirming, setConfirming] = useState(false);
  const router = useRouter();
  const { refresh } = useAppState();
  const quiet = "text-sm text-ink-muted underline-offset-4 hover:text-ink hover:underline";
  if (!confirming) {
    return (
      <button type="button" className={quiet} onClick={() => setConfirming(true)}>
        Reset demo
      </button>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-3 text-sm">
      <span className="text-ink-muted">Clear everything?</span>
      <button
        type="button"
        className="bg-accent px-2.5 py-1 font-semibold text-accent-ink"
        onClick={async () => {
          await post("/api/reset");
          setConfirming(false);
          await refresh();
          router.push("/app");
          router.refresh();
        }}
      >
        Clear
      </button>
      <button type="button" className={quiet} onClick={() => setConfirming(false)}>
        Cancel
      </button>
    </div>
  );
}

function Nav() {
  const pathname = usePathname();
  const badges = useBadges();
  return (
    <nav className="-mx-1 flex gap-3 overflow-x-auto [scrollbar-width:none] lg:mx-0 lg:flex-col lg:gap-0">
      {NAV.map((item) => {
        const active = pathname === item.href;
        const badge = badges[item.href];
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={cx(
              "flex shrink-0 items-center justify-between gap-3 border-b-2 px-1 py-1.5 text-sm transition-colors",
              "lg:border-b-0 lg:border-l-2 lg:px-3",
              active
                ? "border-accent font-semibold text-ink"
                : "border-transparent text-ink-muted hover:border-rule hover:text-ink",
            )}
          >
            {item.label}
            {badge && (
              <span
                className={cx(
                  "font-mono text-xs font-normal tabular-nums",
                  badge === "open" ? "text-accent" : "text-ink-muted",
                )}
              >
                {badge === "open" ? "open" : badge === "done" ? "done" : badge}
              </span>
            )}
          </Link>
        );
      })}
    </nav>
  );
}

function Frame({ children }: { children: React.ReactNode }) {
  const { state, error } = useAppState();
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[15rem_1fr]">
      <aside className="border-b border-rule bg-paper-raised px-4 pt-4 pb-2 lg:sticky lg:top-0 lg:flex lg:h-screen lg:flex-col lg:border-b-0 lg:border-r lg:px-5 lg:py-6">
        <div className="mb-3 flex items-center justify-between lg:mb-8">
          <Wordmark />
          <div className="lg:hidden">
            <ResetButton />
          </div>
        </div>
        <Nav />
        <div className="mt-auto hidden space-y-3 lg:block">
          <p className="font-mono text-[11px] text-ink-muted">
            {state ? (state.llm_enabled ? "Reading with Claude" : "Reading offline, no API key") : ""}
          </p>
          <ResetButton />
        </div>
      </aside>
      <main className="min-w-0 px-4 py-6 sm:px-8 lg:px-12 lg:py-10">
        <div className="max-w-5xl">
          {error && (
            <div className="mb-6 border-l-2 border-blocked py-1 pl-3 text-sm text-blocked">
              {error}
            </div>
          )}
          {children}
        </div>
      </main>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <AppStateProvider>
      <Frame>{children}</Frame>
    </AppStateProvider>
  );
}
