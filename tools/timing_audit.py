#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计 B2 端到端开发耗时墙钟口径：检测同一规范模型的多批次运行是否存在时间重叠。

用法：
    python tools/timing_audit.py [runs_dir] [--strict] [--json]
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import argparse
import json
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "scoring"))
from model_identity import canonical_model_id  # noqa: E402


def epoch(iso: str | None) -> float | None:
    if not iso:
        return None
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def load_run(run_dir: Path) -> dict | None:
    proto_path = run_dir / "protocol.json"
    if not proto_path.exists():
        return None
    proto = json.loads(proto_path.read_text(encoding="utf-8"))
    timing = proto.get("timing") or {}
    start = epoch(timing.get("t0_iso")) or epoch(timing.get("process_iso"))
    end = epoch(timing.get("end_iso"))
    if start is None or end is None:
        return None
    name = run_dir.name
    return {
        "name": name,
        "model": canonical_model_id(proto.get("model_id") or name),
        "start": start,
        "end": end,
        "e2e_min": round((end - start) / 60.0, 2),
        "overlaps": [],
    }


def collect(root: Path) -> list[dict]:
    if not root.exists():
        return []
    if (root / "protocol.json").exists():
        dirs = [root]
    else:
        dirs = [p for p in sorted(root.iterdir()) if p.is_dir() and (p / "protocol.json").exists()]
    rows = [r for r in (load_run(d) for d in dirs) if r is not None]
    for a in rows:
        for b in rows:
            if a is b or a["model"] != b["model"]:
                continue
            if max(a["start"], b["start"]) < min(a["end"], b["end"]):
                a["overlaps"].append(b["name"])
    for a in rows:
        a["b2_comparable"] = not a["overlaps"]
    return rows


def build_report(rows: list[dict]) -> dict:
    any_overlap = any(bool(r["overlaps"]) for r in rows)
    return {
        "ok": not any_overlap,
        "overlapRuns": sum(1 for r in rows if r["overlaps"]),
        "runs": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="检查同一模型多批次运行是否时间重叠导致 B2 墙钟污染")
    ap.add_argument("runs_dir", nargs="?", default=str(ROOT / "runs"), help="运行根目录或单个 run 目录")
    ap.add_argument("--strict", action="store_true", help="发现同模型时间重叠时以退出码 1 结束")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    args = ap.parse_args()

    rows = collect(Path(args.runs_dir))
    if not rows:
        if args.json:
            print(json.dumps({"ok": False, "overlapRuns": 0, "runs": []}, ensure_ascii=False, indent=2))
        else:
            print("没有找到已完成打包计时（含 t0 与 end_iso）的运行记录")
        return 1

    report = build_report(rows)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] or not args.strict else 1

    print(f"{'运行目录':40} {'规范模型ID':24} {'开发耗时':>9}  同模型重叠检查")
    print("-" * 92)
    for r in sorted(rows, key=lambda x: (x["start"], x["name"])):
        ov = "[OVERLAP] " + ", ".join(r["overlaps"]) if r["overlaps"] else "-"
        print(f"{r['name']:40} {r['model']:24} {r['e2e_min']:7.1f}m  {ov}")

    if not report["ok"]:
        print("\n警告：标有 [OVERLAP] 的运行与同模型其他批次时间重叠，API 排队会污染 B2 墙钟耗时。")
        return 1 if args.strict else 0
    print("\nOK：未发现同模型运行时间重叠，B2 端到端墙钟口径有效。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
