#!/usr/bin/env python3
"""
Local post admin for the Hugo portfolio.

A tiny, dependency-free web app to Create / Read / Update / Delete blog posts
without touching Markdown front matter by hand. It reads and writes the files
in content/posts/<slug>/index.md exactly the way Hugo expects.

Run it:
    python3 admin/admin.py
Then open http://localhost:1314

Keep `hugo server` running in another terminal to preview changes live.

This is a LOCAL authoring tool. It has no authentication and must never be
exposed to the internet. It binds to 127.0.0.1 only.
"""

import html
import json
import re
import shutil
import unicodedata
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# --- Paths -------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "content" / "posts"
HOST, PORT = "127.0.0.1", 1314

# --- Front matter helpers ----------------------------------------------------

FM_RE = re.compile(r"^\+\+\+\s*\n(.*?)\n\+\+\+\s*\n(.*)$", re.DOTALL)


def slugify(title: str) -> str:
    """Turn a title into a safe, lowercase, hyphenated folder name."""
    value = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    value = re.sub(r"[-\s]+", "-", value)
    return value or "untitled"


def parse_post(path: Path) -> dict:
    """Read an index.md into a dict of {title, date, draft, summary, tags, body}."""
    text = path.read_text(encoding="utf-8")
    m = FM_RE.match(text)
    fm_raw, body = (m.group(1), m.group(2)) if m else ("", text)

    post = {"title": "", "date": "", "draft": False, "summary": "", "tags": [], "body": body}
    for line in fm_raw.splitlines():
        line = line.strip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        if key == "title":
            post["title"] = val.strip('"')
        elif key == "date":
            post["date"] = val.strip('"')
        elif key == "draft":
            post["draft"] = val.lower() == "true"
        elif key == "summary":
            post["summary"] = val.strip('"')
        elif key == "tags":
            inner = val.strip("[]").strip()
            post["tags"] = [t.strip().strip('"') for t in inner.split(",") if t.strip()]
    return post


def render_front_matter(title, dt, draft, summary, tags) -> str:
    """Produce valid Hugo TOML front matter."""
    tag_list = ", ".join(f'"{t.strip()}"' for t in tags if t.strip())
    esc = lambda s: s.replace('"', '\\"')
    return (
        "+++\n"
        f'title = "{esc(title)}"\n'
        f"date = {dt}\n"
        f"draft = {'true' if draft else 'false'}\n"
        f'summary = "{esc(summary)}"\n'
        f"tags = [{tag_list}]\n"
        "showTableOfContents = true\n"
        "+++\n"
    )


def write_post(slug, title, dt, draft, summary, tags, body) -> Path:
    folder = POSTS_DIR / slug
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "index.md"
    content = render_front_matter(title, dt, draft, summary, tags) + "\n" + body.strip() + "\n"
    path.write_text(content, encoding="utf-8")
    return path


def list_posts() -> list:
    out = []
    if not POSTS_DIR.exists():
        return out
    for folder in sorted(POSTS_DIR.iterdir()):
        index = folder / "index.md"
        if folder.is_dir() and index.exists():
            p = parse_post(index)
            p["slug"] = folder.name
            out.append(p)
    out.sort(key=lambda x: x.get("date", ""), reverse=True)
    return out


