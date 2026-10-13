"""Create the skeleton of a new world: world.json, Identities.md, Setting.md, README.md and the folders.

Usage:  python new_world.py <folder> --name "World name"
Refuses to touch a folder that already has a world.json. Afterwards fill every REPLACE in the canon files and
world.json (worldlib.py check world lists what is left).
"""
import sys
from datetime import date
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
FOLDERS = ["_asset/settings", "_asset/props", "_asset/voices", "_reference/characters/refs", "_reference/settings/refs",
           "_reference/props/refs", "_reference/voices/refs", "_reference/groups", "_reference/archive", "_tasks"]

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or "--name" not in args:
        sys.exit(__doc__)
    i = args.index("--name")
    name = args[i + 1]
    root = Path(args[0] if i != 0 else args[2]).resolve()
    if (root / "world.json").exists():
        sys.exit(f"{root} already has a world.json; edit it instead.")
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
    print(f"World skeleton ready at {root}")
