#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键出榜快捷入口：对 leaderboard/blind-maps/ 下发现的全部已盲评模型运行 src/scoring/finalize.py。

用法：
    python leaderboard/finalize.py                 # 全部模型一次性拉起浏览器压测并出榜
    python leaderboard/finalize.py --dry-run       # 只打印成绩表，不改写 scores.md 与 verdicts/
    python leaderboard/finalize.py --model Demo    # 只汇总指定模型
    其他参数（--allow-partial / --d-aggregate median 等）原样转发。
"""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

args = [
    sys.executable,
    str(ROOT / "src" / "scoring" / "finalize.py"),
    "--review-log",
    str(ROOT / "leaderboard" / "reviews.jsonl"),
    "--d-aggregate",
    "mean",
    "--min-judges",
    "1",
    *sys.argv[1:],
]
raise SystemExit(subprocess.run(args, cwd=str(ROOT)).returncode)
