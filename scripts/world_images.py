"""Draw the reference pictures of a world: character sheets, scene sets, props, group pictures, height line-up.

Every prompt is built from the world's canon blocks (Identities.md / Setting.md), so the pictures and every later
keyframe and video agree. An existing picture is moved to _reference/archive/<kind>/ before it is redrawn.
Prompts and logs go to _reference/<kind>/prompt|log/; source photos are read from _reference/<kind>/refs/.

Usage:  python world_images.py sheet <char> [...]          canon `sheet:<char>` → _asset/<sheet path in world.json>
                                                           (photos in _reference/characters/refs/<char>*.jpg|png anchor it)
        python world_images.py scene <key> [...] [--refs img ...]     (`set` is the same)
                                                           canon `scene:<key>` → _asset/scenes/<key>.png
                                                           (_reference/scenes/refs/<key>_photo.jpg sets the layout)
        python world_images.py prop <prop> [...]           canon `prop:<key>` → _asset/props/<key>.png
                                                           (_reference/props/refs/<key>_photo.jpg anchors the look)
        python world_images.py group <name> [--scene key] [--cast a b] [--action "text"]
                                                           (--scene defaults to the group's `scene` in world.json)
                                                           canon `group:<name>` (or --scene) → _asset/<name>.png
        python world_images.py height                      line-up at true heights → _asset/height_chart.png
        add --dry-run to write the prompts only, --world DIR to pick the world.
"""
import sys
from contextlib import nullcontext
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import worldlib as wl  # noqa: E402

DRY = "--dry-run" in sys.argv


def _opt(args, name, n=1):
    """Pop `--name v1 [v2 ...]` (n=None: all values up to the next --flag)."""
    if name not in args:
        return None, args
    i = args.index(name)
    j = i + 1
    while j < len(args) and not args[j].startswith("--") and (n is None or j - i <= n):
        j += 1
    vals = args[i + 1:j]
    return (vals if n is None else (vals[0] if vals else None)), args[:i] + args[j:]


