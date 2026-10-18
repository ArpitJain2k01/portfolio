#!/usr/bin/env python3
"""
post — a tiny CLI to manage Hugo blog posts without editing front matter by hand.

Usage:
    python3 admin/post.py new "My Post Title" [--tags kubernetes,aws] [--summary "..."]
    python3 admin/post.py list
    python3 admin/post.py publish <slug>      # draft = false
    python3 admin/post.py unpublish <slug>    # draft = true
    python3 admin/post.py delete <slug>
    python3 admin/post.py open <slug>         # print the file path to edit

After `new`, edit content/posts/<slug>/index.md, then `publish` it.
Keep `hugo server` running to preview.
"""

import argparse
import re
import shutil
import sys
import unicodedata
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "content" / "posts"
FM_RE = re.compile(r"^\+\+\+\s*\n(.*?)\n\+\+\+\s*\n(.*)$", re.DOTALL)


def slugify(title: str) -> str:
    value = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    value = re.sub(r"[-\s]+", "-", value)
    return value or "untitled"


def post_path(slug: str) -> Path:
    return POSTS_DIR / slug / "index.md"


def cmd_new(args):
    slug = slugify(args.title)
    path = post_path(slug)
    if path.exists():
        sys.exit(f"✗ Post already exists: {path}")
    tags = ", ".join(f'"{t.strip()}"' for t in (args.tags or "").split(",") if t.strip())
    summary = (args.summary or "").replace('"', '\\"')
    title = args.title.replace('"', '\\"')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "+++\n"
        f'title = "{title}"\n'
        f"date = {date.today().isoformat()}\n"
        "draft = true\n"
        f'summary = "{summary}"\n'
        f"tags = [{tags}]\n"
        "showTableOfContents = true\n"
        "+++\n\n"
        "Write your post in Markdown here.\n",
        encoding="utf-8",
    )
    print(f"✓ Created {path}")
    print(f"  Edit it, then: python3 admin/post.py publish {slug}")


def _read_fm(path: Path):
    text = path.read_text(encoding="utf-8")
    m = FM_RE.match(text)
    return (m.group(1), m.group(2), text) if m else ("", text, text)


def _field(fm: str, key: str, default=""):
    m = re.search(rf"^{key}\s*=\s*(.*)$", fm, re.MULTILINE)
    return m.group(1).strip().strip('"') if m else default


def cmd_list(args):
    if not POSTS_DIR.exists():
        print("No posts.")
        return
    rows = []
    for folder in sorted(POSTS_DIR.iterdir()):
        idx = folder / "index.md"
        if folder.is_dir() and idx.exists():
            fm, _, _ = _read_fm(idx)
            rows.append((
                _field(fm, "date"),
                "draft" if _field(fm, "draft").lower() == "true" else "live",
                folder.name,
                _field(fm, "title"),
            ))
    rows.sort(reverse=True)
    if not rows:
        print("No posts.")
        return
    print(f"{'DATE':<12} {'STATE':<6} {'SLUG':<36} TITLE")
    for dt, state, slug, title in rows:
        print(f"{dt:<12} {state:<6} {slug:<36} {title}")


def _set_draft(slug: str, value: bool):
    path = post_path(slug)
    if not path.exists():
        sys.exit(f"✗ Not found: {slug}")
    text = path.read_text(encoding="utf-8")
    new = re.sub(r"^draft\s*=\s*(true|false)\s*$",
                 f"draft = {'true' if value else 'false'}", text,
                 count=1, flags=re.MULTILINE)
    path.write_text(new, encoding="utf-8")
    print(f"✓ {slug}: draft = {str(value).lower()}")


def cmd_publish(args):
    _set_draft(args.slug, False)


def cmd_unpublish(args):
    _set_draft(args.slug, True)


def cmd_delete(args):
    folder = POSTS_DIR / args.slug
    if not folder.exists() or not folder.is_dir():
        sys.exit(f"✗ Not found: {args.slug}")
    confirm = input(f"Delete '{args.slug}' and all its files? [y/N] ").strip().lower()
    if confirm == "y":
        shutil.rmtree(folder)
        print(f"✓ Deleted {args.slug}")
    else:
        print("Cancelled.")


def cmd_open(args):
    path = post_path(args.slug)
    if not path.exists():
        sys.exit(f"✗ Not found: {args.slug}")
    print(path)


def main():
    p = argparse.ArgumentParser(prog="post", description="Manage Hugo blog posts.")
    sub = p.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("new", help="create a new draft post")
    n.add_argument("title")
    n.add_argument("--tags", help="comma-separated, e.g. kubernetes,aws")
    n.add_argument("--summary", help="short summary for the blog list")
    n.set_defaults(func=cmd_new)

    sub.add_parser("list", help="list all posts").set_defaults(func=cmd_list)

    for name, fn, hlp in [
        ("publish", cmd_publish, "mark a post published (draft=false)"),
        ("unpublish", cmd_unpublish, "mark a post draft (draft=true)"),
        ("delete", cmd_delete, "delete a post and its folder"),
        ("open", cmd_open, "print the post's file path"),
    ]:
        s = sub.add_parser(name, help=hlp)
        s.add_argument("slug")
        s.set_defaults(func=fn)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
