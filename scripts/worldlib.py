"""Shared library for "My World" projects (used by the my-world and world-stories skills).

A world is a folder with a `world.json` manifest and two canon files, `Identities.md` (characters, voices) and
`Setting.md` (world, locations, props). Canon prompt blocks — a `<!-- prompt:<key> -->` marker followed by a fenced
code block — are pasted word for word into every image and video prompt, so every render of the world stays
consistent. Change a character or a place there, never in a single prompt.

Generation runs through this skill's own scripts/ark/ (Seedream images, Seedance videos, BytePlus ARK API), with
config.json for the endpoint and defaults; the settings of one call (model, size, ratio…) are passed to those scripts
in the MY_WORLD_ARK_OVERRIDES env var. Keys live in the skill's credential.json: `model_ark_key` (images, videos) and `speech_model_api_key` (voices).

CLI:  python worldlib.py canon [key] [--world DIR]   list every canon block, or print one
      python worldlib.py check [group ...] [--world DIR]   python | image | video | ffmpeg | voice | world
      python worldlib.py info [--world DIR]   the world's characters, locations and format
      python worldlib.py inputs   the candidate folders of the user's raw material (MY_WORLD_INPUT, _input, upload, mnt, input, in)
      python worldlib.py inspect <image> [sheet|set|any]   can a raw picture be used directly as an asset?
The world folder is --world, else the env var WORLD_DIR, else the nearest folder upwards from the current directory
that holds a world.json, else the skill's _world/ (one world only: a new cast or place is merged into it).
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ARK = SKILL_DIR / "scripts" / "ark"  # Seedream / Seedance scripts (copied from video-workflow; no other skill needed)
CONFIG = SKILL_DIR / "config.json"  # Ark endpoint and default settings
CREDENTIAL = SKILL_DIR / "credential.json"  # model_ark_key (images, videos) + speech_model_api_key (voices)
OVERRIDES_ENV = "MY_WORLD_ARK_OVERRIDES"
WORLD_HOME = SKILL_DIR / "_world"  # the one world of this skill (git-ignored)
# The user's raw material: the folder name depends on the environment (an upload area, a mount, a plain folder), so
# the user decides. MY_WORLD_INPUT names it; otherwise any of these names next to the skill or in the cwd is a candidate.
INPUT_ENV = "MY_WORLD_INPUT"
INPUT_NAMES = ("_input", "upload", "uploads", "mnt", "input", "in")
GROUPS = ("python", "image", "video", "ffmpeg", "voice", "world")
CANON_FILES = ("Identities.md", "Setting.md")
REQUIRED_BLOCKS = ("style", "characters", "video-defs", "video-rules", "audio", "world")
_BLOCK = re.compile(r"<!--\s*prompt:([\w:-]+)\s*-->\s*```[^\n]*\n(.*?)```", re.S)

DEFAULT_FORMAT = {"ratio": "16:9", "keyframe_size": "2560x1440", "resolution": "720p", "short_min": 10,
                  "short_max": 20, "short_options": [10, 15, 20], "segment_seconds": 20, "audio": True}
_CFG = json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.is_file() else {}
# Model ids come from config.json (image_model_id, video_model_id, audio_model_id); world.json `models` overrides.
DEFAULT_MODELS = {"image": _CFG.get("image_model_id", "dola-seedream-5-0-pro-260628"),
                  "video": _CFG.get("video_model_id", "dreamina-seedance-2-5-260628"),
                  "speech": _CFG.get("audio_model_id", "seed-audio-1.0"),
                  "speech_endpoint": _CFG.get("audio_api_endpoint",
                                              "https://voice.ap-southeast-1.bytepluses.com/api/v3/tts/create")}
RATIO_WORDS = {"16:9": "Horizontal 16:9 landscape", "9:16": "Vertical 9:16 portrait", "1:1": "Square 1:1"}
NEG_IMAGE = ("no text, no captions, no speech bubbles, no logo, no brand names, no watermark, no readable signs or "
             "screens, no extra people or animals, no split panels, no borders.")
NEG_VIDEO = ("no watermark, no logo, no brand text, no subtitles, no captions, no on-screen text, subtitle-free, "
             "no twin subjects, no style drift, keep the art style of @image1 throughout, no flicker.")


# ---------------------------------------------------------------- the user's raw input
def find_inputs():
    """Candidate raw-input folders: [MY_WORLD_INPUT] when set, else every existing INPUT_NAMES folder next to the skill
    or in the cwd. More than one (or none) means: ask the user which folder holds their material."""
    if os.environ.get(INPUT_ENV):
        return [Path(os.environ[INPUT_ENV]).resolve()]
    found = []
    for base in (SKILL_DIR, Path.cwd()):
        for n in INPUT_NAMES:
            p = (base / n).resolve()
            if p.is_dir() and p not in found and p != WORLD_HOME.resolve():
                found.append(p)
    return found


def inspect_image(path, kind="sheet"):
    """Measurable conditions for using a raw picture directly as an asset. Returns (facts, problems).
    kind: sheet (character three-view on a plain background), set (empty location), any."""
    from PIL import Image, ImageFilter, ImageStat
    im = Image.open(path)
    w, h = im.size
    facts = {"size": f"{w}x{h}", "ratio": round(w / h, 3), "mode": im.mode}
    problems = []
    if min(w, h) < 1080:
        problems.append(f"short side {min(w, h)}px < 1080px (generated assets are 2K: 2560x1440 or 2816x1584)")
    if kind in ("sheet", "set") and abs(w / h - 16 / 9) > 0.03:
        problems.append(f"aspect {w}:{h} is not 16:9 like the other assets")
    g = im.convert("L")
    sharp = ImageStat.Stat(g.filter(ImageFilter.FIND_EDGES)).var[0]
    facts["edge_variance"] = round(sharp, 1)  # for comparing pictures only: blur is judged by looking, not by this
    if kind == "sheet":
        rgb = im.convert("RGB")
        strips = [rgb.crop(b) for b in ((0, 0, w, h // 20), (0, 0, w // 40, h), (w - w // 40, 0, w, h))]
        mean = [sum(ImageStat.Stat(s).mean) / 3 for s in strips]
        spread = max(sum(ImageStat.Stat(s).stddev) / 3 for s in strips)
        facts["border_brightness"] = round(min(mean)); facts["border_noise"] = round(spread, 1)
        if min(mean) < 200 or spread > 12:
            problems.append("background at the edges is not plain and light (a sheet needs a clean backdrop)")
    if im.mode in ("P", "L", "1"):
        problems.append(f"colour mode {im.mode}: convert to RGB")
    return facts, problems


# ---------------------------------------------------------------- the world
def resolve_world(arg):
    """`--world` value: a folder path."""
    return Path(arg).resolve()


def find_world(start=None):
    """The world folder: WORLD_DIR, else the nearest folder upwards from `start` (or the cwd) with a world.json,
    else the skill's _world/ (there is only ever one world)."""
    if os.environ.get("WORLD_DIR") and start is None:
        return resolve_world(os.environ["WORLD_DIR"])
    p = Path(start or Path.cwd()).resolve()
    for d in [p, *p.parents]:
        if (d / "world.json").is_file():
            return d
    if (WORLD_HOME / "world.json").is_file():
        return WORLD_HOME
    sys.exit(f"DEPENDENCY ERROR [WORLD]: no world.json in {p} or any folder above it, nor in {WORLD_HOME}. "
             "Create the world with my-world's new_world.py, or pass --world DIR / set WORLD_DIR.")


