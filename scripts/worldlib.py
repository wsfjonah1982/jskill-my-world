"""Shared library for "My World" projects (used by the my-world and world-stories skills).

A world is a folder with a `world.json` manifest and two canon files, `Identities.md` (characters, voices) and
`Setting.md` (world, locations, props). Canon prompt blocks — a `<!-- prompt:<key> -->` marker followed by a fenced
code block — are pasted word for word into every image and video prompt, so every render of the world stays
consistent. Change a character or a place there, never in a single prompt.

Generation goes through the `video-workflow` skill (Seedream images, Seedance videos, BytePlus ARK API). Its scripts
read settings only from its own config.json, so this module patches that file for the length of one call, under a
lock, and restores it byte for byte afterwards.

CLI:  python worldlib.py canon [key] [--world DIR]   list every canon block, or print one
      python worldlib.py check [group ...] [--world DIR]   python | image | video | ffmpeg | voice | world
      python worldlib.py info [--world DIR]   the world's characters, locations and format
The world folder is --world, else the env var WORLD_DIR, else the nearest folder upwards from the current
directory that holds a world.json.
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
VW = Path(os.environ.get("VIDEO_WORKFLOW_DIR", SKILL_DIR.parent / "video-workflow"))
GROUPS = ("python", "image", "video", "ffmpeg", "voice", "world")
CANON_FILES = ("Identities.md", "Setting.md")
REQUIRED_BLOCKS = ("style", "characters", "video-defs", "video-rules", "audio", "world")
_BLOCK = re.compile(r"<!--\s*prompt:([\w:-]+)\s*-->\s*```[^\n]*\n(.*?)```", re.S)
# Same lock name as brand-ads-footage, so tools of both never patch the video-workflow config at once.
LOCK_NAME = "config.json.brand-ads-footage.lock"
STALE_LOCK_S = 2 * 60 * 60

DEFAULT_FORMAT = {"ratio": "16:9", "keyframe_size": "2560x1440", "resolution": "720p", "short_min": 10,
                  "short_max": 20, "short_options": [10, 15, 20], "segment_seconds": 20, "audio": True}
DEFAULT_MODELS = {"image": "dola-seedream-5-0-pro-260628", "video": "dreamina-seedance-2-5-260628",
                  "speech": "seed-audio-1.0-multilingual",
                  "speech_endpoint": "https://voice.ap-southeast-1.bytepluses.com/api/v3/tts/create"}
RATIO_WORDS = {"16:9": "Horizontal 16:9 landscape", "9:16": "Vertical 9:16 portrait", "1:1": "Square 1:1"}
NEG_IMAGE = ("no text, no captions, no speech bubbles, no logo, no brand names, no watermark, no readable signs or "
             "screens, no extra people or animals, no split panels, no borders.")
NEG_VIDEO = ("no watermark, no logo, no brand text, no subtitles, no captions, no on-screen text, subtitle-free, "
             "no twin subjects, no style drift, keep the art style of @image1 throughout, no flicker.")


# ---------------------------------------------------------------- the world
def find_world(start=None):
    """The world folder: WORLD_DIR, else the nearest folder upwards from `start` (or the cwd) with a world.json."""
    if os.environ.get("WORLD_DIR") and start is None:
        return Path(os.environ["WORLD_DIR"]).resolve()
    p = Path(start or Path.cwd()).resolve()
    for d in [p, *p.parents]:
        if (d / "world.json").is_file():
            return d
    sys.exit(f"DEPENDENCY ERROR [WORLD]: no world.json in {p} or any folder above it. "
             "Pass --world DIR, set WORLD_DIR, or create a world with my-world's new_world.py.")


def pop_world_arg(argv):
    """Remove `--world DIR` from argv and return (DIR or None, argv)."""
    if "--world" in argv:
        i = argv.index("--world")
        return argv[i + 1], argv[:i] + argv[i + 2:]
    return None, argv


class World:
    def __init__(self, root=None):
        self.root = Path(root).resolve() if root else find_world()
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
        return self.root / "project_overview.html"

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


def _video_workflow(need_video):
    if not (VW / "SKILL.md").is_file():
        return [("SKILL-VIDEO-WORKFLOW", f"Skill 'video-workflow' not found at {VW}. Install it there or set VIDEO_WORKFLOW_DIR.")]
    errs = []
    scripts = ["ark_service.py", "generate_image_from_reference.py", "generate_character_sheet.py"]
    if need_video:
        scripts += ["generate_video_from_reference.py", "resume_video_task.py"]
    for s in scripts:
        if not (VW / "scripts" / s).is_file():
            errs.append(("SKILL-VIDEO-WORKFLOW", f"Skill 'video-workflow' is incomplete: scripts/{s} is missing."))
    try:
        cfg = json.loads((VW / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return errs + [("SKILL-VIDEO-WORKFLOW", f"Skill 'video-workflow' config.json is missing or invalid ({e}).")]
    if not cfg.get("maas_api_endpoint"):
        errs.append(("API-ENDPOINT", "video-workflow config.json has no 'maas_api_endpoint' (BytePlus ARK endpoint)."))
    if not os.environ.get("model_ark_key"):
        cred = VW / "credential.json"
        try:
            ok = bool(json.loads(cred.read_text(encoding="utf-8")).get("model_ark_key"))
        except (OSError, ValueError):
            ok = False
        if not ok:
            errs.append(("API-KEY", "BytePlus ARK API key not found: set the env var 'model_ark_key' "
                                    f"or put 'model_ark_key' in {cred}."))
    return errs


def speech_credential(world=None):
    p = os.environ.get("SPEECH_CREDENTIAL_FILE") or (world.cfg.get("speech_credential") if world else None)
    return Path(p) if p else None


def speech_api_key(world=None):
    """BytePlus speech (Seed Audio) API key: env var first, then the credential file. None if missing."""
    if os.environ.get("speech_model_api_key"):
        return os.environ["speech_model_api_key"]
    cred = speech_credential(world)
    try:
        c = json.loads(cred.read_text(encoding="utf-8")) if cred else {}
    except (OSError, ValueError):
        return None
    return c.get("speech_model_api_key") or c.get("api_key")


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
        errs += _video_workflow(need_video="video" in groups)
    if "ffmpeg" in groups:
        errs += [("FFMPEG", f"'{t}' is not on PATH. Install FFmpeg and add its bin folder to PATH.")
                 for t in ("ffmpeg", "ffprobe") if shutil.which(t) is None]
    if "voice" in groups and not speech_api_key(world):
        errs.append(("SPEECH-KEY", "BytePlus speech API key (Seed Audio) not found: set the env var 'speech_model_api_key', "
                                   "or point world.json 'speech_credential' (or SPEECH_CREDENTIAL_FILE) at a JSON file with it."))
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


# ---------------------------------------------------------------- generation (video-workflow)
def _acquire(lock, wait_s=3 * 60 * 60):
    deadline = time.monotonic() + wait_s
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return
        except FileExistsError:
            if time.time() - lock.stat().st_mtime > STALE_LOCK_S:
                lock.unlink(missing_ok=True)
                continue
            if time.monotonic() > deadline:
                raise TimeoutError(f"Timed out waiting for lock {lock}")
            print("video-workflow config is locked by another generation, waiting...", file=sys.stderr)
            time.sleep(30)


@contextmanager
def patched_config(overrides):
    """Apply `overrides` to video-workflow's config.json for the length of the block, then restore it exactly."""
    cfg = VW / "config.json"
    lock = cfg.with_name(LOCK_NAME)
    _acquire(lock)
    original = cfg.read_bytes()
    try:
        patched = json.loads(original.decode("utf-8"))
        patched.update(overrides)
        cfg.write_text(json.dumps(patched, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        yield
    finally:
        cfg.write_bytes(original)
        lock.unlink(missing_ok=True)


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(VW),
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    return r, ("done" if r.returncode == 0 else "failed: " + (r.stderr.strip().splitlines() or ["?"])[-1])


def image_settings(world, size=None):
    return {"image_model_id": world.models["image"], "image_size": size or world.fmt["keyframe_size"], "watermark": False}


def gen_image(refs, prompt_file, out, log_dir):
    """One Seedream image from reference images + a prompt file. Call inside patched_config(image_settings(...))."""
    _, status = _run([sys.executable, str(VW / "scripts/generate_image_from_reference.py"), "--img", *map(str, refs),
                      "--prompt", str(prompt_file), "--output", str(out), "--log-dir", str(log_dir)])
    return status


def gen_sheet(idea_file, style, refs, out, log_dir):
    """A three-view character sheet (front / side / back) from a description file. Call inside patched_config."""
    cmd = [sys.executable, str(VW / "scripts/generate_character_sheet.py"), "--idea", str(idea_file), "--style", style,
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
        r, status = _run([sys.executable, str(VW / "scripts/generate_video_from_reference.py"), "--img", str(keyframe),
                          "--prompt", str(prompt_file), "--output", str(out), "--log-dir", str(log_dir)])
    if r.returncode == 0 and out.exists():
        return True, "done"
    paid = "task_id" in r.stderr or "task id" in r.stderr.lower()
    hint = (f" — task already submitted (paid): recover it with python {VW / 'scripts/resume_video_task.py'} "
            f"--task-id <id from {log_dir}> --output {out}") if paid else ""
    return False, status + hint


def archive(path, world, kind):
    """Move an existing asset to _reference/archive/<kind>/ with a timestamp before it is redrawn."""
    path = Path(path)
    if path.exists():
        dst = world.root / "_reference" / "archive" / kind
        dst.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(dst / f"{path.stem}_{datetime.now():%Y%m%d_%H%M%S}{path.suffix}"))


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
    else:
        sys.exit("usage: worldlib.py canon [key] | check [group ...] | info  [--world DIR]")
