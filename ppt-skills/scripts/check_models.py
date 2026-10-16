#!/usr/bin/env python3
"""Compare Codex's model list with the models this skill already knows.

Reads $CODEX_HOME/models_cache.json (default ~/.codex) and references/models.json.
Prints the current conversion model and any listed model not seen before.

Usage:
    python check_models.py                         # report
    python check_models.py --ack                   # mark all new models as known (asked once)
    python check_models.py --ack --use gpt-7-sol --effort high   # also switch the conversion model
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / "references" / "models.json"


def listed_models() -> list[dict]:
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    cache = home / "models_cache.json"
    if not cache.is_file():
        return []
    data = json.loads(cache.read_text(encoding="utf-8"))
    return [m for m in data.get("models", []) if m.get("visibility", "list") == "list" and m.get("slug")]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ack", action="store_true", help="Add every currently listed model to known_models.")
    ap.add_argument("--use", metavar="MODEL", help="Set the conversion model.")
    ap.add_argument("--effort", help="Set the conversion reasoning effort (with --use).")
    ap.add_argument("--config", default=str(CONFIG), help=argparse.SUPPRESS)
    args = ap.parse_args()

    config = Path(args.config)
    cfg = json.loads(config.read_text(encoding="utf-8"))
    conv = cfg["conversion"]
    models = listed_models()
    if not models:
        print("未找到 Codex 模型列表（models_cache.json），无法检查新模型；继续使用当前转换模型。")
    slugs = [m["slug"] for m in models]
    new = [m for m in models if m["slug"] not in cfg["known_models"]]

    if args.use:
        conv["model"] = args.use
        if args.effort:
            conv["reasoning_effort"] = args.effort
    if args.ack:
        cfg["known_models"] = sorted(set(cfg["known_models"]) | set(slugs))
    if args.ack or args.use:
        config.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"已更新 {config}")
        new = [] if args.ack else new

    print(f"转换模型：{conv['model']} / {conv['reasoning_effort']}")
    if models and conv["model"] not in slugs:
        print(f"注意：{conv['model']} 不在当前 Codex 可用模型列表里，需要问用户换哪个。")
    if new:
        print("发现新模型（尚未问过用户）：")
        for m in new:
            levels = [lv.get("effort") for lv in m.get("supported_reasoning_levels", [])]
            print(f"- {m['slug']}：{m.get('description', '')}"
                  f"｜推理档位 {levels}｜输入 {m.get('input_modalities', [])}")
    elif models:
        print("没有新模型。")


if __name__ == "__main__":
    main()
