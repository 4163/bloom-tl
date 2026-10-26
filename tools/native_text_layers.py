"""Call the upstream Qt text renderer, then FFmpeg to assemble its raster layers."""
import argparse
import copy
import hashlib
import json
import math
import os
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def size(path):
    with path.open("rb") as stream:
        header = stream.read(24)
    return struct.unpack(">II", header[16:24])


def capture_background(data, cleaned, original, output, width, height, composite, ffmpeg):
    import numpy as np
    from PIL import Image
    from PyQt6.QtGui import QImage
    from editor.paste_overlay_state import compose_paste_overlays
    from manga_translator.utils import open_pil_image, save_pil_image

    def run(*arguments):
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", *map(str, arguments)], check=True)

    if size(cleaned) != (width, height):
        raise ValueError("The reviewed cleanup base must match the output canvas.")
    prepared = output / "cleaned.png"
    overlays = compose_paste_overlays(data.get("paste_overlays", []), (width, height))
    if overlays is not None:
        overlay = output / "native-paste.png"
        image = QImage(overlays.data, width, height, width * 4, QImage.Format.Format_RGBA8888).copy()
        if not image.save(str(overlay), "PNG"):
            raise ValueError("Native paste export failed.")
        run("-i", cleaned, "-i", overlay, "-filter_complex",
            "[0:v][1:v]overlay=0:0:format=auto:alpha=straight,format=rgb24", "-frames:v", "1", prepared)
    else:
        run("-i", cleaned, "-vf", "format=rgb24", "-frames:v", "1", prepared)
    source = output / "original.png"
    decoded = output / "original-native.png"
    with open_pil_image(str(original), eager=True) as original_image:
        save_pil_image(original_image, str(decoded), source_image=original_image, format="PNG")
    run("-i", decoded, "-vf", f"format=rgba,pad={width}:{height}:0:0:color=black@0", "-frames:v", "1", source)
    before = np.asarray(Image.open(source).convert("RGBA"))
    after = np.asarray(Image.open(prepared).convert("RGB"))
    changed = np.any(before[:, :, :3] != after, axis=2) | (before[:, :, 3] != 255)
    mask = output / "cleanup-mask.png"
    Image.fromarray(np.where(changed, 255, 0).astype(np.uint8)).save(mask)
    paint = output / "paint.png"
    run("-i", prepared, "-i", mask, "-filter_complex", "[0:v]format=rgb24[base];[base][1:v]alphamerge,format=rgba",
        "-frames:v", "1", paint)
    composite.parent.mkdir(parents=True, exist_ok=True)
    run("-i", source, "-i", paint, "-i", output / "text.png", "-filter_complex",
        "[0:v][1:v]overlay=0:0:format=auto:alpha=straight[clean];[clean][2:v]overlay=0:0:format=auto:alpha=straight,format=rgb24",
        "-frames:v", "1", composite)
    receipt = {"original_source": str(original), "cleaned_source": str(cleaned),
        "original_source_sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
        "cleaned_source_sha256": hashlib.sha256(cleaned.read_bytes()).hexdigest(),
        "cleanup_pixels": int(changed.sum()), "canvas": [width, height], "sha256": {
            filename: hashlib.sha256((output / filename).read_bytes()).hexdigest()
            for filename in ("original.png", "paint.png", "text.png", "cleaned.png", "cleanup-mask.png")}}
    (output / "capture.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


def render(native_json, output, width, height, ffmpeg):
    if width <= 0 or height <= 0 or width * height > 32_000_000:
        raise ValueError("Invalid canvas or canvas exceeds the PSD limit of 32 million pixels.")
    if sys.platform != "win32":
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    for variable, directory in (("YOLO_CONFIG_DIR", "ultralytics"), ("MPLCONFIGDIR", "matplotlib")):
        local = ROOT / ".runtime/native-cache" / directory
        local.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault(variable, str(local))
    sys.path[:0] = [str(ROOT / "manga-translator-ui"), str(ROOT / "manga-translator-ui/desktop_qt_ui")]
    import numpy as np
    from PyQt6.QtWidgets import QApplication
    from editor.text_render_pipeline import build_text_block_from_region
    from editor.text_renderer_backend import render_text_image_for_region

    app = QApplication.instance() or QApplication([])
    data = json.loads(native_json.read_text(encoding="utf-8-sig"))
    if "regions" not in data:
        data = next(value for value in data.values() if isinstance(value, dict) and "regions" in value)
    output.mkdir(parents=True, exist_ok=False)
    patches = []
    for index, original in enumerate(data["regions"]):
        region = copy.deepcopy(original)
        if not region.get("translation"):
            continue
        requested = region.get("font_family", "")
        font = Path(requested)
        if not font.exists():
            # Old native records used the previous installation's font path.
            font = ROOT / "manga-translator-ui/fonts" / requested.replace("\\", "/").rsplit("/", 1)[-1]
        if font.exists():
            region["font_family"] = str(font)
        elif "/" in requested or "\\" in requested:
            raise ValueError(f"Resolve the missing font explicitly: {requested}")
        block = build_text_block_from_region(region)
        if block is None:
            raise ValueError(f"Invalid native text region {index}")
        lines = np.asarray(region["lines"], dtype=np.float32).reshape(-1, 2)
        low, high = lines.min(0), lines.max(0)
        center = np.asarray(region.get("center", (low + high) / 2), dtype=np.float32)
        half = (high - low) / 2
        points = np.array([center + [-half[0], -half[1]], center + [half[0], -half[1]],
                           center + [half[0], half[1]], center + [-half[0], half[1]]], dtype=np.float32)
        params = {key: region[key] for key in ("font_family", "line_spacing", "letter_spacing", "stroke_width",
            "disable_font_border", "font_color", "text_stroke_color") if key in region}
        params.setdefault("stroke_width", 0.07)
        result = render_text_image_for_region(block, points, None, params)
        if result is None:
            raise ValueError(f"Native renderer returned no text for region {index}")
        image, _, _ = result
        patch = output / f"region-{index:03d}.png"
        if not image.save(str(patch), "PNG"):
            raise ValueError(f"Native PNG export failed: {patch}")
        angle = float(region.get("angle", 0))
        if angle:
            rotated = output / f"region-{index:03d}-rotated.png"
            radians = math.radians(angle)
            subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(patch),
                "-vf", f"rotate={radians}:ow=rotw({radians}):oh=roth({radians}):c=none,format=rgba", "-frames:v", "1", str(rotated)], check=True)
            patch = rotated
        patch_width, patch_height = size(patch)
        patches.append({"file": str(patch), "x": round(float(center[0]) - patch_width / 2),
                        "y": round(float(center[1]) - patch_height / 2)})
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
               f"color=c=black@0.0:s={width}x{height}:r=1,format=rgba"]
    filters = []
    for index, patch in enumerate(patches, 1):
        command += ["-i", patch["file"]]
        previous = "0:v" if index == 1 else f"text{index - 1}"
        filters.append(f"[{previous}][{index}:v]overlay={patch['x']}:{patch['y']}:format=auto:alpha=straight[text{index}]")
    if filters:
        command += ["-filter_complex", ";".join(filters), "-map", f"[text{len(patches)}]"]
    command += ["-frames:v", "1", str(output / "text.png")]
    subprocess.run(command, check=True)
    (output / "regions.json").write_text(json.dumps(patches, indent=2) + "\n", encoding="utf-8")
    # Keep the Qt application alive through all native exports.
    return app, data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native_json", type=Path); parser.add_argument("output", type=Path)
    parser.add_argument("width", type=int); parser.add_argument("height", type=int); parser.add_argument("--ffmpeg", required=True)
    parser.add_argument("--cleaned", type=Path); parser.add_argument("--original", type=Path); parser.add_argument("--composite", type=Path)
    args = parser.parse_args()
    if any((args.cleaned, args.original, args.composite)) and not all((args.cleaned, args.original, args.composite)):
        parser.error("Provide --cleaned, --original and --composite together.")
    app, data = render(args.native_json, args.output, args.width, args.height, args.ffmpeg)
    if args.cleaned:
        capture_background(data, args.cleaned, args.original, args.output, args.width, args.height, args.composite, args.ffmpeg)
