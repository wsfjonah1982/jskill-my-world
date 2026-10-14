"""Token and call ledger for every model the skill uses, so token consumption can be tracked.

Two sources:
  generation  every image, sheet, video and voice call the scripts make (Seedream, Seedance, Seed Audio) is appended
              to <world>/_reference/log/llm_usage.jsonl: time, activity (the command that ran), kind, provider,
              model, output, status, tokens (in / out / total, from the API's `usage`), duration, error.
              Written by scripts/ark/ark_service.write_log and voices.py through record(); the path comes from env
              MY_WORLD_USAGE_LOG, which worldlib.World sets.
  agent       the agent's own LLM use (Claude Code): read from the Claude Code session transcripts of the skill's
              folder (~/.claude/projects/<folder slug>*/**/*.jsonl, or $CLAUDE_CONFIG_DIR/projects), one row per
              session in <world>/_reference/log/agent_usage.json (input, cache write, cache read, output tokens).
              Rewritten on every sync, so it never double-counts.

Usage:  python llm_usage.py [report] [--world DIR]   sync the agent usage, write usage.json, print the totals
        python llm_usage.py sync [--world DIR]       only sync the agent usage
        python llm_usage.py backfill [--world DIR]   import older per-call .log records into the ledger (once)
evaluate_world.py runs `report` too, and world.html shows the totals.
"""
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

LEDGER_ENV, ACTIVITY_ENV = "MY_WORLD_USAGE_LOG", "MY_WORLD_ACTIVITY"
SKILL_DIR = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record(kind, model, status, provider="byteplus", output=None, tokens_in=None, tokens_out=None, tokens_total=None,
           duration_s=None, error=None, path=None, **extra):
    """Append one call to the ledger (env MY_WORLD_USAGE_LOG, or `path`). Never raises: logging must not break work."""
    path = path or os.environ.get(LEDGER_ENV)
    if not path:
        return
    row = {"time": extra.pop("call_time", None) or now(), "activity": os.environ.get(ACTIVITY_ENV, Path(sys.argv[0]).name), "kind": kind,
           "provider": provider, "model": model, "status": status, "output": str(output) if output else None,
           "tokens_in": tokens_in, "tokens_out": tokens_out,
           "tokens_total": tokens_total if tokens_total is not None else
           (tokens_in or 0) + (tokens_out or 0) if (tokens_in or tokens_out) else None,
           "duration_s": duration_s, "error": (str(error)[:300] if error else None), **extra}
    try:  # output relative to the world folder (<world>/_reference/log/llm_usage.jsonl -> <world>)
        row["output"] = os.path.relpath(row["output"], Path(path).resolve().parents[2]).replace(os.sep, "/")
    except (TypeError, ValueError):
        pass
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as ex:
        print(f"warning: usage ledger not written: {ex}", file=sys.stderr)


def read_ledger(root):
    p = Path(root) / "_reference" / "log" / "llm_usage.jsonl"
    rows = []
    if p.is_file():
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    return rows


# ---------------------------------------------------------------- agent (Claude Code transcripts)
def _projects_dir():
    base = os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
    return Path(base) / "projects"


def sync_agent(root):
    """Sum the agent's token use per session from the Claude Code transcripts of the skill folder."""
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(SKILL_DIR))
    sessions = {}
    seen = set()
    pdir = _projects_dir()
    dirs = [d for d in pdir.iterdir() if d.is_dir() and d.name.lower().startswith(slug.lower())] if pdir.is_dir() else []
    for d in dirs:
        for f in d.rglob("*.jsonl"):
            try:
                lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for line in lines:
                if '"usage"' not in line:
                    continue
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                m = e.get("message")
                if not isinstance(m, dict) or not isinstance(m.get("usage"), dict):
                    continue
                key = (m.get("id"), e.get("requestId"))
                if key in seen:  # one API response is written as several transcript lines
                    continue
                seen.add(key)
                u = m["usage"]
                sid = e.get("sessionId") or f.stem
                s = sessions.setdefault(sid, {"session": sid, "model": m.get("model"), "first": e.get("timestamp"),
                                              "last": e.get("timestamp"), "requests": 0, "input": 0, "cache_write": 0,
                                              "cache_read": 0, "output": 0, "subagent": "subagents" in f.parts})
                s["requests"] += 1
                s["input"] += u.get("input_tokens") or 0
                s["cache_write"] += u.get("cache_creation_input_tokens") or 0
                s["cache_read"] += u.get("cache_read_input_tokens") or 0
                s["output"] += u.get("output_tokens") or 0
                ts = e.get("timestamp")
                if ts:
                    s["first"] = min(s["first"] or ts, ts)
                    s["last"] = max(s["last"] or ts, ts)
    rows = sorted(sessions.values(), key=lambda s: s["first"] or "")
    for s in rows:
        s["total"] = s["input"] + s["cache_write"] + s["cache_read"] + s["output"]
    out = Path(root) / "_reference" / "log" / "agent_usage.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"synced": now(), "source": str(pdir), "sessions": rows}, indent=2), encoding="utf-8")
    return rows


