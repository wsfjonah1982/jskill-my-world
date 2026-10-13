"""Create the skeleton of the world in the skill's _world/: world.json, Identities.md, Setting.md, README.md, folders.

Usage:  python new_world.py [--name "World name"] [--input [DIR]] [--world DIR]    (name defaults to "My World")
There is only one world: _world/ is the world folder itself (--world DIR overrides it, for tests).
If _world/ already holds a world.json this refuses: a new cast, character, location or prop is merged into the
existing world (add sections to its Identities.md / Setting.md and entries to world.json), never made a second world.
--input copies the user's raw material (default: the skill's _input/) into _reference/input/, where it is kept as the
source record; sort the pictures into _reference/*/refs/ or _asset/ afterwards.
Afterwards fill every REPLACE in the canon files and world.json (worldlib.py check world lists what is left).
"""
import shutil
import sys
from datetime import date
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATES = SKILL_DIR / "templates"
WORLD_HOME = SKILL_DIR / "_world"
INPUT_DIR = SKILL_DIR / "_input"
FOLDERS = ["_asset/settings", "_asset/props", "_asset/voices", "_reference/characters/refs", "_reference/settings/refs",
           "_reference/props/refs", "_reference/voices/refs", "_reference/groups", "_reference/archive", "_tasks"]


def _pop(args, flag, default=None):
    """Pop `--flag [value]`; returns (value, args). A flag with no value gives `default`."""
    if flag not in args:
        return None, args
    i = args.index(flag)
    if i + 1 < len(args) and not args[i + 1].startswith("--"):
        return args[i + 1], args[:i] + args[i + 2:]
    return default, args[:i] + args[i + 1:]


if __name__ == "__main__":
    args = sys.argv[1:]
    name, args = _pop(args, "--name")
    name = name or "My World"
    src, args = _pop(args, "--input", str(INPUT_DIR))
    target, args = _pop(args, "--world")
    if args:
        sys.exit(__doc__)
    root = Path(target or WORLD_HOME).resolve()
    if (root / "world.json").exists():
        sys.exit(f"{root} already holds a world. Only one world exists: merge the new characters, locations and "
                 "props into its Identities.md, Setting.md and world.json instead.")
    root.mkdir(parents=True, exist_ok=True)
    for f in FOLDERS:
        (root / f).mkdir(parents=True, exist_ok=True)
    for t in ("world.json", "Identities.md", "Setting.md", "README.md"):
        dst = root / t
        if dst.exists():
            print(f"kept existing {t}")
            continue
        dst.write_text((TEMPLATES / t).read_text(encoding="utf-8").replace("{{NAME}}", name)
                       .replace("{{DATE}}", date.today().isoformat()), encoding="utf-8")
        print(f"wrote {dst}")
    if src:
        src = Path(src)
        if not src.is_dir():
            sys.exit(f"--input folder {src} does not exist.")
        shutil.copytree(src, root / "_reference" / "input", dirs_exist_ok=True)
        print(f"copied {src} -> {root / '_reference' / 'input'}")
    print(f"World skeleton ready at {root}")
