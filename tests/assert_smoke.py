#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""双基线（加空壳基线）端到端全链路产物、12 张连环画截图与分数梯度严格断言（tests/assert_smoke.py）。"""
from __future__ import annotations

from pathlib import Path
import json
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python tests/assert_smoke.py <tmp_dir>")
        return 1

    tmp = Path(sys.argv[1]).resolve()
    runs_dir = tmp / "runs"
    blind_dir = tmp / "blind"
    verdicts_dir = tmp / "verdicts"
    scores_md = tmp / "scores.md"
    runs_log = tmp / "runs_log.jsonl"

    errors: list[str] = []

    def check(cond: bool, msg: str):
        if not cond:
            errors.append(msg)

    # 1. 核查生命周期台账 runs_log.jsonl 留档齐全
    check(runs_log.exists(), "缺少运行生命周期台账 runs_log.jsonl")
    if runs_log.exists():
        events = [json.loads(line)["event_type"] for line in runs_log.read_text(encoding="utf-8").splitlines() if line.strip()]
        check(events.count("start") == 3, f"runs_log.jsonl start 事件数应为 3，实测 {events.count('start')}")
        check(events.count("pack") == 3, f"runs_log.jsonl pack 事件数应为 3，实测 {events.count('pack')}")
        check(events.count("finalize") == 3, f"runs_log.jsonl finalize 事件数应为 3，实测 {events.count('finalize')}")

    # 2. 核查每个盲评包均生成了 12 张非空 PNG 连环画（S01..S12）与 STORYBOARD.md
    packs = [p for p in blind_dir.iterdir() if p.is_dir()] if blind_dir.exists() else []
    check(len(packs) == 3, f"blind/ 下应有 3 个盲评包，实测 {len(packs)}")
    for p in packs:
        sb_dir = p / "case-01" / "storyboard"
        pngs = sorted(sb_dir.glob("*.png")) if sb_dir.exists() else []
        check(len(pngs) == 12, f"盲评包 {p.name} 应含 12 张连环画截图（S01..S12），实测 {len(pngs)}")
        for img in pngs:
            check(img.stat().st_size > 1000, f"截图文件异常过小: {img}")

    # 3. 核查三档基线的客观分与总分梯度（EmptyStub < NaiveModel < GoldenModel）
    v_stub_p = verdicts_dir / "emptystub.json"
    v_naive_p = verdicts_dir / "naivemodel.json"
    v_gold_p = verdicts_dir / "goldenmodel.json"
    for vp in (v_stub_p, v_naive_p, v_gold_p):
        check(vp.exists(), f"缺少裁决留档文件: {vp}")

    if not errors:
        v_stub = json.loads(v_stub_p.read_text(encoding="utf-8"))["mean"]
        v_naive = json.loads(v_naive_p.read_text(encoding="utf-8"))["mean"]
        v_gold = json.loads(v_gold_p.read_text(encoding="utf-8"))["mean"]

        obj_stub = round(v_stub["A"] + v_stub["B"] + v_stub["C"], 2)
        obj_naive = round(v_naive["A"] + v_naive["B"] + v_naive["C"], 2)
        obj_gold = round(v_gold["A"] + v_gold["B"] + v_gold["C"], 2)

        print(
            f"[梯度摘要 · xiaonuo-v4.0]\n"
            f"  EmptyStub  : A={v_stub['A']:.2f} B={v_stub['B']:.2f} C={v_stub['C']:.2f} (客观={obj_stub:.2f}/70) | D={v_stub['D']:.2f} => 总分={v_stub['total']:.2f}\n"
            f"  NaiveModel : A={v_naive['A']:.2f} B={v_naive['B']:.2f} C={v_naive['C']:.2f} (客观={obj_naive:.2f}/70) | D={v_naive['D']:.2f} => 总分={v_naive['total']:.2f}\n"
            f"  GoldenModel: A={v_gold['A']:.2f} B={v_gold['B']:.2f} C={v_gold['C']:.2f} (客观={obj_gold:.2f}/70) | D={v_gold['D']:.2f} => 总分={v_gold['total']:.2f}"
        )

        # 空壳基线：客观分必须严格为 0
        check(obj_stub == 0.0, f"EmptyStub 客观分应为 0.0，实测 {obj_stub}")

        # 简陋基线：在 v4.0 真实异步竞态 + 去剧透冲突消解 + 503 容错 + 连环过关制（×0.20 连坐）下，仅做表面应付将被大幅压低
        check(2.0 <= v_naive["A"] <= 14.5, f"NaiveModel A 分超出预期低位区间 [2.0, 14.5]: {v_naive['A']}")
        check(1.5 <= v_naive["C"] <= 13.0, f"NaiveModel C 分超出预期低位区间 [1.5, 13.0]: {v_naive['C']}")
        check(5.0 <= obj_naive <= 30.0, f"NaiveModel 客观总分超出预期区间 [5.0, 30.0]: {obj_naive}")

        # 黄金参考基线：通关全部异步竞态压测链与耦合工作台，拿到高分（>= 66.0/70），与简陋基线拉开 >= 40 分硬差距
        check(v_gold["A"] >= 28.5, f"GoldenModel A 分应 >= 28.5/30，实测 {v_gold['A']}")
        check(v_gold["C"] >= 23.0, f"GoldenModel C 分应 >= 23.0/25，实测 {v_gold['C']}")
        check(v_gold["B"] >= 13.8, f"GoldenModel B 分应 >= 13.8/15，实测 {v_gold['B']}")
        check(obj_gold >= 66.0, f"GoldenModel 客观总分应 >= 66.0/70，实测 {obj_gold}")
        check(obj_gold - obj_naive >= 40.0, f"黄金基线与简陋基线客观分差距应 >= 40 分，实测 {obj_gold - obj_naive:.2f}")
        check(v_gold["total"] > v_naive["total"] > v_stub["total"], "总分排序未满足 GoldenModel > NaiveModel > EmptyStub")

    # 4. 核查每个运行目录内均完整留档了 result.json / 评分.json / audit_report.md / wave_trace.jsonl
    for rname in ("EmptyStub", "NaiveModel", "GoldenModel-s1"):
        for fn in ("protocol.json", "token_usage.json", "result.json", "评分.json", "audit_report.md", "wave_trace.jsonl"):
            fp = runs_dir / rname / fn
            check(fp.exists(), f"运行留档缺失: {rname}/{fn}")

    # 5. 核查排行榜 scores.md 已按名次正确生成
    check(scores_md.exists(), "缺少排行榜文件 scores.md")
    if scores_md.exists():
        md_txt = scores_md.read_text(encoding="utf-8")
        check("| 1 | goldenmodel |" in md_txt, "scores.md 第一名不是 goldenmodel")
        check("| 2 | naivemodel |" in md_txt, "scores.md 第二名不是 naivemodel")
        check("| 3 | emptystub |" in md_txt, "scores.md 第三名不是 emptystub")

    if errors:
        print("双基线与全链路断言失败：")
        for e in errors:
            print("  !! " + e)
        return 1

    print("[ASSERT PASSED] 空壳 / 简陋基线 / 黄金参考基线全链路留档、12张连环画抓拍与高区分度梯度验证全部通过！")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