# ---------------------------------------------------------------- backfill older per-call logs
def backfill(root, speech_model=None):
    """Import the per-call JSON .log records written before the ledger existed (images, sheets, videos)."""
    root = Path(root)
    led = root / "_reference" / "log" / "llm_usage.jsonl"
    have = {r.get("log_timestamp") for r in read_ledger(root) if r.get("log_timestamp")}
    n = 0
    for f in sorted(root.glob("_reference/**/log/*.log")):
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if not isinstance(d, dict) or "model" not in d:
                continue
            t = (d.get("timestamp") or "")[:19] + "+00:00" if d.get("timestamp") else None
            if not d.get("timestamp") or d["timestamp"] in have:
                continue
            kind = "video" if "task_id" in d or "video" in str(d.get("model", "")).lower() else (
                "sheet" if "style" in d else "image")
            os.environ[ACTIVITY_ENV] = "backfill " + f.parent.parent.name
            record(kind, d.get("model"), d.get("status", "unknown"), output=d.get("output"),
                   tokens_in=d.get("tokens_in"), tokens_out=d.get("tokens_out"), tokens_total=d.get("tokens_total"),
                   duration_s=d.get("total_s"), error=d.get("error"), path=led, backfilled=True, call_time=t, log_timestamp=d["timestamp"])
            have.add(d["timestamp"])
            n += 1
    # voices: voices.py wrote a text log ("<local time> saved <clip> duration=<s>" / "<local time> HTTP <code>: …")
    model = speech_model
    for f in sorted(root.glob("_reference/**/voices.log")):
        clip = None
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) (request (\S+):|saved (\S+) duration=([\d.]+)|HTTP (\d+))", line)
            if not m:
                continue
            ts, key = m.group(1), f"voices.log {m.group(1)} {m.group(0)[20:60]}"
            if m.group(3):
                clip = m.group(3)
                continue
            if key in have:
                continue
            t = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").astimezone().isoformat(timespec="seconds")
            os.environ[ACTIVITY_ENV] = "backfill voices"
            out = str(f.parent.parent / (m.group(4) or clip or "?"))
            if m.group(4):
                record("voice", model, "succeeded", output=out, audio_s=float(m.group(5)), path=led, backfilled=True,
                       call_time=t, log_timestamp=key)
            else:
                record("voice", model, "failed", output=out, error=f"HTTP {m.group(6)}", path=led, backfilled=True,
                       call_time=t, log_timestamp=key)
            have.add(key)
            n += 1
    return n


# ---------------------------------------------------------------- report
def summarize(root, sync=True):
    root = Path(root)
    gen = read_ledger(root)
    agent = sync_agent(root) if sync else (json.loads((root / "_reference/log/agent_usage.json").read_text(
        encoding="utf-8")).get("sessions", []) if (root / "_reference/log/agent_usage.json").is_file() else [])
    by_model = defaultdict(lambda: {"calls": 0, "failed": 0, "tokens": 0, "audio_s": 0, "kinds": defaultdict(int)})
    for r in gen:
        m = by_model[(r.get("provider") or "byteplus", r.get("model") or "?")]
        m["calls"] += 1
        m["failed"] += r.get("status") not in ("succeeded", "done", "ok")
        m["tokens"] += r.get("tokens_total") or 0
        m["audio_s"] += r.get("audio_s") or 0
        m["kinds"][r.get("kind") or "?"] += 1
    gen_rows = [{"provider": p, "model": mo, "calls": v["calls"], "failed": v["failed"], "tokens": v["tokens"],
                 "audio_s": round(v["audio_s"], 1), "kinds": dict(v["kinds"])} for (p, mo), v in sorted(by_model.items())]
    ag = defaultdict(lambda: {"sessions": 0, "requests": 0, "input": 0, "cache_write": 0, "cache_read": 0, "output": 0,
                              "total": 0})
    for s in agent:
        a = ag[s.get("model") or "?"]
        a["sessions"] += 1
        for k in ("requests", "input", "cache_write", "cache_read", "output", "total"):
            a[k] += s[k]
    agent_rows = [{"model": k, **v} for k, v in sorted(ag.items())]
    res = {"date": now(), "generation": gen_rows, "agent": agent_rows,
           "generation_calls": sum(r["calls"] for r in gen_rows),
           "generation_tokens": sum(r["tokens"] for r in gen_rows),
           "agent_tokens": sum(r["total"] for r in agent_rows),
           "agent_output_tokens": sum(r["output"] for r in agent_rows),
           "agent_sessions": sum(r["sessions"] for r in agent_rows),
           "first_call": min((r.get("time") for r in gen if r.get("time")), default=None)}
    (root / "_reference" / "log" / "usage.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    return res


def fmt(n):
    return f"{n / 1e6:.2f}M" if n >= 1e6 else f"{n / 1e3:.1f}k" if n >= 1e3 else str(n)


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import worldlib as wl
    wdir, args = wl.pop_world_arg(sys.argv[1:])
    w = wl.World(wdir)
    cmd = args[0] if args else "report"
    if cmd == "sync":
        rows = sync_agent(w.root)
        print(f"{len(rows)} agent sessions synced")
        return
    if cmd == "backfill":
        print(f"{backfill(w.root, w.models.get('speech'))} older calls imported into _reference/log/llm_usage.jsonl")
        return
    r = summarize(w.root)
    print(f"Generation: {r['generation_calls']} calls, {fmt(r['generation_tokens'])} tokens")
    for x in r["generation"]:
        print(f"  {x['model']}: {x['calls']} calls ({', '.join(f'{n} {k}' for k, n in x['kinds'].items())}), "
              f"{x['failed']} failed, {fmt(x['tokens'])} tokens" + (f", {x['audio_s']}s audio" if x["audio_s"] else ""))
    print(f"Agent: {r['agent_sessions']} sessions, {fmt(r['agent_tokens'])} tokens "
          f"({fmt(r['agent_output_tokens'])} output)")
    for x in r["agent"]:
        print(f"  {x['model']}: {x['requests']} requests, input {fmt(x['input'])}, cache write {fmt(x['cache_write'])}, "
              f"cache read {fmt(x['cache_read'])}, output {fmt(x['output'])}")


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    main()
