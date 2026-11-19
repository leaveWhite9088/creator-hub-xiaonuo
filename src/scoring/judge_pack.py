#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""选手收尾与《痛点场景连环画》匿名盲评包生成工具 v4.0（src/scoring/judge_pack.py）。

核心职责：
1. 严格校验沙盒内的 `mock_backend.js` 与官方只读版本 SHA-256 完全一致，杜绝篡改后端数据或延迟作弊；
2. 若运行尚未冻结结束时间，自动打下结束时间戳 t1（end_iso），锁定 B2 端到端墙钟耗时并固化沙盒代码承诺 code_sha256；
3. 将沙盒内的网页源码彻底脱敏（抹除模型真名、运行目录名、系统用户名与本机绝对路径），`mock_backend.js` 原样保留只读副本；
4. 启动“替身体验官”（storyboard.py）对脱敏后的网页自动走完异步检索、对比、规划与 503 提交恢复全场景，抓拍 12 张《交互状态连环画》并附上纯物理事实批注；
5. 输出匿名盲评包 leaderboard/blind/<pack_id>/ 及裁判不可见的私有映射 leaderboard/blind-maps/<model_id>.<pack_id>.blind-map.json；
6. 【铁律】绝不在此时计算或写入任何 A/B/C 客观得分与耗时，确保独立评委零结果光环干扰。
"""
from __future__ import annotations

from pathlib import Path
import argparse
import datetime
import json
import os
import re
import secrets
import shutil
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools"))

from model_identity import canonical_model_id, matches_batch_run  # noqa: E402
import review_log  # noqa: E402
from start_run import compute_workspace_sha256, verify_file_matches_mock_backend  # noqa: E402
import storyboard  # noqa: E402

SKIP_DIRS = {"__pycache__", ".pytest_cache", ".git", "node_modules", ".venv", "venv"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe", ".log", ".tmp"}
TEMPLATE_STATIC_FILES = {"TASK.md", "CONTRACT.md", "DECISIONS.md", "smoke_public.py"}
FORBIDDEN_NAMES = {"评分.json", "result.json", "protocol.json", "wave_trace.jsonl", "audit_report.md", "token_usage.json"}
TEXT_CODE_SUFFIXES = {".html", ".htm", ".css", ".js", ".mjs", ".json", ".md", ".svg", ".txt", ".xml"}


def _epoch(iso: str) -> float:
    return datetime.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def _sanitize_text(text: str, tokens_to_redact: list[str]) -> str:
    out = text
    out = re.sub(r"(?<![A-Za-z])[A-Za-z]:[\\/][^\s\"'`<>|]+", "<REDACTED_PATH>", out)
    out = re.sub(r"/(?:Users|home)/[^\s\"'`<>|]+", "<REDACTED_PATH>", out)
    for tok in sorted({t for t in tokens_to_redact if t and len(t.strip()) >= 3}, key=len, reverse=True):
        out = re.sub(re.escape(tok.strip()), "<ANONYMOUS_CANDIDATE>", out, flags=re.IGNORECASE)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="冻结选手开发计时、抓拍痛点连环画并生成脱敏匿名盲评包")
    ap.add_argument("--model", required=True, help="开局时使用的模型标识")
    ap.add_argument("--model-id", default=None, help="可选：显式指定汇总分组用的规范模型 ID")
    ap.add_argument("--runs", nargs="*", default=None, help="可选：显式指定要打包的 run 目录列表")
    ap.add_argument("--runs-dir", default=str(ROOT / "runs"))
    ap.add_argument("--blind-dir", default=str(ROOT / "leaderboard" / "blind"))
    ap.add_argument("--blind-maps-dir", default=str(ROOT / "leaderboard" / "blind-maps"))
    ap.add_argument("--runs-log", default=None)
    args = ap.parse_args()

    raw_model = args.model.strip()
    model_id = (args.model_id.strip().lower() if args.model_id else canonical_model_id(raw_model)).strip()
    if not model_id:
        print("打包失败：--model/--model-id 不能为空")
        return 1

    runs_root = Path(args.runs_dir).resolve()
    if args.runs:
        runs = [Path(p).resolve() for p in args.runs]
    else:
        if not runs_root.exists():
            print(f"找不到运行目录根路径：{runs_root}")
            return 1
        if canonical_model_id(raw_model) != raw_model.lower():
            runs = sorted(p for p in runs_root.iterdir() if p.is_dir() and matches_batch_run(raw_model, p.name))
        else:
            runs = sorted(p for p in runs_root.iterdir() if p.is_dir() and canonical_model_id(p.name) == model_id)

    runs = [r for r in runs if (r / "protocol.json").exists() and (r / "workspace").is_dir()]
    if not runs:
        print(f"没有找到模型 {model_id} 的有效运行目录（需含 protocol.json 与 workspace/，请先执行 start_run.py）")
        return 1

    bad_runs = [] if (args.model_id and args.runs) else [r.name for r in runs if canonical_model_id(r.name) != model_id]
    if bad_runs:
        print(f"以下运行目录的规范模型 ID 与 {model_id} 不一致：{bad_runs}")
        return 1

    blind_root = Path(args.blind_dir).resolve()
    blind_maps_dir = Path(args.blind_maps_dir).resolve()
    blind_root.mkdir(parents=True, exist_ok=True)
    blind_maps_dir.mkdir(parents=True, exist_ok=True)

    pack_id = secrets.token_hex(6)
    pack_dir = blind_root / pack_id
    pack_dir.mkdir(parents=True, exist_ok=False)

    readme_md = """# 匿名盲评包（仅限独立评委审阅 · v4.0）

