#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""角色隔离、代码冻结与盲评包零身份/零分数泄露审计工具（tools/isolation_audit.py）。

核查五项核心纪律：
1. 仓库核心评分与浏览器剧本哈希是否与开局 protocol.json 记录的 env_commit 一致；
2. 选手打包冻结 t1 后的沙盒源码哈希是否与 code_sha256 一致（防打完卡后补改代码）；
3. 临时草稿目录 draft/ 是否已按规定清空；
4. 匿名盲评包 leaderboard/blind/<pack_id>/ 是否彻底脱敏（零模型真名泄露、零客观分数泄露）；
5. 盲评包内每个案例是否完整生成了《交互状态连环画》（STORYBOARD.md 与 >=8 张 PNG 截图）。
"""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "src" / "scoring"))

from start_run import (  # noqa: E402
    compute_env_commit,
    compute_workspace_sha256,
    verify_file_matches_mock_backend,
)

FORBIDDEN_BLIND_FILES = {
    "评分.json",
    "result.json",
    "protocol.json",
    "wave_trace.jsonl",
    "audit_report.md",
    "token_usage.json",
}
TEXT_SUFFIXES = {".md", ".json", ".html", ".htm", ".css", ".js", ".mjs", ".svg", ".txt", ".xml"}


def audit_isolation(
    runs_dir: Path | None = None,
    blind_dir: Path | None = None,
    blind_maps_dir: Path | None = None,
    draft_dir: Path | None = None,
) -> dict:
    runs_dir = (runs_dir or (ROOT / "runs")).resolve()
    blind_dir = (blind_dir or (ROOT / "leaderboard" / "blind")).resolve()
    blind_maps_dir = (blind_maps_dir or (ROOT / "leaderboard" / "blind-maps")).resolve()
    draft_dir = (draft_dir or (ROOT / "draft")).resolve()

    issues: list[str] = []
    current_env = compute_env_commit(ROOT)

    # 1. 检查 draft/ 是否清空
    if draft_dir.exists():
        leftovers = [str(p.relative_to(draft_dir)) for p in draft_dir.rglob("*") if p.is_file()]
        if leftovers:
            issues.append(f"draft/ 目录未清空，残留文件: {leftovers[:5]}")

    # 2. 检查每个 run 的环境承诺与 t1 代码冻结承诺
    checked_runs = 0
    if runs_dir.exists():
        for rdir in sorted(runs_dir.iterdir()):
            proto_path = rdir / "protocol.json"
            if not rdir.is_dir() or not proto_path.exists():
                continue
            checked_runs += 1
            proto = json.loads(proto_path.read_text(encoding="utf-8"))
            recorded_env = proto.get("env_commit")
            if recorded_env and recorded_env != current_env:
                issues.append(f"运行 {rdir.name} 的 env_commit 与当前仓库评测脚本哈希不一致（疑似中途修改评测脚本）")
            frozen_sha = proto.get("code_sha256")
            ws = rdir / "workspace"
            if ws.exists():
                if not verify_file_matches_mock_backend(ws / "mock_backend.js", ROOT):
                    issues.append(f"运行 {rdir.name} 的 workspace/mock_backend.js 缺失或遭到篡改（违反只读模拟后端契约）")
            if frozen_sha and ws.exists():
                actual_sha = compute_workspace_sha256(ws)
                if actual_sha != frozen_sha:
                    issues.append(f"运行 {rdir.name} 在打包冻结 t1 后沙盒代码发生变动（code_sha256 不匹配）")

    # 3. 检查匿名盲评包脱敏、零客观分泄露与连环画完备度
    checked_packs = 0
    map_by_pack: dict[str, dict] = {}
    if blind_maps_dir.exists():
        for mf in blind_maps_dir.glob("*.blind-map.json"):
            try:
                bm = json.loads(mf.read_text(encoding="utf-8"))
                if bm.get("pack_id"):
                    map_by_pack[bm["pack_id"]] = bm
            except Exception:
                continue

    if blind_dir.exists():
        for pdir in sorted(blind_dir.iterdir()):
            if not pdir.is_dir():
                continue
            checked_packs += 1
            pid = pdir.name
            bm = map_by_pack.get(pid) or {}
            secret_tokens = set()
            for tok in (bm.get("model"), bm.get("model_id")):
                if tok and len(str(tok).strip()) >= 3:
                    secret_tokens.add(str(tok).strip())
            for cmeta in (bm.get("cases") or {}).values():
                rname = (cmeta or {}).get("run")
                if rname and len(str(rname).strip()) >= 3:
                    secret_tokens.add(str(rname).strip())

            cfg_p = ROOT / "configs" / "benchmark.json"
            min_panels = 10
            if cfg_p.exists():
                try:
                    min_panels = max(10, int(json.loads(cfg_p.read_text(encoding="utf-8")).get("storyboard", {}).get("expected_panel_count", 12)))
                except Exception:
                    min_panels = 12
            for cdir in sorted(pdir.glob("case-*")):
                if not cdir.is_dir():
                    continue
                sb_md = cdir / "STORYBOARD.md"
                sb_dir = cdir / "storyboard"
                pngs = list(sb_dir.glob("*.png")) if sb_dir.is_dir() else []
                if not sb_md.exists() or len(pngs) < min_panels:
                    issues.append(
                        f"盲评包 {pid}/{cdir.name} 缺少完整《交互状态连环画》（STORYBOARD.md 存在={sb_md.exists()}，PNG 数={len(pngs)}/{min_panels}）"
                    )
                if not verify_file_matches_mock_backend(cdir / "code" / "mock_backend.js", ROOT):
                    issues.append(f"盲评包 {pid}/{cdir.name}/code/mock_backend.js 缺失或与官方只读原件不一致")

            for f in pdir.rglob("*"):
                if not f.is_file():
                    continue
                if f.name in FORBIDDEN_BLIND_FILES:
                    issues.append(f"盲评包 {pid} 混入违禁成绩/协议文件: {f.relative_to(pdir)}")
                    continue
                if f.suffix.lower() in TEXT_SUFFIXES:
                    try:
                        content = f.read_text(encoding="utf-8", errors="ignore")
                    except Exception:
                        continue
                    for tok in secret_tokens:
                        if re.search(re.escape(tok), content, flags=re.IGNORECASE):
                            issues.append(f"盲评包 {pid}/{f.relative_to(pdir)} 泄露模型或运行身份标识: {tok!r}")
                    for score_kw in ("A_outcome", "B_efficiency", "C_quality", "total_objective_70", "endToEndSeconds"):
                        if score_kw in content:
                            issues.append(f"盲评包 {pid}/{f.relative_to(pdir)} 疑似混入客观分或计时字段: {score_kw}")

    return {
        "ok": len(issues) == 0,
        "checked_runs": checked_runs,
        "checked_packs": checked_packs,
        "issues": issues,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="执行基准隔离、代码冻结、连环画完备度与盲评包脱敏审计")
    ap.add_argument("--runs-dir", default=None)
    ap.add_argument("--blind-dir", default=None)
    ap.add_argument("--blind-maps-dir", default=None)
    ap.add_argument("--draft-dir", default=None)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rep = audit_isolation(
        runs_dir=Path(args.runs_dir) if args.runs_dir else None,
        blind_dir=Path(args.blind_dir) if args.blind_dir else None,
        blind_maps_dir=Path(args.blind_maps_dir) if args.blind_maps_dir else None,
        draft_dir=Path(args.draft_dir) if args.draft_dir else None,
    )
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0 if rep["ok"] or not args.strict else 1

    print(f"隔离与脱敏审计：检查运行目录 {rep['checked_runs']} 个，盲评包 {rep['checked_packs']} 个")
    if rep["ok"]:
        print("OK：未发现脚本篡改、代码冻结点后改动、草稿残留、连环画缺失或盲评身份/客观分泄露。")
        return 0
    for iss in rep["issues"]:
        print("  !! " + iss)
    return 1 if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
