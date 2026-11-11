# Putting Fineprint online

Fineprint is two pieces, so it goes on two free hosts:

| Piece | Host | Gives you |
|---|---|---|
| Website (`/web`, Next.js) | Vercel | The link you share, e.g. `fineprint.vercel.app` |
| API (Python: checker, PDF reading, policy chat) | Render | A backend address only the website talks to |

Both watch the GitHub repo. Push to the deployed branch and both rebuild on their own in a few minutes.

## Before you start

- Decide which branch to deploy. `main` is the stable choice, so merge the open work first. To try it sooner, use `a/web-app`; it has everything, including `render.yaml`.
- You need a GitHub login with access to `mihikaGarg/Fineprint`. Both sites sign in with GitHub.

## 1. The API on Render (about 5 minutes)

1. Go to [render.com](https://render.com) and sign in with GitHub.
2. Click **New** → **Blueprint**.
3. Connect the `mihikaGarg/Fineprint` repository. If it isn't listed, click **Configure GitHub** and give Render access to it.
4. Pick the branch (`main`, or `a/web-app` for now). Render finds `render.yaml` and shows one service, **fineprint-api**.
5. Click **Apply**. The first build takes 2–4 minutes.
6. When it says **Live**, copy the address at the top of the service page. It looks like `https://fineprint-api.onrender.com`; Render may add a suffix if the name is taken.
7. Check it: open that address with `/api/health` on the end. You should see `"status":"ok"`.

## 2. The website on Vercel (about 5 minutes)

1. Go to [vercel.com](https://vercel.com) and sign in with GitHub.
2. Click **Add New** → **Project**, then **Import** next to `mihikaGarg/Fineprint`.
3. Set **Root Directory** to `web` (click **Edit** next to it). Vercel then detects Next.js on its own.
4. Open **Environment Variables** and add:
   - Name: `FINEPRINT_API_URL`
   - Value: the Render address from step 1, with no slash at the end, e.g. `https://fineprint-api.onrender.com`
5. Click **Deploy**. The build takes about a minute.
6. Vercel shows your link. Open it, click **Open the app**, then **Load the demo grant**.

To deploy a branch other than `main` as the main link: **Settings** → **Git** → **Production Branch**.

## Sharing it

- Send the Vercel link to anyone. They don't need an account.
- To add teammates as editors: on Vercel, **Settings** → **Members**; on Render, **Workspace settings** → **Members**.
- Every pull request also gets its own Vercel preview link, posted on the PR, so teammates can try changes before they're merged.

## Adding the API key later

The key only goes in Render's settings. Never put it in the code, in `render.yaml`, or in a chat.

1. On Render, open **fineprint-api** → **Environment**.
2. Click **Add Environment Variable**: name `ANTHROPIC_API_KEY`, value your key.
3. Click **Save, rebuild, and deploy**.
4. Check `/api/health` on the Render address: `"llm_enabled": true`. In the app's sidebar, "Reading offline, no API key" changes to "Reading with Claude".

To turn it off again, delete the variable. Without a key the app always reads documents offline; the expense checker never uses the key at all.

## Good to know

- **The free Render plan sleeps** after about 15 minutes with no visits. The next visit takes 30–60 seconds while it wakes, and the app shows "Can't reach the Fineprint API" until then. Open the link a minute before a demo, or switch the service to the Starter plan (about $7 a month) to keep it awake.
- **Data resets** when the API restarts or wakes up: grants, policies and checked expenses are kept in memory only. Everyone using the link at the same time also shares the same data. Use **Reset demo** to start clean.
- **If you change `FINEPRINT_API_URL`** on Vercel, redeploy the website (**Deployments** → latest → **Redeploy**). The address is fixed in at build time.
- **If the home page numbers look out of date** after changes to the reader or the checker, run `python scripts/export_home_demo.py` and push. That regenerates the real demo output the home page shows.

## If something goes wrong

| What you see | What to check |
|---|---|
| "Can't reach the Fineprint API" for more than a minute | `FINEPRINT_API_URL` on Vercel matches the Render address, with no trailing slash; then redeploy the website |
| Render build fails | The build log; the Python version is set by `PYTHON_VERSION` in `render.yaml` |
| Vercel build fails | **Root Directory** must be `web` |
| The home page works but the app is empty | Normal after a restart: click **Load the demo grant** |
