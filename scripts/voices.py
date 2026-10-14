"""Character voices with BytePlus Seed Audio 1.0 (tts/create; model id from config.json audio_model_id).

Each voice comes from the character's canon block `<!-- prompt:voice:<char> -->` in Identities.md. Once approved, the
solo clips in _asset/voices/<char>.wav are the characters' voice references for the world.

Steps (one JSON script drives them, default _reference/voices/samples.json):
  design    one clip per character -> _asset/voices/<char>.wav, designed from the text description, or cloned from
            a recording the user chose (`references`, <=30s) and steered by the description
  dialogue  the conversation in `turns`, with the solo clips as @Audio1.. references -> <work_dir>/<name>_dialogue.wav
            plus <name>_dialogue_tight.wav with every pause over 0.7s cut to 0.5s (needs ffmpeg)
  page      <work_dir>/voices.html with players, the line texts and what the model actually spoke
  all       design + dialogue + page

Usage:  python voices.py [<script.json>] design|dialogue|page|all [chars...] [--world DIR]

Script: {"name": "sample", "title": "Character voices", "out_dir": "_asset/voices", "work_dir": "_reference/voices",
         "references": {"<char>": "_reference/voices/refs/<file>"}, "samples": {"<char>": "text"},
         "turns": [{"speaker": "<char>", "text": "..."}]}
Existing clips are kept; delete one to regenerate it.
"""
import base64
import html
import json
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import worldlib as wl  # noqa: E402

MAX_PROMPT_CHARS = 3000


def tighten(src, dst, min_gap=0.7, keep=0.5, noise="-40dB"):
    """Shorten every pause longer than min_gap seconds to keep seconds (the model leaves long gaps between turns)."""
    log = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(src), "-af", f"silencedetect=n={noise}:d={min_gap}",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    gaps = [(float(a), float(b)) for a, b in re.findall(r"silence_start: ([\d.]+).*?silence_end: ([\d.]+)", log, re.S)]
    cuts, t0 = [], 0.0
    for a, b in gaps:
        cuts.append((t0, a + keep / 2))
        t0 = b - keep / 2
    cuts.append((t0, None))
    parts = "".join(f"[0:a]atrim={a:.3f}" + (f":{b:.3f}" if b else "") + f",asetpts=PTS-STARTPTS[a{i}];"
                    for i, (a, b) in enumerate(cuts))
    graph = parts + "".join(f"[a{i}]" for i in range(len(cuts))) + f"concat=n={len(cuts)}:v=0:a=1[out]"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-filter_complex", graph,
                    "-map", "[out]", str(dst)], check=True)
    print(f"{dst.name}: {len(gaps)} long pauses shortened to {keep}s")


