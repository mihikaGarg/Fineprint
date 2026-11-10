"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { post } from "@/lib/api";
import { AppStateProvider, useAppState } from "@/lib/app-state";
import { Button, cx } from "./ui";

const NAV = [
  { href: "/app", label: "Overview" },
  { href: "/app/grants", label: "Grants" },
  { href: "/app/policy", label: "Company policy" },
  { href: "/app/rulebook", label: "Rulebook" },
  { href: "/app/expenses", label: "Expenses" },
] as const;

function Wordmark() {
  return (
    <Link href="/" className="font-serif text-2xl tracking-tight">
      Fine<span className="italic">print</span>
    </Link>
  );
}

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
  if (!confirming) {
    return (
      <Button variant="ghost" size="sm" onClick={() => setConfirming(true)}>
        Reset demo
      </Button>
    );
  }
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="text-ink-muted">Clear everything?</span>
      <Button
        size="sm"
        variant="primary"
        onClick={async () => {
          await post("/api/reset");
          setConfirming(false);
          await refresh();
          router.push("/app");
          router.refresh();
        }}
      >
        Clear
      </Button>
      <Button size="sm" variant="ghost" onClick={() => setConfirming(false)}>
        Cancel
      </Button>
    </div>
  );
}

function Nav() {
  const pathname = usePathname();
  const badges = useBadges();
  return (
    <nav className="flex gap-1 overflow-x-auto lg:flex-col">
      {NAV.map((item) => {
        const active = pathname === item.href;
        const badge = badges[item.href];
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cx(
              "flex shrink-0 items-center justify-between gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
              active ? "bg-ink text-paper" : "text-ink-muted hover:bg-paper-raised hover:text-ink",
            )}
          >
            {item.label}
            {badge && (
              <span
                className={cx(
                  "font-mono text-[11px] tabular-nums",
                  badge === "open" && !active && "text-review",
                  badge === "done" && !active && "text-allowed",
                )}
              >
                {badge === "open" ? "●" : badge === "done" ? "✓" : badge}
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
      <aside className="border-b border-rule px-4 py-4 lg:sticky lg:top-0 lg:flex lg:h-screen lg:flex-col lg:border-b-0 lg:border-r lg:px-5 lg:py-6">
        <div className="mb-4 flex items-center justify-between lg:mb-8">
          <Wordmark />
          <div className="lg:hidden">
            <ResetButton />
          </div>
        </div>
        <Nav />
        <div className="mt-auto hidden space-y-3 lg:block">
          <p className="font-mono text-[11px] uppercase tracking-wider text-ink-muted">
            {state ? (state.llm_enabled ? "Claude reader on" : "Offline reader") : ""}
          </p>
          <ResetButton />
        </div>
      </aside>
      <main className="min-w-0 px-4 py-8 sm:px-8 lg:px-12 lg:py-12">
        <div className="mx-auto max-w-5xl">
          {error && (
            <div className="mb-6 rounded-xl border border-blocked/40 bg-blocked-bg px-4 py-3 text-sm text-blocked">
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
