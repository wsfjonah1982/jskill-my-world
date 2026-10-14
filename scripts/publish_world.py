"""Publish the world's pages to BytePlus TOS object storage (public-read), or to a local folder.

What is published: world.html and every local file it links to, following the links of linked HTML pages (the
voices page, sheets, sets, group pictures, voice clips, the canon files). Nothing else: never _reference/input/
(the user's raw material), logs, prompts, the archive or credentials.

Settings: the skill's publish_config.json (deploy_endpoint, deploy_region, deploy_bucket, deploy_prefix_template with
{slug}, local_publish_dir); keys: credential.json tos_access_key_id / tos_secret_access_key (env vars of the same
names win). Without keys the files are copied to local_publish_dir/<slug>/ instead.

The path is unique per world: <deploy_prefix_template with slug = <name>-<8 chars of world.json world_id>>, e.g.
world/my-world-3f9a1c2b/, created once and kept in world.json `publish`, so republishing updates this world's own copy
and worlds from other sessions never collide. Before replacing anything, the published world.json is read back: if it
belongs to another world_id the upload is refused, even with --overwrite.

Usage:  python publish_world.py [--slug SLUG] [--dry-run] [--overwrite] [--keep-stale] [--world DIR]
  --slug        a custom slug instead of the world's own (still checked against the published world_id)
  --dry-run     list what would be published, upload nothing
  --overwrite   replace an upload that has no world_id to check (an old or foreign upload); this world's own copy is
                updated without it
  --keep-stale  do not delete objects under the slug that are no longer part of the world
Prints the public URL of world.html. The log goes to <world>/_reference/log/publish.log.
"""
import json
import mimetypes
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, unquote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import worldlib as wl  # noqa: E402

PUBLISH_CONFIG = wl.SKILL_DIR / "publish_config.json"
SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
NEVER = ("_reference/input/", "_reference/log/", "_reference/archive/", "credential")
TEXT_TYPES = {".html": "text/html; charset=utf-8", ".md": "text/plain; charset=utf-8",
              ".json": "text/plain; charset=utf-8", ".txt": "text/plain; charset=utf-8"}
CACHE_HTML, CACHE_ASSET = "no-cache", "public, max-age=3600"


def linked_files(root):
    """world.html plus every local file it links to, recursively through linked HTML pages."""
    seen, todo = set(), [root / "world.html"]
    while todo:
        p = todo.pop()
        if p in seen or not p.is_file():
            continue
        seen.add(p)
        if p.suffix.lower() in (".html", ".htm"):
            for link in re.findall(r"(?:src|href)=['\"]([^'\"#?]+)", p.read_text(encoding="utf-8")):
                if re.match(r"^([a-z]+:|//)", link, re.I):
                    continue
                q = (p.parent / unquote(link)).resolve()
                if q.is_relative_to(root) and q.is_file():
                    todo.append(q)
    files = sorted(seen)
    bad = [f for f in files if any(n in f.relative_to(root).as_posix() for n in NEVER)]
    if bad:
        raise SystemExit("Refusing to publish private files linked from the pages: "
                         + ", ".join(f.relative_to(root).as_posix() for f in bad))
    return files


def remote_world_id(url):
    """world_id in the published world.json, or None (missing, unreadable)."""
    import requests
    try:
        r = requests.get(url, timeout=30)
        return r.json().get("world_id") if r.ok else None
    except (requests.RequestException, ValueError):
        return None


def credential(name):
    return os.environ.get(name) or (wl._read_json(wl.CREDENTIAL) or {}).get(name) or ""


