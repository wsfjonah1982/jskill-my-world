"""Build project_overview.html, the "My World" page: characters (sheets, facts, voices), group pictures, the world,
locations, props, how stories are made, the project documents and, at the bottom, the Tasks list (date and topic,
newest first) linking to each task's pages. Every linked page gets a nav bar back here (pagenav.py).

Everything is read from world.json, Identities.md and Setting.md and the files in _asset/, so re-running it after a
canon change keeps the page in sync. Media are linked with relative paths (the page is opened locally).

Usage:  python build_overview.py [--world DIR]
"""
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pagenav  # noqa: E402
import worldlib as wl  # noqa: E402

e = html.escape
DOCS = [("Identities.md", "Characters and voices"), ("Setting.md", "World, locations, props"),
        ("README.md", "Status and session log"), ("world.json", "Manifest and format")]
STEPS = [("Topic", "You give a topic or idea"), ("Keyframes", "Designs rendered, you pick 👍/👎 on keyframes.html"),
         ("Script", "Timed shots and dialogue from the canon"),
         ("Short footage", "One clip from an approved keyframe"),
         ("Long take", "Storyboard first, then segments stitched into one film")]


class Overview:
    def __init__(self, world):
        self.w = world
        self.setting = (world.root / "Setting.md").read_text(encoding="utf-8")

    def exists(self, rel):
        return (self.w.root / rel).is_file()

    def img(self, rel, alt, cls=""):
        if not rel or not self.exists(rel):
            return f"<div class='ph {cls}'>No picture yet</div>"
        return f"<a href='{e(rel)}' target=_blank><img class='{cls}' src='{e(rel)}' alt='{e(alt)}' loading=lazy></a>"

    def location_notes(self):
        """From Setting.md headings `#### Title (`key`)`: key → (title, summary, layout_only)."""
        out = {}
        for m in re.finditer(r"^#{3,4}\s+(.+?)\s*\((`[^)]*`)\)\s*\n(.*?)(?=^#{2,4}\s|\Z)", self.setting, re.S | re.M):
            title, keys, body = m.group(1), re.findall(r"`([\w-]+)`", m.group(2)), m.group(3)
            ref_line = next((l for l in body.splitlines() if l.startswith("Reference")), "")
            text = " ".join(l[2:].strip() for l in body.splitlines() if l.startswith("- "))
            if not text:
                para = body.split("<!--")[0]
                text = re.sub(r"^Reference[^.]*\.\s*", "", " ".join(l.strip() for l in para.splitlines() if l.strip()))
            text = re.sub(r"\*\*|`", "", text)
            for k in keys:
                out[k] = (title if len(keys) == 1 else f"{title} · {k}", text, "layout only" in ref_line)
        return out

    def props(self):
        """Recurring props table in Setting.md (| Prop | Look |) with optional `Reference: path`, plus any picture in
        _asset/props/ the table does not name."""
        rows, seen = [], set()
        if "## Recurring props" in self.setting:
            sec = self.setting[self.setting.index("## Recurring props"):]
            sec = sec[:sec.find("<!--")] if "<!--" in sec else sec
            for a, b in re.findall(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|$", sec, re.M):
                if a.strip() in ("Prop", "---") or set(a.strip()) <= {"-"}:
                    continue
                m = re.search(r"\s*Reference:\s*`([^`]+)`", b)
                desc = re.sub(r"\*\*|`", "", b[:m.start()] if m else b).strip().rstrip(" .")
                pic = m.group(1) if m else ""
                seen.add(Path(pic).name)
                rows.append((a.strip(), desc, pic))
        pdir = self.w.root / "_asset" / "props"
        for f in sorted(pdir.glob("*.png")) if pdir.is_dir() else []:
            if f.name not in seen:
                rows.append((f.stem.replace("_", " ").capitalize(), "", wl.rel(f, self.w.root)))
        return rows

    def task_row(self, task):
        topic = pagenav.task_title(task)
        pages = pagenav.task_pages(task)
        label = e(topic)
        if pages:
            label = f"<a href='{e(wl.rel(pages[0][1], self.w.root))}'>{label}</a>"
        sub = " · ".join(f"<a href='{e(wl.rel(p, self.w.root))}'>{e(l)}</a>" for l, p in pages[1:])
        return f"<li><time>{e(task.name[:10])}</time><span>{label}{f'<small> · {sub}</small>' if sub else ''}</span></li>"

    def build(self):
        w, cfg = self.w, self.w.cfg
        vdir = w.root / "_reference" / "voices"
        meta = json.loads((vdir / "voices_meta.json").read_text(encoding="utf-8")) if (vdir / "voices_meta.json").is_file() else {}
        samples = json.loads((vdir / "samples.json").read_text(encoding="utf-8")) if (vdir / "samples.json").is_file() else {}

        chars = ""
        for k, c in w.chars.items():
            clip = f"_asset/voices/{k}.wav"
            dur = meta.get(f"{k}.wav", {}).get("duration")
            voice = w.blocks().get("voice:" + k, "")
            quote = samples.get("samples", {}).get(k)
            vhtml = ""
            if voice or self.exists(clip):
                vhtml = ("<h4>Voice</h4>" + (f"<audio controls preload=none src='{clip}'></audio>" if self.exists(clip) else
                                             "<p class=mut>No voice clip yet</p>")
                         + (f"<p class=mut>{e(voice)}</p>" if voice else "")
                         + (f"<p class=quote>“{e(quote)}”</p>" if quote else "")
                         + (f"<p class=mut>{e(c.get('voice_src', ''))}{f' · {dur}s' if dur else ''}</p>" if c.get('voice_src') or dur else ""))
            tag = " · ".join(filter(None, (c.get("label"), c.get("tag"))))
            sheet_rel = wl.rel(w.sheet(k), w.root)
            chars += (f"<article class=card style='--accent:{e(c.get('colour', '#888'))}'>{self.img(sheet_rel, c['name'] + ' sheet', 'sheet')}"
                      f"<div class=pad><h3>{e(c['name'])} <small>{e(tag)}</small></h3>"
                      f"<ul>{''.join(f'<li>{e(f)}</li>' for f in c.get('facts', []))}</ul>{vhtml}</div></article>")

        groups = [(g["path"], g.get("caption", "")) for g in cfg.get("groups", [])]
        if w.height_chart() and not any(Path(p).name == w.height_chart().name for p, _ in groups):
            groups.append((wl.rel(w.height_chart(), w.root), "Height chart: true relative sizes"))
        groups_html = "".join(f"<figure class=card>{self.img(p, cap)}<figcaption class=pad>{e(cap)}</figcaption></figure>"
                              for p, cap in groups)

        dialogue = ""
        if samples.get("turns"):
            dn = samples["name"] + "_dialogue"
            src = next((f"_reference/voices/{n}.wav" for n in (dn + "_tight", dn) if self.exists(f"_reference/voices/{n}.wav")), "")
            turns = "".join(f"<li><b>{e(w.char_name(t['speaker']))}:</b> {e(t['text'])}</li>" for t in samples["turns"])
            dialogue = (f"<section id=voices><h2>Voices</h2><p class=lead>{e(cfg.get('voices_lead', 'The characters talking together.'))}</p>"
                        f"<article class='card pad'><h3>{e(samples.get('title', 'Sample scene'))}</h3>"
                        + (f"<audio controls preload=none src='{src}'></audio>" if src else "")
                        + f"<ol class=turns>{turns}</ol><p class=mut>All clips on <a href='_reference/voices/voices.html'>voices.html</a>.</p></article></section>")

        world_cards = "".join(f"<div><h3>{e(c['title'])}</h3><p>{e(c['text'])}</p></div>" for c in cfg.get("world_cards", []))
        if not world_cards and "world" in w.blocks():
            world_cards = f"<div><h3>The world</h3><p>{e(w.get('world'))}</p></div>"

        notes = self.location_notes()
        locs = ""
        for k in w.locations():
            title, summary, layout_only = notes.get(k, (k.replace("_", " ").capitalize(), w.get("location:" + k), False))
            pic = wl.rel(w.location_image(k), w.root)
            badge = ("<span class='badge warn'>Older render, layout only</span>" if layout_only else
                     "" if self.exists(pic) else "<span class=badge>Picture needed</span>")
            locs += (f"<article class=card>{self.img(pic, title)}<div class=pad><h3>{e(title)}</h3>"
                     f"<p><code>{e(k)}</code> {badge}</p><p>{e(summary[:320])}</p></div></article>")

        prop_cards = "".join(f"<figure class=card>{self.img(pic, name)}<figcaption class=pad><b>{e(name)}</b>"
                             f"{f' · {e(desc)}' if desc else ''}</figcaption></figure>"
                             for name, desc, pic in self.props() if pic)
        props_html = (f"<section id=props><h2>Props</h2><p class=lead>Designed props look the same every time they "
                      f"appear. The full list is in <a href=Setting.md>Setting.md</a>.</p><div class=grid>{prop_cards}</div></section>"
                      if prop_cards else "")

        diagram = cfg.get("workflow_diagram")
        steps = (f"<a href='{e(diagram)}' target=_blank><img class=diagram src='{e(diagram)}' alt='Workflow diagram'></a>"
                 if diagram and self.exists(diagram) else
                 "<ol class=steps>" + "".join(f"<li><b>{e(a)}</b><span>{e(b)}</span></li>" for a, b in STEPS) + "</ol>")

        task_rows = "".join(self.task_row(t) for t in pagenav.tasks(w))
        task_list = f"<ul class=tasks>{task_rows}</ul>" if task_rows else "<p class=mut>No stories yet: give a topic to start one.</p>"
        docs = "".join(f"<a class=doc href='{e(f)}'><b>{e(f)}</b><span>{e(d)}</span></a>"
                       for f, d in DOCS + [tuple(x) for x in cfg.get("docs", [])] if self.exists(f))
        chips = "".join(f"<span>{e(c)}</span>" for c in cfg.get("chips", []))
        nav = [("characters", "Characters")] + ([("voices", "Voices")] if dialogue else []) + \
              [("world", "World"), ("locations", "Locations")] + ([("props", "Props")] if props_html else []) + \
              [("workflow", "Workflow"), ("docs", "Docs"), ("tasks", "Tasks")]

        page = f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>{e(w.name)}</title>
<style>
:root{{--bg:#f5f8f7;--fg:#1c2928;--mut:#5b6e6b;--card:#fff;--line:#dce6e4;--brand:#2f7d73;--warn:#b56b16;--chip:#eef4f3}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#121818;--fg:#e5eeec;--mut:#9cb0ad;--card:#1b2423;--line:#2c3a39;--brand:#6cc3b6;--warn:#e7a456;--chip:#22302f}}}}
:root[data-theme=dark]{{--bg:#121818;--fg:#e5eeec;--mut:#9cb0ad;--card:#1b2423;--line:#2c3a39;--brand:#6cc3b6;--warn:#e7a456;--chip:#22302f}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1180px;margin:auto;padding:28px 16px 64px}} a{{color:var(--brand)}}
header h1{{font-size:clamp(26px,4vw,38px);margin:0 0 6px}} header p{{color:var(--mut);margin:0;max-width:760px}}
.facts{{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0 0}} .facts span{{background:var(--chip);border:1px solid var(--line);border-radius:99px;padding:3px 12px;font-size:13px}}
nav.sec{{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);margin:20px -16px 0;padding:10px 16px;display:flex;gap:16px;overflow-x:auto;white-space:nowrap}}
nav.sec a{{text-decoration:none;font-weight:600;font-size:14px}}
section{{margin-top:40px;scroll-margin-top:56px}} h2{{font-size:22px;margin:0 0 4px}} .lead{{color:var(--mut);margin:0 0 16px}}
.grid{{display:grid;gap:16px;grid-template-columns:repeat(auto-fill,minmax(min(280px,100%),1fr))}} .grid.three{{grid-template-columns:repeat(auto-fill,minmax(min(320px,100%),1fr))}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;margin:0}}
.card[style]{{border-top:5px solid var(--accent)}} .pad{{padding:14px 16px}}
.card img,.ph{{display:block;width:100%;aspect-ratio:16/9;object-fit:cover;background:var(--chip)}}
.card img.sheet,.ph.sheet{{aspect-ratio:4/3;object-fit:contain}}
.ph{{display:grid;place-items:center;color:var(--mut);font-size:13px;border-bottom:1px dashed var(--line)}}
h3{{margin:0 0 6px;font-size:17px}} h3 small{{font-weight:400;color:var(--mut);font-size:13px}} h4{{margin:12px 0 4px;font-size:14px}}
ul{{margin:0;padding-left:18px}} li{{margin:2px 0}} audio{{width:100%;margin:4px 0}}
.mut{{color:var(--mut);font-size:13px;margin:6px 0}} .quote{{font-style:italic;margin:6px 0}}
.badge{{display:inline-block;font-size:12px;border-radius:6px;padding:1px 8px;background:var(--chip);border:1px solid var(--line)}}
.badge.warn{{color:var(--warn)}} code{{font-size:12px;background:var(--chip);padding:1px 5px;border-radius:4px}}
.world{{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(min(260px,100%),1fr))}} .world div{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px}}
.docs{{display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(180px,1fr))}} .doc{{display:block;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px;text-decoration:none}}
.doc span{{display:block;color:var(--mut);font-size:13px}} img.diagram{{display:block;width:100%;height:auto;border:1px solid var(--line);border-radius:14px}}
.steps{{list-style:none;margin:0;padding:0;display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));counter-reset:s}}
.steps li{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px;counter-increment:s}}
.steps li b::before{{content:counter(s) ". ";color:var(--brand)}} .steps span{{display:block;color:var(--mut);font-size:13px}}
.tasks{{list-style:none;margin:0;padding:0;background:var(--card);border:1px solid var(--line);border-radius:14px}}
.tasks li{{display:flex;gap:16px;padding:10px 16px;margin:0;border-top:1px solid var(--line)}} .tasks li:first-child{{border-top:0}}
.tasks time{{color:var(--mut);font-variant-numeric:tabular-nums;flex:none}} .tasks small{{color:var(--mut)}} footer{{margin-top:48px;color:var(--mut);font-size:13px}}
</style></head><body><main>
<header><h1>{e(w.name)}</h1><p>{e(cfg.get('tagline', ''))}</p><div class=facts>{chips}</div></header>
<nav class=sec>{''.join(f'<a href=#{a}>{e(b)}</a>' for a, b in nav)}</nav>

