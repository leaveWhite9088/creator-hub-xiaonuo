#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""汇总查看中心评审日志（review_merge.py）：按 pack_id + case_id 聚合多位评委的 D 层得分。"""
from __future__ import annotations

from pathlib import Path
import argparse
import datetime
import json
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import review_log  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="聚合中心评审日志并输出 D 层统计表")
    ap.add_argument("--log", default=str(review_log.DEFAULT_LOG), help="中心评审日志 JSONL")
    ap.add_argument("--out", default=None, help="可选：聚合结果 JSON 输出路径")
    ap.add_argument("--aggregate", choices=("mean", "median"), default="mean")
    ap.add_argument("--min-judges", type=int, default=1)
    args = ap.parse_args()

    if args.min_judges < 1:
        print("--min-judges 必须 >= 1")
        return 1

    try:
        reviews = review_log.read_reviews(args.log)
    except review_log.ReviewLogError as e:
        print("读取评审日志失败：" + str(e))
        return 1
    if not reviews:
        print("评审日志为空：" + str(Path(args.log).resolve()))
        return 1

    used, duplicates = review_log.dedupe_latest(reviews)
    groups = review_log.aggregate_reviews(used, args.aggregate)
    below = [g for g in groups if g["judge_count"] < args.min_judges]

    print(f"评审日志：{Path(args.log).resolve()}")
    print(f"原始记录 {len(reviews)} 条；按 (pack_id, case_id, judge_id) 去重后 {len(used)} 条；旧重复 {duplicates} 条")
    print(f"聚合口径：{args.aggregate}；匿名案例数：{len(groups)}")
    print("")
    print(f"{'pack_id':<16}{'case':<10}{'评委数':>6}{'D1(10)':>9}{'D2(10)':>9}{'D3(10)':>9}{'D总(30)':>9}")
    print("-" * 68)
    for g in groups:
        print(
            f"{g['pack_id']:<16}{g['case_id']:<10}{g['judge_count']:>6}"
            f"{g['D1']:>9.2f}{g['D2']:>9.2f}{g['D3']:>9.2f}{g['D']:>9.2f}"
        )
    if below:
        print("")
        for g in below:
            print(f"!! {g['pack_id']}/{g['case_id']} 当前仅有 {g['judge_count']} 位评委（低于要求的 {args.min_judges}）")

    summary = {
        "schema_version": review_log.SCHEMA_VERSION,
        "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "log": str(Path(args.log).resolve()),
        "aggregate": args.aggregate,
        "min_judges": args.min_judges,
        "reviews_total": len(reviews),
        "reviews_used": len(used),
        "duplicates_removed": duplicates,
        "groups": groups,
    }
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\n聚合文件已写入：{out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