def pop_world_arg(argv):
    """Remove `--world DIR` from argv and return (DIR or None, argv)."""
    if "--world" in argv:
        i = argv.index("--world")
        return argv[i + 1], argv[:i] + argv[i + 2:]
    return None, argv


class World:
    def __init__(self, root=None):
        self.root = resolve_world(root) if root else find_world()
        mf = self.root / "world.json"
        if not mf.is_file():
            sys.exit(f"DEPENDENCY ERROR [WORLD]: {mf} is missing.")
        self.cfg = json.loads(mf.read_text(encoding="utf-8"))
        self.fmt = {**DEFAULT_FORMAT, **self.cfg.get("format", {})}
        self.models = {**DEFAULT_MODELS, **self.cfg.get("models", {})}
        self.chars = {c["key"]: c for c in self.cfg.get("characters", [])}
        self._blocks = None

    # names and paths
    @property
    def name(self):
        return self.cfg.get("name", self.root.name)

    def p(self, rel):
        return self.root / rel

    @property
    def tasks_dir(self):
        return self.root / "_tasks"

    @property
    def overview(self):
        return self.root / "world.html"

    def char_name(self, key):
        return self.chars[key]["name"]

    def char_label(self, key):
        """'Xiao Li (the girl)'"""
        c = self.chars[key]
        return f"{c['name']} ({c['label']})" if c.get("label") else c["name"]

    def sheet(self, key):
        return self.root / self.chars[key].get("sheet", f"_asset/{key}.png")

    def default_cast(self):
        return [k for k, c in self.chars.items() if c.get("main", True)]

    def one_each(self, cast):
        """'exactly one girl, exactly one cat' — the count rule the models need for every character on screen."""
        return ", ".join(f"exactly one {self.chars[c].get('kind', self.chars[c]['name'])}" for c in cast)

    @property
    def ratio_words(self):
        return RATIO_WORDS.get(self.fmt["ratio"], self.fmt["ratio"])

    @property
    def neg_image(self):
        return self.cfg.get("negative_image", NEG_IMAGE)

    @property
    def neg_video(self):
        return self.cfg.get("negative_video", NEG_VIDEO)

    @property
    def no_props_rule(self):
        return self.cfg.get("no_props_rule", "Props: only what the scene describes; no other recurring props.")

    # canon
    def blocks(self):
        if self._blocks is None:
            out = {}
            for name in CANON_FILES:
                path = self.root / name
                if not path.is_file():
                    sys.exit(f"DEPENDENCY ERROR [CANON]: {path} is missing; it is the canonical source for every render.")
                for key, text in _BLOCK.findall(path.read_text(encoding="utf-8")):
                    out[key] = " ".join(text.split())
            self._blocks = out
        return self._blocks

    def get(self, key, default=None):
        b = self.blocks()
        if key in b:
            return b[key]
        if default is not None:
            return default
        sys.exit(f"DEPENDENCY ERROR [CANON]: no '<!-- prompt:{key} -->' block in {' or '.join(CANON_FILES)} "
                 f"of {self.root}. Known: {', '.join(sorted(b))}")

    def locations(self):
        return sorted(k.split(":", 1)[1] for k in self.blocks() if k.startswith("location:"))

    def location_image(self, key):
        return self.root / "_asset" / "settings" / f"{key}.png"

    def prop_image(self, key):
        return self.root / "_asset" / "props" / f"{key}.png"

    def height_chart(self):
        p = self.root / self.cfg.get("height_chart", "_asset/height_chart.png")
        return p if p.is_file() else None


