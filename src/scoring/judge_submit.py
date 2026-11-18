#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""评委提交单条盲评打分（judge_submit.py）：只追加到中心评审日志，绝不回显其他评委分数。"""
from __future__ import annotations

from pathlib import Path
import argparse
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
    ap = argparse.ArgumentParser(description="提交 D 层盲评分数至中心评审日志（只写不读）")
    ap.add_argument("--pack-dir", required=True, help="评委拿到的 leaderboard/blind/<pack_id>/ 目录")
    ap.add_argument("--case-id", required=True, help="包内案例编号，如 case-01")
    ap.add_argument("--judge-id", required=True, help="评委唯一标识（同一评委对不同包/案例保持一致）")
    ap.add_argument("--judge-model", required=True, help="评委模型或姓名标识，如 claude-opus-4")
    ap.add_argument("--D1", type=float, required=True, help="D1 寻找、对比与阅读心流体验（0–11 分）")
    ap.add_argument("--D2", type=float, required=True, help="D2 容错引导与微交互体贴度（0–10 分）")
    ap.add_argument("--D3", type=float, required=True, help="D3 状态组织、可维护性与交付诚实度（0–9 分）")
    ap.add_argument(
        "--evidence",
        required=True,
        help="必须引用连环画截图编号（如 [S01] [S06]）及源码文件行号/DECISIONS 核验结论",
    )
    ap.add_argument("--note", required=True, help="必须指出该作品的最强反证/最大交互或工程短板")
    ap.add_argument("--review-log", default=str(review_log.DEFAULT_LOG), help="中心评审日志路径")
    args = ap.parse_args()

    pack_dir = Path(args.pack_dir).resolve()
    manifest_path = pack_dir / "pack.json"
    if not manifest_path.exists():
        print(f"提交失败：找不到盲评包清单 {manifest_path}")
        return 1
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"提交失败：盲评包清单读取异常：{e}")
        return 1

    pack_id = manifest.get("pack_id")
    case_ids = [c.get("case_id") for c in (manifest.get("cases") or []) if c.get("case_id")]
    if not pack_id or args.case_id not in case_ids:
        print(f"提交失败：pack_id 或 case_id 无效（pack={pack_id}, case={args.case_id}）")
        print("当前盲评包可用 case：" + ", ".join(case_ids))
        return 1

    evidence_str = args.evidence.strip()
    note_str = args.note.strip()
    if len(evidence_str) < 8:
        print("提交失败：--evidence 过短，请明确引用连环画截图编号（如 [S01]）与源码位置证据。")
        return 1
    if len(note_str) < 4:
        print("提交失败：--note 不能为空，请写明该作品的最强反证或关键交互短板。")
        return 1

    rec = {
        "schema_version": review_log.SCHEMA_VERSION,
        "judge_id": args.judge_id.strip(),
        "judge_model": args.judge_model.strip(),
        "pack_id": pack_id,
        "case_id": args.case_id,
        "D1": args.D1,
        "D2": args.D2,
        "D3": args.D3,
        "evidence": evidence_str,
        "note": note_str,
    }
    try:
        saved = review_log.append_review(args.review_log, rec, reject_duplicate=True)
    except review_log.DuplicateReviewError as e:
        print("提交失败：" + str(e))
        return 2
    except review_log.ReviewLogError as e:
        print("提交失败：" + str(e))
        return 1

    print("盲评评分提交成功。")
    print(f"  review_id={saved['review_id']}  pack_id={saved['pack_id']}  case_id={saved['case_id']}  total_D={saved['total']:.2f}/30")
    print("  （本次提交仅原子追加，未读取或回显其他任何评委记录。）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
