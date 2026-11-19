#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""选手沙盒公开基础连通性冒烟检查脚本（smoke_public.py · v4.0）。

用途：
  帮助被测试者快速核验本地 workspace/index.html 能否在断网 file:// 协议下正常打开、
  mock_backend.js 是否保持只读未篡改、是否真实调用 window.LincheMockAPI 加载首屏数据，
  以及 CONTRACT.md 规定的基础结构锚点是否齐全。

注意：
  本脚本仅检查最基础的静态与首屏连通性，不涉及异步乱序竞态压测、长短排期冲突消解、
  撤销重做边界、并发提交锁与 503 故障恢复、多视口几何防遮挡或对比度审计。
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 官方只读 mock_backend.js 规范化换行后的 SHA-256（若被选手改动则冒烟直接报警）
EXPECTED_MOCK_BACKEND_SHA256 = "8e1ec5f523b89bd5796db373135bae7e9fd07f404a3c8d10360b149ca231e94d"


def _norm_sha256(p: Path) -> str:
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    here = Path(__file__).resolve().parent
    index_path = here / "index.html"
    mock_path = here / "mock_backend.js"
    if not index_path.exists():
        print(f"[FAIL] 找不到入口文件：{index_path}")
        return 1
    if not mock_path.exists():
        print(f"[FAIL] 缺少官方模拟后端文件（严禁删除）：{mock_path}")
        return 1

    if EXPECTED_MOCK_BACKEND_SHA256 != "__AUTO_VERIFIED_OR_FALLBACK__":
        actual_mock_sha = _norm_sha256(mock_path)
        if actual_mock_sha != EXPECTED_MOCK_BACKEND_SHA256:
            print("[FAIL] 检测到 mock_backend.js 内容被修改！请恢复官方只读原件，严禁篡改模拟后端。")
            return 1

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[FAIL] 当前 Python 环境未安装 playwright，无法执行浏览器冒烟检查。")
        return 1

    blocked_urls: list[str] = []
    page_errors: list[str] = []
    failures: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})

        def _handle_route(route):
            url = route.request.url
            if url.startswith(("http://", "https://", "ws://", "wss://")):
                blocked_urls.append(url)
                route.abort()
            else:
                route.continue_()

        context.route("**/*", _handle_route)
        page = context.new_page()
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        file_url = index_path.as_uri()
        page.goto(file_url, wait_until="domcontentloaded")

        # 等待异步首屏接口 getBootstrap / queryCatalog / evaluatePlan 完成首轮渲染
        try:
            page.wait_for_function(
                """() => {
                    if (document.documentElement.getAttribute('data-unimplemented') === 'true') return true;
                    const pCnt = document.querySelectorAll("[data-testid='project-card']").length;
                    const aCnt = document.querySelectorAll("[data-testid='article-card']").length;
                    return pCnt >= 4 && aCnt >= 4;
                }""",
                timeout=2500,
            )
        except Exception:
            pass
        page.wait_for_timeout(150)

        unimpl = page.evaluate("() => document.documentElement.getAttribute('data-unimplemented')")
        if unimpl == "true":
            print("[FAIL] index.html 仍保留初始占位属性 data-unimplemented='true'，尚未完成开发。")
            browser.close()
            return 1

        if blocked_urls:
            failures.append(f"检测到禁止的外网请求（共 {len(blocked_urls)} 处）：{blocked_urls[:3]}")
        if page_errors:
            failures.append(f"页面运行出现未捕获 JS 异常：{page_errors[:3]}")

        telemetry = page.evaluate(
            "() => (window.LincheMockAPI && typeof window.LincheMockAPI.getTelemetry === 'function') ? window.LincheMockAPI.getTelemetry() : null"
        )
        if not telemetry:
            failures.append("未加载官方 mock_backend.js（找不到 window.LincheMockAPI）")
        else:
            if telemetry.get("bootstrapCalls", 0) < 1 and telemetry.get("queryCalls", 0) < 1:
                failures.append("首屏未调用 window.LincheMockAPI 接口获取数据（严禁在前端静态硬编码绕过后端接口）")

        required_single = [
            "hero-section",
            "theme-toggle",
            "demo-notice",
            "workbench-undo",
            "workbench-redo",
            "search-input",
            "category-filter",
            "favorite-filter",
            "sort-control",
            "project-list",
            "article-list",
            "estimator-section",
            "est-scale",
            "est-start-week",
            "est-result",
            "est-milestones",
            "est-reset",
            "est-apply-to-contact",
            "contact-section",
            "contact-name",
            "contact-email",
            "contact-message",
            "contact-submit",
        ]
        for tid in required_single:
            if page.locator(f"[data-testid='{tid}']").count() < 1:
                failures.append(f"缺少结构锚点：[data-testid='{tid}']")

        proj_cnt = page.locator("[data-testid='project-card']").count()
        if proj_cnt < 4:
            failures.append(f"异步加载后项目卡片数量不足 4 份（当前检测到 {proj_cnt} 份）")

        cmp_cnt = page.locator("[data-testid='compare-toggle']").count()
        if cmp_cnt < 4:
            failures.append(f"项目卡片 compare-toggle 按钮不足 4 个（当前检测到 {cmp_cnt} 个）")

        art_cnt = page.locator("[data-testid='article-card']").count()
        if art_cnt < 4:
            failures.append(f"异步加载后长文卡片数量不足 4 篇（当前检测到 {art_cnt} 篇）")

        cat_cnt = page.locator("[data-testid='category-option']").count()
        if cat_cnt < 4:
            failures.append(f"分类筛选项不足 4 个（当前检测到 {cat_cnt} 个）")

        est_types = page.locator("[data-testid='est-type']").count()
        if est_types < 3:
            failures.append(f"合作模式 est-type 不足 3 项（当前检测到 {est_types} 项）")

        est_addons = page.locator("[data-testid='est-addon']").count()
        if est_addons < 3:
            failures.append(f"附加交付模块 est-addon 不足 3 项（当前检测到 {est_addons} 项）")

        week_slots = page.evaluate(
            """() => {
                const el = document.querySelector("[data-testid='est-start-week']");
                if (!el) return 0;
                if (el.tagName === 'SELECT') return el.options.length;
                const btns = el.querySelectorAll("[data-week], button, [role='radio'], [role='option']");
                return btns.length;
            }"""
        )
        if week_slots < 4:
            failures.append(f"期望启动周 est-start-week 可选档位不足 4 个（当前检测到 {week_slots} 个）")

        # 连通验证 1：对比面板与原生 SVG 元素
        if cmp_cnt >= 2:
            page.locator("[data-testid='compare-toggle']:visible").nth(0).click()
            page.locator("[data-testid='compare-toggle']:visible").nth(1).click()
            page.wait_for_timeout(140)
            if page.locator("[data-testid='compare-bar']:visible").count() < 1:
                failures.append("勾选对比项后，[data-testid='compare-bar'] 未可见显示")
            else:
                open_cmp = page.locator("[data-testid='compare-open']:visible")
                if open_cmp.count() < 1:
                    failures.append("对比栏缺少可见的 [data-testid='compare-open'] 按钮")
                else:
                    open_cmp.first.click()
                    page.wait_for_timeout(160)
                    if page.locator("[data-testid='compare-panel']:visible").count() < 1:
                        failures.append("点击 compare-open 后，[data-testid='compare-panel'] 未可见显示")
                    else:
                        svg_cnt = page.locator("svg[data-testid='compare-chart']:visible, [data-testid='compare-panel'] svg[data-testid='compare-chart']").count()
                        if svg_cnt < 1:
                            failures.append("对比面板内缺少原生矢量图 svg[data-testid='compare-chart']")
                    close_cmp = page.locator("[data-testid='compare-close']:visible")
                    if close_cmp.count() > 0:
                        close_cmp.first.click()
                        page.wait_for_timeout(100)
            clr_cmp = page.locator("[data-testid='compare-clear']:visible")
            if clr_cmp.count() > 0:
                clr_cmp.first.click()
                page.wait_for_timeout(80)

        # 连通验证 2：异步打开第一篇长文详情并返回
        if art_cnt >= 1:
            first_art = page.locator("[data-testid='article-card']").first
            open_btn = first_art.locator("[data-testid='article-open']")
            target = open_btn.first if open_btn.count() > 0 else first_art
            target.click()
            try:
                page.wait_for_function(
                    """() => {
                        const dv = document.querySelector("[data-testid='detail-view']");
                        const db = document.querySelector("[data-testid='detail-body']");
                        return dv && dv.offsetParent !== null && db && (db.innerText || '').trim().length >= 50;
                    }""",
                    timeout=1800,
                )
            except Exception:
                page.wait_for_timeout(280)

            detail = page.locator("[data-testid='detail-view']")
            if detail.count() < 1 or not detail.first.is_visible():
                failures.append("点击第一篇文章后，[data-testid='detail-view'] 未可见显示")
            else:
                for sub_tid in ("detail-title", "detail-body", "detail-back", "article-toc"):
                    if page.locator(f"[data-testid='{sub_tid}']").count() < 1:
                        failures.append(f"文章详情视图缺少结构锚点：[data-testid='{sub_tid}']")
                back_btn = page.locator("[data-testid='detail-back']").first
                if back_btn.count() > 0 and back_btn.is_visible():
                    back_btn.click()
                    page.wait_for_timeout(120)

        browser.close()

    if failures:
        print("==================================================")
        print(f"[SMOKE FAILED] 发现 {len(failures)} 项基础连通问题：")
        for item in failures:
            print(f"  - {item}")
        print("==================================================")
        return 1

    print("==================================================")
    print("[SMOKE PASSED] 离线 file:// 与本地异步后端连通正常，基础结构锚点校验通过！")
    print(f"  已检测项目卡: {proj_cnt} 份 | 文章卡: {art_cnt} 篇 | 启动档期: {week_slots} 个 | 外网请求: 0")
    print("  提示：本脚本仅覆盖基础连通性，请继续全面检查异步竞态、排期冲突处理、撤销历史、表单提交容错、窄屏排版与深浅色对比度。")
    print("==================================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
