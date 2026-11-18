#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单运行客观评测入口 v4.0（src/scoring/score_run.py）。

职责：
  对指定 runs/<名>/workspace/ 执行零大模型参与的三波无头浏览器异步竞态与物理可用性压测剧本（browser_waves.py），
  调用连环门控、连续插值与短板木桶计分模型（metrics.py）算出 A（30）+ B（15）+ C（25）= 70 分客观成绩，
  并在运行目录下生成完整留档：
    - result.json      ：原始物理测量指标与逐项检查明细（含连坐门控标记）
    - 评分.json         ：定稿客观分值与子项拆解
    - audit_report.md  ：人类可读的物理测量、连坐熔断与缺陷定位报告
    - wave_trace.jsonl ：三波剧本逐步执行时间线日志
"""
from __future__ import annotations

from pathlib import Path
import argparse
import datetime
import json
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import browser_waves  # noqa: E402
import metrics  # noqa: E402
from model_identity import canonical_model_id  # noqa: E402


def _render_audit_markdown(run_name: str, model_id: str, scores: dict, report: dict, eval_sec: float) -> str:
    ad = scores.get("A_detail") or {}
    bd = scores.get("B_detail") or {}
    cd = scores.get("C_detail") or {}
    cb = ad.get("chain_breaks") or {}
    brk_txt = ", ".join(f"{k}@{v}" for k, v in cb.items() if v) or "无（三链全通）"

    lines = [
        f"# 无头浏览器三波连环组合压测报告 · {run_name}",
        "",
        f"- **规范模型 ID**：`{model_id}`",
        f"- **评测版本**：`{scores.get('version', 'xiaonuo-v4.0')}`",
        f"- **评测生成时间**：`{datetime.datetime.now().astimezone().isoformat(timespec='seconds')}`",
        f"- **三波剧本执行耗时**：`{eval_sec:.2f} s`",
        f"- **页面可加载 / 是否空壳**：`page_loadable={scores.get('page_loadable')}` / `not_implemented={scores.get('not_implemented')}`",
        f"- **连环链断链位置**：`{brk_txt}`",
        f"- **客观层总分（满分 70）**：**`{scores.get('total_objective_70', 0.0):.2f} / 70.00`**",
        "",
        "## 一、分维度得分总览",
        "",
        "| 维度 | 子项拆解 | 得分 | 满分 | 关键物理实测摘要 |",
        "| --- | --- | ---: | ---: | --- |",
        f"| **A 异步状态链与异常恢复** | A1 `{ad.get('A1', 0):.2f}/2.0` + A2 `{ad.get('A2', 0):.2f}/9.5` + A3 `{ad.get('A3', 0):.2f}/12.0` + A4 `{ad.get('A4', 0):.2f}/6.5` | **{scores.get('A_outcome', 0):.2f}** | 30.00 | 连环熔断 `{brk_txt}`；拦截外网 `{ad.get('external_requests', 0)}` 次 |",
        f"| **B 高压性能与耗时（按A封顶）** | B1性能 `{bd.get('B1_perf5', 0):.2f}/5`（原始 `{bd.get('B1_raw', 0):.2f}`）+ B2耗时 `{bd.get('B2_time10', 0):.2f}/10`（原始 `{bd.get('B2_raw', 0):.2f}`） | **{scores.get('B_efficiency', 0):.2f}** | 15.00 | 封顶乘数 `{bd.get('cap_factor', 0):.3f}`；首屏 `{bd.get('first_paint_ms')}`ms / 320卡搜索P95 `{bd.get('search_p95_ms')}`ms / 滚动帧P95 `{bd.get('scroll_frame_p95_ms')}`ms / 空转rAF={bd.get('has_idle_raf_loop')} |",
        f"| **C 严苛物理可用性底线** | C1几何防截断 `{cd.get('C1_responsive9', 0):.2f}/9` + C2双向焦点锁 `{cd.get('C2_keyboard8', 0):.2f}/8` + C3混沌容错与AA木桶对比度 `{cd.get('C3_resilience_contrast8', 0):.2f}/8` | **{scores.get('C_quality', 0):.2f}** | 25.00 | 最大横向溢出 `{cd.get('max_overflow_px')}`px / 硬截断控件 `{cd.get('clipped_controls_count')}` 个；最低对比度 浅 `{cd.get('min_contrast_light')}` / 深 `{cd.get('min_contrast_dark')}` |",
        "",
    ]

    if scores.get("not_implemented"):
        lines += [
            f"> ⚠️ **终止说明**：{report.get('reason', '未完成初始骨架开发')}，客观层计 0 分。",
            "",
        ]
        return "\n".join(lines)

    w1 = report.get("wave1") or {}
    w2 = report.get("wave2") or {}
    w3 = report.get("wave3") or {}
    groups = [
        ("第一波 · A1 只读异步后端校验与首屏装载完备度（满分 2.0）", w1.get("a1_checks") or []),
        ("第一波 · A2 连环链：乱序检索防竞态 → 双向同步 → 原生 SVG 多维对比图零重叠重绘（满分 9.5）", w1.get("a2_checks") or []),
        ("第一波 · A3 连环链：异步报价防竞态 → 无剧透档期冲突消解 → 跨模块 Undo/Redo → 并发防重与 503 恢复（满分 12.0）", w1.get("a3_checks") or []),
        ("第一波 · A4 连环链：异步双深链直达 → 快速连切防竞态与多步历史栈 → 防遮挡目录定位（满分 6.5）", w1.get("a4_checks") or []),
        ("第二波 · C1 四档视口零溢出、反 overflow:hidden 硬截断与动态遮挡测量（满分 9.0）", w2.get("c1_checks") or []),
        ("第二波 · C3 多态脏缓存/禁存储容错与陡峭 WCAG AA 9 角色木桶对比度（满分 8.0）", w2.get("c3_checks") or []),
        ("第三波 · C2 六区可达、定制焦点环、对比弹层双向焦点锁与详情返回归位（满分 8.0）", w3.get("c2_checks") or []),
    ]

    lines.append("## 二、三波剧本逐项物理测量与连环门控明细")
    lines.append("")
    for title, checks in groups:
        lines.append(f"### {title}")
        lines.append("")
        lines.append("| 编号 | 检查项 | 权重 | 计分得分率 | 状态 | 物理实测与连坐定位说明 |")
        lines.append("| --- | --- | ---: | ---: | :---: | --- |")
        for c in checks:
            mark = "✓" if c.get("passed") and not c.get("gated_by") else "✗"
            gated_by = c.get("gated_by")
            raw_r = c.get("raw_score_ratio", c.get("score_ratio", 0.0))
            gate_prefix = (
                f"**[受上游 `{gated_by}` 未及格连坐×0.20，原始 `{raw_r*100:.1f}%`]** "
                if gated_by
                else ""
            )
            lines.append(
                f"| `{c['id']}` | {c['name']} | {c['weight']:.2f} | `{c['score_ratio']*100:.1f}%` | {mark} | {gate_prefix}{c['detail']} |"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="对单个运行目录执行三波无头浏览器客观评测")
    ap.add_argument("run_dir", help="运行目录路径，如 runs/Demo")
    ap.add_argument("model", nargs="?", default=None, help="模型名称标识（缺省从目录名推导）")
    ap.add_argument("--no-record", action="store_true", help="兼容保留参数：仅在运行目录输出评测明细，不改写总榜")
    args = ap.parse_args()

    rdir = Path(args.run_dir).resolve()
    ws_dir = rdir / "workspace"
    if not rdir.is_dir() or not ws_dir.is_dir():
        print(f"评测失败：找不到运行目录或 workspace/：{rdir}")
        return 1

    proto_path = rdir / "protocol.json"
    proto = json.loads(proto_path.read_text(encoding="utf-8")) if proto_path.exists() else {}
    timing = proto.get("timing") or {}
    model_id = canonical_model_id(args.model or proto.get("model_id") or rdir.name)

    cfg = metrics.load_config()
    t0 = time.perf_counter()
    report, trace = browser_waves.evaluate_workspace(ws_dir, cfg=cfg)
    eval_sec = round(time.perf_counter() - t0, 2)

    scores = metrics.compute_scores(report, timing=timing, cfg=cfg)
    scores["run_name"] = rdir.name
    scores["model_id"] = model_id
    scores["endToEndSeconds"] = timing.get("endToEndSeconds")
    scores["eval_duration_sec"] = eval_sec

    (rdir / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (rdir / "评分.json").write_text(json.dumps(scores, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (rdir / "wave_trace.jsonl").open("w", encoding="utf-8", newline="\n") as tf:
        for ev in trace:
            tf.write(json.dumps(ev, ensure_ascii=False, separators=(",", ":")) + "\n")

    audit_md = _render_audit_markdown(rdir.name, model_id, scores, report, eval_sec)
    (rdir / "audit_report.md").write_text(audit_md, encoding="utf-8")

    print(
        f"[score_run] {rdir.name} ({model_id}): "
        f"A={scores['A_outcome']:.2f}/30  B={scores['B_efficiency']:.2f}/15  "
        f"C={scores['C_quality']:.2f}/25  => 客观总分={scores['total_objective_70']:.2f}/70  (耗时 {eval_sec:.1f}s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
