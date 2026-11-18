#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""选手收尾与《痛点场景连环画》匿名盲评包生成工具 v4.0（src/scoring/judge_pack.py）。

核心职责：
1. 严格校验沙盒内的 `mock_backend.js` 与官方只读版本 SHA-256 完全一致，杜绝篡改后端数据或延迟作弊；
2. 若运行尚未冻结结束时间，自动打下结束时间戳 t1（end_iso），锁定 B2 端到端墙钟耗时并固化沙盒代码承诺 code_sha256；
3. 将沙盒内的网页源码与《交互设计与维护说明》（DECISIONS.md）彻底脱敏（抹除模型真名、运行目录名、系统用户名与本机绝对路径），`mock_backend.js` 原样保留只读副本；
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
TEMPLATE_STATIC_FILES = {"TASK.md", "CONTRACT.md", "smoke_public.py"}
FORBIDDEN_NAMES = {"评分.json", "result.json", "protocol.json", "wave_trace.jsonl", "audit_report.md", "token_usage.json"}
TEXT_CODE_SUFFIXES = {".html", ".htm", ".css", ".js", ".mjs", ".json", ".md", ".svg", ".txt", ".xml"}


def _epoch(iso: str) -> float:
    return datetime.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def _sanitize_text(text: str, tokens_to_redact: list[str]) -> str:
    out = text
    out = re.sub(r"[A-Za-z]:[\\/][^\s\"'`<>|]+", "<REDACTED_PATH>", out)
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

欢迎进入《创作者主页与异步顾问工作台 · 前端可用性与工程体验基准（xiaonuo-v4.0）》D 层盲评！本目录是你作为**独立评委**的**唯一合法输入**。

## 评委三步取证盲评法（严格执行）

1. **第一步：先读量表与 12 格《交互状态连环画》**
   - 阅读同目录 [`RUBRIC.md`](RUBRIC.md)，明确 D1（11分）、D2（10分）、D3（9分）的定档锚点、反端水铁律与硬伤重扣红线；
   - 打开 `case-XX/STORYBOARD.md`，**逐张实际查看 `case-XX/storyboard/S01..S12.png` 真实画面**及客观物理状态批注（含 `[S03]` 原生 SVG 多维对比图及文字包围盒重叠对数、`[S07]` 异步排期与繁忙冲突视觉反馈、`[S08]–[S10]` 冲突消解、方案带入、即时消错及 `503 SERVICE_BUSY` 瞬态异常恢复与正式回执号落盘）。
