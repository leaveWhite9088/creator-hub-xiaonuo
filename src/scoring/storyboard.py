# -*- coding: utf-8 -*-
"""替身体验官 v4.0：无头浏览器自动对接本地异步后端（mock_backend.js）走完耦合工作台与四大痛点全场景，
抓拍 12 张《交互状态连环画》并生成纯客观物理事实批注。

铁律：
  1. 全程拦截并阻断一切外网请求，仅访问盲评包内已脱敏的本地网页与官方只读 mock_backend.js；
  2. 只陈述客观物理数值与 DOM/Telemetry 事实（异步首屏落盘、滚动高度 Y1/Y2、SVG 多维图几何与标签重叠对数、
     排期冲突提示与顺延结果、503 繁忙重试与正式回执单号、100ms 复制反馈），绝不输出主观评语，绝不暴露 A/B/C 客观得分；
  3. 遇到未实现空壳页或局部控件缺失时平稳降级抓拍当前视口，绝不崩溃中断打包流程。
"""
from __future__ import annotations

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent.parent.parent


def _load_storyboard_cfg() -> dict:
    cfg_path = ROOT / "configs" / "benchmark.json"
    if cfg_path.exists():
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        return data.get("storyboard") or {}
    return {}


def capture_storyboard(index_html: Path, out_dir: Path) -> dict:
    """对脱敏后的 index.html 执行标准异步工作台体验路径，输出 S01..S12 截图与 STORYBOARD.md 索引数据。"""
    from playwright.sync_api import sync_playwright

    sb_cfg = _load_storyboard_cfg()
    desk_vp = sb_cfg.get("desktop_viewport") or {"width": 1440, "height": 900}
    mob_vp = sb_cfg.get("mobile_viewport") or {"width": 375, "height": 812}
    copy_delay_ms = int(sb_cfg.get("copy_feedback_delay_ms", 100))

    out_dir.mkdir(parents=True, exist_ok=True)
    panels: list[dict] = []
    dialogs_triggered: list[str] = []

    def add_panel(panel_id: str, title: str, filename: str, pain_group: str, facts: list[str]):
        panels.append(
            {
                "id": panel_id,
                "title": title,
                "filename": filename,
                "pain_group": pain_group,
                "facts": facts,
            }
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport=desk_vp, color_scheme="light")
        try:
            context.grant_permissions(["clipboard-read", "clipboard-write"])
        except Exception:
            pass

        context.route(
            "**/*",
            lambda route: route.abort()
            if route.request.url.startswith(("http://", "https://", "ws://", "wss://"))
            else route.continue_(),
        )

        page = context.new_page()

        def _on_dialog(dialog):
            dialogs_triggered.append(f"{dialog.type}: {dialog.message[:80]}")
            try:
                dialog.dismiss()
            except Exception:
                pass

        page.on("dialog", _on_dialog)
        file_url = index_html.resolve().as_uri()
        page.goto(file_url, wait_until="domcontentloaded")

        is_stub = page.evaluate("() => document.documentElement.getAttribute('data-unimplemented') === 'true'")
        if not is_stub:
            try:
                page.wait_for_function(
                    "() => document.querySelectorAll(\"[data-testid='project-card']\").length >= 4",
                    timeout=1400,
                )
            except Exception:
                pass
        page.wait_for_timeout(160)

        # ---------------- S01：桌面浅色首屏与整体视觉美学 ----------------
        home_meta = page.evaluate(
            """() => {
                const cs = getComputedStyle(document.body);
                const tel = (window.LincheMockAPI && typeof window.LincheMockAPI.getTelemetry === 'function')
                    ? window.LincheMockAPI.getTelemetry()
                    : null;
                return {
                    themeAttr: document.documentElement.getAttribute('data-theme') || '(未标注)',
                    bodyBg: cs.backgroundColor,
                    bodyColor: cs.color,
                    projCnt: document.querySelectorAll("[data-testid='project-card']").length,
                    artCnt: document.querySelectorAll("[data-testid='article-card']").length,
                    hasUndoRedo: !!(document.querySelector("[data-testid='workbench-undo']") && document.querySelector("[data-testid='workbench-redo']")),
                    bootstrapCalls: tel ? tel.bootstrapCalls : 0
                };
            }"""
        )
        s01_name = "S01_overview_desktop_light.png"
        page.screenshot(path=str(out_dir / s01_name), full_page=False)
        add_panel(
            "S01",
            "整体审美与工作台秩序 · 桌面浅色首屏全貌",
            s01_name,
            "整体审美与首屏秩序",
            [
                f"桌面视口 `{desk_vp['width']}×{desk_vp['height']}`；`html[data-theme]={home_meta['themeAttr']}`，背景 `{home_meta['bodyBg']}`，字色 `{home_meta['bodyColor']}`",
                f"异步首屏状态：`getBootstrap` 调用 `{home_meta['bootstrapCalls']}` 次，渲染项目卡 `{home_meta['projCnt']}` 份、长文卡 `{home_meta['artCnt']}` 篇；跨模块撤销/重做入口：`{'有' if home_meta['hasUndoRedo'] else '无'}`"
                + ("（未完成占位页）" if is_stub else ""),
            ],
        )

        # ---------------- S02：痛点一（筛选下滚并进出详情返回瞬间） ----------------
        selected_cat = "all"
        y1 = 0
        opened_detail = False
        try:
            cats = page.locator("[data-testid='category-option']")
            for i in range(cats.count()):
                cv = cats.nth(i).get_attribute("data-category") or ""
                if cv and cv.lower() != "all" and cats.nth(i).is_visible():
                    cats.nth(i).click(timeout=1200)
                    selected_cat = cv
                    page.wait_for_timeout(280)
                    break

            target_y = page.evaluate(
                """() => {
                    const pList = document.querySelector("[data-testid='project-list']");
                    const maxS = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
                    if (pList) {
                        const r = pList.getBoundingClientRect();
                        return Math.min(maxS, Math.max(200, Math.round(window.scrollY + r.top - 90)));
                    }
                    return Math.min(maxS, 260);
                }"""
            )
            page.evaluate(f"window.scrollTo(0, {int(target_y)})")
            page.wait_for_timeout(100)
            y1 = int(page.evaluate("Math.round(window.scrollY)"))

            pc = page.locator("[data-testid='project-card']:visible")
            if pc.count() > 0:
                op = pc.first.locator("[data-testid='project-open']")
                (op.first if op.count() > 0 else pc.first).click(timeout=1400)
                try:
                    page.wait_for_function(
                        """() => {
                            const dv = document.querySelector("[data-testid='detail-view']");
                            const db = document.querySelector("[data-testid='detail-body']");
                            return !!(dv && dv.offsetParent !== null && db && (db.innerText || '').trim().length > 40);
                        }""",
                        timeout=850,
                    )
                except Exception:
                    page.wait_for_timeout(240)
                opened_detail = page.locator("[data-testid='detail-view']:visible").count() > 0
                if opened_detail:
                    bb = page.locator("[data-testid='detail-back']:visible")
                    if bb.count() > 0:
                        bb.first.click(timeout=1400)
                    else:
                        page.go_back()
                    page.wait_for_timeout(180)
        except Exception:
            pass

        back_info = page.evaluate(
            """() => {
                const act = document.querySelector("[data-testid='category-option'][aria-pressed='true'], [data-testid='category-option'][data-active='true']");
                return {
                    y2: Math.round(window.scrollY),
                    activeCat: act ? (act.getAttribute('data-category') || act.textContent.trim()) : '(无激活标记)'
                };
            }"""
        )
        y2 = int(back_info["y2"])
        s02_name = "S02_pain1_after_back.png"
        page.screenshot(path=str(out_dir / s02_name), full_page=False)
        add_panel(
            "S02",
            "痛点一（来回翻找对比）· 筛选并下滚后打开异步详情再返回瞬间",
            s02_name,
            "痛点一：来回翻找与多方案对比",
            [
                f"是否成功完成“打开异步项目详情 → 返回列表”：`{'是' if opened_detail else '否'}`",
                f"打开前列表滚动高度 `Y1 = {y1} px` → 返回后瞬间滚动高度 `Y2 = {y2} px`（位移差 `|Y2 - Y1| = {abs(y2 - y1)} px`）",
                f"打开前筛选分类 `{selected_cat}` → 返回后激活分类 `{back_info['activeCat']}`",
            ],
        )

        # ---------------- S03：痛点一延伸（横向并排对比面板 + 原生 SVG 多维能力图） ----------------
        cmp_facts = {
            "panelVisible": False,
            "comparedCount": 0,
            "panelWidth": 0,
            "svgVisible": False,
            "svgSize": "0×0",
            "svgLabels": 0,
            "svgShapes": 0,
            "overlapPairs": 0,
        }
        try:
            all_b = page.locator("[data-testid='category-option'][data-category='all']")
            if all_b.count() > 0 and all_b.first.is_visible():
                all_b.first.click(timeout=1200)
                try:
                    page.wait_for_function(
                        "() => document.querySelectorAll(\"[data-testid='project-card']\").length >= 4",
                        timeout=700,
                    )
                except Exception:
                    page.wait_for_timeout(260)
            ctogs = page.locator("[data-testid='compare-toggle']:visible")
            if ctogs.count() >= 2:
                ctogs.nth(0).click(timeout=1000)
                ctogs.nth(1).click(timeout=1000)
                page.wait_for_timeout(120)
                copen = page.locator("[data-testid='compare-open']:visible")
                if copen.count() > 0:
                    copen.first.click(timeout=1200)
                    page.wait_for_timeout(180)
            cmp_facts = page.evaluate(
                """() => {
                    const p = document.querySelector("[data-testid='compare-panel']");
                    const pcs = p ? getComputedStyle(p) : null;
                    const pr = p ? p.getBoundingClientRect() : null;
                    const vis = !!(p && pcs && pcs.display !== 'none' && pcs.visibility !== 'hidden' && pr && pr.height > 4 && pr.width > 4);
                    const cnt = Array.from(document.querySelectorAll("[data-testid='compare-toggle']"))
                        .filter(b => {
                            const br = b.getBoundingClientRect();
                            return br.height > 0 && br.width > 0 && (b.getAttribute('aria-pressed') === 'true' || b.getAttribute('data-compared') === 'true');
                        }).length;
                    const svg = document.querySelector("[data-testid='compare-panel'] svg[data-testid='compare-chart'], svg[data-testid='compare-chart']");
                    const sr = svg ? svg.getBoundingClientRect() : null;
                    const svgVis = !!(svg && sr && sr.width >= 80 && sr.height >= 60 && getComputedStyle(svg).display !== 'none');
                    const textEls = svg ? Array.from(svg.querySelectorAll('text')).filter(t => (t.textContent || '').trim().length > 0) : [];
                    let overlapPairs = 0;
                    const boxes = textEls.map(t => t.getBoundingClientRect()).filter(b => b.width > 1 && b.height > 1);
                    for (let i = 0; i < boxes.length; i++) {
                        for (let j = i + 1; j < boxes.length; j++) {
                            const ix = Math.max(0, Math.min(boxes[i].right, boxes[j].right) - Math.max(boxes[i].left, boxes[j].left));
                            const iy = Math.max(0, Math.min(boxes[i].bottom, boxes[j].bottom) - Math.max(boxes[i].top, boxes[j].top));
                            if (ix > 4 && iy > 3) overlapPairs++;
                        }
                    }
                    const shapes = svg ? Array.from(svg.querySelectorAll('polygon, polyline, path, rect, circle')).filter(e => {
                        const tag = e.tagName.toLowerCase();
                        if (tag === 'rect') return parseFloat(e.getAttribute('width') || '0') > 2 && parseFloat(e.getAttribute('height') || '0') > 2;
                        if (tag === 'circle') return parseFloat(e.getAttribute('r') || '0') > 1.5;
                        return (((e.getAttribute('points') || e.getAttribute('d') || '').match(/\\d+/g) || []).length >= 6);
                    }).length : 0;
                    return {
                        panelVisible: vis,
                        comparedCount: cnt,
                        panelWidth: vis ? Math.round(pr.width) : 0,
                        svgVisible: svgVis,
                        svgSize: svgVis ? `${Math.round(sr.width)}×${Math.round(sr.height)} px` : '0×0',
                        svgLabels: textEls.length,
                        svgShapes: shapes,
                        overlapPairs
                    };
                }"""
            )
        except Exception:
            pass

        s03_name = "S03_pain1_compare_panel.png"
        page.screenshot(path=str(out_dir / s03_name), full_page=False)
        add_panel(
            "S03",
            "痛点一延伸（多方案对比与原生 SVG 能力图）· 勾选两份项目打开对比面板",
            s03_name,
            "痛点一：来回翻找与多方案对比",
            [
                f"当前已勾选对比项目数：`{cmp_facts['comparedCount']}` 项；`compare-panel` 可见：`{'是' if cmp_facts['panelVisible'] else '否'}`（宽 `{cmp_facts['panelWidth']} px`）",
                f"原生 `<svg data-testid='compare-chart'>` 可见：`{'是' if cmp_facts['svgVisible'] else '否'}`（尺寸 `{cmp_facts['svgSize']}`，文本标签 `{cmp_facts['svgLabels']}` 个，数据图形 `{cmp_facts['svgShapes']}` 个，文字包围盒重叠对数 `{cmp_facts['overlapPairs']}` 对）",
            ],
        )

        try:
            ccls = page.locator("[data-testid='compare-close']:visible")
            if ccls.count() > 0:
                ccls.first.click(timeout=1000)
            else:
                page.keyboard.press("Escape")
            page.wait_for_timeout(100)
            cclr = page.locator("[data-testid='compare-clear']:visible")
            if cclr.count() > 0:
                cclr.first.click(timeout=1000)
                page.wait_for_timeout(90)
        except Exception:
            pass

        # ---------------- S04：痛点二（无结果空搜索反馈与出路） ----------------
        try:
            s_input = page.locator("[data-testid='search-input']")
            if s_input.count() > 0 and s_input.first.is_visible():
                s_input.first.scroll_into_view_if_needed(timeout=1200)
                s_input.first.fill("量子引力超弦_无匹配词")
                try:
                    page.wait_for_function(
                        """() => {
                            const emp = document.querySelector("[data-testid='empty-state']");
                            return !!(emp && emp.offsetParent !== null && getComputedStyle(emp).visibility !== 'hidden');
                        }""",
                        timeout=850,
                    )
                except Exception:
                    page.wait_for_timeout(320)
                page.wait_for_timeout(80)
        except Exception:
            pass

        empty_facts = page.evaluate(
            """() => {
                const emp = document.querySelector("[data-testid='empty-state']");
                const sInput = document.querySelector("[data-testid='search-input']");
                const empVisible = !!(emp && emp.offsetParent !== null && getComputedStyle(emp).visibility !== 'hidden');
                const empText = empVisible ? emp.innerText.replace(/\\s+/g, ' ').trim().slice(0, 140) : '(不可见)';
                const empActions = empVisible
                    ? Array.from(emp.querySelectorAll('button, a, [role=\"button\"]'))
                        .filter(el => el.offsetParent !== null)
                        .map(el => el.innerText.replace(/\\s+/g, ' ').trim())
                        .filter(Boolean)
                    : [];
                let nearbyClear = [];
                if (sInput && sInput.parentElement) {
                    nearbyClear = Array.from(sInput.parentElement.querySelectorAll('button, [role=\"button\"]'))
                        .filter(el => el.offsetParent !== null)
                        .map(el => el.innerText.trim() || el.getAttribute('aria-label') || '图标按钮');
                }
                return { empVisible, empText, empActions, nearbyClear };
            }"""
        )
        s04_name = "S04_pain2_empty_search.png"
        page.screenshot(path=str(out_dir / s04_name), full_page=False)
        add_panel(
            "S04",
            "痛点二（搜不到卡死空白页）· 异步无结果检索后的引导与恢复控件",
            s04_name,
            "痛点二：搜不到内容受挫",
            [
                f"`empty-state` 可见：`{'是' if empty_facts['empVisible'] else '否'}`；提示文案摘录：`{empty_facts['empText']}`",
                f"空状态内可点击恢复/建议按钮：`{len(empty_facts['empActions'])}` 个（`{empty_facts['empActions'][:6]}`）；搜索框旁清空控件：`{empty_facts['nearbyClear'][:3]}`",
            ],
        )

        try:
            s_input = page.locator("[data-testid='search-input']")
            if s_input.count() > 0:
                s_input.first.fill("")
                try:
                    page.wait_for_function(
                        """() => {
                            const cards = Array.from(document.querySelectorAll("[data-testid='article-card']"));
                            return cards.some(c => c.offsetParent !== null);
                        }""",
                        timeout=950,
                    )
                except Exception:
                    page.wait_for_timeout(320)
                page.wait_for_timeout(80)
        except Exception:
            pass

        # ---------------- S05 & S06：痛点三（含数据表格/代码的长文 50% 桌面与手机画面） ----------------
        art_opened = False
        try:
            art_cards = page.locator("[data-testid='article-card']:visible")
            n_arts = art_cards.count()
            for idx in range(n_arts):
                card = art_cards.nth(idx)
                btn = card.locator("[data-testid='article-open']")
                (btn.first if btn.count() > 0 else card).click(timeout=1400)
                try:
                    page.wait_for_function(
                        """() => {
                            const db = document.querySelector("[data-testid='detail-body']");
                            return !!(db && (db.innerText || '').trim().length > 160);
                        }""",
                        timeout=850,
                    )
                except Exception:
                    page.wait_for_timeout(240)
                has_table_or_code = page.evaluate(
                    """() => {
                        const b = document.querySelector("[data-testid='detail-body']");
                        return !!(b && (b.querySelector('table') || b.querySelector('pre')));
                    }"""
                )
                if has_table_or_code:
                    art_opened = True
                    break
                back = page.locator("[data-testid='detail-back']:visible")
                if back.count() > 0 and idx + 1 < n_arts:
                    back.first.click(timeout=1000)
                    page.wait_for_timeout(160)
                else:
                    art_opened = page.locator("[data-testid='detail-view']:visible").count() > 0
        except Exception:
            pass

        def _scroll_article_mid():
            return page.evaluate(
                """() => {
                    const dv = document.querySelector("[data-testid='detail-view']");
                    const db = document.querySelector("[data-testid='detail-body']");
                    if (dv) {
                        const cs = getComputedStyle(dv);
                        if ((cs.overflowY === 'auto' || cs.overflowY === 'scroll') && dv.scrollHeight > dv.clientHeight + 80) {
                            dv.scrollTop = Math.round((dv.scrollHeight - dv.clientHeight) * 0.5);
                            return { mode: 'container', scrollPos: Math.round(dv.scrollTop) };
                        }
                    }
                    if (db) {
                        const rect = db.getBoundingClientRect();
                        const topAbs = window.scrollY + rect.top;
                        const target = Math.max(0, Math.round(topAbs + Math.max(0, rect.height - window.innerHeight) * 0.5));
                        window.scrollTo(0, target);
                        return { mode: 'window', scrollPos: Math.round(window.scrollY) };
                    }
                    return { mode: 'none', scrollPos: 0 };
                }"""
            )

        scroll_desk = _scroll_article_mid()
        page.wait_for_timeout(140)
        desk_art = page.evaluate(
            """() => {
                const db = document.querySelector("[data-testid='detail-body']");
                const toc = document.querySelector("[data-testid='article-toc']");
                const dbRect = db ? db.getBoundingClientRect() : null;
                let tocInViewport = false;
                let tocActiveCount = 0;
                let tocTotal = 0;
                if (toc && toc.offsetParent !== null) {
                    const tr = toc.getBoundingClientRect();
                    tocInViewport = tr.bottom > 20 && tr.top < window.innerHeight - 20;
                    const items = Array.from(toc.querySelectorAll('a, button'));
                    tocTotal = items.length;
                    tocActiveCount = items.filter(el => {
                        const ac = el.getAttribute('aria-current');
                        return (ac && ac !== 'false') ||
                            el.getAttribute('data-active') === 'true' ||
                            /active|current|highlight/i.test(el.className || '');
                    }).length;
                }
                const hasTable = !!(db && db.querySelector('table'));
                const hasCode = !!(db && db.querySelector('pre'));
                const hasProgress = document.querySelectorAll("progress, [role='progressbar'], [class*='progress']").length > 0;
                return {
                    bodyWidthPx: dbRect ? Math.round(dbRect.width) : 0,
                    tocInViewport,
                    tocTotal,
                    tocActiveCount,
                    hasTable,
                    hasCode,
                    hasProgress
                };
            }"""
        )
        s05_name = "S05_pain3_article_50pct_desktop.png"
        page.screenshot(path=str(out_dir / s05_name), full_page=False)
        add_panel(
            "S05",
            "痛点三（长文表格代码易迷路）· 桌面端滚至 50% 进度阅读画面",
            s05_name,
            "痛点三：长文与表格代码阅读",
            [
                f"长文已打开：`{'是' if art_opened else '否'}`（含表格=`{desk_art['hasTable']}`，含代码块=`{desk_art['hasCode']}`）；正文渲染宽度 `{desk_art['bodyWidthPx']} px`",
                f"滚至 50%（`{scroll_desk['scrollPos']} px`）时目录仍在视口内：`{'是' if desk_art['tocInViewport'] else '否'}`（共 `{desk_art['tocTotal']}` 项，高亮激活 `{desk_art['tocActiveCount']}` 项）；进度指示元素：`{'有' if desk_art['hasProgress'] else '无'}`",
            ],
        )

        page.set_viewport_size(mob_vp)
        page.wait_for_timeout(130)
        _scroll_article_mid()
        page.wait_for_timeout(130)
        mob_art = page.evaluate(
            """() => {
                const doc = document.documentElement;
                const db = document.querySelector("[data-testid='detail-body']");
                const r = db ? db.getBoundingClientRect() : null;
                return {
                    scrollWidth: doc.scrollWidth,
                    clientWidth: doc.clientWidth,
                    leftGapPx: r ? Math.round(r.left) : 0,
                    rightGapPx: r ? Math.round(window.innerWidth - r.right) : 0
                };
            }"""
        )
        s06_name = "S06_pain3_article_50pct_mobile.png"
        page.screenshot(path=str(out_dir / s06_name), full_page=False)
        add_panel(
            "S06",
            "痛点三（长文表格代码易迷路）· 手机窄屏 50% 进度重排画面",
            s06_name,
            "痛点三：长文与表格代码阅读",
            [
                f"手机视口 `{mob_vp['width']}×{mob_vp['height']}`：`scrollWidth={mob_art['scrollWidth']} px` vs `clientWidth={mob_art['clientWidth']} px`；正文边距 左 `{mob_art['leftGapPx']} px` / 右 `{mob_art['rightGapPx']} px`",
            ],
        )

        # 切回桌面并退回列表，进入顾问排期规划工作台
        page.set_viewport_size(desk_vp)
        page.wait_for_timeout(120)
        try:
            bb = page.locator("[data-testid='detail-back']:visible")
            if bb.count() > 0:
                bb.first.click(timeout=1200)
                page.wait_for_timeout(160)
        except Exception:
            pass

        # 无剧透检测规划台内的档期冲突提示与顺延动作按钮
        js_inspect_planner = """() => {
            const sec = document.querySelector("[data-testid='estimator-section']");
            if (!sec) return { msVisible: false, msText: '(无)', conflictVisible: false, conflictText: '(无)', resolveVisible: false, resolveLabel: '(无)' };
            const ms = sec.querySelector("[data-testid='est-milestones']") || document.querySelector("[data-testid='est-milestones']");
            const msVis = !!(ms && ms.offsetParent !== null && (ms.innerText || '').trim().length > 0);
            const alertCand = Array.from(sec.querySelectorAll("[data-testid='est-conflict'], [role='alert'], [aria-live], [data-conflict='true'], .conflict, [class*='conflict'], [class*='warn'], [class*='alert']"))
                .find(el => {
                    const cs = getComputedStyle(el);
                    const r = el.getBoundingClientRect();
                    const t = (el.innerText || '').trim();
                    return cs.display !== 'none' && cs.visibility !== 'hidden' && r.height > 2 && r.width > 4 && /冲突|占用|已满|繁忙|不可用|顺延|档期/.test(t);
                });
            let cfText = alertCand ? alertCand.innerText.replace(/\\s+/g, ' ').trim().slice(0, 100) : '';
            if (!cfText) {
                const full = (sec.innerText || '').replace(/\\s+/g, ' ');
                const m = full.match(/[^。；!！]{0,18}(?:档期冲突|已被占用|已有交付|档期已满|繁忙周|冲突周)[^。；!！]{0,45}/);
                if (m) cfText = m[0].trim();
            }
            const btns = Array.from(sec.querySelectorAll("button, [role='button']"));
            const resBtn = btns.find(b => {
                const cs = getComputedStyle(b);
                const r = b.getBoundingClientRect();
                if (cs.display === 'none' || cs.visibility === 'hidden' || r.height <= 2 || r.width <= 4 || b.disabled) return false;
                if (b.getAttribute('data-testid') === 'est-resolve-conflict') return true;
                const txt = ((b.innerText || '') + ' ' + (b.getAttribute('aria-label') || '')).trim();
                return /顺延|最近空闲|自动调|避开冲突|改期|推荐档期|可用周|跳过繁忙/.test(txt);
            });
            return {
                msVisible: msVis,
                msText: msVis ? ms.innerText.replace(/\\s+/g, ' ').trim().slice(0, 110) : '(不可见)',
                conflictVisible: !!cfText,
                conflictText: cfText || '(未检测到冲突提示)',
                resolveVisible: !!resBtn,
                resolveLabel: resBtn ? (resBtn.innerText || resBtn.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim().slice(0, 32) : '(无)'
            };
        }"""

        # ---------------- S07：耦合规划工作台（异步报价 + 里程碑拆解 + 繁忙档期冲突触发） ----------------
        est_before_txt = ""
        est_after_txt = ""
        planner_facts = {
            "msVisible": False,
            "msText": "(无)",
            "conflictVisible": False,
            "conflictText": "(无)",
            "resolveVisible": False,
            "resolveLabel": "(无)",
        }
        try:
            ct0 = page.locator("[data-testid='compare-toggle']:visible")
            if ct0.count() > 0:
                ct0.first.click(timeout=1000)
                page.wait_for_timeout(80)

            est_sec = page.locator("[data-testid='estimator-section']")
            if est_sec.count() > 0:
                est_sec.first.scroll_into_view_if_needed(timeout=1200)
                page.wait_for_timeout(120)
                est_res = page.locator("[data-testid='est-result']")
                if est_res.count() > 0:
                    est_before_txt = est_res.first.inner_text().replace("\n", " ").strip()[:70]
                types = page.locator("[data-testid='est-type']:visible")
                if types.count() >= 2:
                    types.nth(1).click(timeout=1000)
                    page.wait_for_timeout(80)
                addons = page.locator("[data-testid='est-addon']:visible")
                if addons.count() >= 2:
                    addons.nth(0).click(timeout=1000)
                    addons.nth(1).click(timeout=1000)
                page.wait_for_timeout(260)

                w_el = page.locator("[data-testid='est-start-week']")
                if w_el.count() > 0:
                    w_tag = w_el.first.evaluate("e => e.tagName.toLowerCase()")
                    if w_tag == "select":
                        n_opt = w_el.first.evaluate("e => e.options.length")
                        for oi in range(n_opt):
                            w_el.first.select_option(index=oi)
                            page.wait_for_timeout(240)
                            pf = page.evaluate(js_inspect_planner)
                            if pf.get("conflictVisible"):
                                break
                    else:
                        w_btns = w_el.first.locator("[data-week]:visible, button:visible, [role='radio']:visible")
                        for oi in range(w_btns.count()):
                            w_btns.nth(oi).click(timeout=1000)
                            page.wait_for_timeout(240)
                            pf = page.evaluate(js_inspect_planner)
                            if pf.get("conflictVisible"):
                                break

                if est_res.count() > 0:
                    est_after_txt = est_res.first.inner_text().replace("\n", " ").strip()[:90]

                planner_facts = page.evaluate(js_inspect_planner)
                est_sec.first.scroll_into_view_if_needed(timeout=1000)
                page.wait_for_timeout(80)
        except Exception:
            pass

        s07_name = "S07_workbench_estimator.png"
        page.screenshot(path=str(out_dir / s07_name), full_page=False)
        add_panel(
            "S07",
            "耦合规划工作台 · 异步报价、阶段里程碑与繁忙档期冲突画面",
            s07_name,
            "交互工作台：范围、里程碑与档期规划",
            [
                f"初始 `est-result`：`{est_before_txt or '(未找到)'}` → 叠加模块后：`{est_after_txt or '(未更新)'}`",
                f"阶段里程碑 `est-milestones` 可见：`{'是' if planner_facts['msVisible'] else '否'}`（`{planner_facts['msText']}`）",
                f"档期冲突提示可见：`{'是' if planner_facts['conflictVisible'] else '否'}`（`{planner_facts['conflictText']}`）；顺延调整控件：`{'有（' + planner_facts['resolveLabel'] + '）' if planner_facts['resolveVisible'] else '未发现独立顺延按钮'}`",
            ],
        )

        # ---------------- S08, S09, S10：顺延消解 + 耦合带入 + 校验消错 + 异步提交(503恢复)与 100ms 复制 ----------------
        dialogs_before_form = len(dialogs_triggered)
        handoff_kept_note = False
        conflict_cleared_after_resolve = False
        try:
            clicked_resolve = page.evaluate(
                """() => {
                    const sec = document.querySelector("[data-testid='estimator-section']");
                    if (!sec) return false;
                    const btns = Array.from(sec.querySelectorAll("button, [role='button']"));
                    const resBtn = btns.find(b => {
                        const cs = getComputedStyle(b);
                        const r = b.getBoundingClientRect();
                        if (cs.display === 'none' || cs.visibility === 'hidden' || r.height <= 2 || r.width <= 4 || b.disabled) return false;
                        if (b.getAttribute('data-testid') === 'est-resolve-conflict') return true;
                        const txt = ((b.innerText || '') + ' ' + (b.getAttribute('aria-label') || '')).trim();
                        return /顺延|最近空闲|自动调|避开冲突|改期|推荐档期|可用周|跳过繁忙/.test(txt);
                    });
                    if (resBtn) { resBtn.click(); return true; }
                    return false;
                }"""
            )
            if clicked_resolve:
                page.wait_for_timeout(260)
                pf_after = page.evaluate(js_inspect_planner)
                conflict_cleared_after_resolve = not pf_after.get("conflictVisible")
            else:
                # 若选手未提供顺延按钮，切到靠后的空闲启动周以便后续正常测试联系单提交
                w_el = page.locator("[data-testid='est-start-week']")
                if w_el.count() > 0:
                    w_tag = w_el.first.evaluate("e => e.tagName.toLowerCase()")
                    if w_tag == "select":
                        w_el.first.select_option(value="2026-W52")
                    else:
                        w52 = w_el.first.locator("[data-week='2026-W52']")
                        if w52.count() > 0:
                            w52.first.click(timeout=1000)
                    page.wait_for_timeout(240)

            c_name = page.locator("[data-testid='contact-name']").first
            c_email = page.locator("[data-testid='contact-email']").first
            c_msg = page.locator("[data-testid='contact-message']").first
            c_sub = page.locator("[data-testid='contact-submit'], [data-testid='contact-generate']").first

            c_name.fill("周合作")
            c_email.fill("invalid-email-at")
            c_msg.fill("附注：团队目前在杭州。")
            apply_btn = page.locator("[data-testid='est-apply-to-contact']")
            if apply_btn.count() > 0 and apply_btn.first.is_visible():
                apply_btn.first.click(timeout=1200)
                page.wait_for_timeout(140)
            handoff_kept_note = "团队目前在杭州" in c_msg.input_value() and len(c_msg.input_value()) > 16

            page.locator("[data-testid='contact-section']").first.scroll_into_view_if_needed(timeout=1200)
            c_sub.click(timeout=1200)
            page.wait_for_timeout(220)
        except Exception:
            pass

        err_facts = page.evaluate(
            """() => {
                const errs = Array.from(document.querySelectorAll("[data-testid='contact-error']"))
                    .filter(el => el.offsetParent !== null && el.innerText.trim().length > 0);
                const ae = document.activeElement;
                return {
                    visibleErrorCount: errs.length,
                    errorText: errs.map(e => e.innerText.replace(/\\s+/g, ' ').trim()).join(' | ').slice(0, 150),
                    activeElem: ae ? (ae.getAttribute('data-testid') || ae.tagName.toLowerCase()) : 'none'
                };
            }"""
        )
        alert_used = len(dialogs_triggered) > dialogs_before_form
        s08_name = "S08_pain4_handoff_and_error.png"
        page.screenshot(path=str(out_dir / s08_name), full_page=False)
        add_panel(
            "S08",
            "痛点四（顺延消解、耦合方案带入与填表摩擦）· 带入方案并触发错误邮箱校验瞬间",
            s08_name,
            "痛点四：排期带入、填表与异步提交摩擦",
            [
                f"点击顺延后档期冲突已消除：`{'是' if conflict_cleared_after_resolve else '否/未提供一键顺延'}`；耦合带入是否保留访客原附注：`{'是' if handoff_kept_note else '否'}`；原生阻塞 `alert()`：`{'是' if alert_used else '否'}`",
                f"可见 `contact-error` 数：`{err_facts['visibleErrorCount']}` 处（`{err_facts['errorText'] or '无'}`）；报错后焦点元素：`{err_facts['activeElem']}`",
            ],
        )

        try:
            page.locator("[data-testid='contact-email']").first.fill("zhou@research-lab.org")
            if len(page.locator("[data-testid='contact-message']").first.input_value().strip()) < 16:
                page.locator("[data-testid='contact-message']").first.fill("林澈你好，读了你的模型实测长文很有共鸣，希望沟通两周评测诊断合作。")
            page.wait_for_timeout(160)
        except Exception:
            pass

        fixed_facts = page.evaluate(
            """() => {
                const errs = Array.from(document.querySelectorAll("[data-testid='contact-error']"))
                    .filter(el => el.offsetParent !== null && el.innerText.trim().length > 0);
                const sec = document.querySelector("[data-testid='contact-section']");
                const hasCounter = /\\d+\\s*\\/\\s*\\d+|字数|还剩|字符/.test(sec ? sec.innerText : '');
                return { remainingErrors: errs.length, hasCounter };
            }"""
        )
        s09_name = "S09_pain4_error_auto_cleared.png"
        page.screenshot(path=str(out_dir / s09_name), full_page=False)
        add_panel(
            "S09",
            "痛点四（估算带入与填表摩擦）· 改对邮箱瞬间（未重按提交按钮）",
            s09_name,
            "痛点四：排期带入、填表与异步提交摩擦",
            [
                f"未重按提交按钮时残留错误提示数：`{fixed_facts['remainingErrors']}` 处；联系区实时字数提示：`{'有' if fixed_facts['hasCounter'] else '无'}`",
            ],
        )

        copy_before_label = "(未找到复制按钮)"
        kept_inputs_on_503 = False
        try:
            c_sub = page.locator("[data-testid='contact-submit']:visible, [data-testid='contact-generate']:visible")
            if c_sub.count() > 0:
                c_sub.first.click(timeout=1200)
                # submitInquiry 首次合法请求固定在 165ms 返回 503 SERVICE_BUSY（retryable: true）
                page.wait_for_timeout(240)
                kept_inputs_on_503 = (
                    "周合作" in page.locator("[data-testid='contact-name']").first.input_value()
                    and len(page.locator("[data-testid='contact-message']").first.input_value().strip()) >= 12
                )
                has_inq = page.evaluate(
                    """() => {
                        const r = document.querySelector("[data-testid='contact-receipt'], [data-testid='contact-output']");
                        const t = r ? ((typeof r.value === 'string' ? r.value : r.innerText) || '') : '';
                        return /INQ-2026-\\d{4}/.test(t);
                    }"""
                )
                if not has_inq:
                    # 等待可能存在的自动退避重试，否则点击页面上的重试按钮或再次点击提交按钮完成恢复
                    try:
                        page.wait_for_function(
                            """() => {
                                const r = document.querySelector("[data-testid='contact-receipt'], [data-testid='contact-output']");
                                const t = r ? ((typeof r.value === 'string' ? r.value : r.innerText) || '') : '';
                                return /INQ-2026-\\d{4}/.test(t);
                            }""",
                            timeout=520,
                        )
                    except Exception:
                        retried = page.evaluate(
                            """() => {
                                const sec = document.querySelector("[data-testid='contact-section']") || document.body;
                                const retryBtn = Array.from(sec.querySelectorAll("button, [role='button']")).find(b => {
                                    const r = b.getBoundingClientRect();
                                    return r.height > 2 && r.width > 4 && !b.disabled && /重试|再试|重新提交/.test((b.innerText || '').trim());
                                });
                                if (retryBtn) { retryBtn.click(); return true; }
                                const sub = document.querySelector("[data-testid='contact-submit'], [data-testid='contact-generate']");
                                if (sub && !sub.disabled) { sub.click(); return true; }
                                return false;
                            }"""
                        )
                        if retried:
                            page.wait_for_timeout(260)

            c_copy = page.locator("[data-testid='contact-copy']:visible")
            if c_copy.count() > 0:
                copy_before_label = c_copy.first.inner_text().strip()
                c_copy.first.click(timeout=1200)
                page.wait_for_timeout(copy_delay_ms)
        except Exception:
            pass

        copy_facts = page.evaluate(
            """() => {
                const outEl = document.querySelector("[data-testid='contact-receipt'], [data-testid='contact-output']");
                const copyBtn = document.querySelector("[data-testid='contact-copy']");
                const outText = outEl ? ((typeof outEl.value === 'string' ? outEl.value : outEl.innerText) || '') : '';
                const m = outText.match(/INQ-2026-\\d{4}/);
                const tel = (window.LincheMockAPI && typeof window.LincheMockAPI.getTelemetry === 'function')
                    ? window.LincheMockAPI.getTelemetry()
                    : null;
                const liveEls = Array.from(document.querySelectorAll("[role='status'], [aria-live]"))
                    .filter(el => el.offsetParent !== null && el.innerText.trim().length > 0)
                    .map(el => el.innerText.replace(/\\s+/g, ' ').trim());
                return {
                    outputLen: outText.trim().length,
                    inquiryId: m ? m[0] : '(无后端回执号)',
                    submitCalls: tel ? tel.submitCalls : 0,
                    duplicateSubmits: tel ? tel.duplicateSubmits : 0,
                    copyAfterLabel: copyBtn && copyBtn.offsetParent !== null ? copyBtn.innerText.replace(/\\s+/g, ' ').trim() : '(不可见)',
                    liveMessages: liveEls.slice(0, 3)
                };
            }"""
        )
        s10_name = "S10_pain4_copy_100ms.png"
        page.screenshot(path=str(out_dir / s10_name), full_page=False)
        add_panel(
            "S10",
            f"痛点四（异步提交 503 恢复与一键复制）· 回执落盘与点击复制后 {copy_delay_ms}ms 瞬时状态",
            s10_name,
            "痛点四：排期带入、填表与异步提交摩擦",
            [
                f"首轮 `503 SERVICE_BUSY` 时表单内容未丢失：`{'是' if kept_inputs_on_503 else '否'}`；重试后后端正式回执号：`{copy_facts['inquiryId']}`（`contact-receipt` 长度 `{copy_facts['outputLen']}` 字符，`submitInquiry` 调用 `{copy_facts['submitCalls']}` 次，并发重入 `{copy_facts['duplicateSubmits']}` 次）",
                f"复制按钮 `{copy_delay_ms}ms` 文案变化：`{copy_before_label}` → `{copy_facts['copyAfterLabel']}`；无障碍状态区：`{copy_facts['liveMessages']}`",
            ],
        )

        # ---------------- S11 & S12：深色模式审美对照与手机窄屏悬浮对比条布局 ----------------
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(90)
        try:
            t_btn = page.locator("[data-testid='theme-toggle']:visible")
            if t_btn.count() > 0:
                if (page.evaluate("() => document.documentElement.getAttribute('data-theme') || ''")).lower() != "dark":
                    t_btn.first.click(timeout=1200)
                    page.wait_for_timeout(150)
        except Exception:
            pass

        dark_info = page.evaluate(
            """() => {
                const cs = getComputedStyle(document.body);
                return {
                    themeAttr: document.documentElement.getAttribute('data-theme') || '(未标注)',
                    bodyBg: cs.backgroundColor,
                    bodyColor: cs.color
                };
            }"""
        )
        s11_name = "S11_overview_desktop_dark.png"
        page.screenshot(path=str(out_dir / s11_name), full_page=False)
        add_panel(
            "S11",
            "深浅色与多端对照 · 桌面端深色模式首屏与激活态层次",
            s11_name,
            "多端与深浅色审美对照",
            [
                f"切换后 `html[data-theme]={dark_info['themeAttr']}`；实测背景 `{dark_info['bodyBg']}`，字色 `{dark_info['bodyColor']}`",
            ],
        )

        try:
            t_btn = page.locator("[data-testid='theme-toggle']:visible")
            if t_btn.count() > 0 and (page.evaluate("() => document.documentElement.getAttribute('data-theme') || ''")).lower() == "dark":
                t_btn.first.click(timeout=1200)
                page.wait_for_timeout(110)
            page.set_viewport_size(mob_vp)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(120)
            ct = page.locator("[data-testid='compare-toggle']:visible")
            if ct.count() > 0:
                is_on = (ct.first.get_attribute("aria-pressed") == "true") or (ct.first.get_attribute("data-compared") == "true")
                if not is_on:
                    ct.first.click(timeout=1000)
                    page.wait_for_timeout(100)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(100)
        except Exception:
            pass

        mob_home = page.evaluate(
            """() => {
                const doc = document.documentElement;
                const hero = document.querySelector("[data-testid='hero-section']");
                const hr = hero ? hero.getBoundingClientRect() : null;
                const bar = document.querySelector("[data-testid='compare-bar']");
                const bcs = bar ? getComputedStyle(bar) : null;
                const br = bar ? bar.getBoundingClientRect() : null;
                const barVis = !!(bar && bcs && bcs.display !== 'none' && bcs.visibility !== 'hidden' && br && br.height > 2);
                return {
                    scrollWidth: doc.scrollWidth,
                    clientWidth: doc.clientWidth,
                    heroHeightPx: hr ? Math.round(hr.height) : 0,
                    compareBarVisible: barVis
                };
            }"""
        )
        s12_name = "S12_overview_mobile_home.png"
        page.screenshot(path=str(out_dir / s12_name), full_page=False)
        add_panel(
            "S12",
            "深浅色与多端对照 · 手机窄屏首屏及对比浮动条布局",
            s12_name,
            "多端与深浅色审美对照",
            [
                f"手机视口 `{mob_vp['width']}×{mob_vp['height']}`：`scrollWidth={mob_home['scrollWidth']} px` vs `clientWidth={mob_home['clientWidth']} px`",
                f"首屏 `hero-section` 高度 `{mob_home['heroHeightPx']} px`（占比 `{round(mob_home['heroHeightPx'] / max(1, mob_vp['height']) * 100, 1)}%`）；底部对比栏可见：`{'是' if mob_home['compareBarVisible'] else '否'}`",
            ],
        )

        browser.close()

    return {
        "panel_count": len(panels),
        "is_unimplemented_stub": bool(is_stub),
        "dialogs_triggered": dialogs_triggered,
        "panels": panels,
    }


