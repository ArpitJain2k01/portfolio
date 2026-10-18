# Decap CMS — web admin at `/admin/`

Decap CMS gives you a browser-based admin panel to **write/edit blog posts**,
**swap the resume PDF**, and **edit the About / Experience / Certifications
pages** — from any device. It commits changes to this GitHub repo, which
triggers the normal Pages rebuild. There is **no backend server** holding your
data; the only server-side piece is a tiny OAuth broker used *only* at login.

- Admin page: `static/admin/index.html`
- Config: `static/admin/config.yml`
- OAuth broker (Cloudflare Worker): `oauth-broker/`
- Live admin (after setup): `https://arpitjain2k01.github.io/portfolio/admin/`

## Why a broker is needed

Decap runs in your browser. GitHub login requires exchanging a code for a token
using an OAuth **client secret**, which must never live in browser code. The
broker (a ~70-line Cloudflare Worker) does that exchange. It stores nothing and
only runs during login.

## One-time setup (about 15 minutes)

You do these three steps yourself because they involve your own accounts and
secrets. I can't create accounts or hold your secrets for you.

### 1. Deploy the OAuth broker (Cloudflare Workers — free)

```bash
npm install -g wrangler
cd oauth-broker
wrangler login            # opens a browser; sign in / create a free Cloudflare account
wrangler deploy           # prints your worker URL, e.g. https://decap-oauth-broker.<you>.workers.dev
```

Note the worker URL — call it `BROKER_URL`.

### 2. Create a GitHub OAuth App

1. GitHub → Settings → Developer settings → **OAuth Apps** → **New OAuth App**
   (<https://github.com/settings/developers>).
2. Fill in:
   - **Application name:** `Portfolio CMS` (anything)
   - **Homepage URL:** `https://arpitjain2k01.github.io/portfolio/`
   - **Authorization callback URL:** `BROKER_URL/callback`
     (e.g. `https://decap-oauth-broker.<you>.workers.dev/callback`)
3. Create it. Copy the **Client ID**, then **Generate a new client secret** and copy it.
4. Give those two values to the broker:

   ```bash
   cd oauth-broker
   wrangler secret put GITHUB_CLIENT_ID        # paste the Client ID
   wrangler secret put GITHUB_CLIENT_SECRET    # paste the Client secret
   ```

### 3. Point the CMS at your broker

Edit `static/admin/config.yml` → `backend.base_url` and replace
`https://REPLACE_WITH_OAUTH_BROKER_URL` with your `BROKER_URL`. Commit and push:

```bash
git add static/admin/config.yml
git commit -m "chore(cms): point Decap at the OAuth broker"
git push
```

## Using it

1. Go to `https://arpitjain2k01.github.io/portfolio/admin/`.
2. Click **Login with GitHub**, authorize once.
3. You get a dashboard with:
   - **Blog posts** — create/edit/delete posts; toggle **Draft** off to publish.
   - **Documents → Resume (PDF)** — upload a new PDF (keep the filename
     `arpit-jain-resume.pdf` so the Download button keeps working).
   - **Pages** — edit About, Experience, Certifications.
4. **Publish** commits to `main`; the site rebuilds and is live in ~1 minute.

## Notes & caveats

- **Access control:** anyone who can push to this repo can use the CMS. Keep the
  repo's collaborators limited to you.
- **Local preview of posts** still works via `./admin/dev.sh` (the Python admin)
  — the two don't conflict; both write the same Markdown files.
- **Resume filename:** the Resume page links to `/arpit-jain-resume.pdf`. If you
  upload a PDF with a different name, update the button in `content/resume.md`.
- If login popups are blocked, allow popups for the Pages domain.
- This is optional. If you ever remove it, just delete `static/admin/` and
  `oauth-broker/`.
