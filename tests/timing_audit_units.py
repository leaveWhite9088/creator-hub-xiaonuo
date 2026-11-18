#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B2 端到端墙钟时间重叠审计单元测试（tests/timing_audit_units.py）。"""
from __future__ import annotations

from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import timing_audit  # noqa: E402


def _write_proto(runs_dir: Path, name: str, model_id: str, t0: str, t1: str):
    d = runs_dir / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "protocol.json").write_text(
        json.dumps(
            {
                "run_name": name,
                "model_id": model_id,
                "timing": {"t0_iso": t0, "end_iso": t1},
            }
        ),
        encoding="utf-8",
    )


class TestTimingAudit(unittest.TestCase):
    def test_serial_and_cross_model_ok_but_same_model_overlap_flagged(self):
        tmp = Path(tempfile.mkdtemp(prefix="ch_timing_"))
        try:
            # 同模型串行两批 + 另一模型时间重叠（不同模型并行允许）
            _write_proto(tmp, "alpha-s1", "alpha", "2026-11-14T10:00:00+08:00", "2026-11-14T10:15:00+08:00")
            _write_proto(tmp, "alpha-s2", "alpha", "2026-11-14T10:16:00+08:00", "2026-11-14T10:30:00+08:00")
            _write_proto(tmp, "beta-s1", "beta", "2026-11-14T10:05:00+08:00", "2026-11-14T10:20:00+08:00")

            rep_ok = timing_audit.build_report(timing_audit.collect(tmp))
            self.assertTrue(rep_ok["ok"])
            self.assertEqual(rep_ok["overlapRuns"], 0)

            # 加入与 alpha-s1 时间交叉的 alpha-s3
            _write_proto(tmp, "alpha-s3", "alpha", "2026-11-14T10:10:00+08:00", "2026-11-14T10:25:00+08:00")
            rep_bad = timing_audit.build_report(timing_audit.collect(tmp))
            self.assertFalse(rep_bad["ok"])
            self.assertGreaterEqual(rep_bad["overlapRuns"], 2)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
