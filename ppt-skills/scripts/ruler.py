#!/usr/bin/env python3
"""Draw a labeled pixel grid over a slide image so boxes can be read in SOURCE pixels.

Image viewers often show a downscaled copy; reading positions off the grid
labels keeps every measurement in the source image's own pixel space.
Use --region to zoom into a dense area (labels stay in source pixels).

Usage:
    python ruler.py source.png qa/ruler.png
    python ruler.py source.png qa/ruler_zoom.png --region 1200 300 800 450
    python ruler.py source.png qa/ruler.png --step 50
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONTS = ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/arial.ttf",
         "/System/Library/Fonts/PingFang.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]


def _font(size: int):
    for path in FONTS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _nice_step(span: float) -> int:
    for step in (10, 20, 25, 50, 100, 200, 250, 500):
        if span / step <= 24:
            return step
    return 1000


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("out")
    ap.add_argument("--region", nargs=4, type=int, metavar=("X", "Y", "W", "H"),
                    help="Crop this source-pixel region and enlarge it.")
    ap.add_argument("--step", type=int, help="Grid spacing in source pixels (auto by default).")
    ap.add_argument("--width", type=int, default=1800, help="Output width in pixels.")
    args = ap.parse_args()

    with Image.open(args.image) as im:
        src = im.convert("RGB")
    x0, y0, w, h = args.region if args.region else (0, 0, src.width, src.height)
    x0, y0 = max(0, x0), max(0, y0)
    w, h = min(w, src.width - x0), min(h, src.height - y0)
    if w <= 0 or h <= 0:
        raise SystemExit(f"Error: region is outside the {src.width}x{src.height} image")
    crop = src.crop((x0, y0, x0 + w, y0 + h))
    scale = args.width / w
    out = crop.resize((args.width, max(1, round(h * scale))), Image.LANCZOS)
    step = args.step or _nice_step(max(w, h))

    overlay = Image.new("RGBA", out.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _font(max(12, args.width // 120))
    first_x = (x0 // step + 1) * step if x0 % step else x0
    first_y = (y0 // step + 1) * step if y0 % step else y0
    for gx in range(first_x, x0 + w + 1, step):
        px = (gx - x0) * scale
        major = gx % (step * 2) == 0
        draw.line([(px, 0), (px, out.height)], fill=(255, 0, 80, 150 if major else 80), width=1)
        draw.text((px + 2, 2), str(gx), fill=(255, 0, 80, 255), font=font,
                  stroke_width=2, stroke_fill=(255, 255, 255, 255))
    for gy in range(first_y, y0 + h + 1, step):
        py = (gy - y0) * scale
        major = gy % (step * 2) == 0
        draw.line([(0, py), (out.width, py)], fill=(0, 120, 255, 150 if major else 80), width=1)
        draw.text((2, py + 2), str(gy), fill=(0, 120, 255, 255), font=font,
                  stroke_width=2, stroke_fill=(255, 255, 255, 255))
    result = Image.alpha_composite(out.convert("RGBA"), overlay).convert("RGB")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    result.save(args.out)
    print(f"Wrote {args.out}  (source {src.width}x{src.height}, region {x0},{y0},{w},{h}, grid {step}px)")


if __name__ == "__main__":
    main()
