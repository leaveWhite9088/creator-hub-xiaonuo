# -*- coding: utf-8 -*-
"""三波无头浏览器确定性连环组合压测引擎 v4.0（src/scoring/browser_waves.py）。

核心设计（xiaonuo-v4.0）：
  1. 第一波（A 层 30 分，对接真实感异步后端 + 去剧透业务不变量 + 连环过关制）：
     - A1（2.0 分）：离线零外网、mock_backend.js SHA-256 只读完整性、真实异步接口调用遥测、4 项目 + 4 富长文完备度；
     - A2 连环链（9.5 分）：异步多词全文检索 + 慢快请求乱序防倒灌（Race Guard）+ 防注入 ->
       多分类筛选/排序重排/详情取消收藏联动空态恢复 -> 双项目并排对比面板 + 原生 <svg> 多维能力图（含轴文字防重叠） ->
       追加第 3 项触发 SVG 动态重绘 + ≤3 容量拦截 + 清空闭环；
     - A3 连环链（12.0 分）：异步排期测算单调性 + 多阶段里程碑 + 快速重置防旧报价倒灌 ->
       去剧透忙闲冲突识别与短/长跨度（含 6 周高负载方案）排期消解 ->
       跨模块操作历史栈（Undo/Redo + Ctrl+Z + 输入框焦点防劫持） ->
       耦合全状态非破坏带入 + 跨刷新守恒 + 异步提交防连点并发锁 + 503 瞬时故障保底重试与真实回执核验；
     - A4 连环链（6.5 分）：双类型异步深链接刷新与新窗口直达 -> 快速切篇防旧详情倒灌 + 五步连续历史栈 ->
       长文目录真实滚动定位防吸顶遮挡。
  2. 第二波（C1 9 分 + C3 8 分）：四档视口（含表格长文与 SVG 对比面板态）反截断几何、320px 超长串注入、
     悬浮栏防遮挡、多态脏缓存/禁存储容错、陡峭 WCAG AA 9 角色短板木桶对比度（min_weight=0.65）。
  3. 第三波（C2 8 分 + B1 5 分）：六区纯键盘可达、定制焦点环、详情键盘返回归位 + 对比弹层双向焦点锁（Tab + Shift+Tab）与 Esc 归位、
     空闲无限 rAF 重罚与 320 张卡片高压注入性能压测。
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import re
import statistics
import time

from dom_probes import (
    JS_DETECT_CLIPPED_CONTROLS,
    JS_DETECT_OCCLUSION_AND_OVERLAP,
    JS_EXTRACT_CONTRAST_SAMPLES,
    JS_IDLE_RAF_AND_STRESS_SEARCH,
    JS_VERIFY_SVG_CHART,
)
from metrics import barrel_score_ratio, interp_nodes, load_config, wcag_contrast_ratio

ROOT = Path(__file__).resolve().parent.parent.parent


def _cjk_count(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text or ""))


def _extract_exclusive_body_phrase(full_body: str, surface_texts: list[str]) -> str | None:
    joined_surface = "\n".join(surface_texts).lower()
    chunks = re.findall(r"[\u4e00-\u9fff]{5,14}", full_body or "")
    ordered = chunks[len(chunks) // 2 :] + chunks[: len(chunks) // 2]
    for seg in ordered:
        cand = seg[:4]
        if len(cand) >= 4 and cand.lower() not in joined_surface:
            return cand
    for seg in ordered:
        if len(seg) >= 4:
            return seg[:4]
    return None


def _extract_numbers(text: str) -> list[float]:
    cleaned = re.sub(r"\b20\d{2}-W\d{1,2}\b", " ", text or "", flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:20\d{2}[-/.])?\d{1,2}[/.]\d{1,2}\b", " ", cleaned)
    nums = []
    for m in re.findall(r"\d+(?:\.\d+)?", cleaned):
        try:
            nums.append(float(m))
        except ValueError:
            pass
    return nums


def _make_check(cid: str, name: str, score_ratio: float, weight: float, measured: object, detail: str) -> dict:
    r = round(max(0.0, min(1.0, float(score_ratio))), 4)
    return {
        "id": cid,
        "name": name,
        "passed": r >= 0.85,
        "score_ratio": r,
        "weight": float(weight),
        "measured": measured,
        "detail": detail,
    }


def _verify_mock_backend_integrity(workspace_dir: Path) -> bool:
    official = ROOT / "src" / "sandbox_template" / "mock_backend.js"
    cand = workspace_dir / "mock_backend.js"
    if not official.is_file() or not cand.is_file():
        return False
    h_off = hashlib.sha256(official.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    h_cnd = hashlib.sha256(cand.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    return h_off == h_cnd


def _wait_bootstrap_ready(page, timeout_ms: int = 2600) -> None:
    try:
        page.wait_for_function(
            """() => {
                if (document.documentElement.getAttribute('data-unimplemented') === 'true') return true;
                const pCnt = document.querySelectorAll("[data-testid='project-card']").length;
                const aCnt = document.querySelectorAll("[data-testid='article-card']").length;
                const er = document.querySelector("[data-testid='est-result']");
                return pCnt >= 4 && aCnt >= 4 && (!er || (er.innerText || '').trim().length >= 3);
            }""",
            timeout=timeout_ms,
        )
    except Exception:
        pass
    page.wait_for_timeout(90)


def _wait_detail_ready(page, timeout_ms: int = 1600) -> None:
    try:
        page.wait_for_function(
            """() => {
                const dv = document.querySelector("[data-testid='detail-view']");
                const db = document.querySelector("[data-testid='detail-body']");
                if (!dv || dv.offsetParent === null || !db) return false;
                if (dv.getAttribute('aria-busy') === 'true' || db.getAttribute('aria-busy') === 'true') return false;
                return (db.innerText || '').trim().length >= 45;
            }""",
            timeout=timeout_ms,
        )
    except Exception:
        pass
    page.wait_for_timeout(90)


def _active_compare_count(page) -> int:
    return int(
        page.evaluate(
            """() => Array.from(document.querySelectorAll("[data-testid='compare-toggle']"))
                .filter(b => {
                    const r = b.getBoundingClientRect();
                    return r.height > 0 && r.width > 0 && getComputedStyle(b).visibility !== 'hidden' &&
                        (b.getAttribute('aria-pressed') === 'true' || b.getAttribute('data-compared') === 'true');
                }).length"""
        )
    )


def _get_week_slots_meta(page) -> dict:
    return page.evaluate(
        """() => {
            const el = document.querySelector("[data-testid='est-start-week']");
            if (!el) return { kind: 'missing', count: 0, activeSig: '', activeWeekCode: '' };
            if (el.tagName.toLowerCase() === 'select') {
                const opt = el.options[el.selectedIndex];
                const rawVal = el.value || '';
                const weekMatch = (rawVal + ' ' + (opt ? opt.textContent : '')).match(/202[67]-W\\d{2}/);
                return {
                    kind: 'select',
                    count: el.options.length,
                    activeSig: String(el.selectedIndex) + ':' + rawVal,
                    activeWeekCode: weekMatch ? weekMatch[0] : rawVal
                };
            }
            const items = Array.from(el.querySelectorAll("[data-week], button, [role='radio'], [role='option']"))
                .filter(b => {
                    const cs = getComputedStyle(b);
                    return cs.display !== 'none' && cs.visibility !== 'hidden';
                });
            let activeSig = '';
            let activeWeekCode = '';
            items.forEach((b, idx) => {
                if (
                    b.getAttribute('aria-pressed') === 'true' ||
                    b.getAttribute('aria-checked') === 'true' ||
                    b.getAttribute('aria-selected') === 'true' ||
                    b.getAttribute('data-active') === 'true'
                ) {
                    const wAttr = b.getAttribute('data-week') || '';
                    activeSig = idx + ':' + (wAttr || (b.innerText || '').trim().slice(0, 18));
                    activeWeekCode = wAttr;
                }
            });
            return { kind: 'buttons', count: items.length, activeSig, activeWeekCode };
        }"""
    )


def _select_week_slot(page, index: int) -> None:
    meta = _get_week_slots_meta(page)
    if meta["kind"] == "select":
        sel = page.locator("[data-testid='est-start-week']").first
        val = sel.evaluate("(el, i) => el.options[i] ? el.options[i].value : ''", index)
        if val != "":
            sel.select_option(val)
        else:
            sel.select_option(index=index)
    elif meta["kind"] == "buttons":
        btns = page.locator(
            "[data-testid='est-start-week'] [data-week]:visible, "
            "[data-testid='est-start-week'] button:visible, "
            "[data-testid='est-start-week'] [role='radio']:visible"
        )
        if index < btns.count():
            btns.nth(index).click(timeout=1200)


def _detect_planner_conflict_ui(page) -> dict:
    """去剧透冲突告警探测：不依赖特定 data-testid，检测规划台内（排除启动周选择器本身）是否出现可见的冲突/约满提示。"""
    return page.evaluate(
        """() => {
            const sec = document.querySelector("[data-testid='estimator-section']");
            if (!sec) return { active: false, text: '' };
            const weekGroup = sec.querySelector("[data-testid='est-start-week']");
            const isVis = (el) => {
                if (!el) return false;
                const cs = getComputedStyle(el);
                if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) < 0.1) return false;
                const r = el.getBoundingClientRect();
                return r.width > 2 && r.height > 2;
            };

            // 1. 优先检查显式 role='alert' 或冲突语义容器
            const explicitAlerts = Array.from(sec.querySelectorAll("[role='alert'], [data-testid='est-conflict'], [class*='conflict'], [class*='alert'], [class*='warn']"))
                .filter(el => isVis(el) && (!weekGroup || !weekGroup.contains(el)));
            for (const al of explicitAlerts) {
                const txt = (al.innerText || '').replace(/\\s+/g, ' ').trim();
                if (txt.length >= 4 && /冲突|约满|占用|繁忙|撞期|不可用|超出近期|验收周|内训周/.test(txt)) {
                    return { active: true, text: txt.slice(0, 120) };
                }
            }

            // 2. 扫描规划台内（排除启动周选项列表本身与静态标题）的文本块
            const blocks = Array.from(sec.querySelectorAll("div, p, aside, section, span"))
                .filter(el => isVis(el) && (!weekGroup || (!weekGroup.contains(el) && !el.contains(weekGroup))));
            for (const b of blocks) {
                if (b.children.length > 4) continue;
                const txt = (b.innerText || '').replace(/\\s+/g, ' ').trim();
                if (txt.length >= 6 && txt.length <= 220 && /档期冲突|与忙碌档期冲突|存在冲突|已约满|撞期|存量金融客户|封闭内训周|超出近期开放/.test(txt)) {
                    return { active: true, text: txt.slice(0, 120) };
                }
            }
            return { active: false, text: '' };
        }"""
    )


def _click_planner_conflict_resolver(page) -> bool:
    """在规划台处于冲突态时，定位并点击选手自行设计的冲突消解/顺延/推荐空闲周交互控件。"""
    clicked = page.evaluate(
        """() => {
            const sec = document.querySelector("[data-testid='estimator-section']");
            if (!sec) return false;
            const weekGroup = sec.querySelector("[data-testid='est-start-week']");
            const excludedTestIds = new Set(['est-type', 'est-addon', 'est-scale', 'est-reset', 'est-apply-to-contact']);
            const isVis = (el) => {
                if (!el || el.disabled || el.getAttribute('aria-disabled') === 'true') return false;
                const cs = getComputedStyle(el);
                if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) < 0.1) return false;
                const r = el.getBoundingClientRect();
                return r.width > 4 && r.height > 4;
            };

            const candidates = Array.from(sec.querySelectorAll("button, [role='button'], a"))
                .filter(el => {
                    if (!isVis(el)) return false;
                    const tid = el.getAttribute('data-testid') || '';
                    if (excludedTestIds.has(tid)) return false;
                    if (weekGroup && weekGroup.contains(el)) return false;
                    if (el.closest("[data-testid='est-scale']")) return false;
                    return true;
                });

            // 按顺延/空闲推荐语义优先级排序
            candidates.sort((a, b) => {
                const score = (el) => {
                    const txt = ((el.innerText || '') + ' ' + (el.getAttribute('aria-label') || '') + ' ' + (el.getAttribute('data-testid') || '')).trim();
                    let s = 0;
                    if (el.closest("[role='alert'], [class*='conflict'], [class*='warn'], [data-testid='est-conflict']")) s += 5;
                    if (/顺延|空闲|可用|避开|推荐|调至|自动|切换|解决|消解|resolve/i.test(txt)) s += 10;
                    if (/12月|1月|W\\d{2}/.test(txt)) s += 4;
                    return s;
                };
                return score(b) - score(a);
            });

            if (candidates.length > 0) {
                candidates[0].click();
                return true;
            }
            return false;
        }"""
    )
    return bool(clicked)


def _contact_submit_locator(page):
    loc = page.locator("[data-testid='contact-submit']")
    if loc.count() > 0:
        return loc.first
    return page.locator("[data-testid='contact-generate']").first


def evaluate_workspace(workspace_dir: Path, cfg: dict | None = None) -> tuple[dict, list[dict]]:
    """对 workspace/index.html 依次执行三波无头浏览器连环压测剧本，返回 (run_report, wave_trace)。"""
    from playwright.sync_api import sync_playwright

    cfg = cfg or load_config()
    sc_cfg = cfg["scoring"]
    vp_cfg = cfg["viewports"]
    req_cfg = cfg["content_requirements"]

    index_path = (workspace_dir / "index.html").resolve()
    trace: list[dict] = []

    def log_step(wave: str, step: str, ok: bool, data: dict):
        trace.append({"ts": round(time.time(), 3), "wave": wave, "step": step, "ok": bool(ok), **data})

    if not index_path.exists():
        rep = {
            "page_loadable": False,
            "not_implemented": True,
            "reason": "workspace/index.html 不存在",
            "wave1": {},
            "wave2": {},
            "wave3": {},
        }
        log_step("init", "check_index_html", False, {"reason": "missing index.html"})
        return rep, trace

    mock_intact = _verify_mock_backend_integrity(workspace_dir)
    file_url = index_path.as_uri()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # ====================================================================
        # 第一波剧本：异步联调竞态、去剧透不变量与连环过关（A1 2.0 + A2 9.5 + A3 12.0 + A4 6.5 = 30 分）
        # ====================================================================
        ext_urls: list[str] = []
        w1_errors: list[str] = []
        w1_dialogs: list[str] = []

        ctx1 = browser.new_context(viewport=vp_cfg["desktop"], color_scheme="light")

        def _intercept_external(route):
            u = route.request.url
            if u.startswith(("http://", "https://", "ws://", "wss://")):
                ext_urls.append(u)
                route.abort()
            else:
                route.continue_()

        ctx1.route("**/*", _intercept_external)
        page1 = ctx1.new_page()
        page1.on("pageerror", lambda e: w1_errors.append(str(e)))
        page1.on("dialog", lambda d: (w1_dialogs.append(d.message), d.dismiss()))

        try:
            page1.goto(file_url, wait_until="domcontentloaded", timeout=8000)
            _wait_bootstrap_ready(page1)
        except Exception as exc:
            browser.close()
            rep = {
                "page_loadable": False,
                "not_implemented": True,
                "reason": f"页面加载失败: {exc}",
                "wave1": {"external_requests_count": len(ext_urls)},
                "wave2": {},
                "wave3": {},
            }
            log_step("wave1", "open_index", False, {"error": str(exc)})
            return rep, trace

        is_stub = page1.evaluate("() => document.documentElement.getAttribute('data-unimplemented') === 'true'")
        if is_stub:
            ctx1.close()
            browser.close()
            rep = {
                "page_loadable": True,
                "not_implemented": True,
                "reason": "保留初始未实现标记 data-unimplemented='true'",
                "wave1": {"external_requests_count": len(ext_urls)},
                "wave2": {},
                "wave3": {},
            }
            log_step("wave1", "detect_stub", False, {"not_implemented": True})
            return rep, trace

        a1_checks: list[dict] = []
        a2_checks: list[dict] = []
        a3_checks: list[dict] = []
        a4_checks: list[dict] = []

        # ---- A1.1 离线零外网、mock_backend.js 只读未篡改、真实异步接口接入与零异常（权重 1.0） ----
        init_telemetry = page1.evaluate(
            "() => (window.LincheMockAPI && typeof window.LincheMockAPI.getTelemetry === 'function') ? window.LincheMockAPI.getTelemetry() : null"
        ) or {}
        real_api_boot = (
            mock_intact
            and int(init_telemetry.get("bootstrapCalls", 0)) >= 1
            and int(init_telemetry.get("queryCalls", 0)) >= 1
        )
        ext_lvl = interp_nodes(len(ext_urls), sc_cfg["A"]["external_req_penalty_nodes"])
        err_penalty = (0.45 if w1_errors else 0.0) + (0.25 if w1_dialogs else 0.0)
        base_clean = max(0.0, (ext_lvl / 10.0) - err_penalty)
        a1_1_ratio = base_clean * (1.0 if real_api_boot else 0.0)
        a1_checks.append(
            _make_check(
                "A1.1",
                "离线零外网、mock_backend.js 只读完整性、真实异步接口启动与零运行时异常",
                a1_1_ratio,
                1.0,
                {
                    "mock_backend_intact": mock_intact,
                    "telemetry_boot": init_telemetry,
                    "external_requests": ext_urls[:4],
                    "page_errors": w1_errors[:3],
                },
                f"模拟后端原件未篡改={mock_intact}，真实调用首屏接口={real_api_boot}，外网请求={len(ext_urls)}，异常={len(w1_errors)}",
            )
        )

        surface_texts: list[str] = page1.evaluate(
            """() => Array.from(document.querySelectorAll("[data-testid='project-card'], [data-testid='article-card']"))
                .map(c => c.innerText || '')"""
        )

        # ---- A1.2 异步渲染后四项目、四篇富结构长文及演示说明完备度（权重 1.0） ----
        proj_total = page1.locator("[data-testid='project-card']").count()
        valid_projects = 0
        sample_project_body = ""
        sample_project_id = ""

        for idx in range(min(proj_total, 6)):
            try:
                card = page1.locator("[data-testid='project-card']").nth(idx)
                pid = card.get_attribute("data-id") or f"p-{idx}"
                card_text = card.inner_text().strip()
                open_el = card.locator("[data-testid='project-open']")
                (open_el.first if open_el.count() > 0 else card).click(timeout=1800)
                _wait_detail_ready(page1)
                if page1.locator("[data-testid='detail-view']:visible").count() > 0:
                    d_title = page1.locator("[data-testid='detail-title']").first.inner_text().strip()
                    d_body = page1.locator("[data-testid='detail-body']").first.inner_text().strip()
                    if len(d_title) >= 2 and len(d_body) >= 65 and len(card_text) >= 16:
                        valid_projects += 1
                        if not sample_project_body:
                            sample_project_body = d_body
                            sample_project_id = pid
                    bb = page1.locator("[data-testid='detail-back']:visible")
                    if bb.count() > 0:
                        bb.first.click(timeout=1500)
                    else:
                        page1.go_back()
                    page1.wait_for_timeout(90)
            except Exception:
                pass

        art_total = page1.locator("[data-testid='article-card']").count()
        art_len_scores: list[float] = []
        articles_with_toc = 0
        found_list = False
        found_quote = False
        found_code = False
        found_table = False
        sample_article_body = ""
        sample_article_id = ""
        sample_article_title = ""
        rich_table_article_idx = 0

        for idx in range(min(art_total, 6)):
            try:
                acard = page1.locator("[data-testid='article-card']").nth(idx)
                aid = acard.get_attribute("data-id") or f"a-{idx}"
                aopen = acard.locator("[data-testid='article-open']")
                (aopen.first if aopen.count() > 0 else acard).click(timeout=1800)
                _wait_detail_ready(page1)
                meta = page1.evaluate(
                    """() => {
                        const dv = document.querySelector("[data-testid='detail-view']");
                        const db = document.querySelector("[data-testid='detail-body']");
                        const dt = document.querySelector("[data-testid='detail-title']");
                        const toc = document.querySelector("[data-testid='article-toc']");
                        if (!dv || dv.offsetParent === null || !db) return null;
                        const text = db.innerText || '';
                        const title = dt ? dt.innerText.trim() : '';
                        const headings = db.querySelectorAll('h2, h3, h4').length;
                        const tocLinks = toc ? toc.querySelectorAll('a, button').length : 0;
                        const hasList = db.querySelectorAll('ul li, ol li').length >= 2;
                        const hasQuote = db.querySelectorAll('blockquote').length >= 1;
                        const hasCode = db.querySelectorAll('pre code, pre').length >= 1;
                        const hasTable = db.querySelectorAll('table tr').length >= 2 && db.querySelectorAll('table td, table th').length >= 4;
                        return { title, text, headings, tocLinks, hasList, hasQuote, hasCode, hasTable };
                    }"""
                )
                if meta:
                    cjk_n = _cjk_count(meta["text"])
                    lvl_len = interp_nodes(cjk_n, req_cfg["article_cjk_len_nodes"]) / 10.0
                    art_len_scores.append(lvl_len)
                    if meta["headings"] >= 2 and meta["tocLinks"] >= 2:
                        articles_with_toc += 1
                    found_list = found_list or bool(meta["hasList"])
                    found_quote = found_quote or bool(meta["hasQuote"])
                    found_code = found_code or bool(meta["hasCode"])
                    if meta["hasTable"]:
                        found_table = True
                        rich_table_article_idx = idx
                    if not sample_article_body:
                        sample_article_body = meta["text"]
                        sample_article_id = aid
                        sample_article_title = meta["title"]
                bb = page1.locator("[data-testid='detail-back']:visible")
                if bb.count() > 0:
                    bb.first.click(timeout=1500)
                else:
                    page1.go_back()
                page1.wait_for_timeout(90)
            except Exception:
                pass

        honesty_info = page1.evaluate(
            """(demoEmail) => {
                const notice = document.querySelector("[data-testid='demo-notice']");
                const noticeText = (notice && notice.offsetParent !== null) ? notice.innerText : '';
                const hasDemoMark = /演示|样板|示例|模拟|demo/i.test(noticeText || '');
                const cSec = document.querySelector("[data-testid='contact-section']");
                const cText = cSec ? cSec.innerText : '';
                const hasEmail = cText.toLowerCase().includes(demoEmail.toLowerCase());
                return { hasDemoMark, hasEmail };
            }""",
            req_cfg["contact_demo_email"],
        )

        req_proj = int(req_cfg["project_count"])
        req_art = int(req_cfg["article_count"])
        proj_part = min(1.0, valid_projects / max(1, req_proj))
        top_art = sorted(art_len_scores, reverse=True)[:req_art]
        len_part = (sum(top_art) / req_art) if top_art else 0.0
        toc_part = min(1.0, articles_with_toc / max(1, req_art))
        rich_elems = int(found_list) + int(found_quote) + int(found_code) + int(found_table)
        rich_part = rich_elems / 4.0
        honesty_part = (0.5 if honesty_info["hasDemoMark"] else 0.0) + (0.5 if honesty_info["hasEmail"] else 0.0)
        a1_2_ratio = 0.25 * proj_part + 0.20 * len_part + 0.15 * toc_part + 0.25 * rich_part + 0.15 * honesty_part

        a1_checks.append(
            _make_check(
                "A1.2",
                "异步详情加载完备度、富格式排版（列表/引用/代码/表格）与演示边界标识",
                a1_2_ratio,
                1.0,
                {
                    "valid_projects": f"{valid_projects}/{req_proj}",
                    "toc_articles": f"{articles_with_toc}/{req_art}",
                    "rich_elements": {"list": found_list, "quote": found_quote, "code": found_code, "table": found_table},
                    "honesty": honesty_info,
                },
                f"项目详情 {valid_projects}/{req_proj}，长文目录 {articles_with_toc}/{req_art}，富元素={rich_elems}/4，演示说明={honesty_info['hasDemoMark']}",
            )
        )

        # ====================================================================
        # A2 连环压测链（9.5 分，按 A2.1 -> A2.2 -> A2.3 -> A2.4 顺序连坐门控）
        # ====================================================================
        # ---- A2.1 [第1关] 异步全文多词交集检索 + 慢快请求乱序防倒灌（Out-of-Order Race Guard）+ 防注入（权重 2.6） ----
        art_phrase = _extract_exclusive_body_phrase(sample_article_body, surface_texts) or "短板木桶"
        proj_phrase = _extract_exclusive_body_phrase(sample_project_body, surface_texts) or "熔断器"
        s_input = page1.locator("[data-testid='search-input']").first
        body_search_ok = False
        multi_kw_ok = False
        race_guard_ok = False
        fuzz_safe_ok = False
        errs_before_search = len(w1_errors)

        try:
            if s_input.count() > 0:
                # 1) 深层正文检索（留足防抖 + 异步返回窗口）
                s_input.fill(art_phrase)
                page1.wait_for_timeout(520)
                vis_a = page1.evaluate(
                    "() => Array.from(document.querySelectorAll(\"[data-testid='article-card']\")).filter(e => e.offsetParent !== null).map(e => e.getAttribute('data-id') || '')"
                )
                art_hit = (len(vis_a) >= 1) and (not sample_article_id or sample_article_id in vis_a)

                s_input.fill(proj_phrase)
                page1.wait_for_timeout(520)
                vis_p = page1.evaluate(
                    "() => Array.from(document.querySelectorAll(\"[data-testid='project-card']\")).filter(e => e.offsetParent !== null).map(e => e.getAttribute('data-id') || '')"
                )
                proj_hit = (len(vis_p) >= 1) and (not sample_project_id or sample_project_id in vis_p)
                body_search_ok = art_hit and proj_hit

                # 2) 多关键词空格交集（AND）检索
                title_tok_m = re.findall(r"[\u4e00-\u9fff]{2,4}", sample_article_title)
                if title_tok_m and art_phrase:
                    s_input.fill(f"{title_tok_m[0]} {art_phrase}")
                    page1.wait_for_timeout(340)
                    vis_combo = page1.evaluate(
                        "() => Array.from(document.querySelectorAll(\"[data-testid='article-card']\")).filter(e => e.offsetParent !== null).map(e => e.getAttribute('data-id') || '')"
                    )
                    s_input.fill(f"{title_tok_m[0]} __NEVER_EXISTS_99__")
                    page1.wait_for_timeout(340)
                    vis_impossible = page1.locator("[data-testid='article-card']:visible").count()
                    multi_kw_ok = (len(vis_combo) >= 1) and (not sample_article_id or sample_article_id in vis_combo) and (vis_impossible == 0)

                # 3) 核心对抗：慢请求（单热词 ~230ms）在途时立即发起快请求（双词精确查询 ~35ms），检验是否丢弃过期响应！
                s_input.fill("")
                page1.wait_for_timeout(320)
                q_calls_0 = int(page1.evaluate("() => window.LincheMockAPI ? window.LincheMockAPI.getTelemetry().queryCalls : 0"))
                s_input.fill("评测")
                # 等到慢查询真正发出（最多等 450ms 兼容前端防抖），一旦在途立即改填快速双词查询！
                try:
                    page1.wait_for_function(
                        f"() => window.LincheMockAPI && window.LincheMockAPI.getTelemetry().queryCalls > {q_calls_0}",
                        timeout=480,
                    )
                except Exception:
                    pass
                page1.wait_for_timeout(15)
                s_input.fill("状态机 回放树")
                # 等待 620ms，确保快请求（35ms）与在途慢请求（230ms）以及任何防抖定时器全部走完！
                page1.wait_for_timeout(620)
                final_proj_ids = page1.evaluate(
                    "() => Array.from(document.querySelectorAll(\"[data-testid='project-card']\")).filter(e => e.offsetParent !== null).map(e => e.getAttribute('data-id') || '')"
                )
                race_guard_ok = (final_proj_ids == ["proj-agent-trace"]) and (s_input.input_value() == "状态机 回放树")

                # 4) 正则元字符与 XSS 安全
                for fq in ["[a-z]+ (unclosed_regex \\ * ?", "<img src=x onerror=\"window.__ch_xss=1\">"]:
                    s_input.fill(fq)
                    page1.wait_for_timeout(180)
                s_input.fill(f"   {art_phrase}   ")
                page1.wait_for_timeout(520)
                trimmed_hit = page1.locator("[data-testid='article-card']:visible").count() >= 1
                xss_fired = bool(page1.evaluate("() => Boolean(window.__ch_xss)"))
                fuzz_safe_ok = (len(w1_errors) == errs_before_search) and (not xss_fired) and trimmed_hit

                s_input.fill("")
                page1.wait_for_timeout(350)
        except Exception:
            pass

        a2_1_ratio = (
            (0.25 if body_search_ok else 0.0)
            + (0.25 if multi_kw_ok else 0.0)
            + (0.35 if race_guard_ok else 0.0)
            + (0.15 if fuzz_safe_ok else 0.0)
        )
        a2_checks.append(
            _make_check(
                "A2.1",
                "[链A2-关1] 异步全文多词交集检索、慢快请求乱序防倒灌（Race Guard）与防注入",
                a2_1_ratio,
                2.6,
                {
                    "body_search_ok": body_search_ok,
                    "multi_kw_and_ok": multi_kw_ok,
                    "out_of_order_race_guard_ok": race_guard_ok,
                    "fuzz_safe_ok": fuzz_safe_ok,
                },
                f"正文命中={body_search_ok}，空格多词交集={multi_kw_ok}，慢查询防覆盖新结果={race_guard_ok}，防注入={fuzz_safe_ok}",
            )
        )

        # ---- A2.2 [第2关] 分类筛选 + 排序重排 + 详情取消收藏联动空状态及恢复（权重 2.1） ----
        cat_ok = False
        sort_ok = False
        detail_unfav_sync_ok = False
        empty_recover_ok = False
        specific_cats: list[str] = []
        chosen_cat = ""

        try:
            cat_els = page1.locator("[data-testid='category-option']")
            for i in range(cat_els.count()):
                cv = (cat_els.nth(i).get_attribute("data-category") or "").strip()
                if cv and cv.lower() != "all":
                    specific_cats.append(cv)
            if len(set(specific_cats)) >= int(req_cfg["min_categories"]):
                chosen_cat = specific_cats[0]
                page1.locator(f"[data-testid='category-option'][data-category='{chosen_cat}']").first.click(timeout=1500)
                page1.wait_for_timeout(160)
                cnt_f = page1.locator("[data-testid='project-card']:visible").count()
                page1.locator("[data-testid='category-option'][data-category='all']").first.click(timeout=1500)
                page1.wait_for_timeout(160)
                cnt_all = page1.locator("[data-testid='project-card']:visible").count()
                cat_ok = (0 < cnt_f < cnt_all) and (cnt_all >= req_proj)

            order_before = page1.evaluate(
                """() => ({
                    p: Array.from(document.querySelectorAll("[data-testid='project-card']")).filter(e => e.offsetParent !== null).map(e => e.getAttribute('data-id')),
                    a: Array.from(document.querySelectorAll("[data-testid='article-card']")).filter(e => e.offsetParent !== null).map(e => e.getAttribute('data-id'))
                })"""
            )
            sort_el = page1.locator("[data-testid='sort-control']").first
            if sort_el.count() > 0:
                tag_name = sort_el.evaluate("el => el.tagName.toLowerCase()")
                if tag_name == "select":
                    opts = sort_el.evaluate("el => Array.from(el.options).map(o => o.value)")
                    cur_v = sort_el.input_value()
                    alt_opts = [v for v in opts if v != cur_v]
                    if alt_opts:
                        sort_el.select_option(alt_opts[0])
                        page1.wait_for_timeout(180)
                else:
                    btns = sort_el.locator("[data-sort], button")
                    for bi in range(btns.count()):
                        b = btns.nth(bi)
                        is_act = (b.get_attribute("aria-pressed") == "true") or (b.get_attribute("data-active") == "true")
                        if not is_act and b.is_visible():
                            b.click(timeout=1200)
                            page1.wait_for_timeout(180)
                            break
                order_after = page1.evaluate(
                    """() => ({
                        p: Array.from(document.querySelectorAll("[data-testid='project-card']")).filter(e => e.offsetParent !== null).map(e => e.getAttribute('data-id')),
                        a: Array.from(document.querySelectorAll("[data-testid='article-card']")).filter(e => e.offsetParent !== null).map(e => e.getAttribute('data-id'))
                    })"""
                )
                count_kept = (len(order_after["p"]) == len(order_before["p"])) and (len(order_after["a"]) == len(order_before["a"]))
                changed = (order_after["p"] != order_before["p"]) or (order_after["a"] != order_before["a"])
                sort_ok = count_kept and changed

            p0 = page1.locator("[data-testid='project-card']").first
            fb0 = p0.locator("[data-testid='favorite-btn']").first
            if not ((fb0.get_attribute("aria-pressed") == "true") or (fb0.get_attribute("data-favorited") == "true")):
                fb0.click(timeout=1200)
                page1.wait_for_timeout(110)
            fav_filter = page1.locator("[data-testid='favorite-filter']").first
            fav_filter.click(timeout=1200)
            page1.wait_for_timeout(160)
            if page1.locator("[data-testid='project-card']:visible").count() == 1:
                vis_card = page1.locator("[data-testid='project-card']:visible").first
                op = vis_card.locator("[data-testid='project-open']")
                (op.first if op.count() > 0 else vis_card).click(timeout=1500)
                _wait_detail_ready(page1)
                detail_fav = page1.locator("[data-testid='detail-view']:visible [data-testid='favorite-btn']")
                if detail_fav.count() > 0 and detail_fav.first.is_visible():
                    detail_fav.first.click(timeout=1200)
                    page1.wait_for_timeout(120)
                    page1.locator("[data-testid='detail-back']:visible").first.click(timeout=1200)
                    page1.wait_for_timeout(180)
                    after_unfav_cnt = page1.locator("[data-testid='project-card']:visible").count()
                    emp_now = page1.locator("[data-testid='empty-state']:visible").count() > 0
                    detail_unfav_sync_ok = (after_unfav_cnt == 0) and emp_now
                    if emp_now:
                        rec_b = page1.locator("[data-testid='empty-state']:visible button, [data-testid='empty-state']:visible a, [data-testid='empty-state']:visible [role='button']")
                        if rec_b.count() > 0 and rec_b.first.is_visible():
                            rec_b.first.click(timeout=1200)
                            page1.wait_for_timeout(200)
                            empty_recover_ok = page1.locator("[data-testid='project-card']:visible").count() >= 1
                else:
                    bb = page1.locator("[data-testid='detail-back']:visible")
                    if bb.count() > 0:
                        bb.first.click(timeout=1200)
                        page1.wait_for_timeout(120)

            if not empty_recover_ok:
                if (fav_filter.get_attribute("aria-pressed") == "true") or (fav_filter.get_attribute("data-active") == "true"):
                    fav_filter.click(timeout=1200)
                    page1.wait_for_timeout(120)
                s_input.fill("__NO_MATCH_9527_XYZ__")
                page1.wait_for_timeout(340)
                emp_vis = page1.locator("[data-testid='empty-state']:visible")
                if emp_vis.count() > 0:
                    rb = emp_vis.first.locator("button, a, [role='button']")
                    if rb.count() > 0 and rb.first.is_visible():
                        rb.first.click(timeout=1200)
                        page1.wait_for_timeout(320)
                        empty_recover_ok = page1.locator("[data-testid='project-card']:visible, [data-testid='article-card']:visible").count() >= 1

            s_input.fill("")
            if (fav_filter.get_attribute("aria-pressed") == "true") or (fav_filter.get_attribute("data-active") == "true"):
                fav_filter.click(timeout=1200)
                page1.wait_for_timeout(120)
            all_b = page1.locator("[data-testid='category-option'][data-category='all']")
            if all_b.count() > 0:
                all_b.first.click(timeout=1000)
            page1.wait_for_timeout(320)
            for idx_c in range(page1.locator("[data-testid='project-card']").count()):
                fcb = page1.locator("[data-testid='project-card']").nth(idx_c).locator("[data-testid='favorite-btn']").first
                if (fcb.get_attribute("aria-pressed") == "true") or (fcb.get_attribute("data-favorited") == "true"):
                    fcb.click(timeout=1000)
            page1.wait_for_timeout(100)
        except Exception:
            pass

        a2_2_ratio = (
            (0.25 if cat_ok else 0.0)
            + (0.25 if sort_ok else 0.0)
            + (0.30 if detail_unfav_sync_ok else 0.0)
            + (0.20 if empty_recover_ok else 0.0)
        )
        a2_checks.append(
            _make_check(
                "A2.2",
                "[链A2-关2] 多分类收敛、排序重排、详情内取消收藏跨视图同步与空态恢复",
                a2_2_ratio,
                2.1,
                {"cat_ok": cat_ok, "sort_ok": sort_ok, "detail_unfav_sync_ok": detail_unfav_sync_ok, "empty_recover_ok": empty_recover_ok},
                f"分类收敛={cat_ok}，排序重排={sort_ok}，详情内取消收藏同步空态={detail_unfav_sync_ok}，空态按钮恢复={empty_recover_ok}",
            )
        )

        # ---- A2.3 [第3关] 双项目横向对比面板与原生 <svg data-testid='compare-chart'> 多维图（含标签防重叠，权重 2.4） ----
        cmp_open_ok = False
        svg_2_ok = False
        svg_no_overlap_ok = False
        svg_info_2: dict = {}
        min_axes = int(req_cfg.get("min_svg_axes", 3))
        max_cmp = int(req_cfg.get("max_compare_items", 3))

        try:
            p_cards = page1.locator("[data-testid='project-card']:visible")
            if p_cards.count() >= 4:
                t0_txt = p_cards.nth(0).locator("h2, h3, [data-testid='project-open']").first.inner_text().strip()[:6]
                t1_txt = p_cards.nth(1).locator("h2, h3, [data-testid='project-open']").first.inner_text().strip()[:6]
                p_cards.nth(0).locator("[data-testid='compare-toggle']").first.click(timeout=1200)
                p_cards.nth(1).locator("[data-testid='compare-toggle']").first.click(timeout=1200)
                page1.wait_for_timeout(120)

                if page1.locator("[data-testid='compare-bar']:visible").count() > 0:
                    page1.locator("[data-testid='compare-open']:visible").first.click(timeout=1500)
                    page1.wait_for_timeout(160)
                    panel = page1.locator("[data-testid='compare-panel']:visible")
                    if panel.count() > 0:
                        p_txt = panel.first.inner_text()
                        cmp_open_ok = (t0_txt in p_txt) and (t1_txt in p_txt)
                        svg_info_2 = page1.evaluate(JS_VERIFY_SVG_CHART)
                        svg_2_ok = bool(
                            svg_info_2.get("exists")
                            and svg_info_2.get("visible")
                            and svg_info_2.get("fitsViewport")
                            and int(svg_info_2.get("textLabelCount", 0)) >= min_axes
                            and int(svg_info_2.get("shapeCount", 0)) >= 2
                            and int(svg_info_2.get("distinctStyleCount", 0)) >= 2
                        )
                        svg_no_overlap_ok = svg_2_ok and int(svg_info_2.get("overlappingTextPairs", 99)) == 0
                        cls_btn = page1.locator("[data-testid='compare-close']:visible")
                        if cls_btn.count() > 0:
                            cls_btn.first.click(timeout=1200)
                        else:
                            page1.keyboard.press("Escape")
                        page1.wait_for_timeout(110)
        except Exception:
            pass

        a2_3_ratio = (
            (0.35 if cmp_open_ok else 0.0)
            + (0.45 if svg_2_ok else 0.0)
            + (0.20 if svg_no_overlap_ok else 0.0)
        )
        a2_checks.append(
            _make_check(
                "A2.3",
                "[链A2-关3] 双项目并排对比面板与原生 <svg> 多维能力图（含轴文字零重叠核验）",
                a2_3_ratio,
                2.4,
                {
                    "cmp_open_ok": cmp_open_ok,
                    "svg_valid": svg_2_ok,
                    "svg_no_overlap": svg_no_overlap_ok,
                    "svg_labels": svg_info_2.get("textLabelCount", 0),
                    "svg_overlap_pairs": svg_info_2.get("overlappingTextPairs", 0),
                    "svg_shapes": svg_info_2.get("shapeCount", 0),
                },
                f"并排双项={cmp_open_ok}，原生SVG多维图有效={svg_2_ok}，轴标签零重叠={svg_no_overlap_ok} (shapes={svg_info_2.get('shapeCount',0)}, overlaps={svg_info_2.get('overlappingTextPairs',0)})",
            )
        )

        # ---- A2.4 [第4关] 追加第 3 项触发 SVG 动态坐标重绘 + ≤3 容量上限拦截 + 一键清空（权重 2.4） ----
        svg_dynamic_ok = False
        cmp_cap_ok = False
        cmp_clear_ok = False
        svg_info_3: dict = {}

        try:
            p_cards = page1.locator("[data-testid='project-card']:visible")
            if p_cards.count() >= 4:
                p_cards.nth(2).locator("[data-testid='compare-toggle']").first.click(timeout=1200)
                page1.wait_for_timeout(120)
                if page1.locator("[data-testid='compare-open']:visible").count() > 0:
                    page1.locator("[data-testid='compare-open']:visible").first.click(timeout=1500)
                    page1.wait_for_timeout(160)
                    svg_info_3 = page1.evaluate(JS_VERIFY_SVG_CHART)
                    sig2 = svg_info_2.get("coordSignature") or ""
                    sig3 = svg_info_3.get("coordSignature") or ""
                    svg_dynamic_ok = bool(
                        svg_info_3.get("visible")
                        and int(svg_info_3.get("shapeCount", 0)) >= 3
                        and sig2 != ""
                        and sig3 != ""
                        and sig3 != sig2
                    )
                    cls_btn = page1.locator("[data-testid='compare-close']:visible")
                    if cls_btn.count() > 0:
                        cls_btn.first.click(timeout=1200)
                    else:
                        page1.keyboard.press("Escape")
                    page1.wait_for_timeout(110)

                p_cards.nth(3).locator("[data-testid='compare-toggle']").first.click(timeout=1200)
                page1.wait_for_timeout(110)
                active_cmp_cnt = _active_compare_count(page1)
                cmp_cap_ok = 2 <= active_cmp_cnt <= max_cmp

                clr = page1.locator("[data-testid='compare-clear']:visible")
                if clr.count() > 0:
                    clr.first.click(timeout=1200)
                    page1.wait_for_timeout(110)
                    after_clr_cnt = _active_compare_count(page1)
                    bar_hidden = page1.locator("[data-testid='compare-bar']:visible").count() == 0
                    cmp_clear_ok = (after_clr_cnt == 0) and bar_hidden
        except Exception:
            pass

        a2_4_ratio = (0.50 if svg_dynamic_ok else 0.0) + (0.25 if cmp_cap_ok else 0.0) + (0.25 if cmp_clear_ok else 0.0)
        a2_checks.append(
            _make_check(
                "A2.4",
                "[链A2-关4] 第 3 项加入后 SVG 图形动态重绘、3 项上限拦截与一键清空闭环",
                a2_4_ratio,
                2.4,
                {"svg_dynamic_redraw": svg_dynamic_ok, "shapes_2_to_3": [svg_info_2.get("shapeCount", 0), svg_info_3.get("shapeCount", 0)], "cmp_cap_ok": cmp_cap_ok, "cmp_clear_ok": cmp_clear_ok},
                f"2→3项SVG几何动态重绘={svg_dynamic_ok}，≤{max_cmp}项上限拦截={cmp_cap_ok}，一键清空收起={cmp_clear_ok}",
            )
        )

        # ====================================================================
        # A3 连环压测链（12.0 分，按 A3.1 -> A3.2 -> A3.3 -> A3.4 顺序连坐门控）
        # ====================================================================
        # ---- A3.1 [第1关] 异步排期测算单调性、多阶段里程碑表 + 快速重置防旧报价倒灌（权重 2.6） ----
        est_live_type_ok = False
        est_monotonic_addon_ok = False
        milestones_live_ok = False
        planner_race_reset_ok = False
        est_diag: dict = {}

        try:
            est_res = page1.locator("[data-testid='est-result']").first
            ms_loc = page1.locator("[data-testid='est-milestones']").first
            plan_calls_before = int(page1.evaluate("() => window.LincheMockAPI ? window.LincheMockAPI.getTelemetry().planCalls : 0"))

            page1.locator("[data-testid='est-reset']").first.click(timeout=1200)
            page1.wait_for_timeout(160)
            txt0 = est_res.inner_text().strip()
            ms0 = ms_loc.inner_text().strip() if ms_loc.count() > 0 else ""

            types = page1.locator("[data-testid='est-type']")
            for ti in range(types.count()):
                t_el = types.nth(ti)
                is_sel = (
                    t_el.get_attribute("aria-pressed") == "true"
                    or t_el.get_attribute("aria-checked") == "true"
                    or t_el.get_attribute("data-active") == "true"
                    or (t_el.evaluate("e => e.tagName === 'INPUT' && e.checked"))
                )
                if not is_sel and t_el.is_visible():
                    t_el.click(timeout=1200)
                    page1.wait_for_timeout(140)
                    break
            txt1 = est_res.inner_text().strip()
            has_bad_token = bool(re.search(r"NaN|undefined|null", txt1))
            est_live_type_ok = (len(txt1) >= 4) and (txt1 != txt0) and (not has_bad_token)

            nums_before_addon = _extract_numbers(txt1)
            addons = page1.locator("[data-testid='est-addon']")
            toggled_addons = 0
            for ai in range(addons.count()):
                a_el = addons.nth(ai)
                is_on = (
                    a_el.get_attribute("aria-pressed") == "true"
                    or a_el.get_attribute("data-active") == "true"
                    or (a_el.evaluate("e => e.tagName === 'INPUT' && e.checked"))
                )
                if not is_on and a_el.is_visible():
                    a_el.click(timeout=1200)
                    toggled_addons += 1
                    if toggled_addons >= 2:
                        break
            # >=2 附加模块异步测算耗时 ~185ms
            page1.wait_for_timeout(280)

            scale_el = page1.locator("[data-testid='est-scale']").first
            if scale_el.count() > 0:
                stag = scale_el.evaluate("e => e.tagName.toLowerCase()")
                if stag == "select":
                    s_opts = scale_el.evaluate("e => Array.from(e.options).map(o => o.value)")
                    if len(s_opts) >= 2:
                        scale_el.select_option(s_opts[-1])
                elif stag == "input":
                    scale_el.evaluate("e => { e.value = e.max || '3'; e.dispatchEvent(new Event('input', {bubbles:true})); e.dispatchEvent(new Event('change', {bubbles:true})); }")
                else:
                    s_btns = scale_el.locator("button, [role='button'], [data-scale]")
                    if s_btns.count() >= 2:
                        s_btns.last.click(timeout=1200)
                page1.wait_for_timeout(280)

            txt2 = est_res.inner_text().strip()
            ms2 = ms_loc.inner_text().strip() if ms_loc.count() > 0 else ""
            nums_after_addon = _extract_numbers(txt2)
            plan_calls_after = int(page1.evaluate("() => window.LincheMockAPI ? window.LincheMockAPI.getTelemetry().planCalls : 0"))
            used_plan_api = plan_calls_after > plan_calls_before
            if nums_before_addon and nums_after_addon and "NaN" not in txt2 and used_plan_api:
                est_monotonic_addon_ok = (sum(nums_after_addon) > sum(nums_before_addon)) and (max(nums_after_addon) >= max(nums_before_addon))

            ms_children = int(
                page1.evaluate(
                    """() => {
                        const el = document.querySelector("[data-testid='est-milestones']");
                        if (!el || el.offsetParent === null) return 0;
                        const items = el.querySelectorAll('li, tr, [data-phase], [class*=\"phase\"], [class*=\"milestone\"], [class*=\"step\"]');
                        return items.length >= 2 ? items.length : el.children.length;
                    }"""
                )
            )
            milestones_live_ok = (len(ms2) >= 16) and (ms_children >= 2) and (ms2 != ms0) and ("NaN" not in ms2)

            # 对抗竞态：先勾回 2 个模块发起慢测算（185ms 在途），20ms 后立即点 Reset 发起快测算（35ms），等 340ms 后验证未被旧高价倒灌！
            page1.locator("[data-testid='est-reset']").first.click(timeout=1200)
            page1.wait_for_timeout(140)
            ads_race = page1.locator("[data-testid='est-addon']:visible")
            if ads_race.count() >= 2:
                ads_race.nth(0).click(timeout=1000)
                ads_race.nth(1).click(timeout=1000)
                page1.wait_for_timeout(20)
                page1.locator("[data-testid='est-reset']").first.click(timeout=1200)
                page1.wait_for_timeout(340)
                planner_race_reset_ok = est_res.inner_text().strip() == txt0

            est_diag = {
                "used_plan_api": used_plan_api,
                "live_type": est_live_type_ok,
                "monotonic_addon": est_monotonic_addon_ok,
                "milestones_live": milestones_live_ok,
                "planner_race_reset_ok": planner_race_reset_ok,
            }
        except Exception as exc:
            est_diag = {"error": str(exc)}

        a3_1_ratio = (
            (0.20 if est_live_type_ok else 0.0)
            + (0.25 if est_monotonic_addon_ok else 0.0)
            + (0.25 if milestones_live_ok else 0.0)
            + (0.30 if planner_race_reset_ok else 0.0)
        )
        a3_checks.append(
            _make_check(
                "A3.1",
                "[链A3-关1] 异步排期测算单调递增、多阶段里程碑与快速重置防旧报价倒灌",
                a3_1_ratio,
                2.6,
                est_diag,
                f"模式联动={est_live_type_ok}，叠加递增={est_monotonic_addon_ok}，里程碑拆解={milestones_live_ok}，慢算重置防倒灌={planner_race_reset_ok}",
            )
        )

        # ---- A3.2 [第2关] 去剧透忙闲冲突识别与短/长周期（含 6 周高负载跨度）排期消解（权重 3.0） ----
        slots_enough_ok = False
        short_conflict_resolved_ok = False
        long_span_resolved_ok = False
        sched_diag: dict = {}
        min_slots = int(req_cfg.get("min_schedule_slots", 4))

        try:
            page1.locator("[data-testid='est-reset']").first.click(timeout=1200)
            page1.wait_for_timeout(140)
            w_meta = _get_week_slots_meta(page1)
            slot_cnt = int(w_meta.get("count", 0))
            slots_enough_ok = slot_cnt >= min_slots

            if slot_cnt >= 4:
                # (1) 短周期（2 周默认方案）忙闲识别与消解：先确认存在空闲态无告警，再切入第 0/1 档（撞 11月第4周）验证告警与消解
                free_seen = False
                short_conflict_idx = -1
                for si in range(min(slot_cnt, 8)):
                    _select_week_slot(page1, si)
                    page1.wait_for_timeout(160)
                    c_ui = _detect_planner_conflict_ui(page1)
                    if c_ui["active"]:
                        if short_conflict_idx < 0:
                            short_conflict_idx = si
                    else:
                        free_seen = True

                if free_seen and short_conflict_idx >= 0:
                    _select_week_slot(page1, short_conflict_idx)
                    page1.wait_for_timeout(160)
                    sig_b = _get_week_slots_meta(page1).get("activeSig", "")
                    if _detect_planner_conflict_ui(page1)["active"] and _click_planner_conflict_resolver(page1):
                        page1.wait_for_timeout(260)
                        sig_a = _get_week_slots_meta(page1).get("activeSig", "")
                        short_conflict_resolved_ok = (sig_a != sig_b) and (not _detect_planner_conflict_ui(page1)["active"])

                # (2) 长周期（6 周高负载方案：切第 2 种模式 3w + 2 附加项 2w + 扩规模 1w = 6w）消解压测（防 10 周短日历死锁！）
                types = page1.locator("[data-testid='est-type']:visible")
                if types.count() >= 2:
                    types.nth(1).click(timeout=1000)
                ads = page1.locator("[data-testid='est-addon']:visible")
                for k in range(min(2, ads.count())):
                    is_on = (
                        ads.nth(k).get_attribute("aria-pressed") == "true"
                        or ads.nth(k).get_attribute("data-active") == "true"
                        or ads.nth(k).evaluate("e => e.tagName === 'INPUT' && e.checked")
                    )
                    if not is_on:
                        ads.nth(k).click(timeout=1000)
                page1.wait_for_timeout(280)

                # 选 12月第1周（index 2，跨度将撞上 12月第3周 busy！）
                _select_week_slot(page1, min(2, slot_cnt - 1))
                page1.wait_for_timeout(280)
                long_c_before = _detect_planner_conflict_ui(page1)["active"]
                sig_long_b = _get_week_slots_meta(page1).get("activeSig", "")
                ms_long_b = page1.locator("[data-testid='est-milestones']").first.inner_text().strip() if page1.locator("[data-testid='est-milestones']").count() > 0 else ""

                if long_c_before and _click_planner_conflict_resolver(page1):
                    page1.wait_for_timeout(320)
                    long_c_after = _detect_planner_conflict_ui(page1)["active"]
                    sig_long_a = _get_week_slots_meta(page1).get("activeSig", "")
                    ms_long_a = page1.locator("[data-testid='est-milestones']").first.inner_text().strip() if page1.locator("[data-testid='est-milestones']").count() > 0 else ""
                    long_span_resolved_ok = (not long_c_after) and (sig_long_a != sig_long_b) and (ms_long_a != ms_long_b)

            sched_diag = {
                "slot_count": slot_cnt,
                "slots_enough": slots_enough_ok,
                "short_conflict_resolved": short_conflict_resolved_ok,
                "long_span_resolved": long_span_resolved_ok,
            }
        except Exception as exc:
            sched_diag = {"error": str(exc)}

        a3_2_ratio = (
            (0.15 if slots_enough_ok else 0.0)
            + (0.40 if short_conflict_resolved_ok else 0.0)
            + (0.45 if long_span_resolved_ok else 0.0)
        )
        a3_checks.append(
            _make_check(
                "A3.2",
                "[链A3-关2] 忙闲档期冲突识别及短周期/长跨度（5～6周）空闲排期一键消解",
                a3_2_ratio,
                3.0,
                sched_diag,
                f"可选启动周≥{min_slots}个={slots_enough_ok}，短周期冲突消解={short_conflict_resolved_ok}，5～6周长跨度无死锁消解={long_span_resolved_ok}",
            )
        )

        # ---- A3.3 [第3关] 跨模块操作历史栈（Undo/Redo 覆盖对比篮+规划台 + Ctrl+Z + 输入框焦点防劫持，权重 3.0） ----
        undo_btn_ok = False
        redo_btn_ok = False
        cross_module_ctrlz_ok = False
        input_no_hijack_ok = False
        hist_diag: dict = {}

        try:
            clr_b = page1.locator("[data-testid='compare-clear']:visible")
            if clr_b.count() > 0:
                clr_b.first.click(timeout=1000)
                page1.wait_for_timeout(90)
            page1.locator("[data-testid='est-reset']").first.click(timeout=1200)
            page1.wait_for_timeout(160)

            est_res = page1.locator("[data-testid='est-result']").first
            undo_btn = page1.locator("[data-testid='workbench-undo']").first
            redo_btn = page1.locator("[data-testid='workbench-redo']").first

            # M1（对比篮模块）：加入第 1 个项目
            page1.locator("[data-testid='project-card']:visible").nth(0).locator("[data-testid='compare-toggle']").first.click(timeout=1200)
            page1.wait_for_timeout(110)
            cmp_after_m1 = _active_compare_count(page1)
            est_s0 = est_res.inner_text().strip()

            # M2（规划台模块）：勾选第 1 个附加模块（1 项附加模块耗时 35ms）
            ads_v = page1.locator("[data-testid='est-addon']:visible")
            ads_v.nth(0).click(timeout=1200)
            page1.wait_for_timeout(150)
            est_s1 = est_res.inner_text().strip()

            # M3（规划台模块）：勾选第 2 个附加模块（2 项附加模块耗时 185ms）
            ads_v.nth(1).click(timeout=1200)
            page1.wait_for_timeout(280)
            est_s2 = est_res.inner_text().strip()

            if cmp_after_m1 == 1 and est_s1 != est_s0 and est_s2 != est_s1 and undo_btn.count() > 0 and redo_btn.count() > 0:
                undo_btn.click(timeout=1200)
                page1.wait_for_timeout(220)
                undo_btn_ok = (est_res.inner_text().strip() == est_s1) and (_active_compare_count(page1) == 1)

                redo_btn.click(timeout=1200)
                page1.wait_for_timeout(280)
                redo_btn_ok = est_res.inner_text().strip() == est_s2

                page1.locator("[data-testid='theme-toggle']").first.focus()
                page1.keyboard.press("Control+z")
                page1.wait_for_timeout(140)
                page1.keyboard.press("Control+z")
                page1.wait_for_timeout(140)
                page1.keyboard.press("Control+z")
                page1.wait_for_timeout(220)
                cross_module_ctrlz_ok = (est_res.inner_text().strip() == est_s0) and (_active_compare_count(page1) == 0)

                ads_v.nth(0).click(timeout=1200)
                page1.wait_for_timeout(150)
                est_before_typing = est_res.inner_text().strip()
                msg_box = page1.locator("[data-testid='contact-message']").first
                msg_box.click(timeout=1000)
                msg_box.type("输入框原生撤销防误触验证")
                page1.keyboard.press("Control+z")
                page1.wait_for_timeout(160)
                input_no_hijack_ok = est_res.inner_text().strip() == est_before_typing

            hist_diag = {
                "undo_btn_ok": undo_btn_ok,
                "redo_btn_ok": redo_btn_ok,
                "cross_module_ctrlz_ok": cross_module_ctrlz_ok,
                "input_no_hijack_ok": input_no_hijack_ok,
            }
        except Exception as exc:
            hist_diag = {"error": str(exc)}

        a3_3_ratio = (
            (0.25 if undo_btn_ok else 0.0)
            + (0.25 if redo_btn_ok else 0.0)
            + (0.30 if cross_module_ctrlz_ok else 0.0)
            + (0.20 if input_no_hijack_ok else 0.0)
        )
        a3_checks.append(
            _make_check(
                "A3.3",
                "[链A3-关3] 跨模块撤销/重做栈（覆盖对比篮+异步规划台、Ctrl+Z 与输入框防劫持）",
                a3_3_ratio,
                3.0,
                hist_diag,
                f"按钮撤销={undo_btn_ok}，按钮重做={redo_btn_ok}，Ctrl+Z跨模块回退对比篮={cross_module_ctrlz_ok}，输入框Ctrl+Z不误触={input_no_hijack_ok}",
            )
        )

        # ---- A3.4 [第4关] 耦合非破坏带入、跨刷新守恒 + 异步提交防连点锁与 503 故障保底重试（权重 3.4） ----
        coupled_handoff_ok = False
        conservation_reload_ok = False
        no_duplicate_submit_ok = False
        resilience_503_and_receipt_ok = False
        submit_diag: dict = {}

        try:
            # 确保规划台处于无冲突有效档期且对比篮含第 1 个项目
            page1.locator("[data-testid='est-reset']").first.click(timeout=1200)
            page1.wait_for_timeout(150)
            p0_card = page1.locator("[data-testid='project-card']:visible").nth(0)
            p0_id = (p0_card.get_attribute("data-id") or "").strip()
            p0_title_tok = p0_card.locator("h2, h3, [data-testid='project-open']").first.inner_text().strip()[:4]
            if _active_compare_count(page1) == 0:
                p0_card.locator("[data-testid='compare-toggle']").first.click(timeout=1000)
                page1.wait_for_timeout(90)

            f_name = page1.locator("[data-testid='contact-name']").first
            f_email = page1.locator("[data-testid='contact-email']").first
            f_msg = page1.locator("[data-testid='contact-message']").first

            user_note = "补充说明：我们希望周四下午对齐评测样本细节。"
            f_name.fill("陆技术总监")
            f_email.fill("lu.cto@techcorp.cn")
            f_msg.fill(user_note)
            page1.wait_for_timeout(90)

            page1.locator("[data-testid='est-apply-to-contact']").first.click(timeout=1500)
            page1.wait_for_timeout(160)

            msg_after = f_msg.input_value()
            coupled_handoff_ok = (
                f_name.input_value() == "陆技术总监"
                and f_email.input_value() == "lu.cto@techcorp.cn"
                and (user_note in msg_after)
                and (p0_title_tok in msg_after)
                and (len(msg_after) >= len(user_note) + 20)
                and (len(msg_after) <= int(req_cfg["message_max_len"]))
            )

            # 收藏幂等去重 + 刷新后全工作台状态守恒
            b0 = p0_card.locator("[data-testid='favorite-btn']").first
            if not ((b0.get_attribute("aria-pressed") == "true") or (b0.get_attribute("data-favorited") == "true")):
                b0.click(timeout=1000)
            b0.click(timeout=1000)
            b0.click(timeout=1000)
            page1.wait_for_timeout(90)
            est_before_reload = page1.locator("[data-testid='est-result']").first.inner_text().strip()

            dup_store = page1.evaluate(
                """() => {
                    for (let i = 0; i < localStorage.length; i++) {
                        try {
                            const v = JSON.parse(localStorage.getItem(localStorage.key(i)));
                            if (Array.isArray(v) && new Set(v).size !== v.length) return true;
                        } catch (e) {}
                    }
                    return false;
                }"""
            )

            page1.reload(wait_until="domcontentloaded")
            _wait_bootstrap_ready(page1)
            if p0_id and page1.locator(f"[data-testid='project-card'][data-id='{p0_id}']").count() > 0:
                ca0_fav = page1.locator(f"[data-testid='project-card'][data-id='{p0_id}']").first.locator("[data-testid='favorite-btn']").first
            else:
                ca0_fav = page1.locator("[data-testid='project-card']").nth(0).locator("[data-testid='favorite-btn']").first
            fav_kept = (ca0_fav.get_attribute("aria-pressed") == "true") or (ca0_fav.get_attribute("data-favorited") == "true")
            est_kept = page1.locator("[data-testid='est-result']").first.inner_text().strip() == est_before_reload
            draft_kept = (
                page1.locator("[data-testid='contact-name']").first.input_value() == "陆技术总监"
                and (user_note in page1.locator("[data-testid='contact-message']").first.input_value())
            )
            conservation_reload_ok = fav_kept and est_kept and draft_kept and (not dup_store)

            if fav_kept:
                ca0_fav.click(timeout=1000)
            clr_after = page1.locator("[data-testid='compare-clear']:visible")
            if clr_after.count() > 0:
                clr_after.first.click(timeout=1000)

            # 非法校验拦截 + 连点并发锁（165ms 在途双击）+ 首次 503 SERVICE_BUSY 保底重试与真实回执单核验
            f_name = page1.locator("[data-testid='contact-name']").first
            f_email = page1.locator("[data-testid='contact-email']").first
            f_msg = page1.locator("[data-testid='contact-message']").first
            f_sub = _contact_submit_locator(page1)

            invalid_cases = [
                ("", "", ""),
                ("陈访客", "bad-email-format", "这是一段超过十个字的有效测试合作咨询留言。"),
                ("陈访客", "chen@example.org", "不足十字"),
                ("陈访客", "chen@example.org", "超" * 510),
            ]
            caught = 0
            for nm, em, mg in invalid_cases:
                f_name.fill(nm)
                f_email.fill(em)
                f_msg.fill(mg)
                f_sub.click(timeout=1200)
                page1.wait_for_timeout(200)
                has_err = page1.evaluate(
                    """() => Array.from(document.querySelectorAll("[data-testid='contact-error']"))
                        .some(el => el.offsetParent !== null && el.innerText.trim().length > 0)"""
                )
                if has_err:
                    caught += 1

            errs_before_submit = len(w1_errors)
            valid_msg = "林澈你好，我们研发团队希望预约两周评测诊断并对齐状态机回放方案。"
            f_name.fill("陈远航 <img src=x onerror=window.__form_xss=1>")
            f_email.fill("chen.yh@partner.cn")
            f_msg.fill(valid_msg)
            page1.wait_for_timeout(60)

            # 模拟访客手快双击提交（间隔 15ms 连续触发两次 click）
            page1.evaluate(
                """() => {
                    const btn = document.querySelector("[data-testid='contact-submit']") || document.querySelector("[data-testid='contact-generate']");
                    if (btn) {
                        btn.click();
                        setTimeout(() => { btn.click(); }, 15);
                    }
                }"""
            )
            page1.wait_for_timeout(480)

            tele_after_first = page1.evaluate("() => window.LincheMockAPI ? window.LincheMockAPI.getTelemetry() : {}") or {}
            no_duplicate_submit_ok = (
                int(tele_after_first.get("submitCalls", 0)) >= 1
                and int(tele_after_first.get("duplicateSubmits", 0)) == 0
            )

            # 若前端未做透明自动重试（而是展示 503 错误提示并保留表单内容等待用户点重试），校验输入框未丢失后再点一次重试！
            if int(tele_after_first.get("successfulInquiries", 0)) == 0:
                inputs_preserved_on_503 = (
                    ("陈远航" in f_name.input_value())
                    and (f_email.input_value() == "chen.yh@partner.cn")
                    and (valid_msg in f_msg.input_value())
                )
                if inputs_preserved_on_503 and f_sub.is_enabled():
                    f_sub.click(timeout=1200)
                    page1.wait_for_timeout(320)
            else:
                inputs_preserved_on_503 = True

            tele_final = page1.evaluate("() => window.LincheMockAPI ? window.LincheMockAPI.getTelemetry() : {}") or {}
            issued_ids = tele_final.get("issuedInquiryIds") or []
            receipt_check = page1.evaluate(
                """() => {
                    const recEl = document.querySelector("[data-testid='contact-receipt']") || document.querySelector("[data-testid='contact-output']");
                    const recText = recEl && recEl.offsetParent !== null
                        ? ((typeof recEl.value === 'string' ? recEl.value : recEl.innerText) || '')
                        : '';
                    return { recText, xss: Boolean(window.__form_xss) };
                }"""
            )
            has_genuine_receipt = bool(
                issued_ids
                and any(iid in receipt_check["recText"] for iid in issued_ids)
                and ("陈远航" in receipt_check["recText"])
            )
            resilience_503_and_receipt_ok = (
                caught == 4
                and inputs_preserved_on_503
                and has_genuine_receipt
                and (not receipt_check["xss"])
                and (len(w1_errors) == errs_before_submit)
            )
            submit_diag = {
                "coupled_handoff_ok": coupled_handoff_ok,
                "conservation_reload_ok": conservation_reload_ok,
                "invalid_caught": f"{caught}/4",
                "no_duplicate_submit_ok": no_duplicate_submit_ok,
                "inputs_preserved_on_503": inputs_preserved_on_503,
                "has_genuine_receipt": has_genuine_receipt,
                "issued_ids": issued_ids,
            }
        except Exception as exc:
            submit_diag = {"error": str(exc)}

        a3_4_ratio = (
            (0.25 if coupled_handoff_ok else 0.0)
            + (0.20 if conservation_reload_ok else 0.0)
            + (0.25 if no_duplicate_submit_ok else 0.0)
            + (0.30 if resilience_503_and_receipt_ok else 0.0)
        )
        a3_checks.append(
            _make_check(
                "A3.4",
                "[链A3-关4] 耦合方案非破坏带入、刷新守恒、防并发连点锁与 503 故障保底重试回执",
                a3_4_ratio,
                3.4,
                submit_diag,
                f"非破坏带入={coupled_handoff_ok}，跨刷新守恒={conservation_reload_ok}，双击零重发={no_duplicate_submit_ok}，503保底重试出真实单号={resilience_503_and_receipt_ok}",
            )
        )

        # ====================================================================
        # A4 连环压测链（6.5 分，按 A4.1 -> A4.2 -> A4.3 顺序连坐门控）
        # ====================================================================
        # ---- A4.1 [第1关] 文章与项目双类型异步深链接刷新保持及新标签页直达（权重 2.2） ----
        art_reload_ok = False
        art_newtab_ok = False
        proj_newtab_ok = False
        try:
            all_b = page1.locator("[data-testid='category-option'][data-category='all']")
            if all_b.count() > 0:
                all_b.first.click(timeout=1200)
                page1.wait_for_timeout(160)

            ac2 = page1.locator("[data-testid='article-card']:visible").nth(1)
            (ac2.locator("[data-testid='article-open']").first if ac2.locator("[data-testid='article-open']").count() > 0 else ac2).click(timeout=1500)
            _wait_detail_ready(page1)
            t_art = page1.locator("[data-testid='detail-title']").first.inner_text().strip()
            u_art = page1.url
            page1.reload(wait_until="domcontentloaded")
            _wait_detail_ready(page1)
            if page1.locator("[data-testid='detail-view']:visible").count() > 0:
                art_reload_ok = page1.locator("[data-testid='detail-title']").first.inner_text().strip() == t_art

            p_nt1 = ctx1.new_page()
            p_nt1.goto(u_art, wait_until="domcontentloaded")
            _wait_detail_ready(p_nt1)
            if p_nt1.locator("[data-testid='detail-view']:visible").count() > 0:
                art_newtab_ok = p_nt1.locator("[data-testid='detail-title']").first.inner_text().strip() == t_art
            p_nt1.close()

            page1.locator("[data-testid='detail-back']:visible").first.click(timeout=1200)
            page1.wait_for_timeout(140)
            pc2 = page1.locator("[data-testid='project-card']:visible").nth(1)
            (pc2.locator("[data-testid='project-open']").first if pc2.locator("[data-testid='project-open']").count() > 0 else pc2).click(timeout=1500)
            _wait_detail_ready(page1)
            t_proj = page1.locator("[data-testid='detail-title']").first.inner_text().strip()
            u_proj = page1.url

            p_nt2 = ctx1.new_page()
            p_nt2.goto(u_proj, wait_until="domcontentloaded")
            _wait_detail_ready(p_nt2)
            if p_nt2.locator("[data-testid='detail-view']:visible").count() > 0:
                proj_newtab_ok = p_nt2.locator("[data-testid='detail-title']").first.inner_text().strip() == t_proj
            p_nt2.close()

            bb = page1.locator("[data-testid='detail-back']:visible")
            if bb.count() > 0:
                bb.first.click(timeout=1200)
                page1.wait_for_timeout(120)
        except Exception:
            pass

        a4_1_ratio = (0.35 if art_reload_ok else 0.0) + (0.35 if art_newtab_ok else 0.0) + (0.30 if proj_newtab_ok else 0.0)
        a4_checks.append(
            _make_check(
                "A4.1",
                "[链A4-关1] 异步详情刷新保持与文章/项目双深链接新标签页直达",
                a4_1_ratio,
                2.2,
                {"art_reload_ok": art_reload_ok, "art_newtab_ok": art_newtab_ok, "proj_newtab_ok": proj_newtab_ok},
                f"长文刷新保持={art_reload_ok}，长文新标签直达={art_newtab_ok}，项目新标签直达={proj_newtab_ok}",
            )
        )

        # ---- A4.2 [第2关] 快速切篇防旧详情倒灌 + 五步连续浏览器历史栈（权重 2.5） ----
        detail_race_ok = False
        step_back_to_a1 = False
        step_back_to_list_kept = False
        step_forward_to_a1 = False
        try:
            # 先测快速切篇竞态：点开慢文档 art-gauntlet（195ms）25ms 后立即跳切快文档 art-async-race（40ms），等 320ms 看是否被慢响应覆盖
            slow_card = page1.locator("[data-testid='article-card'][data-id='art-gauntlet']:visible")
            fast_card = page1.locator("[data-testid='article-card'][data-id='art-async-race']:visible")
            if slow_card.count() > 0 and fast_card.count() > 0:
                (slow_card.first.locator("[data-testid='article-open']").first if slow_card.first.locator("[data-testid='article-open']").count() > 0 else slow_card.first).click(timeout=1200)
                page1.wait_for_timeout(25)
                # 若此时仍在列表或刚进入详情壳子，直接通过卡片、下一篇或路由切到第 2 篇
                if fast_card.first.is_visible():
                    (fast_card.first.locator("[data-testid='article-open']").first if fast_card.first.locator("[data-testid='article-open']").count() > 0 else fast_card.first).click(timeout=1200)
                elif page1.locator("[data-testid='article-next']:visible").count() > 0:
                    page1.locator("[data-testid='article-next']:visible").first.click(timeout=1200)
                elif "#article/" in page1.url:
                    page1.evaluate("window.location.hash = '#article/art-async-race'")
                page1.wait_for_timeout(340)
                cur_dt = page1.locator("[data-testid='detail-title']").first.inner_text().strip()
                detail_race_ok = ("慢请求倒灌" in cur_dt) or ("异步前端" in cur_dt)
                bb_r = page1.locator("[data-testid='detail-back']:visible")
                if bb_r.count() > 0:
                    bb_r.first.click(timeout=1200)
                    page1.wait_for_timeout(120)

            target_cat = chosen_cat or (specific_cats[0] if specific_cats else "all")
            if target_cat != "all":
                page1.locator(f"[data-testid='category-option'][data-category='{target_cat}']").first.click(timeout=1200)
                page1.wait_for_timeout(140)
            page1.locator("[data-testid='search-input']").first.fill("")
            page1.wait_for_timeout(200)

            url_home = page1.url
            vis_arts = page1.locator("[data-testid='article-card']:visible")
            if vis_arts.count() >= 2:
                ao0 = vis_arts.nth(0).locator("[data-testid='article-open']")
                (ao0.first if ao0.count() > 0 else vis_arts.nth(0)).click(timeout=1500)
                _wait_detail_ready(page1)
                url_a1 = page1.url
                title_a1 = page1.locator("[data-testid='detail-title']").first.inner_text().strip()

                page1.locator("[data-testid='article-next']:visible").first.click(timeout=1500)
                page1.wait_for_timeout(180)
                _wait_detail_ready(page1)
                url_a2 = page1.url
                title_a2 = page1.locator("[data-testid='detail-title']").first.inner_text().strip()

                if (url_a1 != url_home) and (url_a2 != url_a1) and (title_a2 != title_a1):
                    page1.go_back()
                    page1.wait_for_timeout(240)
                    _wait_detail_ready(page1)
                    if page1.locator("[data-testid='detail-view']:visible").count() > 0:
                        step_back_to_a1 = page1.locator("[data-testid='detail-title']").first.inner_text().strip() == title_a1

                    page1.go_back()
                    page1.wait_for_timeout(220)
                    if page1.locator("[data-testid='detail-view']:visible").count() == 0:
                        act_cat = page1.evaluate(
                            """() => {
                                const el = document.querySelector("[data-testid='category-option'][aria-pressed='true'], [data-testid='category-option'][data-active='true']");
                                return el ? (el.getAttribute('data-category') || '') : '';
                            }"""
                        )
                        step_back_to_list_kept = (target_cat == "all") or (act_cat == target_cat)

                    page1.go_forward()
                    page1.wait_for_timeout(240)
                    _wait_detail_ready(page1)
                    if page1.locator("[data-testid='detail-view']:visible").count() > 0:
                        step_forward_to_a1 = page1.locator("[data-testid='detail-title']").first.inner_text().strip() == title_a1
        except Exception:
            pass

        a4_2_ratio = (
            (0.30 if detail_race_ok else 0.0)
            + (0.25 if step_back_to_a1 else 0.0)
            + (0.25 if step_back_to_list_kept else 0.0)
            + (0.20 if step_forward_to_a1 else 0.0)
        )
        a4_checks.append(
            _make_check(
                "A4.2",
                "[链A4-关2] 快速切篇防慢详情倒灌与连续五步浏览器历史栈",
                a4_2_ratio,
                2.5,
                {
                    "detail_race_ok": detail_race_ok,
                    "back_to_art1": step_back_to_a1,
                    "back_to_list_filter_kept": step_back_to_list_kept,
                    "forward_to_art1": step_forward_to_a1,
                },
                f"快切防慢详情覆盖={detail_race_ok}，后退回上一篇={step_back_to_a1}，再退回列表保筛选={step_back_to_list_kept}，前进重返={step_forward_to_a1}",
            )
        )

        # ---- A4.3 [第3关] 点击文章目录真实滚动定位且不被吸顶导航遮挡（权重 1.8） ----
        toc_scroll_ok = False
        toc_diag: dict = {}
        try:
            if page1.locator("[data-testid='detail-view']:visible").count() == 0:
                ac0 = page1.locator("[data-testid='article-card']:visible").first
                ao0 = ac0.locator("[data-testid='article-open']")
                (ao0.first if ao0.count() > 0 else ac0).click(timeout=1500)
                _wait_detail_ready(page1)
            page1.evaluate("window.scrollTo(0, 0)")
            page1.wait_for_timeout(90)
            toc_items = page1.locator("[data-testid='article-toc']:visible a, [data-testid='article-toc']:visible button")
            if toc_items.count() >= 2:
                last_toc = toc_items.last
                last_toc_txt = last_toc.inner_text().strip()
                last_toc.click(timeout=1500)
                page1.wait_for_timeout(220)
                toc_diag = page1.evaluate(
                    """(tocTxt) => {
                        const headings = Array.from(document.querySelectorAll("[data-testid='detail-body'] h2, [data-testid='detail-body'] h3, [data-testid='detail-body'] h4"));
                        const target = headings.find(h => tocTxt && h.innerText.trim().includes(tocTxt.slice(0, 5))) || headings[headings.length - 1];
                        if (!target) return { ok: false, reason: 'no_heading' };
                        const hr = target.getBoundingClientRect();
                        let stickyBottom = 0;
                        for (const el of document.querySelectorAll('header, nav, [class*=\"top\"], [class*=\"nav\"]')) {
                            const cs = getComputedStyle(el);
                            if ((cs.position === 'fixed' || cs.position === 'sticky') && cs.display !== 'none' && cs.visibility !== 'hidden') {
                                const r = el.getBoundingClientRect();
                                if (r.top <= 10 && r.bottom > stickyBottom && r.height > 2 && r.height < 180) stickyBottom = r.bottom;
                            }
                        }
                        const notHiddenUnderHeader = hr.top >= stickyBottom - 6;
                        const inUpperViewport = hr.top < window.innerHeight * 0.75;
                        return {
                            ok: notHiddenUnderHeader && inUpperViewport,
                            headingTop: Math.round(hr.top),
                            stickyBottom: Math.round(stickyBottom),
                            scrollY: Math.round(window.scrollY)
                        };
                    }""",
                    last_toc_txt,
                )
                toc_scroll_ok = bool(toc_diag.get("ok"))
        except Exception as exc:
            toc_diag = {"error": str(exc)}

        a4_checks.append(
            _make_check(
                "A4.3",
                "[链A4-关3] 点击长文目录真实滚动至目标小标题且预留吸顶栏防遮挡间距",
                1.0 if toc_scroll_ok else 0.0,
                1.8,
                toc_diag,
                f"目录定位落入上半视口且未被顶栏遮盖={toc_scroll_ok} ({toc_diag})",
            )
        )
        log_step("wave1", "A_complete", a2_1_ratio >= 0.7 and a3_4_ratio >= 0.7, {"race_guard": race_guard_ok, "resilience_503": resilience_503_and_receipt_ok})
        ctx1.close()

        # ====================================================================
        # 第二波剧本：四档视口反截断几何与极端环境风暴（C1 9分 + C3 8分 = 17 分）
        # ====================================================================
        c1_checks: list[dict] = []
        c3_checks: list[dict] = []
        c_cfg = sc_cfg["C"]
        c1_w = c_cfg["c1_weights"]
        c3_w = c_cfg["c3_weights"]

        ctx2 = browser.new_context(viewport=vp_cfg["desktop"], color_scheme="light")
        ctx2.route("**/*", _intercept_external)
        page2 = ctx2.new_page()
        page2.goto(file_url, wait_until="domcontentloaded")
        _wait_bootstrap_ready(page2)

        overflow_records: dict[str, int] = {}
        clipped_records: dict[str, int] = {}
        clip_samples: list[str] = []

        for vp_name, vp_dim in vp_cfg.items():
            page2.set_viewport_size(vp_dim)
            page2.wait_for_timeout(90)
            res_h = page2.evaluate(JS_DETECT_CLIPPED_CONTROLS)
            overflow_records[f"{vp_name}_home"] = int(res_h["docOverflowPx"])
            clipped_records[f"{vp_name}_home"] = int(res_h["clippedCount"])
            clip_samples.extend(res_h["samples"])

        try:
            page2.set_viewport_size(vp_cfg["desktop"])
            ac_list = page2.locator("[data-testid='article-card']:visible")
            if ac_list.count() > 0:
                target_ac = ac_list.nth(min(rich_table_article_idx, ac_list.count() - 1))
                ao = target_ac.locator("[data-testid='article-open']")
                (ao.first if ao.count() > 0 else target_ac).click(timeout=1500)
                _wait_detail_ready(page2)
                for vp_name, vp_dim in vp_cfg.items():
                    page2.set_viewport_size(vp_dim)
                    page2.wait_for_timeout(80)
                    res_a = page2.evaluate(JS_DETECT_CLIPPED_CONTROLS)
                    overflow_records[f"{vp_name}_article"] = int(res_a["docOverflowPx"])
                    clipped_records[f"{vp_name}_article"] = int(res_a["clippedCount"])
                    clip_samples.extend(res_a["samples"])
                bb = page2.locator("[data-testid='detail-back']:visible")
                if bb.count() > 0:
                    bb.first.click(timeout=1200)
                    page2.wait_for_timeout(100)
        except Exception:
            pass

        try:
            page2.set_viewport_size(vp_cfg["desktop"])
            ctogs = page2.locator("[data-testid='compare-toggle']:visible")
            if ctogs.count() >= 2:
                ctogs.nth(0).click(timeout=1000)
                ctogs.nth(1).click(timeout=1000)
                page2.wait_for_timeout(90)
                copen = page2.locator("[data-testid='compare-open']:visible")
                if copen.count() > 0:
                    copen.first.click(timeout=1200)
                    page2.wait_for_timeout(120)
                    for vp_name in ("mobile", "mobile_narrow"):
                        page2.set_viewport_size(vp_cfg[vp_name])
                        page2.wait_for_timeout(90)
                        res_c = page2.evaluate(JS_DETECT_CLIPPED_CONTROLS)
                        overflow_records[f"{vp_name}_compare"] = int(res_c["docOverflowPx"])
                        clipped_records[f"{vp_name}_compare"] = int(res_c["clippedCount"])
                        clip_samples.extend(res_c["samples"])
                    ccls = page2.locator("[data-testid='compare-close']:visible")
                    if ccls.count() > 0:
                        ccls.first.click(timeout=1000)
                    else:
                        page2.keyboard.press("Escape")
                    page2.wait_for_timeout(90)
        except Exception:
            pass

        max_overflow_px = max(overflow_records.values()) if overflow_records else 0
        max_clipped_cnt = max(clipped_records.values()) if clipped_records else 0
        ov_part = interp_nodes(max_overflow_px, c_cfg["overflow_px_nodes"]) / 10.0
        clip_part = interp_nodes(max_clipped_cnt, c_cfg["clipped_controls_nodes"]) / 10.0
        c1_1_ratio = 0.55 * ov_part + 0.45 * clip_part

        c1_checks.append(
            _make_check(
                "C1.1",
                "四档视口（含表格长文与 SVG 对比面板）零横向溢出及反 overflow:hidden 控件硬截断",
                c1_1_ratio,
                c1_w["viewport_and_clip"],
                {"max_overflow_px": max_overflow_px, "max_clipped_controls": max_clipped_cnt, "samples": clip_samples[:4]},
                f"最大整页溢出 {max_overflow_px}px，被硬截断越界控件峰值 {max_clipped_cnt} 个",
            )
        )

        # ---- C1.2 320px 极限窄屏超长无空格字符串抗撑破压测 ----
        page2.set_viewport_size(vp_cfg["mobile_narrow"])
        page2.wait_for_timeout(90)
        long_token = "https://creator-hub-offline.local/workbench/" + ("UnbrokenLongMilestoneToken99_" * 4)
        stress_ov = int(
            page2.evaluate(
                """(tok) => {
                    const s = document.querySelector("[data-testid='search-input']");
                    const ct = document.querySelector("[data-testid='project-card'] h2, [data-testid='project-card'] h3, [data-testid='project-open']");
                    const er = document.querySelector("[data-testid='est-result']");
                    const ms = document.querySelector("[data-testid='est-milestones']");
                    const oCt = ct ? ct.textContent : '';
                    const oEr = er ? er.textContent : '';
                    const oMs = ms ? ms.textContent : '';
                    if (s) s.value = tok;
                    if (ct) ct.textContent = oCt + ' ' + tok;
                    if (er) er.textContent = oEr + ' ' + tok;
                    if (ms) ms.textContent = oMs + ' ' + tok;
                    const ov = Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth);
                    if (ct) ct.textContent = oCt;
                    if (er) er.textContent = oEr;
                    if (ms) ms.textContent = oMs;
                    if (s) s.value = '';
                    return ov;
                }""",
                long_token,
            )
        )
        c1_2_ratio = interp_nodes(stress_ov, c_cfg["overflow_px_nodes"]) / 10.0
        c1_checks.append(
            _make_check(
                "C1.2",
                "320px 极限窄屏多区域（含排期里程碑）注入 140 字符无空格长串抗撑破",
                c1_2_ratio,
                c1_w["long_word_stress"],
                {"stress_overflow_px": stress_ov},
                f"多处注入超长无空格串后整页横向溢出 {stress_ov}px",
            )
        )

        # ---- C1.3 & C1.4 375px 手机端悬浮对比栏同时开启下的动态遮挡、按钮防重叠与热区边距 ----
        page2.set_viewport_size(vp_cfg["mobile"])
        page2.wait_for_timeout(100)
        try:
            _contact_submit_locator(page2).click(timeout=1000)
            page2.wait_for_timeout(120)
        except Exception:
            pass

        mob_geom = page2.evaluate(
            JS_DETECT_OCCLUSION_AND_OVERLAP,
            {"minPx": int(c_cfg["touch_target_min_px"]), "idealPx": int(c_cfg["touch_target_ideal_px"])},
        )
        occ_base = mob_geom["unoccluded"] / max(1, mob_geom["checkedTargets"])
        fixed_pen = 1.0 if mob_geom["fixedRatio"] <= float(c_cfg["fixed_bars_max_viewport_ratio"]) else 0.45
        overlap_pen = 1.0 if mob_geom["overlapCount"] == 0 else max(0.2, 1.0 - 0.35 * mob_geom["overlapCount"])
        c1_3_ratio = occ_base * fixed_pen * overlap_pen

        c1_checks.append(
            _make_check(
                "C1.3",
                "手机视口吸顶+悬浮对比栏并发下零遮挡且按钮零物理重叠",
                c1_3_ratio,
                c1_w["dynamic_occlusion_overlap"],
                mob_geom,
                f"固定栏总占屏 {mob_geom['fixedRatio']*100:.1f}%，无遮挡 {mob_geom['unoccluded']}/{mob_geom['checkedTargets']}，按钮重叠对数={mob_geom['overlapCount']}",
            )
        )

        margin_ratio = interp_nodes(mob_geom["minEdgeGapPx"], c_cfg["mobile_margin_px_nodes"]) / 10.0
        c1_4_ratio = 0.55 * float(mob_geom["tapRatio"]) + 0.45 * margin_ratio
        c1_checks.append(
            _make_check(
                "C1.4",
                "手机端全控件触控热区达标率与正文容器左右防贴边留白",
                c1_4_ratio,
                c1_w["touch_and_margin"],
                {"tap_ratio": mob_geom["tapRatio"], "min_edge_gap_px": mob_geom["minEdgeGapPx"]},
                f"触控热区达标率 {mob_geom['tapRatio']*100:.0f}%，容器最小边距 {mob_geom['minEdgeGapPx']}px",
            )
        )
        ctx2.close()

        # ---- C3.1 多态脏缓存混沌注入 ----
        chaos_errors: list[str] = []
        ctx_chaos = browser.new_context(viewport=vp_cfg["desktop"])
        ctx_chaos.route("**/*", _intercept_external)
        ctx_chaos.add_init_script(
            """() => {
                try {
                    const seedChaos = {
                        favorites: '12345',
                        favs: '{"not":"an_array"}',
                        compare: '99999',
                        workbench_history: '{broken[[[',
                        estimator: '"not_an_object"',
                        draft: '"a_plain_string_not_object"',
                        contact_draft: '{broken_json[[[',
                        theme: '99999',
                        linche_hub_favs_v1: '12345',
                        linche_hub_cmp_v1: '{"wrong":true}',
                        linche_hub_est_v1: 'false',
                        linche_hub_draft_v1: 'false',
                        linche_hub_list_state_v1: '"wrong_type"'
                    };
                    for (const [k, v] of Object.entries(seedChaos)) localStorage.setItem(k, v);
                } catch (e) {}
            }"""
        )
        p_chaos = ctx_chaos.new_page()
        p_chaos.on("pageerror", lambda e: chaos_errors.append(str(e)))
        chaos_alive = False
        try:
            p_chaos.goto(file_url, wait_until="domcontentloaded")
            _wait_bootstrap_ready(p_chaos)
            p_chaos.evaluate(
                """() => {
                    try {
                        const keys = [];
                        for (let i = 0; i < localStorage.length; i++) keys.push(localStorage.key(i));
                        keys.forEach((k, idx) => {
                            localStorage.setItem(k, idx % 2 === 0 ? '42' : '{unclosed_json:[');
                        });
                    } catch (e) {}
                }"""
            )
            p_chaos.reload(wait_until="domcontentloaded")
            _wait_bootstrap_ready(p_chaos)
            chaos_alive = (
                p_chaos.locator("[data-testid='project-card']").count() >= 4
                and p_chaos.locator("[data-testid='article-card']").count() >= 4
            )
            if chaos_alive:
                p_chaos.locator("[data-testid='project-card']").first.locator("[data-testid='favorite-btn']").first.click(timeout=1000)
                p_chaos.wait_for_timeout(80)
        except Exception as exc:
            chaos_errors.append(str(exc))
        ctx_chaos.close()

        c3_1_ratio = (0.55 if chaos_alive else 0.0) + (0.45 if len(chaos_errors) == 0 else 0.0)
        c3_checks.append(
            _make_check(
                "C3.1",
                "localStorage 多态混沌注入（损坏串 + 异构错误类型 JSON）零异常恢复",
                c3_1_ratio,
                c3_w["chaos_corrupted_storage"],
                {"alive": chaos_alive, "page_errors": chaos_errors[:3]},
                f"异构脏缓存下异步启动与交互正常={chaos_alive}，未捕获异常数={len(chaos_errors)}",
            )
        )

        # ---- C3.2 存储读写全禁（SecurityError / QuotaExceededError）+ 剪贴板拒绝兜底 ----
        sec_errors: list[str] = []
        ctx_sec = browser.new_context(viewport=vp_cfg["desktop"])
        ctx_sec.route("**/*", _intercept_external)
        ctx_sec.add_init_script(
            """() => {
                Storage.prototype.getItem = function() {
                    throw new DOMException('Blocked storage read', 'SecurityError');
                };
                Storage.prototype.setItem = function() {
                    throw new DOMException('Quota full', 'QuotaExceededError');
                };
                if (navigator.clipboard) {
                    navigator.clipboard.writeText = function() {
                        return Promise.reject(new DOMException('Clipboard denied', 'NotAllowedError'));
                    };
                }
            }"""
        )
        p_sec = ctx_sec.new_page()
        p_sec.on("pageerror", lambda e: sec_errors.append(str(e)))
        sec_fallback_ok = False
        try:
            p_sec.goto(file_url, wait_until="domcontentloaded")
            _wait_bootstrap_ready(p_sec)
            p_sec.locator("[data-testid='est-apply-to-contact']").first.click(timeout=1200)
            p_sec.locator("[data-testid='contact-name']").first.fill("赵容错")
            p_sec.locator("[data-testid='contact-email']").first.fill("zhao@resilience.org")
            p_sec.locator("[data-testid='contact-message']").first.fill("测试本地存储读写全禁且剪贴板受限时，异步咨询提交与手动复制回执依然可用。")
            sub_s = _contact_submit_locator(p_sec)
            sub_s.click(timeout=1200)
            p_sec.wait_for_timeout(420)
            # 若遇首次 503，再点一次完成提交
            tele_s = p_sec.evaluate("() => window.LincheMockAPI ? window.LincheMockAPI.getTelemetry() : {}") or {}
            if int(tele_s.get("successfulInquiries", 0)) == 0 and sub_s.is_enabled():
                sub_s.click(timeout=1200)
                p_sec.wait_for_timeout(300)
            cp = p_sec.locator("[data-testid='contact-copy']:visible")
            if cp.count() > 0:
                cp.first.click(timeout=1000)
                p_sec.wait_for_timeout(120)
            out_txt = p_sec.evaluate(
                """() => {
                    const el = document.querySelector("[data-testid='contact-receipt']") || document.querySelector("[data-testid='contact-output']");
                    if (!el || el.offsetParent === null) return '';
                    return (typeof el.value === 'string' ? el.value : el.innerText) || '';
                }"""
            )
            sec_fallback_ok = ("赵容错" in out_txt) and ("INQ-2026-" in out_txt)
        except Exception as exc:
            sec_errors.append(str(exc))
        ctx_sec.close()

        c3_2_ratio = (0.55 if len(sec_errors) == 0 else 0.0) + (0.45 if sec_fallback_ok else 0.0)
        c3_checks.append(
            _make_check(
                "C3.2",
                "本地存储读写双禁（SecurityError/QuotaExceeded）与剪贴板受限平稳降级",
                c3_2_ratio,
                c3_w["quota_security_clipboard"],
                {"page_errors": sec_errors[:3], "manual_copy_retained": sec_fallback_ok},
                f"存储全禁零未捕获异常={len(sec_errors)==0}，剪贴板受限仍保留回执摘要供手动复制={sec_fallback_ok}",
            )
        )

        # ---- C3.3 & C3.4 系统深浅偏好跟随、全表面背景同步与陡峭 WCAG AA 9 角色木桶对比度 ----
        def _collect_full_theme_samples(scheme: str, toggle_click: bool = False) -> dict:
            c = browser.new_context(viewport=vp_cfg["desktop"], color_scheme=scheme)
            c.route("**/*", _intercept_external)
            pg = c.new_page()
            pg.goto(file_url, wait_until="domcontentloaded")
            _wait_bootstrap_ready(pg)
            if toggle_click:
                pg.locator("[data-testid='theme-toggle']").first.click(timeout=1200)
                pg.wait_for_timeout(140)

            try:
                _contact_submit_locator(pg).click(timeout=1000)
                pg.wait_for_timeout(200)
            except Exception:
                pass
            home_samples = pg.evaluate(JS_EXTRACT_CONTRAST_SAMPLES)
            body_bg = pg.evaluate(
                "() => (getComputedStyle(document.body).backgroundColor.match(/\\d+/g) || [255,255,255]).slice(0,3).map(Number)"
            )

            detail_bg = body_bg
            code_samples = []
            try:
                # 优先打开含代码块的 art-async-race 或首篇长文采样代码块对比度
                code_ac = pg.locator("[data-testid='article-card'][data-id='art-async-race']:visible")
                target_ac = code_ac.first if code_ac.count() > 0 else pg.locator("[data-testid='article-card']:visible").first
                if target_ac.count() > 0:
                    ao = target_ac.locator("[data-testid='article-open']")
                    (ao.first if ao.count() > 0 else target_ac).click(timeout=1200)
                    _wait_detail_ready(pg)
                    detail_samples = pg.evaluate(JS_EXTRACT_CONTRAST_SAMPLES)
                    code_samples = [s for s in detail_samples if s["role"] == "code_block"]
                    detail_bg = pg.evaluate(
                        """() => {
                            const dv = document.querySelector("[data-testid='detail-view']");
                            const m = dv ? getComputedStyle(dv).backgroundColor.match(/\\d+/g) : null;
                            return m && m.length >= 3 && !(m[3] === '0') ? m.slice(0,3).map(Number) : (getComputedStyle(document.body).backgroundColor.match(/\\d+/g) || [255,255,255]).slice(0,3).map(Number);
                        }"""
                    )
            except Exception:
                pass

            persisted = False
            if toggle_click:
                try:
                    bg_before_reload = pg.evaluate("getComputedStyle(document.body).backgroundColor")
                    pg.reload(wait_until="domcontentloaded")
                    _wait_bootstrap_ready(pg)
                    persisted = pg.evaluate("getComputedStyle(document.body).backgroundColor") == bg_before_reload
                except Exception:
                    pass
            c.close()

            merged = {s["role"]: s for s in home_samples}
            for cs in code_samples:
                merged[cs["role"]] = cs
            return {
                "body_bg": body_bg,
                "detail_bg": detail_bg,
                "samples": list(merged.values()),
                "persisted": persisted,
            }

        light_res = _collect_full_theme_samples("light", toggle_click=False)
        dark_auto = _collect_full_theme_samples("dark", toggle_click=False)
        dark_toggled = _collect_full_theme_samples("light", toggle_click=True)

        follows_system = (sum(light_res["body_bg"]) - sum(dark_auto["body_bg"])) > 180
        dark_use = dark_toggled if sum(dark_toggled["body_bg"]) < sum(light_res["body_bg"]) - 120 else dark_auto
        detail_dark_synced = sum(dark_use["detail_bg"]) < 360

        c3_3_ratio = (
            (0.40 if follows_system else 0.0)
            + (0.40 if dark_toggled["persisted"] else 0.0)
            + (0.20 if detail_dark_synced else 0.0)
        )
        c3_checks.append(
            _make_check(
                "C3.3",
                "系统深浅偏好跟随、手动切换跨刷新记忆与详情视图深色底色同步",
                c3_3_ratio,
                c3_w["theme_pref_and_surfaces"],
                {"follows_system": follows_system, "manual_persist": dark_toggled["persisted"], "detail_dark_synced": detail_dark_synced},
                f"系统跟随={follows_system}，手动切换记忆={dark_toggled['persisted']}，详情页深色背景同步={detail_dark_synced}",
            )
        )

        barrel_w = float(c_cfg.get("contrast_barrel_min_weight", 0.65))

        def _eval_barrel_contrast(samples: list[dict]) -> tuple[float, float | None, list[dict]]:
            if not samples:
                return 0.0, None, []
            ratios = []
            raw_crs = []
            details = []
            for s in samples:
                cr = wcag_contrast_ratio(s["fg"], s["bg"])
                raw_crs.append(cr)
                nodes = c_cfg["muted_contrast_nodes"] if s["role"] in ("muted", "badge") else c_cfg["body_contrast_nodes"]
                r = interp_nodes(cr, nodes) / 10.0
                ratios.append(r)
                details.append({"role": s["role"], "contrast": cr, "score_ratio": round(r, 2)})
            return barrel_score_ratio(ratios, min_weight=barrel_w), min(raw_crs), details

        l_score, min_cr_light, l_det = _eval_barrel_contrast(light_res["samples"])
        d_score, min_cr_dark, d_det = _eval_barrel_contrast(dark_use["samples"])
        if sum(dark_use["body_bg"]) > 550 and not dark_toggled["persisted"]:
            d_score *= 0.25
        c3_4_ratio = 0.5 * l_score + 0.5 * d_score

        c3_checks.append(
            _make_check(
                "C3.4",
                "浅色/深色 9 类界面角色（含激活态/徽章/代码块/排期与报错字）WCAG AA 短板木桶对比度",
                c3_4_ratio,
                c3_w["wcag_barrel_contrast"],
                {"light": l_det, "dark": d_det},
                f"浅色最低对比度={min_cr_light}:1 (木桶分 {l_score:.2f})，深色最低对比度={min_cr_dark}:1 (木桶分 {d_score:.2f})",
            )
        )
        log_step("wave2", "C1_C3_complete", c1_1_ratio >= 0.8 and c3_4_ratio >= 0.8, {"max_ov": max_overflow_px, "min_cr_dark": min_cr_dark})

        # ====================================================================
        # 第三波剧本：深度键盘无障碍、双向弹层焦点锁与高压规模性能测量（C2 8分 + B1 5分）
        # ====================================================================
        c2_checks: list[dict] = []
        c2_w = c_cfg["c2_weights"]

        ctx3 = browser.new_context(viewport=vp_cfg["desktop"], color_scheme="light")
        ctx3.route("**/*", _intercept_external)
        page3 = ctx3.new_page()

        t_nav0 = time.perf_counter()
        page3.goto(file_url, wait_until="domcontentloaded")
        page3.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
        first_paint_ms = (time.perf_counter() - t_nav0) * 1000.0
        _wait_bootstrap_ready(page3)

        visited_zones: set[str] = set()
        custom_ring_score_sum = 0.0
        checked_controls = 0
        stuck_trap = False
        prev_sig = None
        same_streak = 0

        for _ in range(68):
            page3.keyboard.press("Tab")
            info = page3.evaluate(
                """() => {
                    const el = document.activeElement;
                    if (!el || el === document.body) return null;
                    const tid = el.getAttribute('data-testid') || '';
                    const sig = el.tagName + '#' + (el.id || '') + ':' + tid + ':' + (el.innerText || '').slice(0, 14);
                    const cs = getComputedStyle(el);
                    const hasOutline = cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth || '0') >= 1.5;
                    const hasShadow = !!(cs.boxShadow && cs.boxShadow !== 'none');
                    const isCustomStyled = hasShadow || (hasOutline && (parseFloat(cs.outlineOffset || '0') >= 1.0 || !/rgb\\(0,\\s*0,\\s*0\\)/.test(cs.outlineColor)));

                    let zone = '';
                    if (tid === 'theme-toggle' || tid === 'workbench-undo' || tid === 'workbench-redo' || el.closest("[data-testid='hero-section']")) zone = 'header';
                    else if (tid === 'search-input' || tid === 'sort-control' || el.closest("[data-testid='sort-control']") || tid === 'category-option' || tid === 'favorite-filter') zone = 'search_filter';
                    else if (el.closest("[data-testid='project-list']")) zone = 'projects';
                    else if (el.closest("[data-testid='estimator-section']")) zone = 'estimator';
                    else if (el.closest("[data-testid='article-list']")) zone = 'articles';
                    else if (el.closest("[data-testid='contact-section']")) zone = 'contact';

                    return { sig, zone, visible: (hasOutline || hasShadow), custom: isCustomStyled };
                }"""
            )
            if not info:
                continue
            if info["sig"] == prev_sig:
                same_streak += 1
                if same_streak >= 4:
                    stuck_trap = True
                    break
            else:
                same_streak = 0
                prev_sig = info["sig"]
                checked_controls += 1
                if info["custom"]:
                    custom_ring_score_sum += 1.0
                elif info["visible"]:
                    custom_ring_score_sum += 0.6
            if info["zone"]:
                visited_zones.add(info["zone"])
            if len(visited_zones) >= 6 and checked_controls >= 12:
                break

        c2_1_ratio = (len(visited_zones) / 6.0) * (0.25 if stuck_trap else 1.0)
        c2_checks.append(
            _make_check(
                "C2.1",
                "纯键盘 Tab 顺序触达全站六大核心功能区（含规划台与项目卡）且无死循环",
                c2_1_ratio,
                c2_w["tab_reachability_6zones"],
                {"visited_zones": sorted(visited_zones), "stuck_trap": stuck_trap},
                f"Tab 触达功能区 {len(visited_zones)}/6 ({sorted(visited_zones)})，焦点卡死={stuck_trap}",
            )
        )

        c2_2_ratio = (custom_ring_score_sum / checked_controls) if checked_controls > 0 else 0.0
        c2_checks.append(
            _make_check(
                "C2.2",
                "键盘聚焦态定制化清晰焦点环（区分精心设计的 :focus-visible 与零样式裸框）",
                c2_2_ratio,
                c2_w["custom_focus_visible"],
                {"checked_controls": checked_controls, "weighted_focus_score": round(custom_ring_score_sum, 2)},
                f"抽检 {checked_controls} 个控件的可见定制焦点环得分率 {c2_2_ratio*100:.1f}%",
            )
        )

        # ---- C2.3 键盘进出详情焦点归位 + 对比面板双向焦点包含锁（Tab & Shift+Tab 防穿透）与 Escape 退出（高权重 5.5） ----
        detail_kbd_score = 0.0
        trap_forward_ok = False
        trap_backward_ok = False
        cmp_esc_return_ok = False
        try:
            marked = page3.evaluate(
                """() => {
                    const btn = document.querySelector("[data-testid='article-card'] [data-testid='article-open']");
                    if (!btn) return false;
                    btn.setAttribute('data-ch-kbd-origin', 'art-btn-0');
                    btn.focus();
                    return document.activeElement === btn;
                }"""
            )
            if marked:
                page3.keyboard.press("Enter")
                _wait_detail_ready(page3)
                if page3.locator("[data-testid='detail-view']:visible").count() > 0:
                    nxt = page3.locator("[data-testid='article-next']:visible").first
                    if nxt.count() > 0:
                        nxt.focus()
                        page3.keyboard.press("Enter")
                        _wait_detail_ready(page3)
                    focus_not_lost = page3.evaluate("() => Boolean(document.activeElement && document.activeElement !== document.body)")

                    # 先试 Escape；若详情页作为独立路由页未用 Esc 退出，则聚焦返回按钮按 Enter 验证纯键盘返回与焦点归位
                    page3.keyboard.press("Escape")
                    page3.wait_for_timeout(150)
                    closed_by_esc = page3.locator("[data-testid='detail-view']:visible").count() == 0
                    if not closed_by_esc:
                        bb_k = page3.locator("[data-testid='detail-back']:visible").first
                        if bb_k.count() > 0:
                            bb_k.focus()
                            page3.keyboard.press("Enter")
                            page3.wait_for_timeout(160)

                    closed_now = page3.locator("[data-testid='detail-view']:visible").count() == 0
                    returned_to_origin = page3.evaluate(
                        """() => {
                            const ae = document.activeElement;
                            if (!ae || ae === document.body) return false;
                            if (ae.getAttribute('data-ch-kbd-origin') === 'art-btn-0') return true;
                            const card = ae.closest("[data-testid='article-card']");
                            return !!(card && card.querySelector("[data-ch-kbd-origin='art-btn-0']"));
                        }"""
                    )
                    if focus_not_lost and closed_now and returned_to_origin:
                        detail_kbd_score = 0.35
                    elif focus_not_lost and closed_now:
                        detail_kbd_score = 0.15

            # 兜底确保 page3 已回到主列表视图，绝不因详情未关而漏测下方对比弹层焦点锁！
            if page3.locator("[data-testid='detail-view']:visible").count() > 0:
                bb_force = page3.locator("[data-testid='detail-back']:visible")
                if bb_force.count() > 0:
                    bb_force.first.click(timeout=1000)
                    page3.wait_for_timeout(140)

            ctogs = page3.locator("[data-testid='compare-toggle']:visible")
            if ctogs.count() >= 2:
                ctogs.nth(0).click(timeout=1000)
                ctogs.nth(1).click(timeout=1000)
                page3.wait_for_timeout(110)
                copen = page3.locator("[data-testid='compare-open']:visible").first
                if copen.count() > 0:
                    copen.evaluate("el => { el.setAttribute('data-ch-cmp-origin', '1'); el.focus(); }")
                    page3.keyboard.press("Enter")
                    page3.wait_for_timeout(150)
                    if page3.locator("[data-testid='compare-panel']:visible").count() > 0:
                        leaked_fwd = False
                        for _ in range(8):
                            page3.keyboard.press("Tab")
                            inside = page3.evaluate(
                                """() => {
                                    const panel = document.querySelector("[data-testid='compare-panel']");
                                    const ae = document.activeElement;
                                    return !!(panel && ae && panel.contains(ae));
                                }"""
                            )
                            if not inside:
                                leaked_fwd = True
                                break
                        trap_forward_ok = not leaked_fwd

                        leaked_bwd = False
                        for _ in range(5):
                            page3.keyboard.press("Shift+Tab")
                            inside = page3.evaluate(
                                """() => {
                                    const panel = document.querySelector("[data-testid='compare-panel']");
                                    const ae = document.activeElement;
                                    return !!(panel && ae && panel.contains(ae));
                                }"""
                            )
                            if not inside:
                                leaked_bwd = True
                                break
                        trap_backward_ok = not leaked_bwd

                        page3.keyboard.press("Escape")
                        page3.wait_for_timeout(140)
                        cmp_closed = page3.locator("[data-testid='compare-panel']:visible").count() == 0
                        cmp_returned = page3.evaluate(
                            """() => {
                                const ae = document.activeElement;
                                return !!(ae && (ae.getAttribute('data-ch-cmp-origin') === '1' || ae.closest("[data-testid='compare-bar']")));
                            }"""
                        )
                        cmp_esc_return_ok = bool(cmp_closed and cmp_returned)
        except Exception:
            pass

        c2_3_ratio = (
            detail_kbd_score
            + (0.25 if trap_forward_ok else 0.0)
            + (0.20 if trap_backward_ok else 0.0)
            + (0.20 if cmp_esc_return_ok else 0.0)
        )
        c2_checks.append(
            _make_check(
                "C2.3",
                "详情键盘返回焦点归位 + 对比面板双向焦点包含锁（Tab 与 Shift+Tab 防穿透）及 Escape 归位",
                c2_3_ratio,
                c2_w["modal_trap_and_focus_return"],
                {
                    "detail_kbd_score": detail_kbd_score,
                    "trap_forward_ok": trap_forward_ok,
                    "trap_backward_ok": trap_backward_ok,
                    "cmp_esc_return_ok": cmp_esc_return_ok,
                },
                f"详情键盘返回归位得分={detail_kbd_score:.2f}/0.35，对比弹层正向Tab锁={trap_forward_ok}，反向Shift+Tab锁={trap_backward_ok}，Esc归位={cmp_esc_return_ok}",
            )
        )

        # ---- B1.2 & B1.3 空闲 rAF 检测 + 320 节点高压注入搜索响应与长文滚动帧间隔测量 ----
        if page3.locator("[data-testid='detail-view']:visible").count() > 0:
            bb = page3.locator("[data-testid='detail-back']:visible")
            if bb.count() > 0:
                bb.first.click(timeout=1000)
                page3.wait_for_timeout(100)
        if page3.locator("[data-testid='compare-panel']:visible").count() > 0:
            ccls = page3.locator("[data-testid='compare-close']:visible")
            if ccls.count() > 0:
                ccls.first.click(timeout=1000)
                page3.wait_for_timeout(100)

        stress_cards_n = int(sc_cfg["B"].get("stress_injected_cards", 320))
        perf_probe = page3.evaluate(JS_IDLE_RAF_AND_STRESS_SEARCH, stress_cards_n)
        has_idle_raf = bool(perf_probe.get("hasIdleRafLoop"))
        sr_durs = sorted(float(x) for x in (perf_probe.get("searchDurations") or [300.0]))
        search_p95_ms = sr_durs[min(len(sr_durs) - 1, int(len(sr_durs) * 0.9))]

        try:
            ac = page3.locator("[data-testid='article-card']:visible")
            if ac.count() > 0:
                ao = ac.first.locator("[data-testid='article-open']")
                (ao.first if ao.count() > 0 else ac.first).click(timeout=1200)
                _wait_detail_ready(page3)
        except Exception:
            pass

        frame_deltas: list[float] = page3.evaluate(
            """async () => {
                const db = document.querySelector("[data-testid='detail-body']");
                const clones = [];
                if (db && db.children.length > 0) {
                    const seed = db.innerHTML;
                    for (let k = 0; k < 5; k++) {
                        const wrap = document.createElement('div');
                        wrap.innerHTML = seed;
                        db.appendChild(wrap);
                        clones.push(wrap);
                    }
                }
                const deltas = [];
                let last = performance.now();
                for (let i = 1; i <= 22; i++) {
                    window.scrollTo(0, i * 65);
                    window.dispatchEvent(new Event('scroll'));
                    await new Promise(r => requestAnimationFrame(r));
                    const now = performance.now();
                    deltas.push(now - last);
                    last = now;
                }
                for (const c of clones) {
                    if (c.parentNode) c.parentNode.removeChild(c);
                }
                return deltas;
            }"""
        )
        sorted_fd = sorted(float(x) for x in frame_deltas) if frame_deltas else [120.0]
        scroll_frame_p95_ms = sorted_fd[min(len(sorted_fd) - 1, int(len(sorted_fd) * 0.9))]

        log_step(
            "wave3",
            "C2_and_B1_complete",
            c2_3_ratio >= 0.5 and not has_idle_raf,
            {
                "first_paint_ms": round(first_paint_ms, 1),
                "search_p95_ms": round(search_p95_ms, 2),
                "scroll_frame_p95_ms": round(scroll_frame_p95_ms, 2),
                "has_idle_raf_loop": has_idle_raf,
            },
        )

        ctx3.close()
        browser.close()

    run_report = {
        "page_loadable": True,
        "not_implemented": False,
        "wave1": {
            "external_requests_count": len(ext_urls),
            "external_requests_sample": ext_urls[:10],
            "page_errors": w1_errors[:10],
            "dialogs_triggered": w1_dialogs[:5],
            "a1_checks": a1_checks,
            "a2_checks": a2_checks,
            "a3_checks": a3_checks,
            "a4_checks": a4_checks,
        },
        "wave2": {
            "max_overflow_px": max_overflow_px,
            "clipped_controls_count": max_clipped_cnt,
            "min_contrast_light": min_cr_light,
            "min_contrast_dark": min_cr_dark,
            "c1_checks": c1_checks,
            "c3_checks": c3_checks,
        },
        "wave3": {
            "c2_checks": c2_checks,
            "performance": {
                "first_paint_ms": round(first_paint_ms, 2),
                "search_median_ms": round(statistics.median(sr_durs), 2),
                "search_p95_ms": round(search_p95_ms, 2),
                "scroll_frame_p95_ms": round(scroll_frame_p95_ms, 2),
                "has_idle_raf_loop": has_idle_raf,
            },
        },
    }
    return run_report, trace
