import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from ark_service import (
    ArkVideoService, download_file, extract_token_usage, BASE_DIR, LOG_DIR, configure_console,
    load_config, load_api_key, write_log,
)

configure_console()

OUTPUT_PATH = BASE_DIR / "_world" / "_reference" / "output" / "output_video.mp4"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resume an already-submitted Seedance video task by its id — poll until it "
                    "finishes, then download it. Use when a generate_video_*.py run died after "
                    "submitting (network error, timeout, closed terminal): the task is already "
                    "billed, so this recovers it without generating again. The task id is in the "
                    "original run's .log record (`task_id`) and in its error message."
    )
    parser.add_argument("--task-id", required=True, help="Video task id from the original run's log")
    parser.add_argument("--output",  default=str(OUTPUT_PATH), help="Output video file path (normally the original run's --output)")
    parser.add_argument("--log-dir", default=str(LOG_DIR), help="Directory for the .log JSON record (defaults to _world/_reference/log)")
    args = parser.parse_args()

    output_path = Path(args.output)
    log_path    = Path(args.log_dir) / f"{output_path.name}.log"

    t_start = time.monotonic()
    log: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "resumed":   True,
        "task_id":   args.task_id,
        "output":    str(output_path),
    }

    try:
        config           = load_config()
        duration_seconds = config["video_duration_seconds"]
        base_url         = config["maas_api_endpoint"]
        poll_interval_s  = config.get("poll_interval_seconds", 15)
        max_polls        = config.get("max_polls", 120)

        print(f"Resuming task: {args.task_id}", file=sys.stderr)
        print(f"Output: {output_path}\n", file=sys.stderr)

        api_key = load_api_key()
        service = ArkVideoService(base_url=base_url, api_key=api_key)

        video_url, metrics = service.wait_for_video(args.task_id, duration_seconds, poll_interval_s, max_polls)

        dl_s    = download_file(video_url, output_path)
        total_s = round(time.monotonic() - t_start, 2)

        print(f"Saved: {output_path}  ({total_s}s, download {dl_s:.1f}s)", file=sys.stderr)

        usage = metrics.get("usage") or {}
        log.update({
            # ttft_s/generation_s are measured from when this resume started polling, not from
            # the original submission, so they're omitted here.
            **extract_token_usage(usage),
            "usage":      usage,
            "download_s": round(dl_s, 2),
            "total_s":    total_s,
            "video_url":  video_url,
            "status":     "succeeded",
        })
        write_log(log_path, log)

        print(str(output_path))
        return 0

    except Exception as exc:
        log.update({"status": "failed", "error": str(exc), "total_s": round(time.monotonic() - t_start, 2)})
        write_log(log_path, log)
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