class Pictures:
    def __init__(self, world):
        self.w = world

    def _dirs(self, kind):
        base = self.w.root / "_reference" / kind
        for d in ("prompt", "log", "refs"):
            (base / d).mkdir(parents=True, exist_ok=True)
        return base

    def _photos(self, kind, key):
        refs = self.w.root / "_reference" / kind / "refs"
        return sorted(p for p in refs.glob(f"{key}*") if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))

    def style_refs(self, exclude=None):
        """Pictures that carry the world's rendering style: world.json `style_refs`, else the first scene set,
        else the first character sheet."""
        w = self.w
        refs = [w.p(r) for r in w.cfg.get("style_refs", []) if w.p(r).is_file()]
        if not refs:
            sets = [w.scene_image(k) for k in w.scenes() if k != exclude and w.scene_image(k).is_file()]
            refs = sets[:1] or [w.sheet(k) for k in w.chars if w.sheet(k).is_file()][:1]
        return refs

    # ----- character sheets
    def sheet(self, key):
        w = self.w
        if key not in w.chars:
            return key, f"unknown character; known: {', '.join(w.chars)}"
        base = self._dirs("characters")
        idea = base / "prompt" / f"{key}_sheet.txt"
        idea.write_text(f"{w.get('sheet:' + key)}\nThe character must fit this world: {w.get('style')}.\n", encoding="utf-8")
        if DRY:
            return key, f"prompt written: {idea}"
        out = w.sheet(key)
        out.parent.mkdir(parents=True, exist_ok=True)
        wl.archive(out, w, "characters")
        with wl.patched_config(wl.image_settings(w, w.cfg.get("sheet_size", "2K"))):
            return key, wl.gen_sheet(idea, w.cfg.get("sheet_style", w.get("style")), self._photos("characters", key),
                                     out, base / "log")

    # ----- scene sets
    def set_prompt(self, key, photo, custom_refs):
        w = self.w
        notes, n = [], 1
        if photo:
            notes.append(f"Image {n} is a real photo of this place: copy its layout, viewpoint and objects, widened to "
                         f"{w.fmt['ratio']}; leave out every person in it, and any text, signs, posters or watermarks.")
            n += 1
        last = n + custom_refs - 1
        notes.append(f"Image{'s' if custom_refs > 1 else ''} {n}{f' to {last}' if custom_refs > 1 else ''} "
                     "come from our animated film: match only the rendering style, colour palette, light and level of "
                     "detail; do not copy their place, layout, objects or characters.")
        return (f"{w.get('style')}. {w.ratio_words}, full-bleed, an empty film set with no people and no animals, "
                "used as the scene reference for this place.\n" + " ".join(notes) + "\n"
                f"The place: {w.get('scene:' + key)}\nThe world: {w.get('world')}\n"
                "Eye-level camera at a natural standing height, a wide establishing view with open space in the middle "
                "where characters can later stand.\nno text, no readable signs, no numbers, no logos, no watermark, "
                "no people, no animals, no characters, no split panels.\n")

    def set(self, key, custom=None):
        w = self.w
        if key not in w.scenes():
            return key, f"unknown scene; known: {', '.join(w.scenes())}"
        base = self._dirs("scenes")
        photos = [p for p in self._photos("scenes", key) if p.stem.endswith("_photo")][:1]
        refs = custom or self.style_refs(exclude=key)
        pf = base / "prompt" / f"{key}.txt"
        pf.write_text(self.set_prompt(key, photos[0] if photos else None, len(refs)), encoding="utf-8")
        if DRY:
            return key, f"prompt written: {pf}"
        out = w.root / "_asset" / "scenes" / f"{key}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        old = wl.archive(out, w, "scenes")
        refs = [old if old and Path(r).resolve() == out.resolve() else r for r in refs]  # redrawing the style ref itself
        return key, wl.gen_image(photos + refs, pf, out, base / "log")

    # ----- props
    def prop(self, key):
        w = self.w
        base = self._dirs("props")
        photos = self._photos("props", key)[:2]
        style = self.style_refs()[:1]
        notes = ([f"Image{'s' if len(photos) > 1 else ''} 1{'-2' if len(photos) > 1 else ''}: real photo(s) of the "
                  "object: keep its shape, proportions, colours and details, re-rendered in our style."] if photos else [])
        notes.append(f"Image {len(photos) + 1} is from our animated film: match only its rendering style.")
        pf = base / "prompt" / f"{key}.txt"
        pf.write_text(f"{w.get('style')}. A single prop reference picture: {w.get('prop:' + key)}\n" + " ".join(notes) +
                      "\nThe object alone, centred, three-quarter view, on a plain light-grey studio background with a "
                      "soft shadow. No hands, no people, no animals, no text, no logo, no watermark.\n", encoding="utf-8")
        if DRY:
            return key, f"prompt written: {pf}"
        out = w.prop_image(key)
        out.parent.mkdir(parents=True, exist_ok=True)
        wl.archive(out, w, "props")
        return key, wl.gen_image(photos + style, pf, out, base / "log")

    # ----- group pictures
    def group(self, name, scene_key=None, cast=None, action=None):
        w = self.w
        cast = cast or w.default_cast()
        base = self._dirs("groups")
        refs, notes = [], []
        if scene_key is None:  # the group's scene from world.json groups[]
            g = next((g for g in w.cfg.get("groups", []) if Path(g.get("path", "")).stem == name), {})
            scene_key = g.get("scene") or g.get("location")
        if scene_key:  # first, as the base picture: later references only add the characters (else the room drifts)
            refs.append(w.scene_image(scene_key))
            notes.append("image 1 is the scene and the base of the picture: keep its exact camera viewpoint, room "
                         "shape, furniture, furniture positions, colours and light, and only add the characters into it")
        for c in cast:
            refs.append(w.sheet(c))
            notes.append(f"image {len(refs)} is the character sheet of {w.char_label(c)}")
        hc = w.height_chart()
        if hc and name != "height_chart" and len(cast) > 1:
            refs.append(hc)
            notes.append(f"image {len(refs)} is the height chart: copy its true relative sizes")
        action = action or w.get("group:" + name)
        pf = base / "prompt" / f"{name}.txt"
        pf.write_text(f"{w.get('style')}. {w.ratio_words} picture, full-bleed.\nReferences: {'; '.join(notes)}.\n"
                      f"Scene: {action}\nCharacters: {w.get('characters')}\n"
                      + (f"Setting: {w.get('scene:' + scene_key)}\n" if scene_key else "")
                      + f"{w.one_each(cast).capitalize()}. {w.neg_image}\n", encoding="utf-8")
        if DRY:
            return name, f"prompt written: {pf}"
        out = w.root / "_asset" / f"{name}.png"
        wl.archive(out, w, "groups")
        return name, wl.gen_image(refs, pf, out, base / "log")

    def height(self):
        w = self.w
        lineup = [c for c in w.chars.values() if c.get("height_cm")]
        if len(lineup) < 2:
            return "height_chart", "needs 'height_cm' on at least two characters in world.json"
        lineup.sort(key=lambda c: -c["height_cm"])
        tallest = lineup[0]["height_cm"]
        desc = "; ".join(f"{c['name']} {c['height_cm']} cm {c.get('height_note', 'tall')} "
                         f"({round(100 * c['height_cm'] / tallest)}% of {lineup[0]['name']}'s height)" for c in lineup)
        scene = ("A height comparison line-up, all characters standing side by side on one flat floor line in front of "
                 f"a plain pale backdrop, full bodies visible, drawn exactly to scale: {desc}. "
                 "No ruler, no numbers, no text (the ruler is added later).")
        return self.group("height_chart", scene_key="", cast=[c["key"] for c in lineup], action=scene)


if __name__ == "__main__":
    wdir, args = wl.pop_world_arg([a for a in sys.argv[1:] if a != "--dry-run"])
    world = wl.World(wdir)
    if not args:
        sys.exit(__doc__)
    if not DRY:
        wl.require(("python", "image"), world)
    pics = Pictures(world)
    kind, args = args[0], args[1:]
    if kind == "sheet":
        jobs = [lambda k=k: pics.sheet(k) for k in args or list(world.chars)]
    elif kind in ("scene", "set"):
        refs, args = _opt(args, "--refs", None)
        custom = [world.p(r) for r in refs] if refs else None
        jobs = [lambda k=k: pics.set(k, custom) for k in args or world.scenes()]
    elif kind == "prop":
        jobs = [lambda k=k: pics.prop(k) for k in args or world.props()]
    elif kind == "group":
        loc, args = _opt(args, "--scene")
        old, args = _opt(args, "--location")  # older name of --scene
        cast, args = _opt(args, "--cast", None)
        action, args = _opt(args, "--action")
        jobs = [lambda n=n: pics.group(n, loc or old, cast, action) for n in args]
    elif kind == "height":
        jobs = [pics.height]
    else:
        sys.exit(__doc__)
    if not jobs:
        sys.exit("name at least one item")
    size = world.fmt["keyframe_size"]
    if kind == "sheet":  # each sheet patches its own size
        for status in map(lambda j: j(), jobs):
            print(*status, flush=True)
    else:
        with (wl.patched_config(wl.image_settings(world, size)) if not DRY else nullcontext()):
            with ThreadPoolExecutor(max_workers=4) as ex:
                for status in ex.map(lambda j: j(), jobs):
                    print(*status, flush=True)