欢迎进入《创作者主页与异步顾问工作台 · 前端可用性与工程体验基准（xiaonuo-v4.0）》D 层盲评！本目录是你作为**独立评委**的**唯一合法输入**（无选手自述文档，100% 凭真实画面与源码本身硬碰硬定级）。

## 评委三步取证盲评法（严格执行）

1. **第一步：先读量表与 12 格《交互状态连环画》**
   - 阅读同目录 [`RUBRIC.md`](RUBRIC.md)，明确 D1（10分）、D2（10分）、D3（10分）的定档锚点、反端水铁律与硬伤降档红线；
   - 打开 `case-XX/STORYBOARD.md`，**逐张实际查看 `case-XX/storyboard/S01..S12.png` 真实画面**及客观物理状态批注（含 `[S01]/[S11]/[S12]` 视觉质感与多端层级、`[S03]` 原生 SVG 多维对比图真实渲染、`[S04]` 空搜索出路、`[S07]–[S10]` 异步排期冲突可视化、一键顺延、方案非破坏带入及 `503 SERVICE_BUSY` 瞬态异常恢复）。
2. **第二步：直接深入脱敏源码（`code/`）核查工程质量与简洁度**
   - 阅读 `case-XX/OVERVIEW.md` 与 `case-XX/code/` 下的完整前端代码（`mock_backend.js` 为官方统一只读后端，重点审阅选手编写的 HTML/CSS/JS）；
   - 核查代码是否简洁克制、模块职责是否高内聚、是否严格通过 `window.LincheMockAPI` 驱动视图、如何用 `AbortController` 与递增请求序号根治异步竞态覆盖、以及是否存在样式覆盖隐藏属性、默认值与后端枚举脱节或无限 `rAF` 等工程瑕疵。
3. **第三步：按需执行无头靶向补测并提交评分**
   - 若读源码发现选手自发设计了静态连环画未覆盖的体验亮点或可疑实现，**严禁开启全屏桌面视觉操控自由乱点**，请调用官方轻量无头补测命令定向验证（收工前必须清空 `draft/`）：
     ```sh
     python tools/judge_probe.py --case-dir "<本case目录>" --viewport 1440x900 --press "Escape" --out draft/probe.png
     ```
   - 完成取证后，按 [`SUBMIT.md`](SUBMIT.md) 的命令将评分原子追加写入中心日志。

## 隔离红线（严禁触碰）
- **严禁**访问上级 `leaderboard/blind-maps/`、`leaderboard/reviews.jsonl`、`leaderboard/scores.md`、`runs/` 或仓库评测脚本；
- **严禁**运行 `score_run.py` 或 `finalize.py` 打探客观分（A/B/C 共 70 分由汇总阶段无头浏览器连环剧本独立算分）；
- **严禁**查看其他评委分数或猜测被测模型名称。
"""
    (pack_dir / "README.md").write_text(readme_md, encoding="utf-8")

    rubric_md = """# D 层视觉设计质感、痛点自发交互巧思与代码架构盲评量表（v4.0 · 满分 30 分）

