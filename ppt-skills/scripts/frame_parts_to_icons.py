#!/usr/bin/env python3
"""Turn frame_parts/icons_manifest.json into layout.json icon entries (optional frame split).

Only used when the user explicitly asks for a split, movable frame. After
`slice_grid.py frame.png frame_parts --components --pad 0 --prefix fp`, each
cutout's bbox (in frame.png pixels) is mapped to source pixels, so placing the
parts at the emitted boxes rebuilds the original frame.png exactly. Put the
output entries FIRST in layout.icons and drop the "frame" field.

Usage:
    python frame_parts_to_icons.py PAGE/frame_parts/icons_manifest.json --ref-width 2400 --ref-height 1350
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def die(msg: str) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    raise SystemExit(2)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manifest", help="frame_parts/icons_manifest.json from slice_grid.py --components.")
    ap.add_argument("--ref-width", type=float, required=True, help="Source slide width in pixels.")
    ap.add_argument("--ref-height", type=float, required=True, help="Source slide height in pixels.")
    ap.add_argument("--out", help="Output JSON (default: frame_parts_layout_icons.json next to the manifest).")
    args = ap.parse_args()

    manifest = Path(args.manifest)
    if not manifest.exists():
        die(f"manifest not found: {manifest}")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if data.get("mode") != "components":
        die("manifest mode must be 'components' (run slice_grid.py --components)")
    frame_w, frame_h = map(float, data["size"])
    sx, sy = args.ref_width / frame_w, args.ref_height / frame_h
    prefix = manifest.parent.name

    icons = []
    for i, item in enumerate(data.get("icons", []), 1):
        l, t, r, b = map(float, item["bbox"])
        if round(float(item.get("width", r - l))) != round(r - l) or \
           round(float(item.get("height", b - t))) != round(b - t):
            die(f"part {i}: cutout size differs from its bbox; do not use --square for frame parts")
        icons.append({"file": f"{prefix}/{item['file']}", "role": "frame_part",
                      "x": round(l * sx, 1), "y": round(t * sy, 1),
                      "w": round((r - l) * sx, 1), "h": round((b - t) * sy, 1)})

    out = Path(args.out) if args.out else manifest.parent / "frame_parts_layout_icons.json"
    out.write_text(json.dumps(icons, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(icons)} frame_part entries to {out}")


if __name__ == "__main__":
    main()
