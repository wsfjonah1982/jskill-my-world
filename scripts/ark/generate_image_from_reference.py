import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from ark_service import (
    ArkImageService, download_file, file_to_data_url, extract_token_usage, BASE_DIR, LOG_DIR,
    configure_console, load_config, load_api_key, write_log,
)

configure_console()

OUTPUT_PATH     = BASE_DIR / "_world" / "_reference" / "output" / "output_edit.png"


def generate_image(service: ArkImageService, prompt: str, image: str | list[str], model_id: str, size: str, watermark: bool) -> tuple[str, dict]:
    images, usage = service.generate_image(model_id=model_id, prompt=prompt, image=image, size=size, watermark=watermark)
    url = images[0]["url"] if images else None
    if not url:
        raise RuntimeError("No image URL returned")
    return url, usage


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--img",    required=True, nargs="+", help="Input image file path(s) — pass multiple to use several reference images in one edit")
    parser.add_argument("--prompt", required=True, help="Path to prompt text file (e.g. image.txt)")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Output image file path")
    parser.add_argument("--log-dir", default=str(LOG_DIR), help="Directory for the .log JSON record (defaults to _world/_reference/log)")
    args = parser.parse_args()

    image_paths = [Path(p) for p in args.img]
    prompt_path = Path(args.prompt)
    output_path = Path(args.output)
    log_path    = Path(args.log_dir) / f"{output_path.name}.log"

    missing = [p for p in image_paths if not p.exists()]
    if missing:
        print(f"Error: input image(s) not found: {', '.join(str(p) for p in missing)}", file=sys.stderr)
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
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "image":     [str(p) for p in image_paths] if len(image_paths) > 1 else str(image_paths[0]),
        "prompt":    prompt,
        "output":    str(output_path),
    }

    try:
        config    = load_config()
        model_id  = config["image_model_id"]
        size      = config["image_size"]
        watermark = config.get("watermark", False)
        base_url  = config["maas_api_endpoint"]
        log["model"] = model_id

        print(f"Input image(s): {', '.join(str(p) for p in image_paths)}", file=sys.stderr)
        print(f"Prompt file: {prompt_path}", file=sys.stderr)
        print(f"Prompt: {prompt}", file=sys.stderr)
        print(f"Model: {model_id}  Size: {size}", file=sys.stderr)
        print(f"Output: {output_path}\n", file=sys.stderr)

        api_key = load_api_key()
        service = ArkImageService(base_url=base_url, api_key=api_key)
        image_data_urls = [file_to_data_url(p) for p in image_paths]
        image = image_data_urls[0] if len(image_data_urls) == 1 else image_data_urls

        print(f"Generating...", file=sys.stderr)
        image_url, usage = generate_image(service, prompt, image, model_id, size, watermark)

        dl_s    = download_file(image_url, output_path)
        total_s = round(time.monotonic() - t_start, 2)

        print(f"Saved: {output_path}  ({total_s}s, download {dl_s:.1f}s)", file=sys.stderr)

        log.update({
            "image_url": image_url,
            **extract_token_usage(usage),
            "usage": usage,
            "total_s": total_s,
            "download_s": round(dl_s, 2),
            "status": "succeeded",
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