# ---------------------------------------------------------------- dependencies
def _python():
    errs = []
    if sys.version_info < (3, 10):
        errs.append(("PY-VERSION", f"Python 3.10+ is required, found {sys.version.split()[0]}."))
    for mod, pkg in (("PIL", "Pillow"), ("numpy", "numpy"), ("requests", "requests")):
        if importlib.util.find_spec(mod) is None:
            errs.append(("PY-PACKAGE", f"Python package '{pkg}' is not installed. Run: pip install {pkg}"))
    return errs


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def ark_api_key():
    """BytePlus ARK API key: env var `model_ark_key`, else `model_ark_key` in the skill's credential.json."""
    return os.environ.get("model_ark_key") or (_read_json(CREDENTIAL) or {}).get("model_ark_key")


def _ark(need_video):
    scripts = ["ark_service.py", "generate_image_from_reference.py", "generate_character_sheet.py",
               "three_angle_character_sheet.txt"]
    if need_video:
        scripts += ["generate_video_from_reference.py", "resume_video_task.py"]
    errs = [("ARK-SCRIPTS", f"my-world is incomplete: scripts/ark/{s} is missing.") for s in scripts
            if not (ARK / s).is_file()]
    cfg = _read_json(CONFIG)
    if cfg is None:
        return errs + [("CONFIG", f"{CONFIG} is missing or invalid.")]
    if not cfg.get("maas_api_endpoint"):
        errs.append(("API-ENDPOINT", f"{CONFIG} has no 'maas_api_endpoint' (BytePlus ARK endpoint)."))
    if not ark_api_key():
        errs.append(("API-KEY", "BytePlus ARK API key not found: set the env var 'model_ark_key' or put "
                                f"'model_ark_key' in {CREDENTIAL} (template: credential_tmp.json)."))
    return errs


def speech_credential(world=None):
    p = os.environ.get("SPEECH_CREDENTIAL_FILE") or (world.cfg.get("speech_credential") if world else None)
    return Path(p) if p else None


