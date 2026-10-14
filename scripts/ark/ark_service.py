"""Ark REST API clients for my-world: Seedream image generation and Seedance video generation.

Copied from the video-workflow skill (scripts/ark_service.py) so my-world runs on its own: plain HTTP calls via
`requests`. Settings come from the skill's aigc_config.json plus the per-call MY_WORLD_ARK_OVERRIDES env var (set by
worldlib); the API key from env `model_ark_key`, else the skill's credential.json.
"""
import base64
import json
import os
import shutil
import sys
import time
import urllib.request
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import llm_usage  # noqa: E402  the token ledger

BASE_DIR           = Path(__file__).resolve().parents[2]  # my-world skill root — credential.json/aigc_config.json live here
CREDENTIAL_PATH    = BASE_DIR / "credential.json"
CONFIG_PATH        = BASE_DIR / "aigc_config.json"
LOG_DIR            = BASE_DIR / "_world" / "_reference" / "log"  # default only; worldlib always passes --log-dir
PROMPT_LIBRARY_DIR = Path(__file__).resolve().parent
OVERRIDES_ENV      = "MY_WORLD_ARK_OVERRIDES"  # JSON settings for one call (model, size, ratio…), set by worldlib
CHARACTER_SHEET_TEMPLATE = PROMPT_LIBRARY_DIR / "three_angle_character_sheet.txt"

DOWNLOAD_TIMEOUT_S        = 120
MAX_POLL_TRANSIENT_ERRORS = 5  # consecutive poll failures tolerated before giving up on a (paid) task


def configure_console() -> None:
    """Allow Unicode output on Windows consoles."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def read_json(path: Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def load_config() -> dict:
    """aigc_config.json, with the per-call settings from the MY_WORLD_ARK_OVERRIDES env var on top."""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")
    cfg = read_json(CONFIG_PATH)
    if os.environ.get(OVERRIDES_ENV):
        cfg.update(json.loads(os.environ[OVERRIDES_ENV]))
    return cfg


def load_api_key() -> str:
    env_key = os.environ.get("model_ark_key")
    if env_key:
        return env_key
    if not CREDENTIAL_PATH.exists():
        raise FileNotFoundError(
            f"model_ark_key env var not set, and credential file not found: {CREDENTIAL_PATH}"
        )
    cred = read_json(CREDENTIAL_PATH)
    api_key = cred.get("model_ark_key")
    if not api_key:
        raise KeyError("model_ark_key env var not set and `model_ark_key` missing in credential.json")
    return api_key


def write_log(log_path: Path, data: dict) -> None:
    """The per-call .log record, and one row in the world's token ledger (scripts/llm_usage.py)."""
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")
    script = Path(sys.argv[0]).stem
    kind = "video" if "video" in script else "sheet" if "sheet" in script else "image"
    llm_usage.record(kind, data.get("model"), data.get("status", "unknown"), output=data.get("output"),
                     tokens_in=data.get("tokens_in"), tokens_out=data.get("tokens_out"),
                     tokens_total=data.get("tokens_total"), duration_s=data.get("total_s"), error=data.get("error"),
                     log_timestamp=data.get("timestamp"), task_id=data.get("task_id"))


def read_text_file(path: Path, label: str) -> str:
    """Reads a user-supplied text file (idea/prompt/script), raising if it's empty."""
    text = Path(path).read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"{label} file is empty: {path}")
    return text


def character_sheet_prompt(subject: str) -> str:
    """The fixed three-angle character-sheet prompt (three_angle_character_sheet.txt next to this file)
    with `<subject description>` filled in — the single source of truth for that template."""
    template = CHARACTER_SHEET_TEMPLATE.read_text(encoding="utf-8").strip()
    return template.replace("<subject description>", subject.strip().rstrip("."))


def extract_token_usage(usage: dict | None) -> dict:
    """Normalizes an Ark API `usage` dict into {tokens_in, tokens_out, tokens_total} for
    logging. Different endpoints use different key names — chat completions use
    prompt_tokens/completion_tokens, image generation uses input_images/output_tokens (verified
    live: {"input_images": 0, "generated_images": 1, "output_tokens": 16384, "total_tokens":
    16384} — no prompt_tokens/completion_tokens at all). Missing values are None, not 0, so a
    genuine zero-token value is never confused with "not reported"."""
    usage = usage or {}
    tokens_in = usage.get("prompt_tokens")
    if tokens_in is None:
        tokens_in = usage.get("input_tokens")
    tokens_out = usage.get("completion_tokens")
    if tokens_out is None:
        tokens_out = usage.get("output_tokens")
    return {
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "tokens_total": usage.get("total_tokens"),
    }


def guess_mime_from_path(path) -> str:
    ext = str(path).rsplit(".", 1)[-1].lower() if "." in str(path) else ""
    if ext in ("jpg", "jpeg"):
        return "image/jpeg"
    if ext == "png":
        return "image/png"
    if ext == "gif":
        return "image/gif"
    if ext == "webp":
        return "image/webp"
    return "application/octet-stream"


