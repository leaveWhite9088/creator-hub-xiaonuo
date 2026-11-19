#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""选手一键开局工具（tools/start_run.py）：记录起点时钟 t0、固化评测环境哈希承诺，并释放专属前端沙盒。

用法：
    python tools/start_run.py --model <模型标识> [--t0 <ISO时间>] [--force]

执行后将在 runs/<模型标识>/workspace/ 下生成选手专属沙盒（含 TASK.md、CONTRACT.md 与 smoke_public.py）。
被测试者随后应立即进入该沙盒目录开展工作，严禁读取上级评测实现或其他运行目录。
"""
from __future__ import annotations

from pathlib import Path
import argparse
import datetime
import hashlib
import json
import shutil
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src" / "scoring"))

from model_identity import canonical_model_id, sanitize_run_name  # noqa: E402
import review_log  # noqa: E402

PROTECTED_FILES = (
    "src/sandbox_template/mock_backend.js",
    "src/scoring/metrics.py",
    "src/scoring/dom_probes.py",
    "src/scoring/browser_waves.py",
    "src/scoring/score_run.py",
)


def compute_mock_backend_sha256(root: Path = ROOT) -> str:
    """计算官方只读模拟后端脚本（mock_backend.js）的规范化 SHA-256 哈希。"""
    p = root / "src" / "sandbox_template" / "mock_backend.js"
    if not p.exists():
        return ""
    norm = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest()


def verify_file_matches_mock_backend(candidate: Path, root: Path = ROOT) -> bool:
    """校验沙盒或盲评包内的 mock_backend.js 是否与官方只读原件完全一致。"""
    expected = compute_mock_backend_sha256(root)
    if not expected or not candidate.is_file():
        return False
    actual = hashlib.sha256(candidate.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    return actual == expected


def compute_env_commit(root: Path = ROOT) -> str:
    """对客观层配置（A/B/C，剔除 D 层与连环画配置）及三波浏览器客观评测脚本计算联合 SHA-256 承诺。
    修改 D 层盲评量表、盲评脚本或汇总排版不会改变该指纹，避免客观分缓存被误作废。
    """
    h = hashlib.sha256()
    cfg_path = root / "configs" / "benchmark.json"
    h.update(b"configs/benchmark.json#objective\0")
    if cfg_path.exists():
        try:
            cfg_obj = json.loads(cfg_path.read_text(encoding="utf-8"))
            cfg_copy = dict(cfg_obj)
            cfg_copy.pop("storyboard", None)
            if isinstance(cfg_copy.get("scoring"), dict):
                sc_copy = dict(cfg_copy["scoring"])
                sc_copy.pop("D", None)
                cfg_copy["scoring"] = sc_copy
            norm_cfg = json.dumps(cfg_copy, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            h.update(hashlib.sha256(norm_cfg).digest())
        except Exception:
            norm = cfg_path.read_bytes().replace(b"\r\n", b"\n")
            h.update(hashlib.sha256(norm).digest())
    else:
        h.update(b"MISSING")

    for rel in PROTECTED_FILES:
        p = root / rel
        h.update(rel.encode("utf-8") + b"\0")
        if p.exists():
            norm = p.read_bytes().replace(b"\r\n", b"\n")
            h.update(hashlib.sha256(norm).digest())
        else:
            h.update(b"MISSING")
    return h.hexdigest()


def compute_workspace_sha256(workspace_dir: Path) -> str:
    """对沙盒前端文件与说明文档计算确定性哈希（忽略缓存与临时日志）。"""
    skip_dirs = {"__pycache__", ".pytest_cache", ".git"}
    skip_suffixes = {".pyc", ".pyo", ".log", ".tmp"}
    h = hashlib.sha256()
    files = []
    for p in workspace_dir.rglob("*"):
        if not p.is_file():
            continue
        if any(part in skip_dirs for part in p.relative_to(workspace_dir).parts):
            continue
        if p.suffix.lower() in skip_suffixes:
            continue
        files.append(p)
    for p in sorted(files, key=lambda x: x.relative_to(workspace_dir).as_posix()):
        rel = p.relative_to(workspace_dir).as_posix()
        raw = p.read_bytes()
        if p.suffix.lower() in {".html", ".htm", ".css", ".js", ".mjs", ".json", ".md", ".svg", ".txt", ".py"}:
            raw = raw.replace(b"\r\n", b"\n")
        h.update(rel.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest() + b"\n")
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="初始化选手独立前端沙盒并启动端到端计时")
    ap.add_argument("--model", required=True, help="运行标识或模型名称，如 deepseek-v4.1-flash")
    ap.add_argument("--t0", default=None, help="可选外部传入起始 ISO 时间戳；缺省自动取当前系统时间")
    ap.add_argument("--runs-dir", default=str(ROOT / "runs"), help="运行根目录（默认 runs/）")
    ap.add_argument("--runs-log", default=None, help="可选：自定义运行生命周期日志路径")
    ap.add_argument("--force", action="store_true", help="若同名运行目录已存在则强制清空重建")
    args = ap.parse_args()

    try:
        run_name = sanitize_run_name(args.model)
    except ValueError as e:
        print(f"开局失败：{e}")
        return 1

    model_id = canonical_model_id(run_name)
    runs_root = Path(args.runs_dir).resolve()
    run_dir = runs_root / run_name
    workspace_dir = run_dir / "workspace"
    template_dir = ROOT / "src" / "sandbox_template"

    if not template_dir.exists():
        print(f"找不到沙盒模板目录：{template_dir}")
        return 1

    if run_dir.exists():
        if not args.force:
            print(f"运行目录已存在：{run_dir}")
            print("如需重开覆盖，请显式传入 --force；否则请直接继续在该目录的 workspace/ 中开发。")
            return 1
        shutil.rmtree(run_dir)

    run_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        template_dir,
        workspace_dir,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )

    now_iso = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    if args.t0:
        try:
            datetime.datetime.fromisoformat(args.t0.replace("Z", "+00:00"))
        except ValueError as e:
            print(f"--t0 不是合法 ISO-8601 时间：{e}")
            return 1
        t0_iso = args.t0
        t0_source = "external"
    else:
        t0_iso = now_iso
        t0_source = "process"

    cfg = json.loads((ROOT / "configs" / "benchmark.json").read_text(encoding="utf-8"))
    env_commit = compute_env_commit(ROOT)
    template_sha = compute_workspace_sha256(workspace_dir)
    mock_sha = compute_mock_backend_sha256(ROOT)

    protocol = {
        "schema_version": 1,
        "benchmark": cfg.get("name", "creator-hub-xiaonuo"),
        "version": cfg.get("version", "xiaonuo-v4.0"),
        "run_name": run_name,
        "model_id": model_id,
        "status": "in_progress",
        "env_commit": env_commit,
        "mock_backend_sha256": mock_sha,
        "template_sha256": template_sha,
        "code_sha256": None,
        "timing": {
            "t0_iso": t0_iso,
            "process_iso": now_iso,
            "t0_source": t0_source,
            "end_iso": None,
            "endToEndSeconds": None,
        },
    }
    (run_dir / "protocol.json").write_text(json.dumps(protocol, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    token_template = {
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "source": "self_report",
        "note": "收尾打包前请填入宿主累计 token 消耗；若宿主无法获取请保留 null 并说明原因",
    }
    (run_dir / "token_usage.json").write_text(
        json.dumps(token_template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    try:
        review_log.append_run_event(
            "start",
            {
                "run_name": run_name,
                "model_id": model_id,
                "t0_iso": t0_iso,
                "t0_source": t0_source,
                "workspace": str(workspace_dir),
            },
            log_path=args.runs_log,
        )
    except Exception:
        pass

    print("================================================================")
    print("开局成功！端到端开发计时已启动。")
    print(f"  运行标识   : {run_name}（规范模型 ID: {model_id}）")
    print(f"  起点时间 t0: {t0_iso} (source={t0_source})")
    print(f"  专属沙盒   : {workspace_dir}")
    print("----------------------------------------------------------------")
    print("【被测试者下一步行动清单】")
    print(f"  1. 进入你的专属沙盒：{workspace_dir}")
    print("  2. 只阅读沙盒内的 TASK.md（开发提示词）与 CONTRACT.md（离线打开与基础 data-testid 契约）")
    print("  3. 在沙盒内完成 index.html（及可选本地样式/脚本文件）开发，确保断网双击直开")
    print(f"  4. 运行公开连通性冒烟检查：python {workspace_dir / 'smoke_public.py'}")
    print(f"  5. 在 {run_dir / 'token_usage.json'} 填入词元消耗自报记录")
    print(f"  6. 收工冻结计时并抓拍连环画生成匿名包：python src/scoring/judge_pack.py --model {run_name}")
    print("【隔离红线】严禁读取 docs/、configs/、src/、leaderboard/、构建与设计说明.md 或其他 runs/ 目录！")
    print("================================================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
