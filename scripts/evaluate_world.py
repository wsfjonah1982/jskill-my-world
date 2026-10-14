"""Evaluate how complete and how good the world is. Run it after every change to the world.

Four parts (rules and numbers in the scoring template, templates/scoring.json; method in references/scoring.md):
  completeness  a checklist, not scored: every canon block, sheet, set, group picture, height chart and voice the
                world needs, plus technical checks of each picture (worldlib.inspect_image) and voice clip.
  quality       scored by the reviewer (Claude) after looking at every picture and listening to every voice, against
                the rubric in the scoring template (templates/scoring.json), in _reference/evaluation/review.json (`template` writes a skeleton).
  approval      the user's approvals, from world.json `approved` {"<asset path>": "YYYY-MM-DD"}; an approval no longer
                counts once the asset is changed after that date. Any unapproved asset means: not ready for stories.
  breadth       how rich the world is (parts in the scoring template): characters with a sheet (minimum 3, full marks at 8), locations
                with a set (minimum 9, full marks at 30), each part = n / full; and group pictures, one per location
                (part = locations with a group picture / locations). The minimums and a group picture for every
                location are also completeness items.
Score = 50% quality + 50% breadth, given only when every quality criterion is scored. Any missing completeness
item or unapproved asset means: not ready for stories, whatever the score. A review older than the newest
canon or asset change is flagged as stale. Score only what was checked: what the reviewer could not verify (e.g. how
a voice sounds) is scored 3 at most and named in the note until the user approves it.

Usage:  python evaluate_world.py [--world DIR]            evaluate; writes _reference/evaluation/evaluation.json and
                                                          the "Evaluation" section of world.md
        python evaluate_world.py template [--world DIR]   write review.json with every criterion to score (keeps scores)
It then rebuilds world.html (build_overview.py), which shows the evaluation.
"""
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import worldlib as wl  # noqa: E402

# The rubric and calculation rules live in a scoring template (templates/scoring.json, or <world>/scoring.json to
# override it), so other projects can reuse them; the method is described in references/scoring.md.
SCORING_TEMPLATE = wl.SKILL_DIR / "templates" / "scoring.json"
QUALITY, BREADTH, WEIGHTS, BANDS, STATUS, SCORING_FILE = [], {}, {}, [], {}, None


def load_scoring(root):
    """Load the scoring template into the module settings: the world's own scoring.json wins over the skill's."""
    global QUALITY, BREADTH, WEIGHTS, BANDS, STATUS, SCORING_FILE
    SCORING_FILE = next(p for p in (root / "scoring.json", SCORING_TEMPLATE) if p.is_file())
    sc = json.loads(SCORING_FILE.read_text(encoding="utf-8"))
    QUALITY = [(c["id"], c["label"], c["weight"], c["means_5"]) for c in sc["quality"]["criteria"]]
    BREADTH = {p["id"]: (p["weight"], None if p["minimum"] == "per_location" else p["minimum"],
                         None if p["full"] == "per_location" else p["full"], p["label"]) for p in sc["breadth"]["parts"]}
    WEIGHTS = sc["weights"]
    BANDS = [tuple(b) for b in sc["bands"]]
    STATUS = {k: v for k, v in sc["status"].items() if not k.startswith("_")}


MAX_SOLO_VOICE_S = 30


def mtime(p):
    return p.stat().st_mtime if p.is_file() else 0


def duration(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True).stdout.strip()
    return float(out) if out else None