def main():
    wdir, args = wl.pop_world_arg(sys.argv[1:])
    w = wl.World(wdir)
    flag = lambda f: f in args
    wid = wl.world_id(w)
    slug = args[args.index("--slug") + 1] if "--slug" in args else w.cfg.get("publish", {}).get("slug") or wl.publish_slug(w)
    if not SLUG_RE.fullmatch(slug):
        sys.exit(f"Invalid slug {slug!r}: 1-64 lowercase letters, digits and hyphens.")
    cfg = wl._read_json(PUBLISH_CONFIG) or {}
    template = cfg.get("deploy_prefix_template", "world/{slug}")
    if not template.rstrip("/").endswith("{slug}"):
        sys.exit(f"deploy_prefix_template must end with {{slug}}, got {template!r}")
    prefix = template.replace("{slug}", slug).strip("/")

    if not w.overview.is_file():
        sys.exit("world.html is missing: run evaluate_world.py (or build_overview.py) first.")
    files = linked_files(w.root)
    rels = [f.relative_to(w.root).as_posix() for f in files]
    size = sum(f.stat().st_size for f in files)
    print(f"{len(files)} files, {size / 1e6:.1f} MB -> {prefix}/", file=sys.stderr)

    ak, sk = credential("tos_access_key_id"), credential("tos_secret_access_key")
    ak, sk = ("" if ak == "..." else ak), ("" if sk == "..." else sk)
    endpoint, region, bucket = cfg.get("deploy_endpoint"), cfg.get("deploy_region"), cfg.get("deploy_bucket")
    if flag("--dry-run"):
        for r in rels:
            print(f"  {r}", file=sys.stderr)
        target = f"https://{bucket}.{endpoint}/{prefix}/world.html" if ak and sk else "local copy"
        print(f"dry run: nothing uploaded; would publish to {target}")
        return
    log = w.root / "_reference" / "log" / "publish.log"
    log.parent.mkdir(parents=True, exist_ok=True)

    if not (ak and sk):
        if ak or sk:
            sys.exit("Only one of tos_access_key_id / tos_secret_access_key is set in credential.json.")
        local = (cfg.get("local_publish_dir") or "").strip()
        if not local:
            sys.exit("No TOS keys in credential.json and no local_publish_dir in publish_config.json: nothing to "
                     "publish to.")
        dest = (Path(local) if Path(local).is_absolute() else wl.SKILL_DIR / local) / slug
        if dest.exists():
            if not flag("--overwrite"):
                sys.exit(f"{dest} already exists; pass --overwrite to replace it.")
            shutil.rmtree(dest)
        for f, r in zip(files, rels):
            (dest / r).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest / r)
        url = (dest / "world.html").as_uri()
    else:
        if not (endpoint and region and bucket):
            sys.exit("publish_config.json needs deploy_endpoint, deploy_region and deploy_bucket.")
        from tos_client import delete_object, list_objects, put_object
        existing = list_objects(endpoint, region, bucket, ak, sk, prefix=prefix + "/")
        if existing:
            owner = remote_world_id(f"https://{bucket}.{endpoint}/{quote(prefix)}/world.json")
            if owner and owner != wid:
                sys.exit(f"{prefix}/ belongs to another world (world_id {owner}, this one is {wid}). Refused, even "
                         "with --overwrite: pick another --slug.")
            if not owner and not flag("--overwrite"):
                sys.exit(f"{len(existing)} object(s) under {prefix}/ have no world_id to check. Pass --overwrite to "
                         "replace them, or pick another --slug.")
        for f, r in zip(files, rels):
            ext = f.suffix.lower()
            ctype = TEXT_TYPES.get(ext) or mimetypes.guess_type(f.name)[0] or "application/octet-stream"
            put_object(endpoint, region, bucket, f"{prefix}/{r}", ak, sk, f.read_bytes(), ctype,
                       cache_control=CACHE_HTML if ext in (".html", ".htm") else CACHE_ASSET)
            print(f"  published {r}  ({ctype})", file=sys.stderr)
        pruned = []
        if not flag("--keep-stale"):
            keep = {f"{prefix}/{r}" for r in rels}
            for k in existing:
                if k not in keep:
                    delete_object(endpoint, region, bucket, k, ak, sk)
                    pruned.append(k)
                    print(f"  removed stale {k}", file=sys.stderr)
        url = f"https://{bucket}.{endpoint}/{quote(prefix)}/world.html"
    mf = w.root / "world.json"
    cfg_w = json.loads(mf.read_text(encoding="utf-8"))
    cfg_w["publish"] = {"slug": slug, "url": url, "date": datetime.now().strftime("%Y-%m-%d")}
    mf.write_text(json.dumps(cfg_w, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"time": datetime.now().isoformat(timespec="seconds"), "slug": slug, "files": len(files),
                             "bytes": size, "url": url}) + "\n")
    print(url)


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    main()
