#!/usr/bin/env python3
"""Check a page layout.json against its source slide image before composing.

Catches the mistakes that silently ruin placement:
  * boxes measured on a downscaled view (ref_width/ref_height != source size),
  * boxes outside the canvas, missing x/y/w/h, missing image files,
  * font sizes that look half-scale (tiny pt, or box height >> size_px),
  * ordinary body text set to bold everywhere.
It does NOT judge whether a box covers the right object -- look at the
source-box overlay and the rendered comparison for that.

Usage:
    python layout_guard.py source.png layout.json
    python layout_guard.py source.png layout.json --fix-scale   # boxes were measured on a scaled copy
Exit code 2 on any error or warning (pass --lenient to allow warnings).
Per-item escape hatches: "small_text_ok": true on a text; "allow_all_bold_text": true on the layout.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

MIN_TEXT_PT = 6.0
MAX_BOLD_RATIO = 0.85


def _label(kind: str, i: int, item: dict) -> str:
    if item.get("file"):
        return f"{kind}[{i}] {Path(str(item['file'])).name}"
    text = item.get("text") or "".join(str(r.get("text", "")) for r in item.get("runs", []))
    return f"{kind}[{i}] {str(text).replace(chr(10), ' ')[:24]}"


def _text_of(item: dict) -> str:
    if item.get("runs"):
        return "".join(str(r.get("text", "")) for r in item["runs"])
    return str(item.get("text", ""))


def _is_bold(item: dict) -> bool:
    runs = [r for r in item.get("runs", []) if str(r.get("text", "")).strip()]
    if runs:
        return all(bool(r.get("bold", item.get("bold", False))) for r in runs)
    return bool(item.get("bold", False))


def check_layout(source: Path, layout_path: Path) -> tuple[list[str], list[str]]:
    from PIL import Image
    from compose_pptx import slide_size_in, text_size_pt

    warnings: list[str] = []
    errors: list[str] = []
    with Image.open(source) as im:
        src_w, src_h = im.size
    lay = json.loads(Path(layout_path).read_text(encoding="utf-8-sig"))
    base = Path(layout_path).resolve().parent

    ref_w, ref_h = lay.get("ref_width"), lay.get("ref_height")
    if not ref_w or not ref_h:
        errors.append(f"missing ref_width/ref_height; set them to the source size {src_w}x{src_h}")
        return warnings, errors
    if (ref_w, ref_h) != (src_w, src_h):
        same_aspect = abs(src_w / ref_w - src_h / ref_h) < 0.005 * src_w / ref_w
        errors.append(
            f"ref_width/ref_height {ref_w}x{ref_h} != source image {src_w}x{src_h}. "
            + ("Boxes look measured on a scaled view: rerun with --fix-scale."
               if same_aspect else "Aspect ratio differs too: re-measure on the real source.")
        )

    for key in ("background", "frame"):
        if lay.get(key) and not (base / lay[key]).is_file():
            errors.append(f"{key} file not found: {lay[key]}")

    for kind in ("icons", "texts"):
        for i, item in enumerate(lay.get(kind, []), 1):
            label = _label(kind, i, item)
            try:
                x, y, w, h = (float(item[k]) for k in ("x", "y", "w", "h"))
            except (KeyError, TypeError, ValueError):
                errors.append(f"{label}: needs numeric x/y/w/h in source pixels")
                continue
            if w <= 0 or h <= 0 or x < -2 or y < -2 or x + w > ref_w + 2 or y + h > ref_h + 2:
                errors.append(f"{label}: box [{x:g},{y:g},{w:g},{h:g}] is outside the {ref_w}x{ref_h} canvas")
            if kind == "icons" and not (base / str(item.get("file", ""))).is_file():
                errors.append(f"{label}: file not found")

    _, slide_h_in = slide_size_in({**lay, "ref_width": float(ref_w), "ref_height": float(ref_h)})
    slide_h_pt = slide_h_in * 72.0
    texts = [(i, t) for i, t in enumerate(lay.get("texts", []), 1) if _text_of(t).strip()]
    for i, t in texts:
        label = _label("texts", i, t)
        if t.get("size") is None and t.get("size_px") is None:
            errors.append(f"{label}: missing size_px (character height in source px) or size (pt)")
            continue
        pt = text_size_pt(t, lay, slide_h_pt)
        if pt < MIN_TEXT_PT and not t.get("small_text_ok"):
            warnings.append(f"{label}: font is only {pt:.1f}pt; size_px may come from a downscaled view "
                            f"(set small_text_ok:true if it really is that small)")
        if t.get("size_px") and t.get("h") and not t.get("small_text_ok"):
            lines = _text_of(t).count("\n") + 1
            if float(t["h"]) / lines / float(t["size_px"]) >= 1.7:
                warnings.append(f"{label}: box height per line is >=1.7x size_px; size_px may be half-scale")

    if len(texts) >= 6 and not lay.get("allow_all_bold_text"):
        bold = sum(1 for _, t in texts if _is_bold(t))
        if bold / len(texts) > MAX_BOLD_RATIO:
            warnings.append(f"{bold}/{len(texts)} text boxes are bold; body text should be bold:false "
                            f"(set allow_all_bold_text:true if the source really is all bold)")
    return warnings, errors


def fix_scale(source: Path, layout_path: Path) -> None:
    """Rescale boxes and size_px measured on a same-aspect scaled view back to source pixels."""
    from PIL import Image
    with Image.open(source) as im:
        src_w, src_h = im.size
    lay = json.loads(Path(layout_path).read_text(encoding="utf-8-sig"))
    sx, sy = src_w / float(lay["ref_width"]), src_h / float(lay["ref_height"])
    for kind in ("icons", "texts"):
        for item in lay.get(kind, []):
            for k, s in (("x", sx), ("w", sx), ("y", sy), ("h", sy)):
                if k in item:
                    item[k] = round(float(item[k]) * s, 1)
            for holder in [item] + list(item.get("runs", [])):
                if holder.get("size_px") is not None:
                    holder["size_px"] = round(float(holder["size_px"]) * sy, 1)
    lay["ref_width"], lay["ref_height"] = src_w, src_h
    Path(layout_path).write_text(json.dumps(lay, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Rescaled boxes by {sx:.4f} x {sy:.4f}; ref is now {src_w}x{src_h}")


def main() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="Source slide image.")
    ap.add_argument("layout", help="Page layout.json.")
    ap.add_argument("--fix-scale", action="store_true", help="Rescale scaled-view measurements to source pixels.")
    ap.add_argument("--lenient", action="store_true", help="Only fail on errors, not warnings.")
    args = ap.parse_args()
    if args.fix_scale:
        fix_scale(Path(args.source), Path(args.layout))
    warnings, errors = check_layout(Path(args.source), Path(args.layout))
    for m in warnings:
        print(f"Warning: {m}")
    for m in errors:
        print(f"Error: {m}")
    print(f"layout_guard: {len(errors)} error(s), {len(warnings)} warning(s)")
    if errors or (warnings and not args.lenient):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