> **核心定档与反端水铁律（无选手自述，100% 凭画面与代码说话）**：
> - **绝不温和折中**：严禁把有明显视觉平庸、交互生硬或代码臃肿/漏洞的作品扎堆打在 7.5～8.5 的“安全区”。必须先按视觉与工程硬伤直接降档，再看亮点拉开真实区分度。
> - **5.0 分（满分的 50%）是“只把接口勉强接通、界面像简陋后台表单、缺乏自发体贴设计与代码分层”的封顶线！**
> - 支持小数（如 `8.6`），必须在 `--evidence` 中写明**连环画截图编号（`[S01]`–`[S12]`）+ 具体源码文件名与行号/函数名证据**。

---

## D1 视觉设计质感与信息层级（0–10 分）
**纯看 12 张真实渲染截图（`[S01]`–`[S12]`）的视觉审美、版式秩序与图表呈现**：
- **8.5–10.0（出色 · 成熟产品/社论级质感）**：
  - `[S01]/[S11]/[S12]` 具备鲜明的现代编辑阅读感与专业顾问工作台秩序：留白呼吸感、字号字重层级、卡片边框/阴影微质感、浅色与深色多层表面配色协调克制；
  - `[S03]` 横向对比面板中的原生 `<svg>` 多维对比图**在画面上清晰完整渲染**，网格、刻度、多边形与图例配色高辨识度且零文字挤压；并排参数表层次分明；
  - `[S05]/[S06]` 长文正文行宽舒适，标题、引用、代码块与表格样式考究，桌面与手机窄屏下视觉比例匀称、吸顶栏与底部对比条紧凑克制不压迫正文。
- **5.0–8.4（达标至良好）**：
  - 若 `[S03]` 原生 SVG 对比图区域在真实画面中完全空白或未打开（**直接重扣 2.0～2.5 分**，封顶 ≤ 7.2 分）、长文或手机端顶栏/浮动条遮挡截断正文（扣 1.2～1.8 分）、下拉框等控件显示空白或错位（扣 1.0～1.5 分）、或版面偏常规后台模板缺乏精致排版层次（6.0–7.5 分）。
- **0.0–4.9（薄弱）**：
  - 版面粗糙拥挤、深色模式刺眼或漏改白底、多处画面卡死停留在同一页未能展示各模块视觉，或页面未完成。

---

## D2 开放痛点的自发交互巧思与体贴度（0–10 分）
**纯看面对四大开放业务痛点时的自发产品交互设计与防挫败体验**：
- **8.5–10.0（出色 · 体贴顺手的交互巧思）**：
  - **痛点一 & 二（选型对比与空搜索出路 `[S02]/[S03]/[S04]`）**：对比篮状态与面板联动直观；搜索支持输入法拼字保护与显式清空，`[S04]` 空结果主动交代未命中原因并提供一键恢复及高价值可点击建议词；
  - **痛点三（沉浸长文阅读 `[S05]/[S06]`）**：具备清晰的阅读位置感知（如顶部阅读进度条、目录随滚动自动高亮当前小节）与顺滑的上下篇/返回列表过渡；
  - **痛点四（忙闲冲突消解、耦合带入与 503 容错恢复 `[S07]→[S10]`）**：在无剧透提示下**主动可视化 14 周忙闲日历并清晰列出冲突原因，提供一键顺延至最近连续空闲周的便捷交互**；跨模块撤销/重做带有语义提示且不劫持输入框；将方案带入留言时**非破坏性合并对比项目与排期摘要，完好保留访客已填附注**；字段级就地报错与改对即时消错；遇 `503` 瞬时繁忙完好保留草稿并引导重试拿到 `INQ-2026-` 回执，点击复制 100ms 内给出确认反馈。
