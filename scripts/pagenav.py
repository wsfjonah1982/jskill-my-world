"""Link every HTML page of a world together.

`stamp(world, page)` writes a navigation bar at the top of a page: a link back to the Tasks list on
world.html, the task the page belongs to, and tabs for the task's other pages. It sits between
`<!-- nav:start -->` and `<!-- nav:end -->`, so stamping again replaces it. Page generators stamp what they write;
build_overview.py restamps every page.

Usage:  python pagenav.py [--world DIR]       restamp all pages
"""
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import worldlib as wl  # noqa: E402

_NAV = re.compile(r"<!-- nav:start -->.*?<!-- nav:end -->\n?", re.S)
e = html.escape

STYLE = """<style>
.pnav{--pn-bg:#ffffff;--pn-fg:#1c2928;--pn-mut:#5b6e6b;--pn-line:#dce6e4;--pn-on:#2f7d73;--pn-chip:#eef4f3;
  background:var(--pn-bg);border-bottom:1px solid var(--pn-line);font:14px/1.4 system-ui,"Segoe UI",sans-serif;color:var(--pn-fg)}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]) .pnav{--pn-bg:#1b2423;--pn-fg:#e5eeec;--pn-mut:#9cb0ad;
  --pn-line:#2c3a39;--pn-on:#6cc3b6;--pn-chip:#22302f}}
:root[data-theme=dark] .pnav{--pn-bg:#1b2423;--pn-fg:#e5eeec;--pn-mut:#9cb0ad;--pn-line:#2c3a39;--pn-on:#6cc3b6;--pn-chip:#22302f}
.pnav .pn-in{max-width:1180px;margin:auto;padding:8px 16px;display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center}
.pnav a{color:var(--pn-on);text-decoration:none}.pnav a:hover{text-decoration:underline}
.pnav .pn-crumb{color:var(--pn-mut)}.pnav .pn-crumb b{color:var(--pn-fg);font-weight:600}
.pnav .pn-tabs{display:flex;flex-wrap:wrap;gap:6px;margin-left:auto}
.pnav .pn-tabs a,.pnav .pn-tabs span{border:1px solid var(--pn-line);border-radius:99px;padding:2px 10px;font-size:13px}
.pnav .pn-tabs span{background:var(--pn-chip);color:var(--pn-fg);font-weight:600}
</style>"""


def title_of(page):
    m = re.search(r"<title>(.*?)</title>", page.read_text(encoding="utf-8", errors="replace"), re.S)
    return html.unescape(m.group(1).strip()) if m else page.stem


def task_title(task):
    idea = task / "idea.json"
    if idea.is_file():
        return json.loads(idea.read_text(encoding="utf-8")).get("title", task.name)
    return task.name


def task_pages(task):
    """(label, path) for a task's pages: keyframes first, then the long-take storyboards, then the rest."""
    pages = [p for p in task.rglob("*.html") if "archive" not in p.relative_to(task).parts]

    def label(p):
        if p.name == "keyframes.html":
            return "Keyframes"
        if p.name == "storyboard.html":
            return f"Storyboard · {p.parent.name.replace('long_', '')}"
        return title_of(p)

    order = {"keyframes.html": 0, "storyboard.html": 1}
    pages.sort(key=lambda p: (order.get(p.name, 2), str(p)))
    return [(label(p), p) for p in pages]


def tasks(world):
    """Task folders, newest first."""
    d = world.tasks_dir
    return sorted((t for t in d.iterdir() if t.is_dir() and not t.name.startswith((".", "_"))),
                  key=lambda t: t.name, reverse=True) if d.is_dir() else []


def nav_html(world, page):
    page = Path(page).resolve()
    crumbs = [f"<a href='{wl.rel(world.overview, page.parent)}'>My World</a>"]
    tabs = ""
    task = next((p for p in page.parents if p.parent == world.tasks_dir), None)
    if task:
        crumbs.append(f"<a href='{wl.rel(world.overview, page.parent)}#tasks'>Tasks</a>")
        t, day = task_title(task), task.name[:10]
        crumbs.append(f"<b>{e(t)}</b>" + ("" if day in t else f" <span>({e(day)})</span>"))
        for label, p in task_pages(task):
            tabs += (f"<span>{e(label)}</span>" if p.resolve() == page
                     else f"<a href='{wl.rel(p, page.parent)}'>{e(label)}</a>")
    else:
        crumbs.append(f"<b>{e(title_of(page))}</b>")
    return (f"<!-- nav:start -->{STYLE}<nav class=pnav aria-label='World pages'><div class=pn-in>"
            f"<span class=pn-crumb>{' › '.join(crumbs)}</span>"
            f"{f'<span class=pn-tabs>{tabs}</span>' if tabs else ''}</div></nav><!-- nav:end -->\n")


def stamp(world, page):
    page = Path(page)
    text = _NAV.sub("", page.read_text(encoding="utf-8"))
    m = re.search(r"<body[^>]*>", text)
    if not m:
        return
    text = text[:m.end()] + "\n" + nav_html(world, page) + text[m.end():].lstrip("\n")
    page.write_text(text, encoding="utf-8")


def stamp_all(world):
    others = [world.p("_reference/voices/voices.html")]
    pages = [p for t in tasks(world) for _, p in task_pages(t)] + [p for p in others if p.is_file()]
    for p in pages:
        stamp(world, p)
    return pages


if __name__ == "__main__":
    wdir, _ = wl.pop_world_arg(sys.argv[1:])
    w = wl.World(wdir)
    for p in stamp_all(w):
        print(p.relative_to(w.root))
