"""Build world.html, the "My World" page: characters (sheets, facts, voices), group pictures, the world,
scenes, props, how stories are made, the project documents and, at the bottom, the Tasks list (date and topic,
newest first) linking to each task's pages. Every linked page gets a nav bar back here (pagenav.py).

Everything is read from world.json, Identities.md and Setting.md and the files in _asset/, so re-running it after a
canon change keeps the page in sync. Media are linked with relative paths (the page is opened locally).

Usage:  python build_overview.py [--world DIR]
"""
import hashlib
import html
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pagenav  # noqa: E402
import worldlib as wl  # noqa: E402

e = html.escape
DOCS = [("Identities.md", "Characters and voices"), ("Setting.md", "World, scenes, props"),
        ("world.md", "Status and session log"), ("world.json", "Manifest and format")]
STEPS = [("Topic", "You give a topic or idea"), ("Keyframes", "Designs rendered, you pick 👍/👎 on keyframes.html"),
         ("Script", "Timed shots and dialogue from the canon"),
         ("Short footage", "One clip from an approved keyframe"),
         ("Long take", "Storyboard first, then segments stitched into one film")]


FEEDBACK_HTML = '\n<div class=fbbar><span id=fbSum>No feedback yet</span><button type=button id=fbOpen>Feedback</button></div>\n<dialog id=fbdlg><div class=dlghead><b>Your feedback</b><button type=button class=x aria-label=Close onclick="this.closest(\'dialog\').close()">×</button></div>\n<div class=dlgbody><p class=mut>👍 Like approves a design. 👎 Unlike asks for changes: say what in a comment. Your choices are kept in this browser.\nWhen done, click <b>Copy feedback</b> and paste it to the Agent (or <b>Download</b> it and give the file).</p>\n<h4>General comments</h4><textarea id=fbGeneral rows=3 placeholder="Anything about the whole world: style, characters, places, voices…"></textarea>\n<h4>Per design</h4><ul id=fbList></ul>\n<p class=fbbtns><button type=button id=fbCopy>Copy feedback</button> <button type=button id=fbDown>Download</button>\n<button type=button id=fbClear>Clear</button> <span id=fbToast class=mut></span></p></div></dialog>\n<script>\n(()=>{const WID=__WID__,KEY=\'myworld-feedback-\'+WID;let st={items:{},general:\'\'};\ntry{st=Object.assign(st,JSON.parse(localStorage.getItem(KEY)||\'{}\'))}catch(e){}\nconst save=()=>{try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){}summary()};\nconst bars=[...document.querySelectorAll(\'.fb\')];\nconst item=b=>{const it=st.items[b.dataset.asset]||(st.items[b.dataset.asset]={label:b.dataset.label,vote:null,comment:\'\'});it.v=b.dataset.v;return it};\nfunction paint(b){const it=st.items[b.dataset.asset]||{},old=!!(it.v&&b.dataset.v&&it.v!==b.dataset.v),v=old?null:it.vote||(b.dataset.approved&&!(\'vote\' in it)?\'like\':null);\n b.querySelector(\'.fb-old\').hidden=!(old&&(it.vote||it.comment));\n b.querySelector(\'.fb-like\').classList.toggle(\'on\',v===\'like\');b.querySelector(\'.fb-unlike\').classList.toggle(\'on\',v===\'unlike\');\n const t=b.querySelector(\'.fb-text\');if(it.comment){t.hidden=false;t.value=it.comment}\n b.querySelector(\'.fb-cm\').classList.toggle(\'on\',!!it.comment)}\nbars.forEach(b=>{paint(b);\n b.querySelector(\'.fb-like\').onclick=()=>{const it=item(b);it.vote=it.vote===\'like\'?null:\'like\';paint(b);save()};\n b.querySelector(\'.fb-unlike\').onclick=()=>{const it=item(b);it.vote=it.vote===\'unlike\'?null:\'unlike\';paint(b);\n  const t=b.querySelector(\'.fb-text\');if(it.vote===\'unlike\'){t.hidden=false;t.focus()}save()};\n b.querySelector(\'.fb-cm\').onclick=()=>{const t=b.querySelector(\'.fb-text\');t.hidden=!t.hidden;if(!t.hidden)t.focus()};\n b.querySelector(\'.fb-text\').oninput=ev=>{item(b).comment=ev.target.value;b.querySelector(\'.fb-cm\').classList.toggle(\'on\',!!ev.target.value);save()}});\nconst g=document.getElementById(\'fbGeneral\');g.value=st.general||\'\';g.oninput=()=>{st.general=g.value;save()};\nconst used=()=>Object.entries(st.items).filter(([,i])=>i.vote||(i.comment||\'\').trim());\nfunction summary(){const u=used(),l=u.filter(([,i])=>i.vote===\'like\').length,d=u.filter(([,i])=>i.vote===\'unlike\').length,\n c=u.filter(([,i])=>(i.comment||\'\').trim()).length+((st.general||\'\').trim()?1:0);\n document.getElementById(\'fbSum\').textContent=(l||d||c)?`👍 ${l} · 👎 ${d} · 💬 ${c}`:\'No feedback yet\';\n document.getElementById(\'fbList\').innerHTML=u.length?u.map(([a,i])=>`<li><b>${i.vote===\'like\'?\'👍\':i.vote===\'unlike\'?\'👎\':\'💬\'} ${esc(i.label)}</b>`+\n  `${(i.comment||\'\').trim()?\' — \'+esc(i.comment):\'\'}</li>`).join(\'\'):\'<li class=mut>Nothing yet: use the buttons under each picture or voice.</li>\'}\nconst esc=s=>String(s).replace(/[&<>"]/g,c=>({\'&\':\'&amp;\',\'<\':\'&lt;\',\'>\':\'&gt;\',\'"\':\'&quot;\'}[c]));\nconst payload=()=>JSON.stringify({type:\'my-world-feedback\',version:2,world_id:WID,page:\'world.html\',date:new Date().toISOString(),\n general:(st.general||\'\').trim(),items:used().map(([a,i])=>({asset:a,label:i.label,vote:i.vote||null,comment:(i.comment||\'\').trim(),seen_version:i.v||null,current_version:(document.querySelector(`.fb[data-asset="${a}"]`)||{dataset:{}}).dataset.v||null}))},null,2);\nconst toast=m=>{const t=document.getElementById(\'fbToast\');t.textContent=m;setTimeout(()=>t.textContent=\'\',2500)};\ndocument.getElementById(\'fbOpen\').onclick=()=>{summary();document.getElementById(\'fbdlg\').showModal()};\ndocument.getElementById(\'fbCopy\').onclick=async()=>{const txt=payload();try{await navigator.clipboard.writeText(txt);toast(\'Copied: paste it to the Agent\')}\n catch(e){const ta=document.createElement(\'textarea\');ta.value=txt;document.body.appendChild(ta);ta.select();document.execCommand(\'copy\');ta.remove();toast(\'Copied\')}};\ndocument.getElementById(\'fbDown\').onclick=()=>{const a=document.createElement(\'a\');a.href=URL.createObjectURL(new Blob([payload()],{type:\'application/json\'}));\n a.download=\'feedback.json\';a.click();URL.revokeObjectURL(a.href)};\ndocument.getElementById(\'fbClear\').onclick=()=>{if(confirm(\'Clear all your likes and comments on this page?\')){st={items:{},general:\'\'};g.value=\'\';\n bars.forEach(b=>{const t=b.querySelector(\'.fb-text\');t.value=\'\';t.hidden=true;paint(b)});save()}};\ndocument.getElementById(\'fbdlg\').addEventListener(\'click\',ev=>{if(ev.target.id===\'fbdlg\')ev.target.close()});summary()})();\n</script>'