- **4.5–8.4（达标至良好）**：
  - 改对字段后错误提示框未即时消失或拿到回执后旧报错条仍残留（**扣 1.2～1.8 分**）、缺少阅读进度或目录高亮跟随（扣 0.8～1.2 分）、遇到繁忙周只报错不给一键顺延（扣 1.5～2.0 分）、带入方案粗暴覆盖原有留言（**重扣 1.5～2.2 分**）、或详情返回列表卡死导致后续规划台与表单交互在连环画中完全无法触发（**直接封顶 ≤ 4.2 分**）。
- **0.0–4.4（薄弱）**：
  - 原生 `alert()` 弹窗报错、503 报错清空用户输入、空搜索死胡同，或核心交互链路断裂。

---

## D3 代码简洁度、高内聚架构与异步状态机质量（0–10 分）
**直接审阅 `code/` 前端源码本身，考察代码精炼度、模块解耦与异步防御工程质量**：
- **必做核查 1（代码简洁度与高内聚分层）**：
  - 奖励用 **精炼克制、结构清晰的代码（如 1500～2800 行高内聚实现）** 干净利落解决全部业务痛点；若代码臃肿堆砌（如 4000+ 行存在大量重复模板拼接或过度包装）、或状态与 DOM 操作散乱揉成一团，扣 **1.0～2.0 分**。
  - 检查 CSS 设计令牌（`:root` 与 `[data-theme="dark"]`）与视图渲染函数是否单点易维护。
- **必做核查 2（异步竞态通道与并发状态机）**：
  - 检查源码对 `queryCatalog`、`getDetail`、`evaluatePlan` 三条通道是否实现了独立的 **`AbortController` 主动中止 + 单调递增请求序号（`seq`）双重防倒灌**，对 `submitInquiry` 是否具备飞行中防重入锁。缺失竞态防护直接扣 **1.8～2.5 分**。
- **必做核查 3（数据源真实性与工程低级漏洞排查）**：
  - 若在前端硬编码抄写项目/文章/报价数据绕过 `window.LincheMockAPI`，**D3 直接封顶 ≤ 2.5 分**；
  - 检查是否存在工程硬伤：如 CSS `display:flex` 覆盖 `[hidden]` 导致错误框无法隐藏、初始状态枚举值（如 `scaleId`）与后端字典不匹配、路由返回盲目调用 `history.back()` 导致导航卡死、缺少输入法 `compositionstart/end` 或输入框 `Ctrl+Z` 防劫持、模态框缺少双向焦点锁、或存在无限空转 `rAF` 循环（**每命中一项工程漏洞直接扣 1.0～2.0 分**）。
- **8.5–10.0（出色）**：代码精炼干脆、模块职责边界极清晰、三通道异步防竞态与历史栈无懈可击、零低级工程漏洞。
- **5.0–8.4（达标至良好）**：接通真实接口且具备基本防竞态，但存在个别状态不一致漏洞、路由/样式瑕疵或代码略显冗长。

---

