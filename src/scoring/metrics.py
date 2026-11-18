# -*- coding: utf-8 -*-
"""客观层确定性计分模型 v4.0（A30 + B15 + C25 = 70 分）：异步竞态与连环组合过关制、连续插值、短板木桶对比度与封顶计算。

核心原则：
  1. 零大模型参与：全部得分由无头浏览器实测物理指标与确定性断言直接算出；
  2. 连环组合压测过关制（Chained Gauntlets）：A2 / A3 / A4 每条业务链按步骤顺序考核，一旦上游步骤得分率低于及格门限（0.55），后续所有步骤均乘以连坐衰减乘数（0.20）；
  3. 单一配置源：所有分值上限、门控阈值、连续插值节点、对比度木桶权重与时间半衰期均从 configs/benchmark.json 读取；
  4. 防躺平封顶：B1 与 B2 均以 A 层得分率作为上限乘数封顶，并重罚空闲无限 rAF 空转循环。
"""
from __future__ import annotations

from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CONFIG_PATH = ROOT / "configs" / "benchmark.json"


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def interp_nodes(value: float, nodes: list[list[float]]) -> float:
    """在按横坐标递增的 [x, level_0_to_10] 关键节点之间执行连续线性插值。"""
    if not nodes:
        return 0.0
    pts = sorted((float(x), float(y)) for x, y in nodes)
    val = float(value)
    if val <= pts[0][0]:
        return pts[0][1]
    if val >= pts[-1][0]:
        return pts[-1][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= val <= x1:
            if x1 == x0:
                return y1
            ratio = (val - x0) / (x1 - x0)
            return y0 + ratio * (y1 - y0)
    return pts[-1][1]


def srgb_channel_to_linear(c255: float) -> float:
    """按 WCAG 2.1 标准将 0..255 sRGB 通道转换为线性亮度分量。"""
    s = max(0.0, min(255.0, float(c255))) / 255.0
    if s <= 0.04045:
        return s / 12.92
    return ((s + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: tuple[float, float, float] | list[float]) -> float:
    """计算 RGB 颜色的 WCAG 2.1 相对亮度 L ∈ [0, 1]。"""
    r, g, b = rgb[0], rgb[1], rgb[2]
    return (
        0.2126 * srgb_channel_to_linear(r)
        + 0.7152 * srgb_channel_to_linear(g)
        + 0.0722 * srgb_channel_to_linear(b)
    )


def wcag_contrast_ratio(fg_rgb: tuple[float, float, float] | list[float], bg_rgb: tuple[float, float, float] | list[float]) -> float:
    """按 WCAG 2.1 标准公式 (L_lighter + 0.05) / (L_darker + 0.05) 计算精确对比度（1.0 ~ 21.0）。"""
    l1 = relative_luminance(fg_rgb)
    l2 = relative_luminance(bg_rgb)
    hi, lo = (l1, l2) if l1 >= l2 else (l2, l1)
    return round((hi + 0.05) / (lo + 0.05), 2)


def barrel_score_ratio(ratios: list[float], min_weight: float = 0.65) -> float:
    """短板木桶聚合：结合均值与最低单点得分率，防止高对比正文掩盖局部不可读控件。"""
    if not ratios:
        return 0.0
    clamped = [max(0.0, min(1.0, float(x))) for x in ratios]
    w_min = max(0.0, min(1.0, float(min_weight)))
    mean_v = sum(clamped) / len(clamped)
    min_v = min(clamped)
    return (1.0 - w_min) * mean_v + w_min * min_v


def apply_chain_gates(
    checks: list[dict],
    pass_threshold: float = 0.55,
    broken_mult: float = 0.20,
    enabled: bool = True,
) -> tuple[list[dict], str | None]:
    """对单条连环组合压测链按顺序施加门控（幂等，保留 raw_score_ratio 与 gated_by）。"""
    out: list[dict] = []
    broken_by: str | None = None
    thr = max(0.0, min(1.0, float(pass_threshold)))
    mult = max(0.0, min(1.0, float(broken_mult)))

    for idx, orig in enumerate(checks or []):
        c = dict(orig)
        if "raw_score_ratio" in c and c["raw_score_ratio"] is not None:
            raw_r = max(0.0, min(1.0, float(c["raw_score_ratio"])))
        elif "score_ratio" in c and c["score_ratio"] is not None:
            raw_r = max(0.0, min(1.0, float(c["score_ratio"])))
        else:
            raw_r = 1.0 if c.get("passed") else 0.0

        c["raw_score_ratio"] = round(raw_r, 4)
        if enabled and broken_by is not None:
            eff_r = round(raw_r * mult, 4)
            c["score_ratio"] = eff_r
            c["gated_by"] = broken_by
        else:
            c["score_ratio"] = round(raw_r, 4)
            c["gated_by"] = None
            if enabled and raw_r < thr:
                broken_by = str(c.get("id") or f"step_{idx + 1}")
        out.append(c)

    return out, broken_by


def weighted_ratio(checks: list[dict]) -> tuple[float, float, float]:
    """对带 weight 与 score_ratio（或布尔 passed）的检查项列表计算加权得分率 (earned, total, ratio)。"""
    if not checks:
        return 0.0, 0.0, 0.0
    total_w = sum(float(c.get("weight", 1.0)) for c in checks)
    if total_w <= 0:
        return 0.0, 0.0, 0.0
    earned_w = 0.0
    for c in checks:
        w = float(c.get("weight", 1.0))
        if "score_ratio" in c and c["score_ratio"] is not None:
            r = max(0.0, min(1.0, float(c["score_ratio"])))
        else:
            r = 1.0 if c.get("passed") else 0.0
        earned_w += w * r
    return earned_w, total_w, earned_w / total_w


def compute_scores(run_report: dict, timing: dict | None = None, cfg: dict | None = None) -> dict:
    """由三波无头浏览器实测报告（run_report）与计时协议（timing）计算定稿客观分。"""
    cfg = cfg or load_config()
    sc_cfg = cfg["scoring"]
    a_cfg = sc_cfg["A"]
    b_cfg = sc_cfg["B"]
    c_cfg = sc_cfg["C"]
    cg_cfg = sc_cfg.get("chain_gate") or {}
    cg_enabled = bool(cg_cfg.get("enabled", True))
    cg_thr = float(cg_cfg.get("pass_threshold", 0.55))
    cg_mult = float(cg_cfg.get("broken_downstream_multiplier", 0.20))

    not_impl = bool(run_report.get("not_implemented")) or not bool(run_report.get("page_loadable"))
    w1 = run_report.get("wave1") or {}
    w2 = run_report.get("wave2") or {}
    w3 = run_report.get("wave3") or {}
    perf = w3.get("performance") or {}

    if not_impl:
        return {
            "version": cfg.get("version", "xiaonuo-v4.0"),
            "not_implemented": True,
            "page_loadable": bool(run_report.get("page_loadable")),
            "A_outcome": 0.0,
            "A_detail": {
                "A1": 0.0,
                "A2": 0.0,
                "A3": 0.0,
                "A4": 0.0,
                "A1_content_offline": 0.0,
                "A2_search_filter_svg_compare": 0.0,
                "A3_planner_conflict_undo_persist": 0.0,
                "A4_deeplink_history_toc": 0.0,
                "A1_level": 0.0,
                "A2_level": 0.0,
                "A3_level": 0.0,
                "A4_level": 0.0,
                "chain_breaks": {"A2": "A2.1", "A3": "A3.1", "A4": "A4.1"},
                "external_requests": w1.get("external_requests_count", 0),
            },
            "B_efficiency": 0.0,
            "B_detail": {
                "B1_perf5": 0.0,
                "B2_time10": 0.0,
                "B1_raw": 0.0,
                "B2_raw": 0.0,
                "cap_factor": 0.0,
                "first_paint_ms": None,
                "search_p95_ms": None,
                "scroll_frame_p95_ms": None,
                "has_idle_raf_loop": False,
            },
            "C_quality": 0.0,
            "C_detail": {
                "C1_responsive9": 0.0,
                "C2_keyboard8": 0.0,
                "C3_resilience_contrast8": 0.0,
                "max_overflow_px": None,
                "clipped_controls_count": None,
                "min_contrast_light": None,
                "min_contrast_dark": None,
            },
            "C_levels": {"C1": 0.0, "C2": 0.0, "C3": 0.0},
            "total_objective_70": 0.0,
        }

    # -------------------- A 深层耦合工作台与连环状态过关制（30 分） --------------------
    a1_checks = list(w1.get("a1_checks") or [])
    a2_gated, brk_a2 = apply_chain_gates(w1.get("a2_checks") or [], cg_thr, cg_mult, cg_enabled)
    a3_gated, brk_a3 = apply_chain_gates(w1.get("a3_checks") or [], cg_thr, cg_mult, cg_enabled)
    a4_gated, brk_a4 = apply_chain_gates(w1.get("a4_checks") or [], cg_thr, cg_mult, cg_enabled)

    if "a2_checks" in w1:
        w1["a2_checks"] = a2_gated
    if "a3_checks" in w1:
        w1["a3_checks"] = a3_gated
    if "a4_checks" in w1:
        w1["a4_checks"] = a4_gated

    _, _, r_a1 = weighted_ratio(a1_checks)
    _, _, r_a2 = weighted_ratio(a2_gated)
    _, _, r_a3 = weighted_ratio(a3_gated)
    _, _, r_a4 = weighted_ratio(a4_gated)

    a1_max = float(a_cfg["a1_content_offline_max"])
    a2_max = float(a_cfg["a2_search_filter_compare_max"])
    a3_max = float(a_cfg["a3_estimator_persist_form_max"])
    a4_max = float(a_cfg["a4_deeplink_history_toc_max"])

    a1_score = round(a1_max * r_a1, 2)
    a2_score = round(a2_max * r_a2, 2)
    a3_score = round(a3_max * r_a3, 2)
    a4_score = round(a4_max * r_a4, 2)
    A_total = round(min(float(a_cfg["max"]), a1_score + a2_score + a3_score + a4_score), 2)

    # -------------------- C 严苛物理可用性底线（25 分） --------------------
    if r_a1 < 0.40:
        r_c1 = r_c2 = r_c3 = 0.0
    else:
        _, _, r_c1 = weighted_ratio(w2.get("c1_checks") or [])
        _, _, r_c3 = weighted_ratio(w2.get("c3_checks") or [])
        _, _, r_c2 = weighted_ratio(w3.get("c2_checks") or [])

    c1_max = float(c_cfg["c1_responsive_geometry_max"])
    c2_max = float(c_cfg["c2_keyboard_a11y_max"])
    c3_max = float(c_cfg["c3_resilience_contrast_max"])

    c1_score = round(c1_max * r_c1, 2)
    c2_score = round(c2_max * r_c2, 2)
    c3_score = round(c3_max * r_c3, 2)
    C_total = round(min(float(c_cfg["max"]), c1_score + c2_score + c3_score), 2)

    # -------------------- B 高压性能与开发效率（15 分，以 A 层得分率封顶） --------------------
    a_max = float(a_cfg["max"])
    cap_anchor = a_max * float(b_cfg.get("cap_a_ratio", 1.0))
    cap_factor = min(1.0, A_total / cap_anchor) if cap_anchor > 0 else 1.0

    fp_ms = float(perf.get("first_paint_ms", 2500.0))
    sr_ms = float(perf.get("search_p95_ms", 350.0))
    sc_ms = float(perf.get("scroll_frame_p95_ms", 150.0))
    idle_raf = bool(perf.get("has_idle_raf_loop", False))

    lvl_fp = interp_nodes(fp_ms, b_cfg["first_paint_ms_nodes"])
    lvl_sr = interp_nodes(sr_ms, b_cfg["search_latency_ms_nodes"])
    lvl_sc = interp_nodes(sc_ms, b_cfg["scroll_frame_p95_ms_nodes"])

    bw = b_cfg["b1_weights"]
    lvl_b1 = (
        float(bw["first_paint"]) * lvl_fp
        + float(bw["stress_search_latency"]) * lvl_sr
        + float(bw["stress_scroll_fps"]) * lvl_sc
    )
    if idle_raf:
        lvl_b1 *= max(0.0, 1.0 - float(b_cfg.get("idle_raf_penalty_ratio", 0.40)))
    lvl_b1 = max(0.0, min(10.0, lvl_b1))

    b1_max = float(b_cfg["b1_max"])
    b1_raw = b1_max * (lvl_b1 / 10.0)
    b1_score = round(min(b1_raw, b1_max * cap_factor), 2)

    timing = timing or {}
    e2e_sec = timing.get("endToEndSeconds")
    b2_max = float(b_cfg["b2_max"])
    if isinstance(e2e_sec, (int, float)) and e2e_sec >= 0:
        e2e_min = float(e2e_sec) / 60.0
        free_min = float(b_cfg["b2_free_min"])
        halflife = float(b_cfg["b2_halflife_min"])
        over_min = max(0.0, e2e_min - free_min)
        b2_raw = b2_max * (0.5 ** (over_min / halflife))
    else:
        b2_raw = 0.0
    b2_score = round(min(b2_raw, b2_max * cap_factor), 2)
    B_total = round(b1_score + b2_score, 2)

    return {
        "version": cfg.get("version", "xiaonuo-v4.0"),
        "not_implemented": False,
        "page_loadable": True,
        "A_outcome": A_total,
        "A_detail": {
            "A1": a1_score,
            "A2": a2_score,
            "A3": a3_score,
            "A4": a4_score,
            "A1_content_offline": a1_score,
            "A2_search_filter_svg_compare": a2_score,
            "A3_planner_conflict_undo_persist": a3_score,
            "A4_deeplink_history_toc": a4_score,
            "A1_level": round(r_a1 * 10.0, 2),
            "A2_level": round(r_a2 * 10.0, 2),
            "A3_level": round(r_a3 * 10.0, 2),
            "A4_level": round(r_a4 * 10.0, 2),
            "chain_breaks": {
                "A2": brk_a2,
                "A3": brk_a3,
                "A4": brk_a4,
            },
            "external_requests": int(w1.get("external_requests_count", 0)),
        },
        "B_efficiency": B_total,
        "B_detail": {
            "B1_perf5": b1_score,
            "B2_time10": b2_score,
            "B1_raw": round(b1_raw, 2),
            "B2_raw": round(b2_raw, 2),
            "B1_level": round(lvl_b1, 2),
            "cap_factor": round(cap_factor, 4),
            "first_paint_ms": round(fp_ms, 1),
            "search_p95_ms": round(sr_ms, 2),
            "scroll_frame_p95_ms": round(sc_ms, 2),
            "has_idle_raf_loop": idle_raf,
        },
        "C_quality": C_total,
        "C_detail": {
            "C1_responsive9": c1_score,
            "C2_keyboard8": c2_score,
            "C3_resilience_contrast8": c3_score,
            "max_overflow_px": w2.get("max_overflow_px"),
            "clipped_controls_count": w2.get("clipped_controls_count"),
            "min_contrast_light": w2.get("min_contrast_light"),
            "min_contrast_dark": w2.get("min_contrast_dark"),
        },
        "C_levels": {
            "C1": round(r_c1 * 10.0, 2),
            "C2": round(r_c2 * 10.0, 2),
            "C3": round(r_c3 * 10.0, 2),
        },
        "total_objective_70": round(A_total + B_total + C_total, 2),
    }