class Voices:
    def __init__(self, world, script_path):
        self.w = world
        self.spec = json.loads(Path(script_path).read_text(encoding="utf-8"))
        self.out = world.p(self.spec.get("out_dir", "_asset/voices"))
        self.work = world.p(self.spec.get("work_dir", "_reference/voices"))
        for d in (self.out, self.work):
            d.mkdir(parents=True, exist_ok=True)
        self.meta_path = self.work / "voices_meta.json"
        self.meta = json.loads(self.meta_path.read_text(encoding="utf-8")) if self.meta_path.exists() else {}

    def log(self, msg):
        (self.work / "log").mkdir(exist_ok=True)
        with open(self.work / "log" / "voices.log", "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")

    def tts(self, prompt, references, out):
        import requests
        if len(prompt) > MAX_PROMPT_CHARS:
            raise SystemExit(f"text_prompt is {len(prompt)} chars, over the {MAX_PROMPT_CHARS} limit")
        payload = {"model": self.w.models["speech"], "text_prompt": prompt, "references": references,
                   "audio_config": {"format": "wav", "sample_rate": 24000, "enable_subtitle": True},
                   "watermark": {"aigc_watermark": False}}
        self.log(f"request {out.name}: {len(references)} reference(s)\n{prompt}")
        for attempt in (1, 2, 3):  # connection errors (e.g. TLS resets) happen before any result exists
            try:
                r = requests.post(self.w.models["speech_endpoint"], json=payload, timeout=180,
                                  headers={"X-Api-Key": wl.speech_api_key(self.w), "Content-Type": "application/json",
                                           "X-Api-Request-Id": str(uuid.uuid4())})
                break
            except requests.exceptions.ConnectionError as ex:
                self.log(f"attempt {attempt} connection error: {ex}")
                if attempt == 3:
                    raise SystemExit(f"tts/create unreachable after 3 attempts: {ex}")
                time.sleep(5 * attempt)
        if not r.ok:
            self.log(f"HTTP {r.status_code}: {r.text[:500]}")
            raise SystemExit(f"tts/create HTTP {r.status_code} for {out.name}: {r.text[:300]}")
        d = r.json()
        if d.get("code") not in (0, None):
            raise SystemExit(f"tts/create failed: code={d.get('code')} message={d.get('message')}")
        out.write_bytes(base64.b64decode(d["audio"]) if d.get("audio") else requests.get(d["url"], timeout=180).content)
        spoken = (d.get("subtitle") or {}).get("text", "")
        self.meta[out.name] = {"duration": d.get("duration"), "spoken": spoken}
        self.meta_path.write_text(json.dumps(self.meta, indent=2, ensure_ascii=False), encoding="utf-8")
        self.log(f"saved {out.name} duration={d.get('duration')} spoken={spoken!r}")
        print(f"{out.name}: {d.get('duration')}s  spoken: {spoken}", flush=True)

    def clip(self, char):
        return self.out / f"{char}.wav"

    def design(self, chars):
        for char in chars or list(self.spec["samples"]):
            out = self.clip(char)
            if out.exists():
                print(f"{out.name}: exists")
                continue
            c = self.w.chars[char]
            ref = self.spec.get("references", {}).get(char)
            if ref:
                refs = [{"audio_data": base64.b64encode(self.w.p(ref).read_bytes()).decode("ascii")}]
                prompt = f"@Audio1 ({c['name']}) is {self.w.get('voice:' + char)}\n\n@Audio1: {self.spec['samples'][char]}"
            else:
                refs = []
                prompt = (f"Voice: {self.w.get('voice:' + char)}\n{c.get('pronoun', 'They')} says: "
                          f"{self.spec['samples'][char]}")
            self.tts(prompt, refs, out)

    def dialogue(self):
        out = self.work / f"{self.spec['name']}_dialogue.wav"
        if out.exists():
            print(f"{out.name}: exists")
            return
        order = [c for c in self.w.chars if any(t["speaker"] == c for t in self.spec["turns"])]
        missing = [c for c in order if not self.clip(c).exists()]
        if missing:
            raise SystemExit(f"run 'design' first, missing voice clips: {', '.join(missing)}")
        idx = {c: i + 1 for i, c in enumerate(order)}
        refs = [{"audio_data": base64.b64encode(self.clip(c).read_bytes()).decode("ascii")} for c in order]
        pre = "\n".join(f"@Audio{idx[c]} ({self.w.char_name(c)}) is {self.w.get('voice:' + c)}" for c in order)
        lines = "\n".join(f"@Audio{idx[t['speaker']]}: {t['text']}" for t in self.spec["turns"])
        self.tts(f"{pre}\n\n{lines}", refs, out)
        tighten(out, out.with_name(out.stem + "_tight.wav"))

    def page(self):
        e = html.escape
        rows = ""
        for char, text in self.spec["samples"].items():
            m = self.meta.get(f"{char}.wav", {})
            rows += (f"<section><h2>{e(self.w.char_name(char))}</h2><p class=d>{e(self.w.get('voice:' + char))}</p>"
                     f"<audio controls src='{wl.rel(self.clip(char), self.work)}'></audio><p><b>Script:</b> {e(text)}</p>"
                     f"<p class=s><b>Spoken ({m.get('duration', '?')}s):</b> {e(m.get('spoken', ''))}</p></section>")
        dn = f"{self.spec['name']}_dialogue.wav"
        m = self.meta.get(dn, {})
        turns = "".join(f"<li><b>{e(self.w.char_name(t['speaker']))}:</b> {e(t['text'])}</li>" for t in self.spec.get("turns", []))
        dlg = (f"<section><h2>Dialogue</h2><p class=d>Tightened (long pauses shortened to 0.5s):</p>"
               f"<audio controls src='{dn[:-4]}_tight.wav'></audio><p class=d>Original from the model:</p>"
               f"<audio controls src='{dn}'></audio><ol>{turns}</ol>"
               f"<p class=s><b>Spoken ({m.get('duration', '?')}s):</b> {e(m.get('spoken', ''))}</p></section>") if turns else ""
        page = f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>Character Voices</title><style>
:root{{--bg:#f7faf9;--fg:#1d2b2a;--mut:#5d6f6d;--card:#fff;--line:#d9e4e2}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#141a1a;--fg:#e6efed;--mut:#9fb2af;--card:#1d2626;--line:#2e3b3a}}}}
body{{background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif;margin:0}}
main{{max-width:860px;margin:auto;padding:24px 16px}} section{{background:var(--card);border:1px solid var(--line);
border-radius:12px;padding:16px;margin:16px 0}} h2{{margin:0 0 4px}} .d,.s{{color:var(--mut);font-size:14px}}
audio{{width:100%;margin:8px 0}} li{{margin:4px 0}}</style></head><body><main>
<h1>{e(self.spec.get('title', 'Character voices'))}</h1><p class=d>Voices from Identities.md with Seed Audio.
"Spoken" is the model's own transcript of each clip.</p>{rows}{dlg}</main></body></html>"""
        p = self.work / "voices.html"
        p.write_text(page, encoding="utf-8")
        print(p)


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):  # Chinese line texts on a Windows console
        stream.reconfigure(encoding="utf-8", errors="replace")
    wdir, args = wl.pop_world_arg(sys.argv[1:])
    world = wl.World(wdir)
    if args and args[0].endswith(".json"):
        script, args = Path(args[0]), args[1:]
    else:
        script = world.p("_reference/voices/samples.json")
    if not args:
        sys.exit(__doc__)
    step, chars = args[0], args[1:]
    if step != "page":
        wl.require(("python", "voice") + (("ffmpeg",) if step in ("dialogue", "all") else ()), world)
    v = Voices(world, script)
    if step in ("design", "all"):
        v.design(chars)
    if step in ("dialogue", "all") and v.spec.get("turns"):
        v.dialogue()
    if step in ("page", "all"):
        v.page()
