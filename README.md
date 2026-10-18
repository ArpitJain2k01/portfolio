# Arpit Jain — Portfolio & Learning Blog

A fast, mobile-responsive portfolio and technical blog built with [Hugo](https://gohugo.io/) and the [Congo](https://jpanther.github.io/congo/) theme. Write posts in Markdown, push to GitHub, and the site deploys itself to GitHub Pages.

## Prerequisites

- [Hugo **extended**](https://gohugo.io/installation/) ≥ 0.168 (`brew install hugo`)
- Git

## Run it locally

```bash
hugo server --baseURL "http://localhost:1313/" --appendPort=false
```

Open <http://localhost:1313>. The server live-reloads as you edit. To preview draft posts, add `--buildDrafts`.

> **Why the `--baseURL` flags?** The site's production `baseURL` has a real domain, and Hugo bakes it into the CSS/JS asset URLs. Without these flags the preview tries to load assets from the production domain and renders **unstyled**. `./admin/dev.sh` already includes them — use it and you never have to think about this.

## Add a new blog post

You have three ways to manage posts (create / edit / delete) — see **[admin/README.md](admin/README.md)** for full details:

1. **Web admin** (no terminal, form-based editor): `python3 admin/admin.py` → <http://localhost:1314>
2. **CLI**: `python3 admin/post.py new "Title" --tags kubernetes,aws`
3. **Hosted CMS** (edit from your phone/anywhere): Decap CMS at `/admin/` — setup documented in `admin/README.md`

Quick start — run the site preview and the admin together:

```bash
./admin/dev.sh      # Hugo on :1313, post admin on :1314
```

### Or by hand

```bash
hugo new posts/my-post-slug/index.md
```

That creates `content/posts/my-post-slug/index.md` with front matter. Edit it:

```toml
+++
title = "My Post Title"
date = 2026-10-18
draft = false            # set false to publish
summary = "One or two sentences shown on the blog list and in link previews."
tags = ["kubernetes", "aws"]
showTableOfContents = true
+++

Write your post in Markdown here.
```

- Put images for the post in the **same folder** (`content/posts/my-post-slug/`) and reference them as `![alt](image.png)`.
- Code blocks get syntax highlighting and a copy button automatically:

  ````markdown
  ```bash
  kubectl get pods -A
  ```
  ````

- Tags create filterable tag pages automatically.

## Edit the pages and your details

| What | Where |
|---|---|
| Name, title, bio, social links, avatar | `config/_default/languages.en.toml` |
| Nav menu | `config/_default/menus.en.toml` |
| Theme behavior (dark/light, TOC, sharing) | `config/_default/params.toml` |
| Site title / baseURL | `config/_default/hugo.toml` |
| About page | `content/about.md` |
| CV page | `content/cv.md` |
| Certifications page | `content/certifications.md` |
| Profile avatar | `assets/img/avatar.jpg` (replace the placeholder) |

### Things to replace before going live

- `config/_default/hugo.toml` → `baseURL`
- `config/_default/languages.en.toml` → LinkedIn handle, email
- `content/about.md`, `content/cv.md`, `content/certifications.md` → your real details
- `assets/img/avatar.jpg` → a real photo (square, ~400×400)
- Optional: add a CV PDF to `static/arpit-jain-cv.pdf` and link it from `content/cv.md`

## Deploy to GitHub Pages

1. Create a GitHub repo and push this folder (the Congo theme is a git submodule — it is pulled automatically by the workflow).
2. In the repo: **Settings → Pages → Build and deployment → Source → GitHub Actions**.
3. Push to `main`. The workflow in `.github/workflows/deploy.yml` builds and deploys automatically.

> If deploying to `https://<user>.github.io/<repo>/` (a project site), the workflow sets the correct `baseURL` for you. For a user site (`<user>.github.io`) or a custom domain, set `baseURL` in `hugo.toml` and add a `CNAME` file to `static/` for a custom domain.

### Cloudflare Pages (alternative)

- Framework preset: **Hugo**
- Build command: `hugo --gc --minify`
- Build output directory: `public`
- Environment variable: `HUGO_VERSION = 0.168.0`

## Project structure

```
config/_default/   site + theme configuration
content/
  posts/           blog posts (one folder per post)
  about.md
  cv.md
  certifications.md
assets/img/        avatar and other pipeline-processed images
static/            files served as-is (PDFs, CNAME, etc.)
themes/congo/      the theme (git submodule)
.github/workflows/ GitHub Pages deploy
```