<section id=characters><h2>Characters</h2><p class=lead>Canonical descriptions live in <a href=Identities.md>Identities.md</a>.
Every render uses these sheets as references.</p><div class='grid three'>{chars}</div>
{f"<h3 style='margin-top:24px'>Group references</h3><div class=grid>{groups_html}</div>" if groups_html else ""}</section>
{dialogue}
<section id=world><h2>The world</h2><p class=lead>From <a href=Setting.md>Setting.md</a>.</p><div class=world>{world_cards}</div></section>

<section id=locations><h2>Locations</h2><p class=lead>Each location has a key that story files name (<code>"location": "{e((w.locations() or ['key'])[0])}"</code>).</p><div class=grid>{locs}</div></section>
{props_html}
<section id=workflow><h2>How stories are made</h2><p class=lead>With the <b>world-stories</b> skill. You approve at every gate; videos are only rendered after approval.</p>{steps}</section>

<section id=docs><h2>Documents</h2><div class=docs>{docs}</div></section>

<section id=tasks><h2>Tasks</h2><p class=lead>One folder per topic in <code>_tasks/</code>, newest first. On each page, <b>Copy feedback</b> and paste it to the Agent.</p>{task_list}</section>
<footer>Generated {date.today()} by the my-world skill (<code>build_overview.py</code>). Re-run it after changing the canon, the assets or the tasks.</footer>
</main></body></html>"""
        w.overview.write_text(page, encoding="utf-8")
        print(w.overview)
        for p in pagenav.stamp_all(w):
            print("  linked", p.relative_to(w.root))


if __name__ == "__main__":
    wdir, _ = wl.pop_world_arg(sys.argv[1:])
    Overview(wl.World(wdir)).build()