def speech_api_key(world=None):
    """BytePlus speech (Seed Audio) API key: env var `speech_model_api_key`, then the world's speech_credential file,
    then `speech_model_api_key` in the skill's credential.json. None if missing. (The ARK key is rejected by the
    speech API with 401 Invalid X-Api-Key, so it is not a fallback.)"""
    if os.environ.get("speech_model_api_key"):
        return os.environ["speech_model_api_key"]
    cred = speech_credential(world)
    c = (_read_json(cred) or {}) if cred else {}
    key = c.get("speech_model_api_key") or c.get("api_key")
    return key or (_read_json(CREDENTIAL) or {}).get("speech_model_api_key")


def _world(world):
    if world is None:
        return [("WORLD", "no world folder given")]
    errs = [("CANON", f"{f} is missing; it is the canonical source of every render.")
            for f in CANON_FILES if not (world.root / f).is_file()]
    if errs:
        return errs
    if not world.chars:
        errs.append(("WORLD", "world.json has no characters."))
    blocks = world.blocks()
    need = list(REQUIRED_BLOCKS) + (["voice"] if world.fmt["audio"] else [])
    errs += [("CANON", f"canon block '<!-- prompt:{k} -->' is missing.") for k in need if k not in blocks]
    errs += [("CANON", f"canon block '{k}' still has a REPLACE placeholder.") for k, v in blocks.items() if "REPLACE" in v]
    if not world.locations():
        errs.append(("CANON", "Setting.md has no '<!-- prompt:location:<key> -->' block."))
    for k in world.chars:
        if not world.sheet(k).is_file():
            errs.append(("ASSET", f"Character sheet of '{k}' is missing: {world.sheet(k)} (my-world: world_images.py sheet {k})."))
    return errs


def check(groups=GROUPS, world=None):
    errs = []
    if "python" in groups:
        errs += _python()
    if "image" in groups or "video" in groups:
        errs += _ark(need_video="video" in groups)
    if "ffmpeg" in groups:
        errs += [("FFMPEG", f"'{t}' is not on PATH. Install FFmpeg and add its bin folder to PATH.")
                 for t in ("ffmpeg", "ffprobe") if shutil.which(t) is None]
    if "voice" in groups and not speech_api_key(world):
        errs.append(("SPEECH-KEY", "BytePlus speech API key (Seed Audio) not found: put 'speech_model_api_key' in "
                                   f"{CREDENTIAL} (next to model_ark_key), or set the env var 'speech_model_api_key'."))
    if "world" in groups:
        errs += _world(world)
    return list(dict.fromkeys(errs))


def require(groups=GROUPS, world=None):
    """Print every missing dependency as `DEPENDENCY ERROR [<code>]: <message>` and exit 1; silent when all present.
    A missing dependency is reported to the user verbatim, never worked around."""
    errs = check(groups, world)
    for code, msg in errs:
        print(f"DEPENDENCY ERROR [{code}]: {msg}", file=sys.stderr)
    if errs:
        sys.exit(1)


# ---------------------------------------------------------------- generation (scripts/ark)
_OVERRIDES = []  # stack of per-call settings; a module global so worker threads of one batch share it


@contextmanager
def patched_config(overrides):
    """Settings (model, size, ratio…) for every generation call inside the block, on top of config.json."""
    _OVERRIDES.append(dict(overrides))
    try:
        yield
    finally:
        _OVERRIDES.pop()


def _run(cmd):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    if _OVERRIDES:
        env[OVERRIDES_ENV] = json.dumps({k: v for o in _OVERRIDES for k, v in o.items()})
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ARK), env=env)
    return r, ("done" if r.returncode == 0 else "failed: " + (r.stderr.strip().splitlines() or ["?"])[-1])


def image_settings(world, size=None):
    return {"image_model_id": world.models["image"], "image_size": size or world.fmt["keyframe_size"], "watermark": False}


def gen_image(refs, prompt_file, out, log_dir):
    """One Seedream image from reference images + a prompt file. Call inside patched_config(image_settings(...))."""
    _, status = _run([sys.executable, str(ARK / "generate_image_from_reference.py"), "--img", *map(str, refs),
                      "--prompt", str(prompt_file), "--output", str(out), "--log-dir", str(log_dir)])
    return status


