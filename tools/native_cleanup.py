"""Run the pinned upstream inpainter on a reviewed native page mask."""
import argparse
import asyncio
import base64
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def clean(layout, source, output, width, height):
    if width <= 0 or height <= 0 or width * height > 32_000_000:
        raise ValueError("Invalid cleanup canvas or canvas exceeds 32 million pixels.")
    if output.exists():
        raise ValueError("Cleanup output already exists. Use a fresh run.")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    for variable, directory in (("YOLO_CONFIG_DIR", "ultralytics"), ("MPLCONFIGDIR", "matplotlib")):
        local = ROOT / ".runtime/native-cache" / directory
        local.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault(variable, str(local))
    sys.path.insert(0, str(ROOT / "manga-translator-ui"))
    import cv2
    import numpy as np
    from manga_translator.config import Inpainter, InpainterConfig
    from manga_translator.inpainting import dispatch
    from manga_translator.utils import dump_image, load_image, open_pil_image, save_pil_image

    data = json.loads(layout.read_text(encoding="utf-8-sig"))
    if "regions" not in data:
        data = next(value for value in data.values() if isinstance(value, dict) and "regions" in value)
    settings = dict(data["cleanup"])
    device = settings.pop("device", "cpu")
    settings.pop("source", None)
    if "inpainter" not in settings:
        raise ValueError("Choose an inpainter explicitly for this page.")
    defaults = json.loads((ROOT / "profiles/render.json").read_text(encoding="utf-8"))["inpainter"]
    config = InpainterConfig(**(defaults | settings))
    with open_pil_image(str(source), eager=True) as image:
        rgb, alpha = load_image(image)
        if rgb.shape[:2] != (height, width):
            raise ValueError("Cleanup input must already match the output canvas.")
        encoded = data.get("mask_raw")
        if encoded:
            if data.get("mask_is_refined") is not True:
                raise ValueError("Review and refine the native cleanup mask first.")
            mask = cv2.imdecode(np.frombuffer(base64.b64decode(encoded, validate=True), np.uint8), cv2.IMREAD_GRAYSCALE)
            if mask is None or mask.shape != (height, width):
                raise ValueError("Native mask does not match the cleanup canvas.")
        elif data["regions"]:
            raise ValueError("Supply an explicit refined mask, including an empty mask when source art is retained.")
        else:
            mask = np.zeros((height, width), np.uint8)
        result = asyncio.run(dispatch(Inpainter(config.inpainter), rgb, mask, config,
                                     config.inpainting_size, device))
        output.parent.mkdir(parents=True, exist_ok=True)
        save_pil_image(dump_image(image, result, alpha, mask=mask), str(output), source_image=image, format="PNG")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("layout", type=Path)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("width", type=int)
    parser.add_argument("height", type=int)
    args = parser.parse_args()
    clean(args.layout, args.source, args.output, args.width, args.height)
