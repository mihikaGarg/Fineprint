# Fineprint

Every dollar, cleared by the clause.

Fineprint compiles grant agreements into enforceable spend rules and checks expenses against them, with verified clause citations. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Product

**Try it live: [fineprint-n62f.vercel.app](https://fineprint-n62f.vercel.app)**

1. Click **Open the app**, then **Load the demo grant**: every spending rule in a five-page award agreement, each quoted with its page.
2. Go to **Company policy** → **Use the sample**: the assistant reads a university expense policy and asks about anything it leaves open.
3. Go to **Expenses** → **Run the 16 sample expenses**: each one is allowed, blocked or sent for review, with the clause that decided it.

The API runs on a free server that sleeps when idle, so the first load can take about a minute. How it's hosted: [docs/DEPLOY.md](docs/DEPLOY.md).

## Setup

```bash
uv sync
make check
```