def gen_sheet(idea_file, style, refs, out, log_dir):
    """A three-view character sheet (front / side / back) from a description file. Call inside patched_config."""
    cmd = [sys.executable, str(ARK / "generate_character_sheet.py"), "--idea", str(idea_file), "--style", style,
           "--output", str(out), "--log-dir", str(log_dir)]
    if refs:
        cmd += ["--img", *map(str, refs)]
    return _run(cmd)[1]


def gen_video(world, keyframe, prompt_file, duration, out, log_dir):
    """One Seedance first-frame clip: the keyframe is the literal opening frame. Returns (ok, message).
    Seedance is paid per task: once a task id exists, never submit again; recover it with resume_video_task.py."""
    out = Path(out)
    if out.exists():
        return True, "exists"
    overrides = {"video_model_id": world.models["video"], "video_ratio": world.fmt["ratio"],
                 "video_resolution": world.fmt["resolution"], "video_duration_seconds": int(duration),
                 "generate_audio": bool(world.fmt["audio"]), "watermark": False}
    with patched_config(overrides):
        r, status = _run([sys.executable, str(ARK / "generate_video_from_reference.py"), "--img", str(keyframe),
                          "--prompt", str(prompt_file), "--output", str(out), "--log-dir", str(log_dir)])
    if r.returncode == 0 and out.exists():
        return True, "done"
    paid = "task_id" in r.stderr or "task id" in r.stderr.lower()
    hint = (f" — task already submitted (paid): recover it with python {ARK / 'resume_video_task.py'} "
            f"--task-id <id from {log_dir}> --output {out}") if paid else ""
    return False, status + hint


def archive(path, world, kind):
    """Move an existing asset to _reference/archive/<kind>/ with a timestamp before it is redrawn; returns the new path."""
    path = Path(path)
    if path.exists():
        dst = world.root / "_reference" / "archive" / kind
        dst.mkdir(parents=True, exist_ok=True)
        dst = dst / f"{path.stem}_{datetime.now():%Y%m%d_%H%M%S}{path.suffix}"
        shutil.move(str(path), str(dst))
        return dst
    return None


def rel(path, base):
    return os.path.relpath(path, base).replace(os.sep, "/")


# ---------------------------------------------------------------- CLI
if __name__ == "__main__":
    wdir, args = pop_world_arg(sys.argv[1:])
    cmd = args[0] if args else "info"
    if cmd == "check":
        groups = args[1:] or list(GROUPS)
        bad = [g for g in groups if g not in GROUPS]
        if bad:
            sys.exit(f"Unknown group(s): {', '.join(bad)}. Choose from: {', '.join(GROUPS)}")
        w = World(wdir) if ("world" in groups or "voice" in groups) else None
        require(groups, w)
        print(f"All dependencies present ({', '.join(groups)}).")
    elif cmd == "canon":
        w = World(wdir)
        if len(args) > 1:
            print(w.get(args[1]))
        else:
            for k, v in w.blocks().items():
                print(f"[{k}] {v}\n")
    elif cmd == "info":
        w = World(wdir)
        print(f"World: {w.name}  ({w.root})")
        for k, c in w.chars.items():
            print(f"  character {k}: {w.char_label(k)}  sheet {'ok' if w.sheet(k).is_file() else 'MISSING'}")
        for k in w.locations():
            print(f"  location {k}: picture {'ok' if w.location_image(k).is_file() else 'MISSING'}")
        print(f"  format: {w.fmt}")
    elif cmd == "inputs":
        found = find_inputs()
        for p in found:
            print(f"{p}  ({sum(1 for f in p.rglob('*') if f.is_file())} files)")
        if len(found) != 1:
            print(("No" if not found else "Several") + " input folders found: ask the user which folder holds their "
                  f"material, then pass it as --input DIR (or set {INPUT_ENV}).")
    elif cmd == "inspect" and len(args) > 1:
        facts, problems = inspect_image(args[1], args[2] if len(args) > 2 else "sheet")
        print("  ".join(f"{k}={v}" for k, v in facts.items()))
        print("\n".join(f"PROBLEM: {p}" for p in problems) or "measurable checks OK: now look at it (see SKILL.md)")
    else:
        sys.exit("usage: worldlib.py canon [key] | check [group ...] | info | inputs | inspect <image> [sheet|set|any]"
                 "  [--world DIR]")