2. **第二步：结合脱敏源码与《交互设计与维护说明》双重取证**
   - 阅读 `case-XX/OVERVIEW.md`、`case-XX/DECISIONS.md` 与 `case-XX/code/` 下的完整前端代码（`mock_backend.js` 为官方统一只读后端，重点审阅选手编写的 HTML/CSS/JS）；
   - 核查选手是否真实通过 `window.LincheMockAPI` 驱动视图、如何用 `AbortController` 或递增请求序号根治异步竞态覆盖、以及如何在不丢失已填内容的前提下优雅消化并发提交与 `503` 瞬态繁忙；
   - **必做诚实度核验**：逐条核实 `DECISIONS.md` 第 4 节的 **5 条核心声明（C1–C5）** 在 `code/` 中是否真实落地。
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

    rubric_md = """# D 层视觉审美、异步工作台体贴度与前端工程思想盲评量表（v4.0 · 满分 30 分）

> **核心定档与反端水铁律**：
> - **绝不温和折中**：严禁把有明显视觉粗糙、异步交互生硬或工程竞态漏洞的作品扎堆打在 7.5～8.5 的“安全区”。必须先按硬伤直接降档，再看自发设计亮点。
> - **5 级（满分的 50% 左右）是“只把接口勉强接通、界面像简陋后台表单、面对冲突/报错/空结果毫无自发体贴设计”的封顶线！**
> - 由于 `TASK.md` 与 `CONTRACT.md` 已全面移除具体 UI 标准答案剧透，只有**面对开放业务痛点能主动设计出优雅解法、版式审美耐看、且异步状态机严丝合缝**的作品，才允许给到 **8.2～9.6+ 级**。
> - 支持小数（如 `8.6`），必须在 `--evidence` 中写明**连环画截图编号（`[S01]`–`[S12]`）+ 源码文件名与行号/函数名 + `DECISIONS.md` C1–C5 核验结论**。

---

## D1 视觉审美、SVG 多维对比与沉浸阅读心流（0–11 分）
聚焦**整体现代编辑感审美（`[S01]/[S11]/[S12]`）**、**痛点一（来回翻找与 SVG 多维对比 `[S02]/[S03]`）**与**痛点三（长文与表格代码阅读 `[S05]/[S06]`）**：
- **8.8–11.0（出色）**：
  - `[S01]/[S11]/[S12]` 具备成熟的独立研究者主页与专业顾问工具质感：留白节奏、字号层级、卡片微质感与深浅色表面层次协调克制；
  - `[S02]` 异步详情返回列表精准恢复滚动高度（`Y1≈Y2`）与原筛选态；`[S03]` 横向对比面板既有对齐易读的多方案表格，又有**几何比例准确、轴标签零重叠（`overlapPairs = 0`）、图例配色高辨识度的原生 `<svg>` 多维量化对比图**；
  - `[S05]/[S06]` 长文行宽舒适（60–75 字宽），数据表格、代码块与引用块排版考究，滚至中段目录自动跟随高亮且具备阅读位置感知，手机窄屏表格/代码块顺滑局部横滑而不撑破页面。
- **5.0–8.7（达标至良好）**：
  - 若返回列表丢失滚动高度跳回顶部（`|Y2 - Y1| > 200px`，扣 1.2～2.2 分）、`[S03]` SVG 轴标签重叠挤压（`overlapPairs > 0`，扣 1.2～2.0 分）或纯装饰假图（重扣 2.0 分）、长文 50% 处目录滚出视口或无高亮跟随（扣 1.2～1.8 分）、或手机端顶栏/对比浮动条挤压遮挡正文（扣 1.5～2.0 分），视版式精细度在 5.0–7.5 分定档；视觉干净且仅有个别次要细节短板的给 7.6–8.7 分。
- **0.0–4.9（薄弱）**：
  - 版面粗糙拥挤、深色模式刺眼或局部漏改白底、SVG/表格撑破错位、返回丢状态，或页面未完成。

---

## D2 异步过渡稳定性、档期冲突自发解法与异常恢复体贴度（0–10 分）
聚焦**异步加载/检索/算价的过渡体验**、**痛点二（空结果受挫 `[S04]`）**、**耦合排期冲突的自发交互解法（`[S07]`）**与**痛点四（耦合带入、校验消错、503 繁忙恢复与复制反馈 `[S08]/[S09]/[S10]`）**：
- **8.0–10.0（出色）**：
  - 异步请求期间具备平滑克制的加载态（骨架屏、局部微指示或保留旧内容半透明过渡），杜绝整块高度坍塌闪烁；搜索具备防抖、显式清空按钮与中文输入法 `compositionstart/compositionend` 保护，`[S04]` 空结果主动提供清晰的恢复动作与有效建议词；
  - `[S07]→[S08]` 在无剧透提示下，**主动可视化 14 周忙闲日历或繁忙周原因，并提供直观的一键顺延/推荐空闲周交互**；跨模块撤销/重做入口清晰且不劫持输入框打字撤销；将规划方案带入联系单时，**非破坏性合并对比项目与排期摘要，完好保留访客已写附注**；
  - `[S08]→[S09]→[S10]` 杜绝原生 `alert()`，字段级就地报错并聚焦首个错项，`[S09]` 改对瞬间自动消错；面对 `submitInquiry` 首轮 `503 SERVICE_BUSY` 瞬态繁忙，**完好保留全部已填表单内容并提供清晰重试反馈或优雅退避重试**，拿到真实 `INQ-2026-XXXX` 回执，点击复制 100ms 内给出瞬时确认反馈。
- **4.5–7.9（达标至良好）**：
  - 异步切换时列表或报价区剧烈闪白坍塌（扣 1.0～1.5 分）、缺少输入法拼字保护（扣 0.9 分且封顶 ≤ 7.9 分）、缺少搜索清空按钮或空状态无实质恢复出路（扣 1.0～1.5 分）、遇到繁忙周只冷冰冰报错而不给顺延引导（扣 1.2～1.8 分）、带入方案粗暴覆盖原有留言（重扣 1.5～2.2 分）、`503` 报错生硬或无防止连点重入锁（扣 1.2～1.8 分）。只做通基本表单提交的封顶 **5.2 分**。
- **0.0–4.4（薄弱）**：
  - 原生弹窗报错、绕过后端伪造假回执单号、503 报错导致用户输入清空，或空搜索死胡同。

---

## D3 异步竞态控制、状态机解耦与工程诚实度（0–9 分）
考察前端异步竞态防护、跨模块命令历史栈、视图与状态分层质量，以及**《DECISIONS.md》与实际源码的逐行诚实一致性**：
- **必做核查 1（异步竞态与并发控制审查）**：检查源码对 `queryCatalog`、`getDetail`、`evaluatePlan` 是否实现了可靠的 **`AbortController` 取消或单调递增请求令牌（Request Seq ID）校验**，对 `submitInquiry` 是否具备飞行中防重入锁（`inFlight` lock）。缺失竞态防护导致慢请求可能覆盖新状态的，直接扣 **1.5～2.5 分**。
- **必做核查 2（数据源真实性与单点配置追踪）**：检查是否严格以 `window.LincheMockAPI` 作为唯一业务数据源（若在前端硬编码抄写项目/文章/报价公式绕过接口，**D3 直接封顶 ≤ 2.5 分**）；追踪 `DECISIONS.md` 说明的主题色与 UI 常量是否单点可维护。
- **必做核查 3（5 条核心声明诚实度核验）**：逐条核实 `DECISIONS.md` 第 4 节 `C1–C5` 在 `code/` 中是否真实存在：
  - **硬性封顶红线 1**：未填写 `DECISIONS.md`（或保留模板占位符）的，**D3 ≤ 2.0 分**；
  - **硬性封顶红线 2**：核验发现 **2 条及以上**声明在源码中未实现、假实现或夸大吹牛的，**D3 ≤ 4.0 分**；
  - **硬性封顶红线 3**：存在无限空转 `rAF` 循环、对比弹窗无双向焦点锁、输入框 `Ctrl+Z` 被全局劫持的，每项扣 1.2～2.0 分。
- **7.4–9.0（出色）**：异步取消/序号防护严密、不可变状态快照/历史栈边界清晰、零冗余依赖，`DECISIONS.md` 定位精准且 C1–C5 100% 属实。
- **4.5–7.3（达标至良好）**：声明属实且接通真实接口，但部分异步链路缺少乱序防护、状态耦合散落或文档说明笼统。

---

## 提交输出硬性要求
1. `--evidence`：**同时引用连环画编号（如 `[S01][S03][S07][S08][S10]`）+ 具体源码文件与行号/函数名 + `DECISIONS.md` C1–C5 逐条核验结论**；
2. `--note`：**明确指出该作品的“最强反证 / 最突出的视觉、异步交互或工程短板”**。
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
        decisions_content = "# 缺失 DECISIONS.md\n\n该选手未提交《交互设计与维护说明》。\n"
        decisions_filled = False

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
            if rel_posix == "DECISIONS.md":
                raw_text = src_file.read_text(encoding="utf-8", errors="replace")
                decisions_content = _sanitize_text(raw_text, tokens_to_redact)
                decisions_filled = ("（请填写）" not in decisions_content) and (len(decisions_content.strip()) > 200)
                continue

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

        (case_dir / "DECISIONS.md").write_text(decisions_content, encoding="utf-8")

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
            f"- **《交互设计与维护说明》状态**：{'已填写（请打开 DECISIONS.md 审阅并核实 C1–C5 五条源码声明）' if decisions_filled else '⚠️ 疑似保留空白模板或未完整填写（请打开 DECISIONS.md 核实，属实按 RUBRIC 红线封顶处理）'}",
            f"- **官方只读后端 `mock_backend.js` 校验**：已通过 SHA-256 一致性校验",
            f"- **选手自写前端代码行数（不含官方 `mock_backend.js`）**：{contestant_lines} 行",
            "",
            "## 包内文件清单",
            "",
            "| 路径 | 行数 / 说明 |",
            "| --- | ---: |",
            f"| `STORYBOARD.md` | {len(sb_md_text.splitlines())} 行（含 `{sb_data['panel_count']}` 张截图索引与客观物理批注） |",
            f"| `DECISIONS.md` | {len(decisions_content.splitlines())} 行 |",
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
                "decisions": f"{case_id}/DECISIONS.md",
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

请在完整查看 `STORYBOARD.md`（及 `storyboard/*.png` 截图）、`DECISIONS.md` 与 `code/` 源码后，对每个 `case-XX` 执行一次提交命令（加锁原子追加至中心日志，绝不回显他人评分）：

```sh
python src/scoring/judge_submit.py \\
  --pack-dir "{pack_dir}" \\
  --case-id case-01 \\
  --judge-id <你的评委唯一ID，如 judge-alpha> \\
  --judge-model <你的模型标识，如 claude-opus-4> \\
  --D1 <0-11> --D2 <0-10> --D3 <0-9> \\
  --evidence "[S01][S03][S07][S08][S10] + [code/xxx.js:Lxx] + [DECISIONS C1-C5 核验结论]" \\
  --note "<指出该作品的最强反证/核心视觉、异步交互或工程短板>"
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
