#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""评委靶向无头补测工具（tools/judge_probe.py）。

设计背景（对齐《构建与设计说明》第四节·第三步）：
  严禁评委开启全屏桌面视觉操控（Computer Use）自由乱点；但当评委在审阅脱敏源码时，
  发现选手实现了静态 10 张连环画未能覆盖的特色痛点交互（如快捷键唤起命令面板、抽屉快速预览、
  文章对比视图等），可通过本轻量级无头浏览器工具对盲评包内的脱敏网页执行确定性操作并截图验证。

安全边界：
  - 仅允许打开盲评包案例目录（含 pack.json 的父目录）下的 code/index.html；
  - 强制阻断全部外网请求；
  - 补测截图默认输出至 draft/probe_*.png（提醒：评委提交完评分收工前请清空 draft/）。

用法示例：
    python tools/judge_probe.py --case-dir leaderboard/blind/<pack_id>/case-01 \\
        --viewport 1440x900 --press "Control+k" --out draft/probe_cmd.png
    python tools/judge_probe.py --case-dir leaderboard/blind/<pack_id>/case-01 \\
        --click "[data-testid='project-open']" --scroll-y 300 --eval "document.activeElement?.tagName"
"""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser(description="评委专用：对匿名盲评包内脱敏网页执行轻量级靶向无头补测与截图")
    ap.add_argument("--case-dir", required=True, help="盲评包内的案例目录，如 leaderboard/blind/<pack_id>/case-01")
    ap.add_argument("--viewport", default="1440x900", help="视口宽高，格式如 1440x900 或 375x812")
    ap.add_argument("--theme", choices=("light", "dark"), default="light", help="系统模拟配色偏好")
    ap.add_argument("--click", action="append", default=[], help="按顺序点击的 CSS 选择器（可多次传入）")
    ap.add_argument("--fill", action="append", default=[], help="填充输入框，格式 selector=value（可多次传入）")
    ap.add_argument("--press", action="append", default=[], help="发送键盘按键，如 Escape、Tab、Control+k（可多次传入）")
    ap.add_argument("--scroll-y", type=int, default=None, help="窗口纵向滚动到的像素高度")
    ap.add_argument("--eval", dest="eval_js", default=None, help="在页面内执行的只读 JS 诊断表达式")
    ap.add_argument("--out", default=str(ROOT / "draft" / "judge_probe.png"), help="截图保存路径（默认 draft/judge_probe.png）")
    args = ap.parse_args()

    case_dir = Path(args.case_dir).resolve()
    pack_json = case_dir.parent / "pack.json"
    index_html = case_dir / "code" / "index.html"
    if not pack_json.exists() or not index_html.exists():
        print("拒绝执行：--case-dir 必须指向合法匿名盲评包内的案例目录（父目录须含 pack.json 且内含 code/index.html）。")
        return 1

    try:
        vw_s, vh_s = args.viewport.lower().split("x", 1)
        vw, vh = int(vw_s), int(vh_s)
    except Exception:
        print(f"非法 --viewport 格式：{args.viewport}（期望如 1440x900）")
        return 1

    from playwright.sync_api import sync_playwright

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    action_log: list[str] = []
    eval_result = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": vw, "height": vh}, color_scheme=args.theme)
        context.route(
            "**/*",
            lambda route: route.abort()
            if route.request.url.startswith(("http://", "https://", "ws://", "wss://"))
            else route.continue_(),
        )
        page = context.new_page()
        page.goto(index_html.as_uri(), wait_until="domcontentloaded")
        try:
            page.wait_for_function(
                """() => {
                    if (document.documentElement.getAttribute('data-unimplemented') === 'true') return true;
                    return document.querySelectorAll("[data-testid='project-card']").length >= 1;
                }""",
                timeout=2200,
            )
        except Exception:
            pass
        page.wait_for_timeout(160)

        for item in args.fill:
            if "=" not in item:
                continue
            sel, val = item.split("=", 1)
            loc = page.locator(sel.strip()).first
            loc.fill(val)
            page.wait_for_timeout(320)
            action_log.append(f"fill({sel.strip()!r}, {val!r})")

        for sel in args.click:
            loc = page.locator(sel.strip()).first
            loc.click(timeout=3000)
            page.wait_for_timeout(280)
            action_log.append(f"click({sel.strip()!r})")

        for key in args.press:
            page.keyboard.press(key.strip())
            page.wait_for_timeout(120)
            action_log.append(f"press({key.strip()!r})")

        if args.scroll_y is not None:
            page.evaluate(f"window.scrollTo(0, {int(args.scroll_y)})")
            page.wait_for_timeout(120)
            action_log.append(f"scrollTo(0, {int(args.scroll_y)})")

        if args.eval_js:
            eval_result = page.evaluate(args.eval_js)

        page.screenshot(path=str(out_path), full_page=False)
        scroll_y_now = page.evaluate("Math.round(window.scrollY)")
        browser.close()

    report = {
        "case": case_dir.name,
        "viewport": f"{vw}x{vh}",
        "theme": args.theme,
        "actions": action_log,
        "scroll_y": scroll_y_now,
        "eval_result": eval_result,
        "screenshot": str(out_path),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("\n提示：评委提交打分完毕后，请记得删除 draft/ 下的临时补测截图以通过隔离审计。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
