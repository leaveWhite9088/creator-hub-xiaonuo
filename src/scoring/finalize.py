#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键汇总出榜引擎（src/scoring/finalize.py）。

核心闭环流程（严格对齐《构建与设计说明》第二节与第五节）：
1. 按规范模型 ID 自动发现 leaderboard/blind-maps/*.blind-map.json（或全量发现全部已打包模型）；
2. 核验每个运行的环境哈希承诺 env_commit 与打包冻结代码承诺 code_sha256，防止卡点后偷改代码或改尺子；
3. 从中心追加式评审日志 leaderboard/reviews.jsonl 聚合独立评委的 D1/D2/D3 盲评得分（满分 30 分）；
4. 现场统一拉起 score_run.py 执行三波无头浏览器确定性剧本，定稿 A/B/C 客观得分（满分 70 分）；
5. 执行同模型 B2 时间重叠审计，留档结构化裁决文件 leaderboard/verdicts/<模型>.json 并重排更新 leaderboard/scores.md。
"""
from __future__ import annotations

from pathlib import Path
import argparse
import datetime
import json
import statistics
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools"))

from model_identity import canonical_model_id  # noqa: E402
import review_log  # noqa: E402
from start_run import compute_env_commit, compute_workspace_sha256, verify_file_matches_mock_backend  # noqa: E402
import timing_audit  # noqa: E402

DEFAULT_SCORES_HEADER = """# 排行榜 · creator-hub-xiaonuo

> D 层视觉审美、异步工作台体贴度与前端工程思想评分（30 分）由独立评委审阅匿名盲评包后通过 `judge_submit.py` 追加至中心日志 `leaderboard/reviews.jsonl`；
> A/B/C 异步竞态压测与物理可用性客观分（70 分）在评委盲评全部完成后，由 `finalize.py` 现场统一拉起无头浏览器执行三波确定性标准剧本测量合成。
>
> **当前版本：`xiaonuo-v4.0`**（历史 `xiaonuo-v3.0`、`xiaonuo-v2.0` 与 `xiaonuo-v1.0` 归档榜单及全量留档分别见 `leaderboard/archive/xiaonuo-v3.0/scores.md`、`leaderboard/archive/xiaonuo-v2.0/scores.md` 与 `leaderboard/archive/xiaonuo-v1.0/scores.md`）。

## 赛制口径

| 维度 | 规则 |
| --- | --- |
| 任务形态 | 独立 AI 研究者“林澈”的离线异步顾问工作台与实测文集（双击 `index.html` 本地 `file://` 直接运行，对接官方只读 `mock_backend.js`，零外网依赖） |
| 真实前端范式 | 官方只读 `window.LincheMockAPI` 承载全部业务数据（省去手写大量假文案负担），真实模拟变长延迟（`35ms`–`230ms` 乱序返回）、`AbortSignal` 取消、繁忙周排期冲突、飞行中并发重入拒绝与首轮 `503 SERVICE_BUSY` 瞬态故障；`TASK.md` 与 `CONTRACT.md` 全面剔除 UI 标准答案剧透 |
| 连环过关 | A2/A3/A4 三大主干链均实行**顺序连坐门控**（任一上游步骤得分率 `< 55%`，后续下游步骤均乘以 `0.20` 衰减），静态保底压至 A1=2.0 分：覆盖快慢请求防竞态覆盖、原生 `<svg>` 多维图标签零重叠重绘、无剧透档期冲突消解、跨模块 Undo/Redo（含输入框防劫持）、15ms 连点防重锁与 `503` 无损重试恢复 |
| 物理压测 | 第二波：四档视口（含表格长文与 SVG 对比面板）反截断几何、320px 超长串抗撑破、多态脏存储容错与陡峭 WCAG AA 9 角色木桶对比度（`min_weight=0.65`）；第三波：6 区键盘可达、对比弹层双向焦点锁（`Tab` + `Shift+Tab`）与详情返回归位、反空转 `rAF` 及 320 卡高压渲染延迟 |
| 计时口径 | B2 采用端到端真实墙钟（`start_run.py` 打 `t0` → `judge_pack.py` 冻结 `t1` 并锁定代码 SHA-256）；18 分钟内满分，之后每 24 分钟减半；B1/B2 均以 A 层得分率封顶 |
| 盲评隔离 | `judge_pack.py` 充当“替身体验官”抓拍 12 张《交互状态连环画》（`S01`–`S12`）并附纯物理事实批注，连同脱敏源码打入 `leaderboard/blind/<pack_id>/`（绝不含模型名与客观分）；评委按三步取证法与反端水铁律独立盲评 |

## 计分结构（满分 100）

`A30（A1后端校验与首屏保底 2.0 + A2乱序检索与SVG多维对比链 9.5 + A3异步报价冲突消解与503恢复链 12.0 + A4异步双深链与防竞态历史栈链 6.5） + B15（B1高压性能 5 + B2开发耗时 10，按 A 得分率封顶） + C25（C1反截断几何 9 + C2双向弹层焦点锁 8 + C3混沌容错与AA木桶对比度 8） + D30（D1视觉设计质感与信息层级 10 + D2开放痛点的自发交互巧思 10 + D3代码简洁度与高内聚架构 10）`

---
"""


def _f2(val) -> str:
    return f"{val:.2f}" if isinstance(val, (int, float)) else "-"


def _agg(rows: list[dict], key: str) -> tuple[float | None, float | None]:
    vals = [float(r[key]) for r in rows if isinstance(r.get(key), (int, float))]
    if not vals:
        return None, None
    return round(statistics.mean(vals), 2), round((max(vals) - min(vals)) / 2.0, 2)


REQUIRED_OBJECTIVE_FILES = ("评分.json", "result.json", "audit_report.md", "wave_trace.jsonl")


def can_reuse_objective_cache(
    rdir: Path,
    expected_env_commit: str,
    expected_code_sha256: str,
) -> tuple[bool, dict | None, str]:
    """核验单局运行目录中的已定稿客观分是否满足双指纹（env_commit + code_sha256）防篡改缓存复用条件。"""
    for fn in REQUIRED_OBJECTIVE_FILES:
        if not (rdir / fn).is_file():
            return False, None, f"缺少客观留档文件 {fn}"
    try:
        sc = json.loads((rdir / "评分.json").read_text(encoding="utf-8"))
    except Exception as e:
        return False, None, f"评分.json 读取异常: {e}"
    if not isinstance(sc, dict):
        return False, None, "评分.json 格式非法"
    rec_env = sc.get("env_commit")
    rec_code = sc.get("code_sha256")
    if not rec_env or not rec_code:
        return False, None, "评分.json 缺少 env_commit 或 code_sha256 校验指纹"
    if rec_env != expected_env_commit:
        return False, None, "env_commit 已变更（评分配置或评测脚本发生更新）"
    if rec_code != expected_code_sha256:
        return False, None, "code_sha256 已变更（该局交付物快照发生变动）"
    for k in ("A_outcome", "B_efficiency", "C_quality", "total_objective_70"):
        if not isinstance(sc.get(k), (int, float)):
            return False, None, f"评分.json 缺少有效得分字段 {k}"
    return True, sc, "双指纹校验通过，直接复用已定稿客观分"


def main() -> int:
    ap = argparse.ArgumentParser(description="统一拉起无头浏览器三波剧本定稿客观分并合并盲评日志生成排行榜")
    ap.add_argument("--model", default=None, help="规范模型名；缺省自动发现 blind-maps 下全部模型一次性出榜")
    ap.add_argument("--model-id", default=None, help="显式覆盖规范模型 ID")
    ap.add_argument("--runs", nargs="*", default=None, help="显式指定 run 目录；缺省由 blind-map 自动关联")
    ap.add_argument("--runs-dir", default=str(ROOT / "runs"))
    ap.add_argument("--blind-map", action="append", default=None, help="指定 blind-map JSON 文件路径，可重复")
    ap.add_argument("--blind-maps-dir", default=str(ROOT / "leaderboard" / "blind-maps"))
    ap.add_argument("--review-log", default=str(review_log.DEFAULT_LOG), help="中心化评审日志 JSONL")
    ap.add_argument("--d", default=None, help="调试用：直接按逗号传入各 run 的 D 分")
    ap.add_argument("--d-aggregate", choices=("mean", "median"), default="mean")
    ap.add_argument("--min-judges", type=int, default=1)
    ap.add_argument("--leaderboard-path", default=str(ROOT / "leaderboard" / "scores.md"))
    ap.add_argument("--verdicts-dir", default=str(ROOT / "leaderboard" / "verdicts"))
    ap.add_argument("--runs-log", default=None)
    ap.add_argument("--allow-partial", action="store_true", help="允许仅汇总已有足够评委打分的 run")
    ap.add_argument(
        "--rescore",
        "--force-rescore",
        dest="rescore",
        action="store_true",
        help="强制重跑无头浏览器客观评测（忽略已缓存的定稿客观分）",
    )
    ap.add_argument("--skip-integrity", action="store_true", help="跳过 env_commit/code_sha256 哈希核验（仅限本地调试）")
    ap.add_argument("--dry-run", action="store_true", help="只打印成绩表，不改写 scores.md 与 verdicts")
    args = ap.parse_args()

    leaderboard_path = Path(args.leaderboard_path).resolve()
    verdicts_dir = Path(args.verdicts_dir).resolve()
    blind_maps_dir = Path(args.blind_maps_dir).resolve()
    runs_root = Path(args.runs_dir).resolve()

    # -------------------- 全模型批量一键出榜模式 --------------------
    if not args.model:
        discovered: list[str] = []
        if blind_maps_dir.exists():
            for mf in sorted(blind_maps_dir.glob("*.blind-map.json")):
                try:
                    bm = json.loads(mf.read_text(encoding="utf-8"))
                except Exception:
                    continue
                mid = canonical_model_id(bm.get("model_id") or bm.get("model", ""))
                if mid and mid not in discovered:
                    discovered.append(mid)
        if not discovered:
            print(f"未指定 --model，且在 {blind_maps_dir} 中未发现任何 blind-map 文件")
            return 1

        print(f"全量出榜模式：共发现 {len(discovered)} 个待汇总模型：{', '.join(discovered)}")
        if not args.dry_run:
            leaderboard_path.parent.mkdir(parents=True, exist_ok=True)
            if leaderboard_path.exists():
                head = leaderboard_path.read_text(encoding="utf-8")
                head = (
                    head.split("### 最终成绩")[0]
                    .split("## 大榜（按各模型总分均值排名）")[0]
                    .split("*暂无已归档正式榜单记录")[0]
                    .rstrip()
                    + "\n\n"
                )
            else:
                head = DEFAULT_SCORES_HEADER.rstrip() + "\n\n"
            leaderboard_path.write_text(head, encoding="utf-8")

        failed: list[str] = []
        for mid in discovered:
            print(f"\n================ 正在浏览器压测与汇总模型：{mid} ================")
            sub_cmd = [sys.executable, str(Path(__file__).resolve()), "--model", mid, *sys.argv[1:]]
            r = subprocess.run(sub_cmd)
            if r.returncode != 0:
                failed.append(mid)

        if not args.dry_run:
            board = []
            for mid in discovered:
                if mid in failed:
                    continue
                vf = verdicts_dir / f"{mid}.json"
                if vf.exists():
                    board.append(json.loads(vf.read_text(encoding="utf-8")))
            board.sort(key=lambda v: (-(v.get("mean", {}).get("total") or 0.0), v.get("model", "")))

            blines = [
                "## 大榜（按各模型总分均值排名）",
                "",
                "| 排名 | 模型 | 总分(100) | A主干(30) | B1性能(5) | B2耗时(10) | C1几何(9) | C2键盘(8) | C3容错对比(8) | D1视觉(10) | D2巧思(10) | D3代码(10) | 首屏(ms) | 开发(分) | 已评run |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
            for idx, v in enumerate(board, 1):
                m = v.get("mean") or {}
                s = v.get("summary") or {}
                fps = [r["firstPaintMs"] for r in v.get("runs", []) if isinstance(r.get("firstPaintMs"), (int, float))]
                e2es = [r["endToEndMin"] for r in v.get("runs", []) if isinstance(r.get("endToEndMin"), (int, float))]
                fp_str = f"{statistics.mean(fps):.0f}" if fps else "-"
                e2e_str = f"{statistics.mean(e2es):.1f}" if e2es else "-"
                blines.append(
                    f"| {idx} | {v['model']} | **{_f2(m.get('total'))}** "
                    f"| {_f2(m.get('A'))} | {_f2(m.get('B1'))} | {_f2(m.get('B2'))} "
                    f"| {_f2(m.get('C1'))} | {_f2(m.get('C2'))} | {_f2(m.get('C3'))} "
                    f"| {_f2(m.get('D1'))} | {_f2(m.get('D2'))} | {_f2(m.get('D3'))} "
                    f"| {fp_str} | {e2e_str} | {s.get('runs_scored', '-')} |"
                )
            blines += ["", ""]

            text = leaderboard_path.read_text(encoding="utf-8")
            head, sep, body = text.partition("### 最终成绩")
            head = head.rstrip() + "\n\n"
            sec_by_model: dict[str, str] = {}
            extra_secs: list[str] = []
            if sep:
                raw_secs = (sep + body).split("\n### 最终成绩")
                for i_s, chunk_raw in enumerate(raw_secs):
                    chunk = (chunk_raw if i_s == 0 else "### 最终成绩" + chunk_raw).strip()
                    if not chunk:
                        continue
                    first_line = chunk.splitlines()[0]
                    if first_line.startswith("### 最终成绩 · "):
                        m_part = first_line[len("### 最终成绩 · ") :].split(" — ", 1)[0].strip()
                        sec_by_model[m_part] = chunk
                    else:
                        extra_secs.append(chunk)
            ordered_secs = [sec_by_model.pop(v["model"]) for v in board if v["model"] in sec_by_model]
            ordered_secs.extend(sec_by_model.values())
            ordered_secs.extend(extra_secs)
            detail_text = ("\n\n".join(ordered_secs) + "\n") if ordered_secs else ""
            leaderboard_path.write_text(head + "\n".join(blines) + detail_text, encoding="utf-8")
            print(f"\n大榜与各模型浏览器评测/盲评明细已写入：{leaderboard_path}")

        t_rows = timing_audit.collect(runs_root)
        if t_rows:
            t_rep = timing_audit.build_report(t_rows)
            if not t_rep["ok"]:
                print(f"!! 时间审计提醒：发现 {t_rep['overlapRuns']} 个运行存在同模型墙钟时间重叠，请核查 B2 可比性。")

        if failed:
            print(f"\n以下模型出榜失败：{', '.join(failed)}")
            return 1
        return 0

    # -------------------- 单模型压测定稿与合成模式 --------------------
    if args.min_judges < 1:
        print("--min-judges 必须 >= 1")
        return 1

    model_id = (args.model_id.strip().lower() if args.model_id else canonical_model_id(args.model)).strip()
    if not model_id:
        print("--model/--model-id 不能为空")
        return 1

    map_files = [Path(p).resolve() for p in (args.blind_map or [])]
    if not map_files and blind_maps_dir.exists():
        for mf in sorted(blind_maps_dir.glob("*.blind-map.json")):
            try:
                bm = json.loads(mf.read_text(encoding="utf-8"))
            except Exception:
                continue
            if canonical_model_id(bm.get("model_id") or bm.get("model", "")) == model_id:
                map_files.append(mf)
    map_files = list(dict.fromkeys(map_files))

    model_inputs = {args.model}
    run_to_case: dict[str, str] = {}
    run_to_pack: dict[str, str] = {}
    for mf in map_files:
        if not mf.exists():
            print(f"找不到盲评映射文件：{mf}")
            return 1
        bm = json.loads(mf.read_text(encoding="utf-8"))
        map_mid = canonical_model_id(bm.get("model_id") or bm.get("model", ""))
        if map_mid and map_mid != model_id:
            print(f"盲评映射模型 {map_mid} 与 --model {model_id} 不一致")
            return 1
        if bm.get("model"):
            model_inputs.add(bm["model"])
        pack_id = bm.get("pack_id")
        if not pack_id:
            print(f"映射缺少 pack_id：{mf}")
            return 1
        for cid, meta in (bm.get("cases") or {}).items():
            rname = (meta or {}).get("run")
            if not rname:
                continue
            if rname in run_to_case:
                print(f"运行 {rname} 重复出现在多个 blind-map 中")
                return 1
            run_to_case[rname] = cid
            run_to_pack[rname] = pack_id

    if args.runs:
        runs = [Path(p).resolve() for p in args.runs]
    elif run_to_case:
        runs = []
        for rname in sorted(run_to_case):
            cand = runs_root / rname
            if not cand.exists():
                cand = Path(rname)
            runs.append(cand.resolve())
    else:
        print(f"模型 {model_id} 未提供 --runs 且未找到对应的 blind-map（请先运行 judge_pack.py）")
        return 1

    runs_total_all = len(runs)

    ds: list[float | None] = []
    d_dims: list[dict | None] = []
    case_ids: list[str | None] = []
    pack_ids: list[str | None] = []
    d_counts: list[int | None] = []

    if args.d:
        d_source = "direct"
        d_aggregate = "direct"
        raw_ds = [float(x) for x in args.d.split(",")]
        if len(raw_ds) != len(runs):
            print(f"--d 数量（{len(raw_ds)}）与运行数（{len(runs)}）不一致")
            return 1
        ds = raw_ds
        d_dims = [{"D1": None, "D2": None, "D3": None} for _ in runs]
        case_ids = [run_to_case.get(r.name) for r in runs]
        pack_ids = [run_to_pack.get(r.name) for r in runs]
        d_counts = [None for _ in runs]
    else:
        d_source = "review_log"
        d_aggregate = args.d_aggregate
        try:
            reviews = review_log.read_reviews(args.review_log)
        except review_log.ReviewLogError as e:
            print(f"读取中心评审日志失败：{e}")
            return 1
        if not reviews:
            print(f"中心评审日志为空（请先由独立评委运行 judge_submit.py 提交盲评分）：{args.review_log}")
            return 1
        used, duplicates = review_log.dedupe_latest(reviews)
        if duplicates:
            print(f"提示：评审日志存在 {duplicates} 条同评委更新记录，已按最新时间去重")
        groups = review_log.aggregate_reviews(used, args.d_aggregate)
        by_key = {(g["pack_id"], g["case_id"]): g for g in groups}

        for r in runs:
            cid = run_to_case.get(r.name)
            pid = run_to_pack.get(r.name)
            if not cid or not pid:
                if args.allow_partial:
                    ds.append(None)
                    d_dims.append(None)
                    case_ids.append(None)
                    pack_ids.append(None)
                    d_counts.append(0)
                    continue
                print(f"私有映射中缺少运行 {r.name}")
                return 1
            g = by_key.get((pid, cid))
            if not g or g["judge_count"] < args.min_judges:
                if args.allow_partial:
                    ds.append(None)
                    d_dims.append(None)
                    case_ids.append(cid)
                    pack_ids.append(pid)
                    d_counts.append(0)
                    continue
                if not g:
                    print(f"评审日志尚无 pack={pid} case={cid}（对应运行 {r.name}）的评委打分")
                else:
                    print(f"运行 {r.name} 当前评委数 {g['judge_count']} 少于要求的 --min-judges {args.min_judges}")
                return 1
            ds.append(g["D"])
            d_dims.append({"D1": g["D1"], "D2": g["D2"], "D3": g["D3"]})
            case_ids.append(cid)
            pack_ids.append(pid)
            d_counts.append(g["judge_count"])

    judge_reviews_all = sum(x or 0 for x in d_counts)
    scored_idx = [i for i, d in enumerate(ds) if d is not None]
    if not scored_idx:
        print("没有已完成盲评打分的运行可供汇总出榜")
        return 1

    runs = [runs[i] for i in scored_idx]
    ds = [ds[i] for i in scored_idx]
    d_dims = [d_dims[i] for i in scored_idx]
    case_ids = [case_ids[i] for i in scored_idx]
    pack_ids = [pack_ids[i] for i in scored_idx]
    d_counts = [d_counts[i] for i in scored_idx]

    current_env = compute_env_commit(ROOT)
    rows: list[dict] = []
    errors: list[str] = []

    for rdir, d_val, dims, cid, pid, j_cnt in zip(runs, ds, d_dims, case_ids, pack_ids, d_counts):
        name = rdir.name
        proto_path = rdir / "protocol.json"
        ws_dir = rdir / "workspace"
        if not proto_path.exists() or not ws_dir.is_dir():
            errors.append(f"{name}: 缺少 protocol.json 或 workspace/ 目录")
            continue

        proto = json.loads(proto_path.read_text(encoding="utf-8"))
        env_ok = proto.get("env_commit") == current_env
        frozen_sha = proto.get("code_sha256")
        actual_sha = compute_workspace_sha256(ws_dir)
        code_ok = bool(frozen_sha) and (actual_sha == frozen_sha)
        mock_ok = verify_file_matches_mock_backend(ws_dir / "mock_backend.js", ROOT)

        if not args.skip_integrity:
            if not env_ok:
                errors.append(f"{name}: env_commit 不匹配（评测脚本或配置在开局后发生变更）")
                continue
            if not code_ok:
                errors.append(f"{name}: code_sha256 不匹配（选手在冻结 t1 后改动了沙盒代码，成绩作废）")
                continue
            if not mock_ok:
                errors.append(f"{name}: workspace/mock_backend.js 缺失或遭到篡改（违反只读后端纪律，成绩作废）")
                continue

        target_code_sha = frozen_sha or actual_sha
        cache_ok, cached_sc, cache_msg = (
            (False, None, "显式指定 --rescore 强制重算")
            if args.rescore
            else can_reuse_objective_cache(rdir, current_env, target_code_sha)
        )
        if cache_ok and cached_sc is not None:
            sc = cached_sc
            obj_source = "cached"
            print(
                f"  [客观分缓存复用] {name}: {cache_msg} "
                f"(A={sc['A_outcome']:.2f}, B={sc['B_efficiency']:.2f}, C={sc['C_quality']:.2f})"
            )
        else:
            print(f"  [客观分现场评测] {name}: {cache_msg}，正在拉起三波无头浏览器剧本...")
            rr = subprocess.run(
                [sys.executable, str(HERE / "score_run.py"), str(rdir), model_id, "--no-record"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if rr.returncode != 0 or not (rdir / "评分.json").exists():
                tail = (((rr.stdout or "") + "\n" + (rr.stderr or "")).strip())[-500:]
                errors.append(f"{name}: score_run.py 执行失败：{tail}")
                continue
            sc = json.loads((rdir / "评分.json").read_text(encoding="utf-8"))
            obj_source = "fresh"
        tok = {}
        tok_path = rdir / "token_usage.json"
        if tok_path.exists():
            try:
                tok = json.loads(tok_path.read_text(encoding="utf-8"))
            except Exception:
                tok = {}

        A = float(sc.get("A_outcome") or 0.0)
        B = float(sc.get("B_efficiency") or 0.0)
        C = float(sc.get("C_quality") or 0.0)
        ad = sc.get("A_detail") or {}
        bd = sc.get("B_detail") or {}
        cd = sc.get("C_detail") or {}
        dd = dims or {}
        e2e_sec = sc.get("endToEndSeconds")
        e2e_min = round(float(e2e_sec) / 60.0, 1) if isinstance(e2e_sec, (int, float)) else None

        rows.append(
            {
                "run": name,
                "pack_id": pid,
                "case_id": cid,
                "judge_count": j_cnt,
                "code_commit": (frozen_sha or actual_sha)[:12],
                "env_commit": (sc.get("env_commit") or current_env)[:12],
                "objective_source": obj_source,
                "integrity_ok": bool(env_ok and code_ok and mock_ok),
                "not_implemented": bool(sc.get("not_implemented")),
                "firstPaintMs": bd.get("first_paint_ms"),
                "endToEndMin": e2e_min,
                "total_tokens": tok.get("total_tokens"),
                "A": A,
                "B": B,
                "C": C,
                "D": float(d_val or 0.0),
                "total": round(A + B + C + float(d_val or 0.0), 2),
                "A1": ad.get("A1", ad.get("A1_content_offline5")),
                "A2": ad.get("A2", ad.get("A2_search_filter_compare9")),
                "A3": ad.get("A3", ad.get("A3_estimator_persist_form8")),
                "A4": ad.get("A4", ad.get("A4_deeplink_history_toc8")),
                "B1": bd.get("B1_perf5"),
                "B2": bd.get("B2_time10"),
                "C1": cd.get("C1_responsive9"),
                "C2": cd.get("C2_keyboard8"),
                "C3": cd.get("C3_resilience_contrast8"),
                "D1": dd.get("D1"),
                "D2": dd.get("D2"),
                "D3": dd.get("D3"),
            }
        )

    if errors:
        print("汇总出榜终止，存在以下阻断项：")
        for e in errors:
            print("  !! " + e)
        return 1

    mA, rA = _agg(rows, "A")
    mB, rB = _agg(rows, "B")
    mC, rC = _agg(rows, "C")
    mD, rD = _agg(rows, "D")
    mT, rT = _agg(rows, "total")
    mB1, rB1 = _agg(rows, "B1")
    mB2, rB2 = _agg(rows, "B2")
    mC1, rC1 = _agg(rows, "C1")
    mC2, rC2 = _agg(rows, "C2")
    mC3, rC3 = _agg(rows, "C3")
    mD1, rD1 = _agg(rows, "D1")
    mD2, rD2 = _agg(rows, "D2")
    mD3, rD3 = _agg(rows, "D3")
    mFP, _ = _agg(rows, "firstPaintMs")
    mE2E, _ = _agg(rows, "endToEndMin")

    lines = [
        f"\n### 最终成绩 · {model_id} — {datetime.datetime.now():%Y-%m-%d %H:%M}",
        "",
        "| 运行批次 | 代码承诺 | 首屏(ms) | 开发(分) | A主干(30) | B1性能(5) | B2耗时(10) | C1几何(9) | C2键盘(8) | C3容错对比(8) | D1视觉(10) | D2巧思(10) | D3代码(10) | 评委数 | 总分(100) | 完整性 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in rows:
        fp_s = f"{r['firstPaintMs']:.0f}" if isinstance(r.get("firstPaintMs"), (int, float)) else "-"
        e2e_s = f"{r['endToEndMin']:.1f}" if isinstance(r.get("endToEndMin"), (int, float)) else "-"
        lines.append(
            f"| {r['run']} | `{r['code_commit']}` | {fp_s} | {e2e_s} "
            f"| {_f2(r['A'])} | {_f2(r['B1'])} | {_f2(r['B2'])} "
            f"| {_f2(r['C1'])} | {_f2(r['C2'])} | {_f2(r['C3'])} "
            f"| {_f2(r['D1'])} | {_f2(r['D2'])} | {_f2(r['D3'])} "
            f"| {r['judge_count'] if r['judge_count'] is not None else '-'} | **{r['total']:.2f}** "
            f"| {'✓' if r['integrity_ok'] else '✗'} |"
        )
    if len(rows) > 1:
        fp_m_s = f"{mFP:.0f}" if isinstance(mFP, (int, float)) else "-"
        e2e_m_s = f"{mE2E:.1f}" if isinstance(mE2E, (int, float)) else "-"
        lines.append(
            f"| **平均** | - | {fp_m_s} | {e2e_m_s} "
            f"| {_f2(mA)} | {_f2(mB1)} | {_f2(mB2)} "
            f"| {_f2(mC1)} | {_f2(mC2)} | {_f2(mC3)} "
            f"| {_f2(mD1)} | {_f2(mD2)} | {_f2(mD3)} | - | **{mT:.2f}** | - |"
        )

    lines += [
        "",
        f"**均值 ± 极差半宽**：A {mA:.2f} ±{rA:.2f}｜B {mB:.2f} ±{rB:.2f}｜C {mC:.2f} ±{rC:.2f}"
        f"｜D {mD:.2f} ±{rD:.2f}｜**总分 {mT:.2f} ±{rT:.2f}**",
        "",
        f"- 模型汇总：共发现运行 {runs_total_all} 次（已出榜 {len(rows)} 次），累计采信评委评审 {judge_reviews_all} 条。",
        f"- 定稿口径：A/B/C 由 `score_run.py` 现场拉起无头浏览器执行三波标准剧本测量计算，D 来源=`{d_source}`（聚合方式=`{d_aggregate}`）。",
    ]
    section_text = "\n".join(lines)
    print(section_text)

    if args.dry_run:
        print("\n[dry-run] 未改写排行榜与裁决留档文件。")
        return 0

    verdicts_dir.mkdir(parents=True, exist_ok=True)
    verdict_obj = {
        "model": model_id,
        "model_inputs": sorted(model_inputs),
        "finalized_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "blind_pack_ids": sorted({r["pack_id"] for r in rows if r.get("pack_id")}),
        "review_log": str(Path(args.review_log).resolve()),
        "d_source": d_source,
        "d_aggregate": d_aggregate,
        "summary": {
            "runs_total": runs_total_all,
            "runs_scored": len(rows),
            "judge_reviews": judge_reviews_all,
        },
        "runs": rows,
        "mean": {
            "A": mA,
            "B": mB,
            "C": mC,
            "D": mD,
            "total": mT,
            "B1": mB1,
            "B2": mB2,
            "C1": mC1,
            "C2": mC2,
            "C3": mC3,
            "D1": mD1,
            "D2": mD2,
            "D3": mD3,
        },
        "range_half": {
            "A": rA,
            "B": rB,
            "C": rC,
            "D": rD,
            "total": rT,
            "B1": rB1,
            "B2": rB2,
            "C1": rC1,
            "C2": rC2,
            "C3": rC3,
            "D1": rD1,
            "D2": rD2,
            "D3": rD3,
        },
    }
    verdict_path = verdicts_dir / f"{model_id}.json"
    verdict_path.write_text(json.dumps(verdict_obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    leaderboard_path.parent.mkdir(parents=True, exist_ok=True)
    if not leaderboard_path.exists():
        leaderboard_path.write_text(DEFAULT_SCORES_HEADER + "\n", encoding="utf-8")
    with leaderboard_path.open("a", encoding="utf-8") as f:
        f.write(section_text + "\n")

    try:
        review_log.append_run_event(
            "finalize",
            {"model_id": model_id, "runs_scored": len(rows), "total_mean": mT},
            log_path=args.runs_log,
        )
    except Exception:
        pass

    print(f"\n已写入裁决留档：{verdict_path} 及榜单：{leaderboard_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
