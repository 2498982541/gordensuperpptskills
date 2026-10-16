#!/usr/bin/env python3
"""One-command checks for a single converted page directory.

The page directory holds source.png (the slide image) and, once written,
layout.json plus the layer images it references. Outputs go to PAGE/qa/.

Stages:
  layers  background+frame flattened next to the source -> qa/layers.png
          (use it to see which icons/decorations the frame already contains)
  boxes   layout_guard + every icon/text box drawn on the source -> qa/source_boxes.png
          (use it to confirm each box really covers the right object)
  full    (default) guard -> source boxes -> compose page.pptx -> render it with
          PowerPoint -> qa/render/slide_01.png, qa/preview_boxes.png,
          qa/side_by_side.png, qa/blend.png, qa/diff_heatmap.png

Usage:
    python build_page.py PAGE_DIR [--stage layers|boxes|full]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from compose_pptx import build_pptx, render_with_powerpoint  # noqa: E402
from layout_guard import check_layout  # noqa: E402

FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]


def _font(size: int):
    from PIL import ImageFont
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _label(item: dict) -> str:
    if item.get("file"):
        return Path(str(item["file"])).stem
    text = item.get("text") or "".join(str(r.get("text", "")) for r in item.get("runs", []))
    text = str(text).replace("\n", " ")
    return text[:14] + ("…" if len(text) > 14 else "")


def draw_boxes(image, layout: dict, title: str):
    from PIL import ImageDraw
    out = image.convert("RGB")
    draw = ImageDraw.Draw(out)
    kx, ky = out.width / float(layout["ref_width"]), out.height / float(layout["ref_height"])
    font = _font(max(14, out.width // 110))
    for kind, color in (("icons", (255, 170, 0)), ("texts", (0, 160, 255))):
        for i, item in enumerate(layout.get(kind, []), 1):
            try:
                x, y, w, h = (float(item[k]) for k in ("x", "y", "w", "h"))
            except (KeyError, TypeError, ValueError):
                continue
            box = [x * kx, y * ky, (x + w) * kx, (y + h) * ky]
            draw.rectangle(box, outline=color, width=2 if kind == "texts" else 3)
            tag = f"{'I' if kind == 'icons' else 'T'}{i} {_label(item)}"
            # Label sits just above the box so it never hides the content being checked.
            ty = box[1] - font.size - 4 if box[1] >= font.size + 4 else box[3] + 2
            draw.text((box[0], ty), tag, fill=color, font=font,
                      stroke_width=2, stroke_fill=(255, 255, 255))
    draw.rectangle([0, 0, len(title) * font.size * 0.62 + 16, font.size + 10], fill=(0, 0, 0))
    draw.text((8, 4), title, fill=(255, 255, 255), font=font)
    return out


def side_by_side(left, right, labels=("source", "result")):
    from PIL import Image, ImageDraw
    right = right.convert("RGB")
    left = left.convert("RGB").resize(right.size)
    canvas = Image.new("RGB", (right.width * 2 + 12, right.height), (40, 40, 40))
    canvas.paste(left, (0, 0))
    canvas.paste(right, (right.width + 12, 0))
    draw = ImageDraw.Draw(canvas)
    font = _font(max(16, right.width // 80))
    for x, text in ((0, labels[0]), (right.width + 12, labels[1])):
        draw.rectangle([x, 0, x + len(text) * font.size * 0.7 + 16, font.size + 10], fill=(0, 0, 0))
        draw.text((x + 8, 4), text, fill=(255, 255, 255), font=font)
    return canvas


def stage_layers(page: Path, qa: Path) -> None:
    from PIL import Image
    with Image.open(page / "source.png") as src:
        source = src.convert("RGB")
    canvas = Image.new("RGBA", source.size, (128, 128, 128, 255))
    for name in ("background.png", "frame.png"):
        p = page / name
        if p.exists():
            with Image.open(p) as layer:
                canvas.alpha_composite(layer.convert("RGBA").resize(source.size))
    out = qa / "layers.png"
    side_by_side(source, canvas, ("source", "background + frame")).save(out)
    print(f"Wrote {out}")


def guard_and_boxes(page: Path, qa: Path) -> dict:
    from PIL import Image
    layout_path = page / "layout.json"
    warnings, errors = check_layout(page / "source.png", layout_path)
    for m in warnings:
        print(f"Warning: {m}")
    for m in errors:
        print(f"Error: {m}")
    layout = json.loads(layout_path.read_text(encoding="utf-8-sig"))
    if not errors:
        with Image.open(page / "source.png") as src:
            draw_boxes(src, layout, "source + layout boxes").save(qa / "source_boxes.png")
        print(f"Wrote {qa / 'source_boxes.png'}")
    if errors or warnings:
        print("layout_guard failed: fix the layout (or mark small_text_ok / allow_all_bold_text "
              "only when the source really looks like that).")
        raise SystemExit(2)
    return layout


def stage_full(page: Path, qa: Path) -> None:
    from PIL import Image, ImageChops, ImageOps
    layout = guard_and_boxes(page, qa)
    pptx = build_pptx([page / "layout.json"], page / "page.pptx")
    render = render_with_powerpoint(pptx, qa / "render")[0]

    with Image.open(page / "source.png") as src, Image.open(render) as prv:
        preview = prv.convert("RGB")
        source = src.convert("RGB").resize(preview.size)
    draw_boxes(preview, layout, "PowerPoint render + layout boxes").save(qa / "preview_boxes.png")
    side_by_side(source, preview, ("source", "PowerPoint render")).save(qa / "side_by_side.png")
    Image.blend(source, preview, 0.5).save(qa / "blend.png")
    diff = ImageOps.grayscale(ImageChops.difference(source, preview))
    heat = Image.new("RGBA", preview.size, (255, 0, 0, 0))
    heat.putalpha(diff.point(lambda v: min(220, int(v * 1.35))))
    base = source.convert("RGBA")
    base.alpha_composite(heat)
    base.convert("RGB").save(qa / "diff_heatmap.png")
    changed = sum(diff.histogram()[48:]) / (preview.width * preview.height)
    print(f"Changed-pixel share: {changed:.1%} (diagnostic only; judge by eye)")
    for name in ("side_by_side.png", "preview_boxes.png", "blend.png", "diff_heatmap.png"):
        print(f"Wrote {qa / name}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("page", help="Page directory containing source.png (and layout.json).")
    ap.add_argument("--stage", choices=("layers", "boxes", "full"), default="full")
    args = ap.parse_args()
    page = Path(args.page).resolve()
    if not (page / "source.png").is_file():
        print(f"Error: {page / 'source.png'} not found", file=sys.stderr)
        raise SystemExit(2)
    qa = page / "qa"
    qa.mkdir(exist_ok=True)
    if args.stage == "layers":
        stage_layers(page, qa)
    elif args.stage == "boxes":
        guard_and_boxes(page, qa)
    else:
        stage_full(page, qa)


if __name__ == "__main__":
    main()