def render_storyboard_markdown(case_id: str, sb_data: dict) -> str:
    """将抓拍结果渲染为盲评包内的 STORYBOARD.md（纯客观物理事实批注，不含任何分数）。"""
    n_p = sb_data.get("panel_count", 12)
    lines = [
        f"# 交互状态连环画事实索引卡 · {case_id}",
        "",
        "> **阅读说明（给独立评委）**：",
        f"> 1. 以下 **{n_p} 张关键视觉与异步工作台交互状态截图（`[S01]`–`[S{n_p:02d}]`）** 由官方打包脚本在完全断网的无头浏览器中对接只读 `mock_backend.js` 按统一剧本自动抓拍；",
        "> 2. 图下批注**仅记录实测物理数值、SVG 包围盒与接口调用事实，不包含任何机器打分或优劣定性**；",
        "> 3. 请务必**逐张查看 `storyboard/` 下的真实画面**，结合 `code/` 源码与 `DECISIONS.md` 对 D1、D2、D3 独立定级；若需验证额外交互，可调用 `python tools/judge_probe.py --case-dir <本case目录> ...` 靶向补测。",
        "",
    ]
    if sb_data.get("is_unimplemented_stub"):
        lines += [
            "> ⚠️ **客观事实提示**：检测到 `index.html` 仍带有初始模板属性 `data-unimplemented=\"true\"`。",
            "",
        ]

    for p in sb_data.get("panels") or []:
        pid = p["id"]
        lines.append(f"## [{pid}] {p['title']}")
        lines.append("")
        lines.append(f"- **所属场景**：{p['pain_group']}")
        lines.append(f"- **截图路径**：[`storyboard/{p['filename']}`](storyboard/{p['filename']})")
        for fact in p.get("facts") or []:
            lines.append(f"- **客观观测**：{fact}")
        lines.append("")
        lines.append(f"![{pid} {p['title']}](storyboard/{p['filename']})")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