def file_to_data_url(path) -> str:
    path = Path(path)
    data = path.read_bytes()
    mime = guess_mime_from_path(path)
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def download_file(url: str, output_path) -> float:
    """Downloads file and returns elapsed seconds."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT_S) as resp, output_path.open("wb") as f:
        shutil.copyfileobj(resp, f)
    return time.monotonic() - t0


class TransientApiError(RuntimeError):
    """A retryable API failure (HTTP 429 / 5xx)."""


class ArkImageService:
    """Seedream image generation/edit client."""

    def __init__(self, base_url: str, api_key: str):
        self._url = base_url.rstrip('/') + '/images/generations'
        self._headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }

    def generate_image(self, model_id: str, prompt: str, image: list[str] | str | None = None,
                        size: str | None = None, watermark: bool | None = None) -> tuple[list[dict], dict]:
        """Returns (images, usage) — usage is the Ark API's token-usage dict, if the response
        included one (image models are not always token-billed), or {} otherwise."""
        img_count = len(image) if isinstance(image, list) else (1 if image else 0)
        print(f"Image generation: model={model_id} prompt_len={len(prompt)} images={img_count} "
              f"size={size} watermark={watermark}", file=sys.stderr)

        payload = {
            'model': model_id,
            'prompt': prompt,
            'response_format': 'url',
        }
        if image:
            payload['image'] = image
        if size is not None:
            payload['size'] = size
        if watermark is not None:
            payload['watermark'] = watermark

        resp = requests.post(self._url, headers=self._headers, json=payload, timeout=300)
        if resp.status_code != 200:
            raise RuntimeError(f"Ark API error {resp.status_code}: {resp.text}")
        data = resp.json()

        images = [
            {'url': img.get('url'), 'b64_json': img.get('b64_json')}
            for img in (data.get('data') or [])
        ]
        usage = data.get('usage') or {}
        print(f"Image generation done: count={len(images)} usage={usage}", file=sys.stderr)
        return images, usage


class ArkVideoService:
    """Seedance video generation client — create a task, then poll until it succeeds."""

    def __init__(self, base_url: str, api_key: str):
        self._url = base_url.rstrip('/') + '/contents/generations/tasks'
        self._headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }

    def create_task(self, model_id: str, content: list, duration_seconds: int, ratio: str | None,
                     resolution: str, generate_audio: bool, watermark: bool) -> tuple[str, str | None]:
        # For first-frame/first-last-frame generation (an image_url in content), the API derives
        # the output ratio from the input image and rejects an explicit `ratio` — pass ratio=None
        # in that case. Text-only generation requires it.
        print(f"Video task create: model={model_id} duration={duration_seconds} ratio={ratio or '(follows input image)'} "
              f"resolution={resolution} generate_audio={generate_audio} watermark={watermark}", file=sys.stderr)
        payload = {
            'model': model_id,
            'content': content,
            'duration': duration_seconds,
            'resolution': resolution,
            'generate_audio': generate_audio,
            'watermark': watermark,
        }
        if ratio is not None:
            payload['ratio'] = ratio
        resp = requests.post(self._url, headers=self._headers, json=payload, timeout=60)
        if resp.status_code != 200:
            raise RuntimeError(f"Ark API error {resp.status_code}: {resp.text}")
        result = resp.json()
        task_id = result.get('id')
        request_id = result.get('request_id')
        if not task_id:
            raise RuntimeError(f"Task created but no id returned: {result}")
        print(f"Video task created: {task_id}", file=sys.stderr)
        return task_id, request_id

    def _get_task(self, task_id: str) -> dict:
        resp = requests.get(f"{self._url}/{task_id}", headers=self._headers, timeout=30)
        if resp.status_code == 429 or resp.status_code >= 500:
            raise TransientApiError(f"Ark API error {resp.status_code}: {resp.text}")
        if resp.status_code != 200:
            raise RuntimeError(f"Ark API error {resp.status_code}: {resp.text}")
        return resp.json()

    def wait_for_video(self, task_id: str, duration_seconds: int,
                        poll_interval_seconds: int = 15, max_polls: int = 120) -> tuple[str, dict]:
        """Returns (video_url, timing_and_usage_dict)."""
        t_submit = time.monotonic()
        t_running = None  # TTFT: time until task enters "running"
        transient_errors = 0

        for attempt in range(1, max_polls + 1):
            # The task is already submitted (and billed) — a network blip or 5xx while polling
            # must not abandon it. Retry transient failures; anything persistent still raises,
            # and the task can be picked up later with resume_video_task.py --task-id.
            try:
                result = self._get_task(task_id)
            except (requests.RequestException, TransientApiError) as exc:
                transient_errors += 1
                if transient_errors > MAX_POLL_TRANSIENT_ERRORS:
                    raise RuntimeError(
                        f"Polling task {task_id} failed {transient_errors} times in a row: {exc}"
                    ) from exc
                print(f"[{attempt}/{max_polls}] poll error ({transient_errors}/{MAX_POLL_TRANSIENT_ERRORS}), "
                      f"retrying: {exc}", file=sys.stderr)
                time.sleep(poll_interval_seconds)
                continue
            transient_errors = 0
            status = result.get('status')
            now = time.monotonic()
            print(f"[{attempt}/{max_polls}] status: {status}  elapsed: {now - t_submit:.1f}s", file=sys.stderr)

            if t_running is None and status == 'running':
                t_running = now

            if status == 'succeeded':
                t_succeeded = now
                content = result.get('content') or {}
                video_url = content.get('video_url')
                if not video_url:
                    raise RuntimeError(f"Task succeeded but no video_url: {result}")

                usage = result.get('usage') or {}
                ttft = (t_running - t_submit) if t_running else None
                gen_time = t_succeeded - (t_running or t_submit)
                metrics = {
                    "ttft_s": round(ttft, 2) if ttft is not None else None,
                    "generation_s": round(gen_time, 2),
                    "tpot_s": round(gen_time / duration_seconds, 2) if duration_seconds else None,
                    "usage": usage,
                    "request_id": result.get('request_id'),
                }
                return video_url, metrics

            if status in ('failed', 'expired'):
                error = result.get('error')
                raise RuntimeError(f"Video generation {status}: {error or result}")

            time.sleep(poll_interval_seconds)

        raise TimeoutError(
            f"Task did not finish after {max_polls * poll_interval_seconds}s. id: {task_id}"
        )