class Overview:
    def __init__(self, world):
        self.w = world
        self.setting = (world.root / "Setting.md").read_text(encoding="utf-8")

    def exists(self, rel):
        return (self.w.root / rel).is_file()

    def ver(self, rel):
        """Short content hash of an asset: changes whenever it is redrawn (cache-busting and feedback versions)."""
        f = self.w.root / rel
        return hashlib.sha1(f.read_bytes()).hexdigest()[:10] if f.is_file() else ""

    def src(self, rel):
        """URL of an asset with its version, so a browser or CDN never shows an old copy after a redraw."""
        v = self.ver(rel)
        return f"{rel}?v={v}" if v else rel

    def approved_now(self):
        """{asset path: date} of the user's approvals that still hold (the asset has not changed since)."""
        out = {}
        for rel, day in self.w.cfg.get("approved", {}).items():
            f = self.w.root / rel
            if f.is_file() and datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d") <= day:
                out[rel] = day
        return out

    def fb(self, rel, label):
        """Like / Unlike / Comment bar for one asset; the page script keeps the choice in the browser."""
        if not rel or not self.exists(rel):
            return ""
        day = self._approved.get(rel, "")
        return (f"<div class=fb data-asset='{e(rel)}' data-label='{e(label)}' data-approved='{e(day)}' data-v='{self.ver(rel)}'>"
                "<button type=button class=fb-like title='Like: approve this design'>👍 Like</button>"
                "<button type=button class=fb-unlike title='Unlike: needs changes (say what in a comment)'>👎 Unlike</button>"
                "<button type=button class=fb-cm>💬 Comment</button>"
                + (f"<span class=fb-ok>Approved {e(day)}</span>" if day else "")
                + "<span class=fb-old hidden>Redrawn since your feedback: please look again</span>"
                + f"<textarea class=fb-text rows=2 hidden placeholder='What should change in {e(label)}?'></textarea></div>")

    def img(self, rel, alt, cls=""):
        if not rel or not self.exists(rel):
            return f"<div class='ph {cls}'>No picture yet</div>"
        return f"<a href='{e(self.src(rel))}' target=_blank><img class='{cls}' src='{e(self.src(rel))}' alt='{e(alt)}' loading=lazy></a>"

    def scene_notes(self):
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
        self._approved = self.approved_now()
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
                vhtml = ("<h4>Voice</h4>" + (f"<audio controls preload=none src='{e(self.src(clip))}'></audio>" if self.exists(clip) else
                                             "<p class=mut>No voice clip yet</p>") + self.fb(clip, c["name"] + " voice")
                         + (f"<p class=mut>{e(voice)}</p>" if voice else "")
                         + (f"<p class=quote>“{e(quote)}”</p>" if quote else "")
                         + (f"<p class=mut>{e(c.get('voice_src', ''))}{f' · {dur}s' if dur else ''}</p>" if c.get('voice_src') or dur else ""))
            tag = " · ".join(filter(None, (c.get("label"), c.get("tag"))))
            sheet_rel = wl.rel(w.sheet(k), w.root)
            chars += (f"<article class=card style='--accent:{e(c.get('colour', '#888'))}'>{self.img(sheet_rel, c['name'] + ' sheet', 'sheet')}"
                      f"<div class=pad><h3>{e(c['name'])} <small>{e(tag)}</small></h3>{self.fb(sheet_rel, c['name'] + ' sheet')}"
                      f"<ul>{''.join(f'<li>{e(f)}</li>' for f in c.get('facts', []))}</ul>{vhtml}</div></article>")

        groups = [(g["path"], g.get("caption", "")) for g in cfg.get("groups", [])]
        if w.height_chart() and not any(Path(p).name == w.height_chart().name for p, _ in groups):
            groups.append((wl.rel(w.height_chart(), w.root), "Height chart: true relative sizes"))
        groups_html = "".join(f"<figure class=card>{self.img(p, cap)}<figcaption class=pad>{e(cap)}"
                              f"{self.fb(p, Path(p).stem.replace('_', ' ') + ' (group picture)')}</figcaption></figure>"
                              for p, cap in groups)

        dialogue = ""
        if samples.get("turns"):
            dn = samples["name"] + "_dialogue"
            src = next((f"_reference/voices/{n}.wav" for n in (dn + "_tight", dn) if self.exists(f"_reference/voices/{n}.wav")), "")
            turns = "".join(f"<li><b>{e(w.char_name(t['speaker']))}:</b> {e(t['text'])}</li>" for t in samples["turns"])
            dialogue = (f"<section id=voices><h2>Voices</h2><p class=lead>{e(cfg.get('voices_lead', 'The characters talking together.'))}</p>"
                        f"<article class='card pad'><h3>{e(samples.get('title', 'Sample scene'))}</h3>"
                        + (f"<audio controls preload=none src='{e(self.src(src))}'></audio>" if src else "")
                        + self.fb(f"_reference/voices/{dn}.wav", "Sample dialogue")
                        + f"<ol class=turns>{turns}</ol><p class=mut>All clips on <a href='_reference/voices/voices.html'>voices.html</a>.</p></article></section>")

        world_cards = "".join(f"<div><h3>{e(c['title'])}</h3><p>{e(c['text'])}</p></div>" for c in cfg.get("world_cards", []))
        if not world_cards and "world" in w.blocks():
            world_cards = f"<div><h3>The world</h3><p>{e(w.get('world'))}</p></div>"

        notes = self.scene_notes()
        locs = ""
        for k in w.scenes():
            title, summary, layout_only = notes.get(k, (k.replace("_", " ").capitalize(), w.get("scene:" + k), False))
            pic = wl.rel(w.scene_image(k), w.root)
            badge = ("<span class='badge warn'>Older render, layout only</span>" if layout_only else
                     "" if self.exists(pic) else "<span class=badge>Picture needed</span>")
            locs += (f"<article class=card>{self.img(pic, title)}<div class=pad><h3>{e(title)}</h3>{self.fb(pic, title + ' (set)')}"
                     f"<p><code>{e(k)}</code> {badge}</p><p>{e(summary[:320])}</p></div></article>")

        prop_cards = "".join(f"<figure class=card>{self.img(pic, name)}<figcaption class=pad><b>{e(name)}</b>"
                             f"{f' · {e(desc)}' if desc else ''}{self.fb(pic, name + ' (prop)')}</figcaption></figure>"
                             for name, desc, pic in self.props())
        props_html = (f"<section id=props><h2>Props</h2><p class=lead>Characters, scenes and props are the three "
                      f"factors of the world: each prop looks the same every time it appears. The full list is in "
                      f"<a href=Setting.md>Setting.md</a>.</p><div class=grid>{prop_cards or '<p class=mut>No props yet.</p>'}</div></section>")

        diagram = cfg.get("workflow_diagram")
        steps = (f"<a href='{e(diagram)}' target=_blank><img class=diagram src='{e(diagram)}' alt='Workflow diagram'></a>"
                 if diagram and self.exists(diagram) else
                 "<ol class=steps>" + "".join(f"<li><b>{e(a)}</b><span>{e(b)}</span></li>" for a, b in STEPS) + "</ol>")

        task_rows = "".join(self.task_row(t) for t in pagenav.tasks(w))
        task_list = f"<ul class=tasks>{task_rows}</ul>" if task_rows else "<p class=mut>No stories yet: give a topic to start one.</p>"
        docs = "".join(f"<a class=doc href='{e(f)}'><b>{e(f)}</b><span>{e(d)}</span></a>"
                       for f, d in DOCS + [tuple(x) for x in cfg.get("docs", [])] if self.exists(f))
        chips = "".join(f"<span>{e(c)}</span>" for c in cfg.get("chips", []))
        evp = w.root / "_reference" / "evaluation" / "evaluation.json"
        ev = json.loads(evp.read_text(encoding="utf-8")) if evp.is_file() else None
        eval_html = ""
        usp = w.root / "_reference" / "log" / "usage.json"
        us = json.loads(usp.read_text(encoding="utf-8")) if usp.is_file() else None
        usage_html = ""
        if us:
            k = lambda n: f"{n / 1e6:.2f}M" if n >= 1e6 else f"{n / 1e3:.1f}k" if n >= 1e3 else str(n)
            grow = "".join(f"<tr><td>{e(x['model'])}</td><td>{x['calls']}</td><td>{e(', '.join(f'{n} {t}' for t, n in x['kinds'].items()))}</td>"
                           f"<td>{x['failed']}</td><td>{k(x['tokens']) if x['tokens'] else '–'}</td>"
                           f"<td>{str(x.get('audio_s')) + ' s' if x.get('audio_s') else '–'}</td></tr>" for x in us["generation"])
            arow = "".join(f"<tr><td>{e(x['model'])}</td><td>{x['sessions']}</td><td>{x['requests']}</td><td>{k(x['input'])}</td>"
                           f"<td>{k(x['cache_write'])}</td><td>{k(x['cache_read'])}</td><td>{k(x['output'])}</td>"
                           f"<td><b>{k(x['total'])}</b></td></tr>" for x in us["agent"])
            usage_html = (f"<section id=usage><h2>Model usage</h2><p class=lead>Every model call, from "
                          f"<code>_reference/log/llm_usage.jsonl</code> and the agent's session transcripts "
                          f"(<code>llm_usage.py</code>); updated {e(us['date'][:16].replace('T', ' '))} UTC.</p><div class=evals>"
                          f"<div class=card><b>{us['generation_calls']}</b><span>Generation calls</span></div>"
                          f"<div class=card><b>{k(us['generation_tokens'])}</b><span>Generation tokens</span></div>"
                          f"<div class=card><b>{k(us['agent_tokens'])}</b><span>Agent tokens ({us['agent_sessions']} sessions)</span></div>"
                          f"<div class=card><b>{k(us['agent_output_tokens'])}</b><span>Agent output tokens</span></div></div>"
                          "<h3>Generation (images, sheets, videos, voices)</h3><table class=evt><tr><th>Model</th><th>Calls</th>"
                          f"<th>Kinds</th><th>Failed</th><th>Tokens</th><th>Audio</th></tr>{grow}</table>"
                          "<h3>Agent (LLM)</h3><table class=evt><tr><th>Model</th><th>Sessions</th><th>Requests</th><th>Input</th>"
                          f"<th>Cache write</th><th>Cache read</th><th>Output</th><th>Total</th></tr>{arow}</table></section>")
        if ev:
            num = lambda v, unit="": "?" if v is None else f"{v}{unit}"
            ST = {"ok": "Pass", "warn": "Check", "bad": "Fail"}
            th = ev.get("status") or {"score": {"pass": 75, "check": 60}, "criterion": {"pass": 4, "check": 3}}
            sp, sc, cp, cc = th["score"]["pass"], th["score"]["check"], th["criterion"]["pass"], th["criterion"]["check"]
            wq, wb = (f"{v:.0%}" for v in (ev.get("weights") or {"quality": .5, "breadth": .5}).values())
            st = lambda lv: f"<span class='st st-{lv}'>{ST[lv]}</span>"
            lvl = lambda v, ok, warn: "ok" if v is not None and v >= ok else "warn" if v is not None and v >= warn else "bad"
            ul = lambda xs: f"<ul>{''.join(f'<li>{e(x)}</li>' for x in xs)}</ul>" if xs else "<p class=mut>None.</p>"
            rows = "".join(f"<tr class=r-{lvl(c['score'], cp, cc)}><td>{st(lvl(c['score'], cp, cc))}</td><td>{e(c['label'])}</td>"
                           f"<td>{c['weight']}</td><td><span class=bar style='--v:{((c['score'] or 1) - 1) * 25}%'></span> "
                           f"{num(c['score'])}/5</td><td class=mut>{e(c['note'])}</td></tr>" for c in ev["criteria"])
            areas, brows = ev.get("completeness_areas") or [], ev.get("breadth_rows") or []
            blv = lambda x: "ok" if x["count"] >= x["full"] else "warn" if x["count"] >= x["minimum"] else "bad"
            qcalc = " + ".join(f"{c['weight']} × ({num(c['score'])}−1)/4" for c in ev["criteria"])
            parts = [
                ("d-overall", "Overall", f"<p><b>Overall = {e(ev.get('overall_calc') or 'quality and breadth, once quality is scored')}</b></p>"
                 f"<p class=mut>{wq} quality + {wb} breadth. A missing checklist item or an unapproved asset means not ready "
                 f"for stories, whatever the score. Rules: <code>{e(ev.get('scoring_file', 'templates/scoring.json'))}</code>"
                 " (method: references/scoring.md).</p>"),
                ("d-quality", "Quality", f"<p><b>Quality = ({qcalc}) / {sum(c['weight'] for c in ev['criteria'])} × 100 = "
                 f"{num(ev['quality'])}</b></p><p class=mut>Each criterion scored 1–5 by the reviewer after looking at every "
                 f"picture; reviewed {e(ev.get('review_date') or 'never')}.</p><table class=evt><tr><th></th><th>Criterion</th>"
                 f"<th>Weight</th><th>Score</th><th>Note</th></tr>{rows}</table>"),
                ("d-breadth", "Breadth", f"<p><b>Breadth = {e(ev.get('breadth_calc', ''))}</b></p><p class=mut>Part score = "
                 "count / full marks, at most 100; points = weight × part score.</p><table class=evt><tr>"
                 "<th></th><th>Part</th><th>Weight</th><th>Count</th><th>Min</th><th>Full</th><th>Score</th><th>Points</th></tr>"
                 + "".join(f"<tr class=r-{blv(x)}><td>{st(blv(x))}</td><td>{e(x['part'])}</td><td>{x['weight']}</td><td>{x['count']}"
                           f"{' <b class=bad>below min</b>' if x['count'] < x['minimum'] else ''}</td><td>{x['minimum']}</td>"
                           f"<td>{x['full']}</td><td>{x['score']}</td><td>{x['points']}</td></tr>" for x in brows)
                 + f"<tr><td></td><td><b>Total</b></td><td>100</td><td></td><td></td><td></td><td></td><td><b>{ev['breadth']}</b></td></tr></table>"),
                ("d-check", "Checklist", f"<p><b>Checklist = {ev.get('completeness_done', '?')} / {ev['items']} items = "
                 f"{ev['completeness']}%</b></p><p class=mut>Not scored: every item is needed before stories.</p>"
                 "<table class=evt><tr><th></th><th>Area</th><th>Done</th><th>Missing</th></tr>"
                 + "".join(f"<tr class=r-{'ok' if x['done'] == x['total'] else 'bad'}><td>{st('ok' if x['done'] == x['total'] else 'bad')}</td><td>{e(x['area'])}</td><td>{x['done']}/{x['total']}</td><td class=mut>"
                           f"{e(', '.join(x['missing']) or '–')}</td></tr>" for x in areas) + "</table>"
                 + (f"<h4>Technical problems</h4>{ul(ev['problems'])}" if ev.get("problems") else "")),
                ("d-approve", "Approvals", f"<p><b>{ev.get('approved', 0)} of {ev.get('assets', 0)} assets approved by you</b></p>"
                 f"<h4>{st('warn')} Waiting for your approval</h4>{ul(ev.get('pending_approval', []))}"),
                ("d-issues", "Issues", (f"<p>{st('warn')} Open problems found in the review.</p>" if ev.get("issues") else "")
                 + ul(ev.get("issues", []))),
            ]
            card = lambda d, v, label, lv: (f"<button type=button class='card c-{lv}' data-go={d}><b>{v}</b><span>"
                                            f"{st(lv)} {label}</span></button>")
            cards = (card("d-overall", num(ev["overall"]), "Overall / 100", lvl(ev["overall"], sp, sc))
                     + card("d-quality", num(ev["quality"]), f"Quality · {wq}", lvl(ev["quality"], sp, sc))
                     + card("d-breadth", num(ev.get("breadth")), f"Breadth · {wb}", lvl(ev.get("breadth"), sp, sc))
                     + card("d-check", num(ev["completeness"], "%"), "Checklist · not scored",
                            "ok" if ev["completeness"] == 100 else "bad")
                     + card("d-approve", f"{ev.get('approved', 0)}/{ev.get('assets', 0)}", "Approved by you",
                            "ok" if not ev.get("pending_approval") else "warn"))
            todo = [f"<a href=#evaluation data-go={d}>{t}</a>" for d, t in (
                ("d-check", f"{len(ev.get('missing', []))} checklist items missing"),
                ("d-approve", f"{len(ev.get('pending_approval', []))} assets to approve"),
                ("d-issues", f"{len(ev.get('issues', []))} open issues")) if not t.startswith("0 ")]
            dlg = ("<dialog id=scoredlg><div class=dlghead><b>How the score is calculated</b><button type=button "
                   "class=x aria-label=Close onclick=\"this.closest('dialog').close()\">×</button></div><div class=dlgbody>"
                   + f"<p class=legend>{st('ok')} passed {st('warn')} passed with remarks: check or improve {st('bad')} failed</p>"
                   + "".join(f"<section id={d} class=dpart><h3>{t}</h3>{body}</section>" for d, t, body in parts)
                   + "</div></dialog>")
            eval_html = (f"<section id=evaluation><h2>Evaluation</h2><p class=lead>{e(ev['date'])} · <b>{e(ev['band'].split(':')[0])}</b>"
                         f"{' · <b class=warn>review is stale</b>' if ev.get('review_stale') else ''}</p>"
                         f"<div class=evals>{cards}</div><p>{' · '.join(todo)}{' · ' if todo else ''}"
                         f"<a href=#evaluation data-go=d-overall><b>Score details</b></a></p>{dlg}"
                         "<script>document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',ev=>{"
                         "ev.preventDefault();document.getElementById('scoredlg').showModal();"
                         "document.getElementById(b.dataset.go).scrollIntoView({block:'start'})}));"
                         "document.getElementById('scoredlg').addEventListener('click',ev=>{if(ev.target.id==='scoredlg')"
                         "ev.target.close()})</script></section>")
        feedback_html = FEEDBACK_HTML.replace("__WID__", json.dumps(wl.world_id(w)))
        nav = [("characters", "Characters")] + ([("voices", "Voices")] if dialogue else []) + \
              [("world", "World"), ("scenes", "Scenes"), ("props", "Props")] + \
              [("workflow", "Workflow")] + ([("evaluation", "Evaluation")] if eval_html else []) + ([("usage", "Usage")] if usage_html else []) +               [("docs", "Docs"), ("tasks", "Tasks")]

        page = f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>My World</title>