## 提交输出硬性要求
1. `--evidence`：**必须同时引用连环画截图编号（如 `[S01][S03][S07][S09][S10]`）+ 具体源码文件与行号/函数名**；
2. `--note`：**明确指出该作品的“最强反证 / 最突出的视觉、交互或代码工程短板”**。
"""
    (pack_dir / "RUBRIC.md").write_text(rubric_md, encoding="utf-8")

    os_user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    official_mock_path = ROOT / "src" / "sandbox_template" / "mock_backend.js"
    cases = []
    mapping_cases = {}

    for idx, rdir in enumerate(runs, 1):
        case_id = f"case-{idx:02d}"
        proto_path = rdir / "protocol.json"
        proto = json.loads(proto_path.read_text(encoding="utf-8"))
        ws_dir = rdir / "workspace"
        if not (ws_dir / "index.html").exists():
            print(f"打包失败：{ws_dir} 下缺少入口文件 index.html")
            shutil.rmtree(pack_dir, ignore_errors=True)
            return 1

        if not verify_file_matches_mock_backend(ws_dir / "mock_backend.js", ROOT):
            print(f"打包拒绝：{rdir.name}/workspace/mock_backend.js 缺失或遭到修改，违反官方只读后端纪律！")
            shutil.rmtree(pack_dir, ignore_errors=True)
            return 1

        # 冻结计时 t1 与代码承诺哈希
        timing = proto.setdefault("timing", {})
        current_code_sha = compute_workspace_sha256(ws_dir)
        if not timing.get("end_iso"):
            now_iso = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
            t0_str = timing.get("t0_iso") or timing.get("process_iso") or now_iso
            e2e_sec = max(0.0, round(_epoch(now_iso) - _epoch(t0_str), 2))
            timing["end_iso"] = now_iso
            timing["endToEndSeconds"] = e2e_sec
            proto["code_sha256"] = current_code_sha
            proto["status"] = "packed"
            proto_path.write_text(json.dumps(proto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            recorded_sha = proto.get("code_sha256")
            if recorded_sha and recorded_sha != current_code_sha:
                print(f"打包拒绝：{rdir.name} 在首次冻结 t1 ({timing.get('end_iso')}) 后修改了沙盒源码，违反计时冻结纪律！")
                shutil.rmtree(pack_dir, ignore_errors=True)
                return 1
            if not recorded_sha:
                proto["code_sha256"] = current_code_sha
                proto_path.write_text(json.dumps(proto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        tokens_to_redact = [
            raw_model,
            model_id,
            rdir.name,
            proto.get("run_name") or "",
            proto.get("model_id") or "",
            os_user if len(os_user) >= 3 else "",
        ]

        case_dir = pack_dir / case_id
        code_out_dir = case_dir / "code"
        sb_out_dir = case_dir / "storyboard"
        code_out_dir.mkdir(parents=True, exist_ok=True)
        sb_out_dir.mkdir(parents=True, exist_ok=True)

        file_manifest = []

        for src_file in sorted(ws_dir.rglob("*"), key=lambda x: x.relative_to(ws_dir).as_posix()):
            if not src_file.is_file():
                continue
            rel_parts = src_file.relative_to(ws_dir).parts
            if any(p in SKIP_DIRS for p in rel_parts):
                continue
            if src_file.name in FORBIDDEN_NAMES or src_file.name in TEMPLATE_STATIC_FILES:
                continue
            if src_file.suffix.lower() in SKIP_SUFFIXES:
                continue

            rel_posix = src_file.relative_to(ws_dir).as_posix()
            dst_file = code_out_dir / rel_posix
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            if rel_posix == "mock_backend.js":
                # 官方只读异步后端原样复制，确保 SHA-256 与官方模板逐字节一致
                shutil.copy2(official_mock_path, dst_file)
                line_cnt = len(official_mock_path.read_text(encoding="utf-8").splitlines())
            elif src_file.suffix.lower() in TEXT_CODE_SUFFIXES:
                raw_text = src_file.read_text(encoding="utf-8", errors="replace")
                clean_text = _sanitize_text(raw_text, tokens_to_redact)
                dst_file.write_text(clean_text, encoding="utf-8")
                line_cnt = len(clean_text.splitlines())
            else:
                shutil.copy2(src_file, dst_file)
                line_cnt = 0
            file_manifest.append((f"code/{rel_posix}", line_cnt))

        # 启动“替身体验官”抓拍 12 张连环画（直接作用于已脱敏的 code/index.html，确保截图零敏感信息泄露）
        print(f"正在为 {case_id} 启动无头替身体验官抓拍《痛点场景连环画》...")
        sb_data = storyboard.capture_storyboard(code_out_dir / "index.html", sb_out_dir)
        sb_md_text = storyboard.render_storyboard_markdown(case_id, sb_data)
        (case_dir / "STORYBOARD.md").write_text(sb_md_text, encoding="utf-8")

        contestant_lines = sum(x[1] for x in file_manifest if x[0] != "code/mock_backend.js")
        overview_lines = [
            f"# 匿名作品概览 · {case_id}",
            "",
            f"- **《交互状态连环画》状态**：已生成 `{sb_data['panel_count']}` 张标准场景截图（请务必打开 [`STORYBOARD.md`](STORYBOARD.md) 逐图审阅）",
            f"- **官方只读后端 `mock_backend.js` 校验**：已通过 SHA-256 一致性校验",
            f"- **选手自写前端代码行数（不含官方 `mock_backend.js`）**：{contestant_lines} 行",
            "",
            "## 包内文件清单",
            "",
            "| 路径 | 行数 / 说明 |",
            "| --- | ---: |",
            f"| `STORYBOARD.md` | {len(sb_md_text.splitlines())} 行（含 `{sb_data['panel_count']}` 张截图索引与客观物理批注） |",
        ]
        for rel_p, lcnt in file_manifest:
            tag = f"{lcnt} 行（官方只读异步后端）" if rel_p == "code/mock_backend.js" else (f"{lcnt} 行" if lcnt else "静态资源")
            overview_lines.append(f"| `{rel_p}` | {tag} |")
        (case_dir / "OVERVIEW.md").write_text("\n".join(overview_lines) + "\n", encoding="utf-8")

        cases.append(
            {
                "case_id": case_id,
                "overview": f"{case_id}/OVERVIEW.md",
                "storyboard": f"{case_id}/STORYBOARD.md",
                "code_dir": f"{case_id}/code",
                "panel_count": sb_data["panel_count"],
            }
        )
        mapping_cases[case_id] = {
            "run": rdir.name,
            "code_sha256": proto.get("code_sha256"),
            "end_iso": timing.get("end_iso"),
        }

        try:
            review_log.append_run_event(
                "pack",
                {
                    "run_name": rdir.name,
                    "model_id": model_id,
                    "pack_id": pack_id,
                    "case_id": case_id,
                    "end_iso": timing.get("end_iso"),
                    "endToEndSeconds": timing.get("endToEndSeconds"),
                    "code_sha256": proto.get("code_sha256"),
                    "storyboard_panels": sb_data["panel_count"],
                },
                log_path=args.runs_log,
            )
        except Exception:
            pass

    manifest = {
        "schema_version": 2,
        "benchmark_version": "xiaonuo-v4.0",
        "pack_id": pack_id,
        "blind": True,
        "rubric": "RUBRIC.md",
        "cases": cases,
    }
    (pack_dir / "pack.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    submit_md = f"""# 提交盲评打分

