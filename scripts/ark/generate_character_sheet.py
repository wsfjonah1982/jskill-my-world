import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from ark_service import (
    ArkImageService, download_file, file_to_data_url, extract_token_usage, BASE_DIR, LOG_DIR,
    configure_console, load_config, load_api_key, write_log, character_sheet_prompt, read_text_file,
)

configure_console()

OUTPUT_PATH     = BASE_DIR / "_world" / "_reference" / "output" / "character_sheet.png"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a character reference sheet (turnaround, three views, full body, "
                    "clean white background) from a subject description, using the fixed template "
                    "prompt/three_angle_character_sheet.txt — no chat model call, deterministic prompt every time. With --img, one or more photos "
                    "anchor the subject's appearance/style instead of generating from the "
                    "description alone."
    )
    parser.add_argument("--idea",   required=True, help="Path to a .txt file describing the subject's appearance")
    parser.add_argument("--style",  default=None, help="Art style (defaults to aigc_config.json's default_style)")
    parser.add_argument("--img",    default=None, nargs="+", help="Optional reference photo(s) to anchor appearance/style")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Output image file path")
    parser.add_argument("--log-dir", default=str(LOG_DIR), help="Directory for the .log JSON record (defaults to _world/_reference/log)")
    args = parser.parse_args()

    idea_path   = Path(args.idea)
    image_paths = [Path(p) for p in args.img] if args.img else []
    output_path = Path(args.output)
    log_path    = Path(args.log_dir) / f"{output_path.name}.log"

    if not idea_path.exists():
        print(f"Error: idea file not found: {idea_path}", file=sys.stderr)
        return 1
    missing = [p for p in image_paths if not p.exists()]
    if missing:
        print(f"Error: reference image(s) not found: {', '.join(str(p) for p in missing)}", file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)

    t_start = time.monotonic()
    log: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "idea_file": str(idea_path),
        "reference_images": [str(p) for p in image_paths],
        "output":    str(output_path),
    }

    try:
        config    = load_config()
        model_id  = config["image_model_id"]
        size      = config["image_size"]
        watermark = config.get("watermark", False)
        base_url  = config["maas_api_endpoint"]
        style     = args.style or config.get("default_style", "")
        idea      = read_text_file(idea_path, "Idea")

        prompt = character_sheet_prompt(idea)
        prompt = f"{prompt} Art style: {style}."
        log.update({"model": model_id, "style": style, "prompt": prompt})

        print(f"Idea: {idea_path} ({len(idea)} chars)  Style: {style}", file=sys.stderr)
        if image_paths:
            print(f"Reference image(s): {', '.join(str(p) for p in image_paths)}", file=sys.stderr)
        print(f"Prompt: {prompt}", file=sys.stderr)
        print(f"Model: {model_id}  Size: {size}", file=sys.stderr)
        print(f"Output: {output_path}\n", file=sys.stderr)

        api_key = load_api_key()
        service = ArkImageService(base_url=base_url, api_key=api_key)

        image = None
        if image_paths:
            image_data_urls = [file_to_data_url(p) for p in image_paths]
            image = image_data_urls[0] if len(image_data_urls) == 1 else image_data_urls

        print("Generating...", file=sys.stderr)
        images, usage = service.generate_image(model_id=model_id, prompt=prompt, image=image, size=size, watermark=watermark)
        image_url = images[0]["url"] if images else None
        if not image_url:
            raise RuntimeError("No image URL returned")

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