class Evaluation:
    def __init__(self, w):
        self.w = w
        load_scoring(w.root)
        self.dir = w.root / "_reference" / "evaluation"
        self.items = []    # (area, item, ok, note)
        self.problems = []  # technical problems found in existing files
        self.watched = []  # files whose change makes a review stale
        self.assets = []   # files the user has to approve

    def need(self, area, item, ok, note=""):
        self.items.append((area, item, bool(ok), note))

    def picture(self, path, kind):
        self.watched.append(path)
        self.assets.append(path)
        if path.is_file():
            _, probs = wl.inspect_image(path, kind)
            self.problems += [f"{wl.rel(path, self.w.root)}: {p}" for p in probs]
        return path.is_file()

    def completeness(self):
        w, b = self.w, self.w.blocks()
        audio = w.fmt["audio"]
        self.watched += [w.root / f for f in wl.CANON_FILES]  # not world.json: publish and approvals rewrite it
        for k in list(wl.REQUIRED_BLOCKS) + (["voice"] if audio else []):
            self.need("Canon", f"block {k}", k in b)
        left = [k for k, v in b.items() if "REPLACE" in v]
        self.need("Canon", "no REPLACE placeholders left", not left, ", ".join(left))
        for k, c in w.chars.items():
            name = c.get("name", k)
            self.need("Characters", f"{name}: sheet:{k} block", f"sheet:{k}" in b)
            self.need("Characters", f"{name}: sheet picture", self.picture(w.sheet(k), "sheet"), wl.rel(w.sheet(k), w.root))
            self.need("Characters", f"{name}: height_cm", c.get("height_cm"))
            if audio:
                clip = w.root / "_asset" / "voices" / f"{k}.wav"
                self.watched.append(clip)
                self.assets.append(clip)
                self.need("Voices", f"{name}: voice:{k} block", f"voice:{k}" in b)
                self.need("Voices", f"{name}: voice clip", clip.is_file())
                d = duration(clip) if clip.is_file() else None
                if d and d > MAX_SOLO_VOICE_S:
                    self.problems.append(f"{wl.rel(clip, w.root)}: {d:.1f}s, over {MAX_SOLO_VOICE_S}s (too long to "
                                         "be a voice reference)")
        for k in w.locations():
            self.need("Locations", f"{k}: set picture", self.picture(w.location_image(k), "set"))
        self.need("Locations", "style_refs set in world.json", w.cfg.get("style_refs"))
        for k in sorted(x.split(":", 1)[1] for x in b if x.startswith("prop:")):
            self.need("Props", f"{k}: prop picture", self.picture(w.prop_image(k), "any"))
        lo_min, ch_min = BREADTH["locations"][1], BREADTH["characters"][1]
        self.need("Breadth", f"at least {ch_min} characters", len(w.chars) >= ch_min, f"{len(w.chars)}")
        self.need("Breadth", f"at least {lo_min} locations", len(w.locations()) >= lo_min, f"{len(w.locations())}")
        covered = self.group_locations()
        for k in w.locations():
            self.need("Groups", f"{k}: group picture", k in covered)
        if len(w.chars) > 1:
            hc = w.root / w.cfg.get("height_chart", "_asset/height_chart.png")
            self.need("Groups", "height chart", self.picture(hc, "set"))
        for g in w.cfg.get("groups", []):
            p = w.root / g["path"]
            if p.name != "height_chart.png":
                self.need("Groups", f"{p.stem} picture", self.picture(p, "set"))
        if audio and len(w.chars) > 1:
            vdir = w.root / "_reference" / "voices"
            dlg = sorted(p for p in vdir.glob("*_dialogue.wav"))
            self.need("Voices", "sample dialogue", dlg)
            self.assets += dlg[:1]
            self.need("Voices", "voices page", (vdir / "voices.html").is_file())
        done = sum(ok for *_, ok, _ in self.items)
        return round(100 * done / len(self.items)) if self.items else 0

    def completeness_areas(self):
        """[{area, done, total, missing}] in the order the areas were checked: how completeness is calculated."""
        areas = {}
        for area, item, ok, _ in self.items:
            a = areas.setdefault(area, {"area": area, "done": 0, "total": 0, "missing": []})
            a["total"] += 1
            a["done"] += ok
            if not ok:
                a["missing"].append(item)
        return list(areas.values())

    def approvals(self):
        approved = self.w.cfg.get("approved", {})
        pending = []
        for p in self.assets:
            if not p.is_file():
                continue
            rel = wl.rel(p, self.w.root)
            day = approved.get(rel)
            changed = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d")
            if not day:
                pending.append(rel)
            elif changed > day:
                pending.append(f"{rel} (changed {changed}, approved {day})")
        return len([p for p in self.assets if p.is_file()]), pending

    def quality(self):
        rp = self.dir / "review.json"
        review = json.loads(rp.read_text(encoding="utf-8")) if rp.is_file() else {}
        scores = review.get("scores", {})
        rows, total, weight = [], 0, 0
        for cid, label, wt, _ in QUALITY:
            s = scores.get(cid, {})
            v = s.get("score")
            rows.append({"id": cid, "label": label, "weight": wt, "score": v, "note": s.get("note", "")})
            if isinstance(v, (int, float)):
                total += wt * (v - 1) / 4
                weight += wt
        q = round(100 * total / weight) if weight and weight == sum(x[2] for x in QUALITY) else None  # all scored
        stale = bool(review) and mtime(rp) < max(mtime(p) for p in self.watched) - 1
        missing = [r["label"] for r in rows if not isinstance(r["score"], (int, float))]
        return q, rows, review, stale, missing

    def group_locations(self):
        """Locations that have at least one existing group picture (world.json groups[] `location`)."""
        return {g["location"] for g in self.w.cfg.get("groups", [])
                if g.get("location") and (self.w.root / g["path"]).is_file()}

    def breadth(self):
        w = self.w
        locs = [k for k in w.locations() if w.location_image(k).is_file()]
        counts = {"characters": sum(w.sheet(k).is_file() for k in w.chars), "locations": len(locs),
                  "groups": len(self.group_locations() & set(locs))}
        full = {k: v[2] if v[2] is not None else len(locs) for k, v in BREADTH.items()}
        parts = {k: round(100 * min(counts[k], full[k]) / full[k]) if full[k] else 0 for k in BREADTH}
        score = round(sum(BREADTH[k][0] * parts[k] for k in parts) / sum(v[0] for v in BREADTH.values()))
        self.breadth_rows = [{"part": BREADTH[k][3], "weight": BREADTH[k][0], "count": counts[k],
                              "minimum": BREADTH[k][1] if BREADTH[k][1] is not None else full[k],
                              "full": full[k], "score": parts[k], "points": round(BREADTH[k][0] * parts[k] / 100, 1)}
                             for k in BREADTH]
        return score, counts, parts

    def run(self):
        c = self.completeness()
        br, counts, parts = self.breadth()
        q, rows, review, stale, missing = self.quality()
        n_assets, pending = self.approvals()
        overall = (round(WEIGHTS["quality"] * q + WEIGHTS["breadth"] * br)
                   if q is not None else None)
        band = next(t for lim, t in BANDS if (overall or 0) >= lim) if overall is not None else (
            "quality review incomplete" if review else "quality not reviewed yet")
        n_missing = sum(not ok for *_, ok, _ in self.items)
        blockers = ([f"{n_missing} checklist item{'s' if n_missing > 1 else ''} missing"] if n_missing else []) + (
            [f"{len(pending)} of {n_assets} assets wait for the user's approval"] if pending else [])
        if blockers:
            base = band.split(":")[0]
            band = base + (": " if base == "not ready" else ", but not ready for stories: ") + "; ".join(blockers)
        result = {"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "overall": overall, "band": band,
                  "completeness": c, "completeness_areas": self.completeness_areas(),
                  "completeness_done": sum(ok for *_, ok, _ in self.items),
                  "weights": WEIGHTS, "status": STATUS,
                  "scoring_file": wl.rel(SCORING_FILE, self.w.root) if SCORING_FILE.is_relative_to(self.w.root)
                  else f"<skill>/{SCORING_FILE.relative_to(wl.SKILL_DIR).as_posix()}",
                  "overall_calc": (f"{WEIGHTS['quality']:.0%} × {q} + "
                                   f"{WEIGHTS['breadth']:.0%} × {br} = {overall}" if q is not None else None),
                  "quality": q, "breadth": br, "breadth_counts": counts,
                  "breadth_parts": parts, "breadth_rows": self.breadth_rows, "breadth_calc": " + ".join(
                      f"{x['weight']}% × {x['score']}" for x in self.breadth_rows) + f" = {br}", "breadth_text": (
                      f"{counts['characters']} characters, {counts['locations']} locations, group pictures for "
                      f"{counts['groups']} of {counts['locations']} locations"), "review_date": review.get("date"), "review_stale": stale,
                  "unscored": missing, "missing": [f"{a}: {i}" + (f" ({n})" if n else "")
                                                   for a, i, ok, n in self.items if not ok],
                  "problems": self.problems, "criteria": rows, "issues": review.get("issues", []),
                  "pending_approval": pending, "approved": n_assets - len(pending), "assets": n_assets,
                  "items": len(self.items)}
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "evaluation.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        self.write_md(result)
        return result

    def write_md(self, r):
        q = r["quality"] if r["quality"] is not None else "?"
        sp, sc = STATUS["score"]["pass"], STATUS["score"]["check"]
        dot = lambda v, ok, warn: "🟢" if v is not None and v >= ok else "🟡" if v is not None and v >= warn else "🔴"
        qcalc = " + ".join(f"{x['weight']}×({x['score'] if x['score'] is not None else '?'}−1)/4" for x in r["criteria"])
        lines = ["## Evaluation", "",
                 f"{r['date']}, quality reviewed {r['review_date'] or 'never'}"
                 + (" (**stale: re-review**)" if r["review_stale"] else "") + f". **{r['band']}.** Details: the "
                 "Score details popup in world.html.", "",
                 "Status: 🟢 passed · 🟡 passed with remarks · 🔴 failed.", "",
                 "| | Score | Value | Calculation |", "|---|---|---|---|",
                 f"| {dot(r['overall'], sp, sc)} | **Overall** | **{r['overall'] if r['overall'] is not None else '?'}** | "
                 f"{r['overall_calc'] or '50% quality + 50% breadth, once quality is scored'} |",
                 f"| {dot(r['quality'], sp, sc)} | Quality | {q} | ({qcalc}) / {sum(x['weight'] for x in r['criteria'])} × 100 |",
                 f"| {dot(r['breadth'], sp, sc)} | Breadth | {r['breadth']} | {r['breadth_calc']}; " + ", ".join(
                     f"{x['part'].lower()} {x['count']}/{x['full']}" for x in r["breadth_rows"]) + " |",
                 f"| {'🟢' if r['completeness'] == 100 else '🔴'} | Checklist (not scored) | {r['completeness']}% | {r['completeness_done']} / {r['items']} items |",
                 f"| {'🟡' if r['pending_approval'] else '🟢'} | Approved by the user | {r['approved']}/{r['assets']} | |"]
        for title, key in (("Missing", "missing"), ("Technical problems", "problems"), ("Issues", "issues"),
                           ("Waiting for approval", "pending_approval")):
            if r[key]:
                lines += ["", f"**{title}:** " + "; ".join(r[key])]
        block = "<!-- evaluation:start -->\n" + "\n".join(lines) + "\n<!-- evaluation:end -->"
        p = self.w.root / "world.md"
        s = p.read_text(encoding="utf-8") if p.is_file() else ""
        if "<!-- evaluation:start -->" in s:
            s = re.sub(r"<!-- evaluation:start -->.*?<!-- evaluation:end -->", lambda _: block, s, flags=re.S)
        else:
            m = re.search(r"^## Pending tasks", s, re.M)  # just above the pending tasks, else at the end
            s = s[:m.start()] + block + "\n\n" + s[m.start():] if m else s.rstrip() + "\n\n" + block + "\n"
        p.write_text(s, encoding="utf-8")

    def template(self):
        rp = self.dir / "review.json"
        old = json.loads(rp.read_text(encoding="utf-8")) if rp.is_file() else {}
        scores = old.get("scores", {})
        out = {"date": old.get("date", ""), "reviewer": old.get("reviewer", "Claude"),
               "scores": {cid: {"score": scores.get(cid, {}).get("score"), "note": scores.get(cid, {}).get("note", ""),
                                "means_5": desc} for cid, _, _, desc in QUALITY},
               "issues": old.get("issues", [])}
        self.dir.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        print(rp)


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    wdir, args = wl.pop_world_arg(sys.argv[1:])
    ev = Evaluation(wl.World(wdir))
    if args[:1] == ["template"]:
        ev.template()
        sys.exit()
    r = ev.run()
    import llm_usage  # noqa: E402  the token totals shown on the page
    u = llm_usage.summarize(ev.w.root)
    import build_overview  # noqa: E402  the page shows this evaluation
    build_overview.Overview(ev.w).build()
    print(f"Overall {r['overall'] if r['overall'] is not None else '?'}/100 ({r['band']}): completeness "
          f"{r['completeness']}%, quality {r['quality'] if r['quality'] is not None else 'not reviewed'}, breadth "
          f"{r['breadth']} (" + r["breadth_text"] + ")"
          + (" (review is STALE: re-review)" if r["review_stale"] else ""))
    print(f"  approved by the user: {r['approved']} of {r['assets']} assets")
    print(f"  model usage: {u['generation_calls']} generation calls, {llm_usage.fmt(u['generation_tokens'])} tokens; agent "
          f"{llm_usage.fmt(u['agent_tokens'])} tokens in {u['agent_sessions']} sessions")
    for title, key in (("missing", "missing"), ("problem", "problems"), ("unscored", "unscored"),
                       ("waiting for approval", "pending_approval")):
        for x in r[key]:
            print(f"  {title}: {x}")