<style>
:root{{--bg:#f5f8f7;--fg:#1c2928;--mut:#5b6e6b;--card:#fff;--line:#dce6e4;--brand:#2f7d73;--warn:#b56b16;--ok:#2e7d32;--bad:#c62828;--chip:#eef4f3}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#121818;--fg:#e5eeec;--mut:#9cb0ad;--card:#1b2423;--line:#2c3a39;--brand:#6cc3b6;--warn:#e7a456;--ok:#6fcf7a;--bad:#f07b7b;--chip:#22302f}}}}
:root[data-theme=dark]{{--bg:#121818;--fg:#e5eeec;--mut:#9cb0ad;--card:#1b2423;--line:#2c3a39;--brand:#6cc3b6;--warn:#e7a456;--ok:#6fcf7a;--bad:#f07b7b;--chip:#22302f}}
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
.evals{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}} .evals .card{{padding:14px 16px}}
.evals b{{display:block;font-size:30px}} .evals span{{color:var(--mut);font-size:13px}}
.evt{{width:100%;border-collapse:collapse;font-size:14px;display:block;overflow-x:auto}} .evt td,.evt th{{text-align:left;padding:8px;border-top:1px solid var(--line);vertical-align:top}}
.evals .card{{font:inherit;text-align:left;cursor:pointer;color:inherit}} .evals .card:hover{{border-color:var(--brand)}}
dialog#scoredlg{{width:min(860px,calc(100vw - 32px));max-height:85vh;padding:0;border:1px solid var(--line);border-radius:14px;background:var(--card);color:inherit}}
dialog#scoredlg::backdrop{{background:rgba(0,0,0,.45)}} .dlghead{{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;border-bottom:1px solid var(--line)}}
.dlgbody{{padding:4px 16px 16px;overflow:auto;max-height:calc(85vh - 52px)}} .dpart h3{{margin:14px 0 4px}}
.st{{display:inline-block;font-size:11px;font-weight:700;padding:1px 7px;border-radius:9px;color:#fff;vertical-align:1px}}
.st-ok{{background:var(--ok)}} .st-warn{{background:var(--warn)}} .st-bad{{background:var(--bad)}} .bad{{color:var(--bad)}}
.evt tr.r-ok td:first-child{{box-shadow:inset 3px 0 var(--ok)}} .evt tr.r-warn td:first-child{{box-shadow:inset 3px 0 var(--warn)}}
.evt tr.r-bad td:first-child{{box-shadow:inset 3px 0 var(--bad)}} .evt tr.r-bad{{background:color-mix(in srgb,var(--bad) 7%,transparent)}}
.evals .c-ok{{border-top:4px solid var(--ok)}} .evals .c-warn{{border-top:4px solid var(--warn)}} .evals .c-bad{{border-top:4px solid var(--bad)}}
.evals .c-bad b{{color:var(--bad)}} .evals .st{{color:#fff}} .legend{{margin:12px 0 0;display:flex;gap:8px;flex-wrap:wrap;align-items:center;font-size:13px;color:var(--mut)}}
.fb{{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:8px 0}} .fb button,.fbbar button,.fbbtns button{{font:inherit;font-size:13px;padding:4px 10px;border-radius:16px;border:1px solid var(--line);background:var(--card);color:inherit;cursor:pointer}}
.fb .fb-like.on{{background:var(--ok);border-color:var(--ok);color:#fff}} .fb .fb-unlike.on{{background:var(--bad);border-color:var(--bad);color:#fff}} .fb .fb-cm.on{{border-color:var(--brand);color:var(--brand)}}
.fb-ok{{font-size:12px;color:var(--ok);font-weight:600}} .fb-old{{font-size:12px;color:var(--warn,#b7791f);font-weight:600}} .fb-text,#fbGeneral{{width:100%;box-sizing:border-box;font:inherit;font-size:14px;padding:8px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:inherit}}
.fbbar{{position:fixed;right:16px;bottom:16px;z-index:10;display:flex;gap:10px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:24px;padding:6px 6px 6px 14px;box-shadow:0 4px 16px rgba(0,0,0,.15);font-size:14px}}
.fbbar #fbOpen{{background:var(--brand);border-color:var(--brand);color:#fff}} dialog#fbdlg{{width:min(640px,calc(100vw - 32px));max-height:85vh;padding:0;border:1px solid var(--line);border-radius:14px;background:var(--card);color:inherit}}
dialog#fbdlg::backdrop{{background:rgba(0,0,0,.45)}} #fbList{{padding-left:18px}} #fbList li{{margin:4px 0}} .fbbtns #fbCopy{{background:var(--brand);border-color:var(--brand);color:#fff}} main{{padding-bottom:72px}}
.x{{font-size:22px;line-height:1;background:none;border:0;color:inherit;cursor:pointer}} .warn{{color:var(--warn)}}
.bar{{display:inline-block;width:60px;height:8px;border-radius:4px;background:linear-gradient(90deg,var(--brand) var(--v),var(--line) var(--v))}}
</style></head><body><main>
<header><h1>My World</h1><p>{e(cfg.get('tagline', ''))}</p><div class=facts>{chips}</div></header>
<nav class=sec>{''.join(f'<a href=#{a}>{e(b)}</a>' for a, b in nav)}</nav>

<section id=characters><h2>Characters</h2><p class=lead>Canonical descriptions live in <a href=Identities.md>Identities.md</a>.
Every render uses these sheets as references.</p><div class='grid three'>{chars}</div>
{f"<h3 style='margin-top:24px'>Group references</h3><div class=grid>{groups_html}</div>" if groups_html else ""}</section>
{dialogue}
<section id=world><h2>The world</h2><p class=lead>From <a href=Setting.md>Setting.md</a>.</p><div class=world>{world_cards}</div></section>

<section id=scenes><h2>Scenes</h2><p class=lead>Each scene has a key that story files name (<code>"scene": "{e((w.scenes() or ['key'])[0])}"</code>).</p><div class=grid>{locs}</div></section>
{props_html}
<section id=workflow><h2>How stories are made</h2><p class=lead>With the <b>world-stories</b> skill. You approve at every gate; videos are only rendered after approval.</p>{steps}</section>

{eval_html}
{usage_html}
<section id=docs><h2>Documents</h2><div class=docs>{docs}</div></section>

<section id=tasks><h2>Tasks</h2><p class=lead>One folder per topic in <code>_tasks/</code>, newest first. On each page, <b>Copy feedback</b> and paste it to the Agent.</p>{task_list}</section>
<footer>Generated {date.today()} by the my-world skill (<code>build_overview.py</code>). Re-run it after changing the canon, the assets or the tasks.</footer>
</main>{feedback_html}</body></html>"""
        w.overview.write_text(page, encoding="utf-8")
        print(w.overview)
        for p in pagenav.stamp_all(w):
            print("  linked", p.relative_to(w.root))


if __name__ == "__main__":
    wdir, _ = wl.pop_world_arg(sys.argv[1:])
    Overview(wl.World(wdir)).build()