# --- HTML UI -----------------------------------------------------------------

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Post Admin</title>
<style>
  :root {{ color-scheme: light dark; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
         max-width: 820px; margin: 0 auto; padding: 1.5rem; line-height: 1.5;
         background: #0f172a; color: #e2e8f0; }}
  h1, h2 {{ color: #fff; }}
  a {{ color: #60a5fa; }}
  .bar {{ display: flex; gap: .5rem; align-items: center; flex-wrap: wrap;
          margin-bottom: 1.25rem; }}
  .btn {{ display: inline-block; background: #2563eb; color: #fff; border: 0;
          padding: .5rem .9rem; border-radius: .5rem; cursor: pointer;
          text-decoration: none; font-size: .9rem; }}
  .btn.sec {{ background: #334155; }}
  .btn.danger {{ background: #b91c1c; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: .6rem;
           padding: 1rem; margin-bottom: .8rem; }}
  .card h3 {{ margin: 0 0 .3rem; }}
  .meta {{ font-size: .82rem; color: #94a3b8; }}
  .tag {{ display: inline-block; background: #334155; border-radius: .4rem;
          padding: .05rem .5rem; font-size: .75rem; margin-right: .3rem; }}
  .draft {{ color: #fbbf24; font-weight: 600; }}
  label {{ display: block; margin: .8rem 0 .25rem; font-weight: 600; font-size: .9rem; }}
  input, textarea {{ width: 100%; padding: .55rem; border-radius: .45rem;
          border: 1px solid #475569; background: #0f172a; color: #e2e8f0;
          font-size: .95rem; font-family: inherit; }}
  textarea {{ min-height: 320px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
  .row {{ display: flex; gap: 1rem; flex-wrap: wrap; }}
  .row > div {{ flex: 1; min-width: 180px; }}
  .hint {{ font-size: .8rem; color: #94a3b8; margin-top: .2rem; }}
  .flash {{ background: #065f46; color: #d1fae5; padding: .6rem .9rem;
            border-radius: .5rem; margin-bottom: 1rem; }}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def layout(body: str) -> bytes:
    return PAGE.format(body=body).encode("utf-8")


def list_view(flash: str = "") -> str:
    rows = []
    for p in list_posts():
        tags = "".join(f'<span class="tag">{html.escape(t)}</span>' for t in p["tags"])
        draft = '<span class="draft">● DRAFT</span>' if p["draft"] else '<span style="color:#34d399">● published</span>'
        rows.append(f"""
        <div class="card">
          <h3>{html.escape(p['title'])}</h3>
          <div class="meta">{html.escape(p['date'])} · {draft} · {tags}</div>
          <p class="meta">{html.escape(p['summary'])}</p>
          <div class="bar">
            <a class="btn" href="/edit?slug={p['slug']}">Edit</a>
            <a class="btn sec" href="http://localhost:1313/posts/{p['slug']}/" target="_blank">Preview</a>
            <form method="POST" action="/delete" style="display:inline"
                  onsubmit="return confirm('Delete \\'{html.escape(p['title'])}\\'? This cannot be undone.');">
              <input type="hidden" name="slug" value="{p['slug']}">
              <button class="btn danger" type="submit">Delete</button>
            </form>
          </div>
        </div>""")
    flash_html = f'<div class="flash">{html.escape(flash)}</div>' if flash else ""
    posts_html = "".join(rows) or '<p class="meta">No posts yet. Create your first one.</p>'
    return f"""
    <div class="bar">
      <h1 style="margin:0;flex:1">Post Admin</h1>
      <a class="btn" href="/new">+ New post</a>
    </div>
    {flash_html}
    {posts_html}
    <p class="hint">Edits write Markdown into <code>content/posts/</code>. Keep
    <code>hugo server</code> running to preview. This tool is local-only.</p>
    """


def edit_view(slug: str = "", flash: str = "") -> str:
    is_new = slug == ""
    if is_new:
        p = {"title": "", "date": date.today().isoformat(), "draft": True,
             "summary": "", "tags": [], "body": "Write your post in Markdown here.\n"}
    else:
        index = POSTS_DIR / slug / "index.md"
        if not index.exists():
            return list_view(flash=f"Post '{slug}' not found.")
        p = parse_post(index)
    title_label = "New post" if is_new else f"Editing: {html.escape(p['title'])}"
    checked = "checked" if p["draft"] else ""
    return f"""
    <div class="bar">
      <a class="btn sec" href="/">← All posts</a>
      <h1 style="margin:0;flex:1;font-size:1.3rem">{title_label}</h1>
    </div>
    <form method="POST" action="/save">
      <input type="hidden" name="original_slug" value="{html.escape(slug)}">
      <label>Title</label>
      <input name="title" required value="{html.escape(p['title'])}" placeholder="My Post Title">
      <div class="row">
        <div>
          <label>Date</label>
          <input name="date" value="{html.escape(p['date'])}" placeholder="2026-10-18">
        </div>
        <div>
          <label>Tags (comma-separated)</label>
          <input name="tags" value="{html.escape(', '.join(p['tags']))}" placeholder="kubernetes, aws">
        </div>
      </div>
      <label>Summary</label>
      <input name="summary" value="{html.escape(p['summary'])}" placeholder="One or two sentences shown on the blog list.">
      <label><input type="checkbox" name="draft" {checked} style="width:auto"> Draft (unchecked = published)</label>
      <label>Body (Markdown)</label>
      <textarea name="body">{html.escape(p['body'].strip())}</textarea>
      <div class="bar" style="margin-top:1rem">
        <button class="btn" type="submit">Save</button>
        <a class="btn sec" href="/">Cancel</a>
      </div>
    </form>
    """


# --- HTTP handler ------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def _send(self, body: bytes, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/":
            self._send(layout(list_view(flash=q.get("flash", [""])[0])))
        elif u.path == "/new":
            self._send(layout(edit_view(slug="")))
        elif u.path == "/edit":
            self._send(layout(edit_view(slug=q.get("slug", [""])[0])))
        else:
            self._send(layout('<p>Not found. <a href="/">Home</a></p>'), status=404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        data = parse_qs(self.rfile.read(length).decode("utf-8"))
        get = lambda k, d="": data.get(k, [d])[0]

        if self.path == "/save":
            title = get("title").strip()
            if not title:
                return self._redirect("/new")
            dt = get("date").strip() or date.today().isoformat()
            draft = "draft" in data
            summary = get("summary").strip()
            tags = [t.strip() for t in get("tags").split(",") if t.strip()]
            body = get("body")
            original = get("original_slug").strip()
            new_slug = slugify(title)

            # Rename folder if the title (and thus slug) changed on an existing post.
            if original and original != new_slug:
                old_folder = POSTS_DIR / original
                new_folder = POSTS_DIR / new_slug
                if old_folder.exists() and not new_folder.exists():
                    # move any images/assets too, then rewrite index.md
                    shutil.move(str(old_folder), str(new_folder))
            slug = new_slug
            write_post(slug, title, dt, draft, summary, tags, body)
            return self._redirect(f"/?flash=Saved '{title}'")

        if self.path == "/delete":
            slug = get("slug").strip()
            folder = POSTS_DIR / slug
            if slug and folder.exists() and folder.is_dir() and POSTS_DIR in folder.parents:
                shutil.rmtree(folder)
                return self._redirect(f"/?flash=Deleted '{slug}'")
            return self._redirect("/?flash=Delete failed")

        self._send(layout("<p>Bad request</p>"), status=400)

    def log_message(self, *args):
        pass  # quiet


def main():
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Post admin running at http://{HOST}:{PORT}")
    print("Keep `hugo server` running in another terminal for live preview.")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