请在完整查看 `STORYBOARD.md`（及 `storyboard/*.png` 截图）与 `code/` 源码后，对每个 `case-XX` 执行一次提交命令（加锁原子追加至中心日志，绝不回显他人评分）：

```sh
python src/scoring/judge_submit.py \\
  --pack-dir "{pack_dir}" \\
  --case-id case-01 \\
  --judge-id <你的评委唯一ID，如 judge-alpha> \\
  --judge-model <你的模型标识，如 claude-opus-4> \\
  --D1 <0-10> --D2 <0-10> --D3 <0-10> \\
  --evidence "[S01][S03][S07][S08][S10] + [code/xxx.js:Lxx]" \\
  --note "<指出该作品的最强反证/核心视觉、异步交互或代码工程短板>"
```

若使用过 `tools/judge_probe.py` 进行靶向补测，提交前请确保清空 `draft/` 目录。同一 `judge-id` 对同一 case 的重复提交将被拒绝。
"""
    (pack_dir / "SUBMIT.md").write_text(submit_md, encoding="utf-8")

    map_path = blind_maps_dir / f"{model_id}.{pack_id}.blind-map.json"
    map_obj = {
        "model": raw_model,
        "model_id": model_id,
        "pack_id": pack_id,
        "created_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "cases": mapping_cases,
    }
    map_path.write_text(json.dumps(map_obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("================================================================")
    print("选手收尾完成！计时已冻结，《痛点场景连环画》匿名盲评包已生成。")
    print(f"  规范模型 ID  : {model_id}")
    print(f"  匿名盲评包   : {pack_dir}")
    print(f"  包内案例数   : {len(cases)} ({', '.join(c['case_id'] for c in cases)})")
    print(f"  私有映射文件 : {map_path}（严禁交给评委！）")
    print("----------------------------------------------------------------")
    print("【下一步交接说明】")
    print(f"  1. 请仅将匿名包路径 `{pack_dir}` 交给独立评委进行盲评；")
    print("  2. 评委全部提交后，再运行 `python leaderboard/finalize.py` 现场拉起三波浏览器剧本定稿出榜。")
    print("================================================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
