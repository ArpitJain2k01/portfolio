# Managing posts (CRUD)

Three ways to create, edit, and delete blog posts — pick whichever suits the moment. All of them write the same `content/posts/<slug>/index.md` files, so you can mix and match.

---

## 1. Web admin (easiest — no terminal, no front matter)

A local browser app with a form-based editor and a list of all posts with Edit / Preview / Delete buttons.

```bash
python3 admin/admin.py
```

Open <http://localhost:1314>. From there you can:

- **+ New post** — fill in title, tags, summary, body; save.
- **Edit** — change any field or the Markdown body.
- **Draft toggle** — check "Draft" to hide a post, uncheck to publish.
- **Delete** — removes the post and its folder (asks for confirmation).
- **Preview** — opens the live rendered post (needs `hugo server` running).

Run `hugo server` in a second terminal so Preview and live-reload work:

```bash
hugo server
```

> This admin is **local only** — it binds to `127.0.0.1` and has no login. Never expose it to the internet. It's a desktop authoring tool, not a server.

## 2. CLI (fast, from the terminal)

```bash
python3 admin/post.py list                       # show all posts + state
python3 admin/post.py new "My Post Title" \
        --tags kubernetes,aws --summary "..."     # create a draft
python3 admin/post.py open my-post-title          # print the file path to edit
python3 admin/post.py publish my-post-title       # draft = false
python3 admin/post.py unpublish my-post-title     # draft = true
python3 admin/post.py delete my-post-title        # remove (asks to confirm)
```

Typical flow: `new` → edit the file in your editor → `publish`.

## 3. Hosted Git-based CMS (edit from your phone or any browser, anywhere)

The two tools above run on your laptop. If you want to write or fix a post from your phone, a tablet, or any browser **without this repo checked out**, add a Git-based CMS. The recommended option is [**Decap CMS**](https://decapcms.org) (the maintained successor to Netlify CMS). It gives you an admin page at `https://your-site/admin/` that commits Markdown straight to your GitHub repo — which then triggers your existing deploy workflow.

How it fits:

```
You edit at  your-site/admin/   (phone/browser, logged in via GitHub)
        │
        ▼
Decap commits content/posts/<slug>/index.md to GitHub
        │
        ▼
GitHub Actions builds + deploys (your existing deploy.yml)
```

Minimal setup:

1. Create `static/admin/index.html`:

   ```html
   <!doctype html>
   <html lang="en">
   <head>
     <meta charset="utf-8" />
     <meta name="viewport" content="width=device-width, initial-scale=1" />
     <title>Content Manager</title>
   </head>
   <body>
     <script src="https://unpkg.com/decap-cms@^3.0.0/dist/decap-cms.js"></script>
   </body>
   </html>
   ```

2. Create `static/admin/config.yml`:

   ```yaml
   backend:
     name: github
     repo: ArpitJain2k01/portfolio      # change to your repo
     branch: main
   media_folder: "assets/img"
   public_folder: "/img"
   collections:
     - name: posts
       label: Posts
       folder: content/posts
       path: "{{slug}}/index"
       create: true
       slug: "{{slug}}"
       fields:
         - { label: Title, name: title, widget: string }
         - { label: Date, name: date, widget: datetime }
         - { label: Draft, name: draft, widget: boolean, default: true }
         - { label: Summary, name: summary, widget: text }
         - { label: Tags, name: tags, widget: list, default: [] }
         - { label: "Show TOC", name: showTableOfContents, widget: boolean, default: true }
         - { label: Body, name: body, widget: markdown }
   ```

3. Authentication: GitHub's device/OAuth flow needs a small OAuth broker. The simplest path is to host the site on a platform with a built-in Git-gateway/identity (e.g. a Netlify or Cloudflare Pages Function acting as the OAuth proxy). Follow the current Decap "GitHub backend" docs for the exact broker setup — it's a one-time ~15-minute step.

Once configured, you log in at `/admin/`, write a post on your phone, hit publish, and the commit → build → deploy happens automatically.

> Trade-off: the web admin and CLI need your laptop; the Git-based CMS works from anywhere but needs the one-time OAuth broker. Many people set up all three and use whichever is handy.

---

## Which should I use?

| Situation | Use |
|---|---|
| At my laptop, want a nice editor | Web admin (`admin/admin.py`) |
| At my laptop, quick action | CLI (`admin/post.py`) |
| On my phone / away from my machine | Decap CMS at `/admin/` |
