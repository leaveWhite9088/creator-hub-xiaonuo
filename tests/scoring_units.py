#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""计分插值、WCAG 木桶对比度、空闲 rAF 惩罚、A 得分率封顶、评审防重与隔离脱敏单元测试（tests/scoring_units.py）。"""
from __future__ import annotations

from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "scoring"))
sys.path.insert(0, str(ROOT / "tools"))

import isolation_audit  # noqa: E402
import metrics  # noqa: E402
from model_identity import canonical_model_id, matches_batch_run, sanitize_run_name  # noqa: E402
import review_log  # noqa: E402


class TestScoringAndInfra(unittest.TestCase):
    def test_wcag_and_barrel_contrast(self):
        self.assertEqual(metrics.wcag_contrast_ratio([0, 0, 0], [255, 255, 255]), 21.0)
        self.assertEqual(metrics.wcag_contrast_ratio([120, 120, 120], [120, 120, 120]), 1.0)
        low_dark_cr = metrics.wcag_contrast_ratio([92, 92, 92], [24, 24, 24])
        self.assertLess(low_dark_cr, 3.0)
        high_dark_cr = metrics.wcag_contrast_ratio([241, 245, 249], [14, 18, 24])
        self.assertGreater(high_dark_cr, 13.0)

        # 验证木桶对比度：若 8 个角色满分 1.0，但 1 个角色（如激活态按钮白字浅黄底）为 0.0，得分被短板显著拉低
        skewed = [1.0] * 8 + [0.0]
        barrel = metrics.barrel_score_ratio(skewed, min_weight=0.55)
        self.assertLess(barrel, 0.45)
        self.assertAlmostEqual(metrics.barrel_score_ratio([1.0] * 9, min_weight=0.55), 1.0, places=4)

    def test_b_capped_by_a_halflife_and_idle_raf_penalty(self):
        cfg = metrics.load_config()
        half_a_report = {
            "page_loadable": True,
            "not_implemented": False,
            "wave1": {
                "a1_checks": [{"id": "a1", "score_ratio": 0.5, "weight": 1.0}],
                "a2_checks": [{"id": "a2", "score_ratio": 0.5, "weight": 1.0}],
                "a3_checks": [{"id": "a3", "score_ratio": 0.5, "weight": 1.0}],
                "a4_checks": [{"id": "a4", "score_ratio": 0.5, "weight": 1.0}],
            },
            "wave2": {
                "c1_checks": [{"id": "c1", "score_ratio": 1.0, "weight": 1.0}],
                "c3_checks": [{"id": "c3", "score_ratio": 1.0, "weight": 1.0}],
            },
            "wave3": {
                "c2_checks": [{"id": "c2", "score_ratio": 1.0, "weight": 1.0}],
                "performance": {
                    "first_paint_ms": 80.0,
                    "search_p95_ms": 10.0,
                    "scroll_frame_p95_ms": 16.0,
                    "has_idle_raf_loop": False,
                },
            },
        }
        full_a_report = json.loads(json.dumps(half_a_report))
        for k in ("a1_checks", "a2_checks", "a3_checks", "a4_checks"):
            full_a_report["wave1"][k][0]["score_ratio"] = 1.0

        sc = metrics.compute_scores(half_a_report, timing={"endToEndSeconds": 300.0}, cfg=cfg)
        self.assertEqual(sc["A_outcome"], 15.0)
        self.assertAlmostEqual(sc["B_detail"]["cap_factor"], 0.5, places=3)
        self.assertEqual(sc["B_detail"]["B1_perf5"], 2.5)
        self.assertEqual(sc["B_detail"]["B2_time10"], 5.0)
        self.assertEqual(sc["B_efficiency"], 7.5)

        # 验证 v4.0 满分 A 时，超过 18 分钟免费窗一个半衰期（18 + 24 = 42 分钟 = 2520 秒），B2 衰减至 5.0 分
        sc_half = metrics.compute_scores(full_a_report, timing={"endToEndSeconds": 2520.0}, cfg=cfg)
        self.assertEqual(sc_half["A_outcome"], 30.0)
        self.assertEqual(sc_half["B_detail"]["B2_time10"], 5.0)
        self.assertEqual(sc_half["B_detail"]["B1_perf5"], 5.0)

        # 验证空闲无限 requestAnimationFrame 空转循环惩罚（乘 0.60 => 5.0 * 0.60 = 3.0）
        raf_bad = json.loads(json.dumps(full_a_report))
        raf_bad["wave3"]["performance"]["has_idle_raf_loop"] = True
        sc_raf = metrics.compute_scores(raf_bad, timing={"endToEndSeconds": 300.0}, cfg=cfg)
        self.assertEqual(sc_raf["B_detail"]["B1_perf5"], 3.0)

    def test_sequential_chain_gates(self):
        chain = [
            {"id": "A3.1", "score_ratio": 1.0, "weight": 2.4},
            {"id": "A3.2", "score_ratio": 0.4, "weight": 3.0},
            {"id": "A3.3", "score_ratio": 1.0, "weight": 3.1},
            {"id": "A3.4", "score_ratio": 0.8, "weight": 2.5},
        ]
        gated, brk = metrics.apply_chain_gates(chain, pass_threshold=0.55, broken_mult=0.20, enabled=True)
        self.assertEqual(brk, "A3.2")
        self.assertAlmostEqual(gated[0]["score_ratio"], 1.0, places=4)
        self.assertAlmostEqual(gated[1]["score_ratio"], 0.4, places=4)
        self.assertAlmostEqual(gated[2]["score_ratio"], 0.2, places=4)
        self.assertEqual(gated[2]["gated_by"], "A3.2")
        self.assertAlmostEqual(gated[3]["score_ratio"], 0.16, places=4)
        # 验证幂等性：重复应用不会二次连乘 0.20
        gated_again, brk2 = metrics.apply_chain_gates(gated, pass_threshold=0.55, broken_mult=0.20, enabled=True)
        self.assertEqual(brk2, "A3.2")
        self.assertAlmostEqual(gated_again[2]["score_ratio"], 0.2, places=4)

    def test_unimplemented_zero(self):
        sc = metrics.compute_scores({"page_loadable": True, "not_implemented": True})
        self.assertTrue(sc["not_implemented"])
        self.assertEqual(sc["total_objective_70"], 0.0)

    def test_model_identity(self):
        self.assertEqual(canonical_model_id("DeepSeek-R1-s1"), "deepseek-r1")
        self.assertEqual(canonical_model_id("deepseek-r1"), "deepseek-r1")
        self.assertEqual(canonical_model_id("gemini-4-carbon（Max）-run2"), "gemini-4-carbon（max）")
        self.assertTrue(matches_batch_run("demo-s1", "demo-s1"))
        with self.assertRaises(ValueError):
            sanitize_run_name("../escape")

    def test_review_log_and_isolation_leak_detection(self):
        tmp = Path(tempfile.mkdtemp(prefix="ch_unit_"))
        try:
            log_p = tmp / "reviews.jsonl"
            r1 = review_log.append_review(
                log_p,
                {
                    "judge_id": "j1",
                    "judge_model": "opus",
                    "pack_id": "p123",
                    "case_id": "case-01",
                    "D1": 9.0,
                    "D2": 8.0,
                    "D3": 7.5,
                    "evidence": "[S01] code/app.js:10",
                    "note": "minor mobile toc issue",
                },
            )
            self.assertEqual(r1["total"], 24.5)
            with self.assertRaises(review_log.DuplicateReviewError):
                review_log.append_review(
                    log_p,
                    {
                        "judge_id": "j1",
                        "judge_model": "opus",
                        "pack_id": "p123",
                        "case_id": "case-01",
                        "D1": 10.0,
                        "D2": 9.0,
                        "D3": 8.0,
                    },
                )
            review_log.append_review(
                log_p,
                {
                    "judge_id": "j2",
                    "judge_model": "gemini",
                    "pack_id": "p123",
                    "case_id": "case-01",
                    "D1": 7.0,
                    "D2": 6.0,
                    "D3": 6.5,
                },
            )
            agg = review_log.aggregate_reviews(review_log.read_reviews(log_p), mode="mean")
            self.assertEqual(len(agg), 1)
            self.assertEqual(agg[0]["D1"], 8.0)
            self.assertEqual(agg[0]["D2"], 7.0)
            self.assertEqual(agg[0]["D3"], 7.0)
            self.assertEqual(agg[0]["D"], 22.0)

            blind_dir = tmp / "blind"
            bmaps_dir = tmp / "blind-maps"
            pdir = blind_dir / "pack99"
            (pdir / "case-01").mkdir(parents=True)
            bmaps_dir.mkdir(parents=True)
            (bmaps_dir / "secretmodel.pack99.blind-map.json").write_text(
                json.dumps({"model": "SecretModelX", "model_id": "secretmodelx", "pack_id": "pack99", "cases": {"case-01": {"run": "SecretModelX-s1"}}}),
                encoding="utf-8",
            )
            (pdir / "case-01" / "DECISIONS.md").write_text("由 SecretModelX 生成，total_objective_70=68", encoding="utf-8")
            (pdir / "case-01" / "code").mkdir(parents=True, exist_ok=True)
            (pdir / "case-01" / "code" / "mock_backend.js").write_text("// tampered mock backend", encoding="utf-8")
            rep = isolation_audit.audit_isolation(
                runs_dir=tmp / "runs",
                blind_dir=blind_dir,
                blind_maps_dir=bmaps_dir,
                draft_dir=tmp / "draft",
            )
            self.assertFalse(rep["ok"])
            joined = "\n".join(rep["issues"])
            self.assertIn("缺少完整《交互状态连环画》", joined)
            self.assertIn("泄露模型或运行身份标识", joined)
            self.assertIn("total_objective_70", joined)
            self.assertIn("mock_backend.js 缺失或与官方只读原件不一致", joined)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
