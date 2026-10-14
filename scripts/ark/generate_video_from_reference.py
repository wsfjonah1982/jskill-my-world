import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from ark_service import (
    ArkVideoService, download_file, file_to_data_url, extract_token_usage, BASE_DIR, LOG_DIR,
    configure_console, load_config, load_api_key, write_log,
)

configure_console()

OUTPUT_PATH     = BASE_DIR / "_world" / "_reference" / "output" / "output_video.mp4"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--img",    required=True, help="Input image file path")
    parser.add_argument("--prompt", required=True, help="Path to prompt text file")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Output video file path (e.g. out.mp4)")
    parser.add_argument("--log-dir", default=str(LOG_DIR), help="Directory for the .log JSON record (defaults to _world/_reference/log)")
    args = parser.parse_args()

    image_path  = Path(args.img)
    prompt_path = Path(args.prompt)
    output_path = Path(args.output)
    log_path    = Path(args.log_dir) / f"{output_path.name}.log"

    if not image_path.exists():
        print(f"Error: input image not found: {image_path}", file=sys.stderr)
        return 1
    if not prompt_path.exists():
        print(f"Error: prompt file not found: {prompt_path}", file=sys.stderr)
        return 1

    prompt = prompt_path.read_text(encoding="utf-8").strip()
    if not prompt:
        print(f"Error: prompt file is empty: {prompt_path}", file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)

    t_start = time.monotonic()
    log: dict = {
        "timestamp":  datetime.now(timezone.utc).isoformat(),
        "image":      str(image_path),
        "prompt":     prompt,
        "output":     str(output_path),
    }

    try:
        config           = load_config()
        model_id         = config["video_model_id"]
        duration_seconds = config["video_duration_seconds"]
        resolution       = config["video_resolution"]
        generate_audio   = config.get("generate_audio", False)
        watermark        = config.get("watermark", False)
        base_url         = config["maas_api_endpoint"]
        poll_interval_s  = config.get("poll_interval_seconds", 15)
        max_polls        = config.get("max_polls", 120)
        # Output ratio follows the first-frame image for image-to-video — aigc_config.json's
        # video_ratio does not apply here (it does for generate_video_from_text.py).

        log.update({
            "model":          model_id,
            "duration_s":     duration_seconds,
            "resolution":     resolution,
            "generate_audio": generate_audio,
        })

        print(f"Input image: {image_path}", file=sys.stderr)
        print(f"Prompt file: {prompt_path}", file=sys.stderr)
        print(f"Prompt: {prompt}", file=sys.stderr)
        print(f"Model: {model_id}  Duration: {duration_seconds}s  Ratio: (follows input image)  "
              f"Resolution: {resolution}  Audio: {generate_audio}", file=sys.stderr)
        print(f"Output: {output_path}\n", file=sys.stderr)

        api_key        = load_api_key()
        service        = ArkVideoService(base_url=base_url, api_key=api_key)
        image_data_url = file_to_data_url(image_path)

        task_id, submit_request_id = service.create_task(
            model_id=model_id,
            content=[
                {"type": "image_url", "image_url": {"url": image_data_url}},
                {"type": "text", "text": prompt},
            ],
            # Output ratio follows the first-frame image for image-to-video — the API rejects
            # an explicit ratio here, so aigc_config.json's video_ratio does not apply to this script.
            duration_seconds=duration_seconds, ratio=None, resolution=resolution,
            generate_audio=generate_audio, watermark=watermark,
        )
        log["task_id"] = task_id

        video_url, metrics = service.wait_for_video(task_id, duration_seconds, poll_interval_s, max_polls)

        dl_s    = download_file(video_url, output_path)
        total_s = round(time.monotonic() - t_start, 2)

        print(f"Saved: {output_path}  ({total_s}s, download {dl_s:.1f}s)", file=sys.stderr)

        usage = metrics.get("usage") or {}
        log.update({
            "ttft_s":       metrics["ttft_s"],
            "generation_s": metrics["generation_s"],
            "tpot_s":       metrics["tpot_s"],
            **extract_token_usage(usage),
            "usage":        usage,
            "download_s":   round(dl_s, 2),
            "total_s":      total_s,
            "video_url":    video_url,
            "status":       "succeeded",
        })
        write_log(log_path, log)

        print(str(output_path))
        return 0

    except Exception as exc:
        log.update({"status": "failed", "error": str(exc), "total_s": round(time.monotonic() - t_start, 2)})
        write_log(log_path, log)
        print(f"Error: {exc}", file=sys.stderr)
        if log.get("task_id"):
            print(f"The task was already submitted — resume it without paying again: python scripts/resume_video_task.py "
                  f"--task-id {log['task_id']} --output {output_path}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
