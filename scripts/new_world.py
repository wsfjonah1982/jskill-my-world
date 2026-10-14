"""Create the skeleton of the world in the skill's _world/: world.json, Identities.md, Setting.md, world.md, folders.

Usage:  python new_world.py [--name "World name"] [--input [DIR]] [--world DIR]    (name defaults to "My World")
There is only one world: _world/ is the world folder itself (--world DIR overrides it, for tests).
If _world/ already holds a world.json this refuses: a new cast, character, location or prop is merged into the
existing world (add sections to its Identities.md / Setting.md and entries to world.json), never made a second world.
--input DIR copies the user's raw material into _reference/input/, where it stays as the source record (the raw folder
may be archived later, so the world never points at it). Its name depends on the environment (_input, upload, mnt,
input, in...) and is the user's choice; --input alone takes the only candidate worldlib.find_inputs() sees (or
MY_WORLD_INPUT) and stops if there are none or several. Sort the pictures into _reference/*/refs/ or _asset/ afterwards
(a raw picture goes into _asset/ directly only after worldlib.py inspect and a visual check).
Afterwards fill every REPLACE in the canon files and world.json (worldlib.py check world lists what is left).
"""
import shutil
import sys
from datetime import date
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATES = SKILL_DIR / "templates"
WORLD_HOME = SKILL_DIR / "_world"
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
    src, args = _pop(args, "--input", "auto")
    if src == "auto":
        sys.path.insert(0, str(SKILL_DIR / "scripts"))
        from worldlib import find_inputs
        found = find_inputs()
        if len(found) != 1:
            sys.exit(("No input folder found" if not found else "Several input folders: " + ", ".join(map(str, found)))
                     + ". Ask the user which folder holds their material and pass it: --input DIR.")
        src = str(found[0])
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
    for t in ("world.json", "Identities.md", "Setting.md", "world.md"):
        dst = root / t
        if dst.exists():
            print(f"kept existing {t}")
            continue
        dst.write_text((TEMPLATES / t).read_text(encoding="utf-8").replace("{{NAME}}", name)
                       .replace("{{DATE}}", date.today().isoformat()), encoding="utf-8")
        print(f"wrote {dst}")
    sys.path.insert(0, str(SKILL_DIR / "scripts"))
    import worldlib
    print(f"world_id {worldlib.world_id(worldlib.World(root))} (makes the publish path unique)")
    if src:
        src = Path(src)
        if not src.is_dir():
            sys.exit(f"--input folder {src} does not exist.")
        shutil.copytree(src, root / "_reference" / "input", dirs_exist_ok=True)
        (root / "_reference" / "input" / "SOURCE.txt").write_text(f"copied from {src.resolve()} on {date.today()}\n",
                                                                  encoding="utf-8")
        print(f"copied {src} -> {root / '_reference' / 'input'}")
    print(f"World skeleton ready at {root}")
