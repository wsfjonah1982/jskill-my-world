"""Apply the feedback the user gives on world.html (👍 Like / 👎 Unlike / 💬 comments, "Copy feedback" JSON).

The page keeps the choices in the browser; the user pastes the JSON to the agent or gives the downloaded
feedback.json. This script:
  - checks it belongs to this world (world_id),
  - saves it as _reference/feedback/feedback_<time>.json (the history of what the user said),
  - Like   -> the asset is approved: world.json `approved` {path: today},
  - Unlike -> the approval is withdrawn, and the asset goes on the to-do list with its comment,
  - comments (with or without a vote) and the general comment go on the to-do list,
  - version check (feedback version 2): the page sends the version of each asset the user saw (`seen_version`, a
    content hash). Feedback on a version that has been redrawn since is NOT applied as an approval, and its comment
    is marked "about an older version", so a stale comment is not acted on twice,
  - each to-do names the canon block that drives the asset (sheet:<char>, scene:<key>, prop:<key>, group:<name>, voice:<char>…),
  - writes _reference/feedback/todo.md and prints it, so the agent can act item by item: change the canon block
    first, then redraw (never edit the picture), then show the user the result.

Usage:  python feedback.py apply <feedback.json | -> [--world DIR]   (- reads the pasted JSON from stdin)
        python feedback.py todo [--world DIR]                       print the open to-do list again
"""
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import worldlib as wl  # noqa: E402


def load(src):
    text = sys.stdin.read() if src == "-" else Path(src).read_text(encoding="utf-8")
    m = re.search(r"\{.*\}", text, re.S)  # tolerate text pasted around the JSON
    if not m:
        sys.exit("No feedback JSON found.")
    d = json.loads(m.group(0))
    if d.get("type") != "my-world-feedback":
        sys.exit("This is not my-world feedback (type must be 'my-world-feedback').")
    return d


def version(f):
    """Same content hash as build_overview.Overview.ver."""
    return hashlib.sha1(f.read_bytes()).hexdigest()[:10]


def canon_key(w, asset):
    """The canon block an asset is drawn or spoken from: where a comment on it has to be worked in."""
    a = Path(asset)
    for k, c in w.chars.items():
        if asset == c.get("sheet", f"_asset/{k}.png"):
            return f"sheet:{k}"
    if a.parent.name == "voices" and a.parent.parent.name == "_asset":
        return f"voice:{a.stem}"
    if a.parent.name in ("scenes", "settings"):
        return f"scene:{a.stem}"
    if a.parent.name == "props":
        return f"prop:{a.stem}"
    if a.stem == "height_chart":
        return "characters (height_cm in world.json)"
    if a.parent.name == "voices":
        return "_reference/voices/samples.json (turns) and the voice:<char> blocks"
    if any(g.get("path") == asset for g in w.cfg.get("groups", [])):
        return f"group:{a.stem}"
    return "?"


def apply(w, d):
    wid = wl.world_id(w)
    if d.get("world_id") != wid:
        sys.exit(f"The feedback is for world {d.get('world_id')}, this world is {wid}: not applied.")
    fdir = w.root / "_reference" / "feedback"
    fdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    (fdir / f"feedback_{stamp}.json").write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

    mf = w.root / "world.json"
    cfg = json.loads(mf.read_text(encoding="utf-8"))
    approved = cfg.setdefault("approved", {})
    today = datetime.now().strftime("%Y-%m-%d")
    liked, unliked, todo = [], [], []
    for it in d.get("items", []):
        asset, label, vote, comment = it.get("asset"), it.get("label") or it.get("asset"), it.get("vote"), it.get("comment", "")
        if not asset or not (w.root / asset).is_file() or ".." in Path(asset).parts:
            todo.append(f"- [ ] (unknown asset {asset!r}) {comment}".rstrip())
            continue
        key = canon_key(w, asset)
        seen = it.get("seen_version")
        if seen and seen != version(w.root / asset):
            if vote or comment:
                todo.append(f"- [ ] ⏳ {label} (`{asset}`, canon `{key}`): about an OLDER version, redrawn since; "
                            f"{'vote ' + vote + ', ' if vote else ''}comment: {comment or '-'}. Check the new version "
                            "already answers it; if not, ask the user to look again before redrawing.")
            continue
        ref = f"{label} (`{asset}`, canon `{key}`)"
        if vote == "like":
            approved[asset] = today
            liked.append(label)
            if comment:
                todo.append(f"- [ ] 👍 {ref}, liked with a note: {comment}")
        elif vote == "unlike":
            approved.pop(asset, None)
            unliked.append(label)
            todo.append(f"- [ ] 👎 {ref}: {comment or 'no comment given: ask the user what to change'}")
        elif comment:
            todo.append(f"- [ ] 💬 {ref}: {comment}")
    if d.get("general"):
        todo.insert(0, f"- [ ] 💬 General: {d['general']}")
    mf.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    md = [f"# Feedback to act on ({today}, from feedback_{stamp}.json)", "",
          f"Approved (👍): {', '.join(liked) or 'none'}.", f"Approval withdrawn (👎): {', '.join(unliked) or 'none'}.", ""]
    md += todo or ["Nothing to change."]
    md += ["", "For each item: read the comment in the user's language and look at the asset first. Decide whether it is "
           "a rule for the whole world (e.g. 'the dog needs a leash outdoors': put it in the shared canon blocks and the "
           "world rules, then redraw every asset it affects) or about this asset only (change only its canon block). "
           "Then redraw from the canon; never edit the picture. Show the user the new version; it needs a new 👍 "
           "before it counts as approved."]
    (fdir / "todo.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return "\n".join(md)


def main():
    wdir, args = wl.pop_world_arg(sys.argv[1:])
    w = wl.World(wdir)
    if args[:1] == ["apply"] and len(args) == 2:
        print(apply(w, load(args[1])))
        print("\nNext: run evaluate_world.py (approvals changed), then work through the list.")
    elif args[:1] == ["todo"]:
        t = w.root / "_reference" / "feedback" / "todo.md"
        print(t.read_text(encoding="utf-8") if t.is_file() else "No feedback applied yet.")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    main()
