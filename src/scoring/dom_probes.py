# -*- coding: utf-8 -*-
"""无头浏览器端物理探针脚本集合 v3.0（src/scoring/dom_probes.py）。

提供给 browser_waves.py 在浏览器页面上下文执行的纯确定性几何、SVG 图表、色值、遮挡与性能探针：
  - 原生 <svg data-testid='compare-chart'> 多维坐标与动态重绘签名核验
  - Alpha 合成 9 角色真实渲染 RGB 提取（覆盖激活态按钮、代码块、排期里程碑、报错红字等重灾区）
  - 反 overflow:hidden 取巧截断检测（含 SVG 图表与里程碑行）
  - 动态悬浮条遮挡与按钮包围盒物理重叠检测
  - 空闲无限 requestAnimationFrame 循环检测与 320 张卡片高压 DOM 注入延迟探针
"""
from __future__ import annotations

JS_VERIFY_SVG_CHART = """
() => {
    const svg = document.querySelector("[data-testid='compare-panel'] svg[data-testid='compare-chart'], svg[data-testid='compare-chart']");
    if (!svg || svg.tagName.toLowerCase() !== 'svg') {
        return {
            exists: false,
            visible: false,
            fitsViewport: false,
            textLabelCount: 0,
            shapeCount: 0,
            distinctStyleCount: 0,
            coordSignature: '',
            width: 0,
            height: 0
        };
    }
    const cs = getComputedStyle(svg);
    const r = svg.getBoundingClientRect();
    const visible = cs.display !== 'none' && cs.visibility !== 'hidden' && parseFloat(cs.opacity) >= 0.1 && r.width >= 110 && r.height >= 80;
    const vw = window.innerWidth;
    const fitsViewport = r.right <= vw + 5 && r.left >= -5;

    const textEls = Array.from(svg.querySelectorAll('text')).filter(t => (t.textContent || '').trim().length > 0);
    const textNodes = textEls.map(t => (t.textContent || '').trim());
    const uniqueLabels = Array.from(new Set(textNodes));

    let overlappingTextPairs = 0;
    const textRects = textEls.map(t => t.getBoundingClientRect()).filter(tr => tr.width > 1 && tr.height > 1);
    for (let i = 0; i < textRects.length; i++) {
        for (let j = i + 1; j < textRects.length; j++) {
            const a = textRects[i];
            const b = textRects[j];
            const ox = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));
            const oy = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
            if (ox > 4 && oy > 3) overlappingTextPairs++;
        }
    }

    // 提取多顶点数据形状（polygon / polyline / path）及其几何坐标签名
    const candidateEls = Array.from(svg.querySelectorAll('polygon, polyline, path'));
    const validShapes = [];
    const styleSet = new Set();

    for (const el of candidateEls) {
        const raw = el.getAttribute('points') || el.getAttribute('d') || '';
        const nums = raw.match(/-?\\d+(?:\\.\\d+)?/g) || [];
        if (nums.length >= 6) {
            const ecs = getComputedStyle(el);
            if (ecs.display === 'none' || ecs.visibility === 'hidden') continue;
            const normNums = nums.slice(0, 24).map(n => Math.round(parseFloat(n) * 10) / 10).join(',');
            const stroke = ecs.stroke || el.getAttribute('stroke') || '';
            const fill = ecs.fill || el.getAttribute('fill') || '';
            validShapes.push(el.tagName.toLowerCase() + ':' + normNums);
            styleSet.add(stroke + '|' + fill);
        }
    }

    return {
        exists: true,
        visible,
        fitsViewport,
        textLabelCount: uniqueLabels.length,
        overlappingTextPairs,
        labelsSample: uniqueLabels.slice(0, 6),
        shapeCount: validShapes.length,
        distinctStyleCount: styleSet.size,
        coordSignature: validShapes.join(';'),
        width: Math.round(r.width),
        height: Math.round(r.height)
    };
}
"""

JS_EXTRACT_CONTRAST_SAMPLES = """
() => {
    function parseRgba(str) {
        if (!str) return [0, 0, 0, 0];
        const m = str.match(/rgba?\\(\\s*([\\d.]+)[,\\s]+([\\d.]+)[,\\s]+([\\d.]+)(?:[,/\\s]+([\\d.]+))?\\s*\\)/i);
        if (!m) return [0, 0, 0, 0];
        return [
            parseFloat(m[1]),
            parseFloat(m[2]),
            parseFloat(m[3]),
            m[4] !== undefined ? parseFloat(m[4]) : 1.0
        ];
    }

    function compositeOver(fg, bg) {
        const a = fg[3] + bg[3] * (1 - fg[3]);
        if (a <= 0) return [255, 255, 255, 0];
        return [
            (fg[0] * fg[3] + bg[0] * bg[3] * (1 - fg[3])) / a,
            (fg[1] * fg[3] + bg[1] * bg[3] * (1 - fg[3])) / a,
            (fg[2] * fg[3] + bg[2] * bg[3] * (1 - fg[3])) / a,
            a
        ];
    }

    function effectiveBg(el) {
        const layers = [];
        let cur = el;
        while (cur && cur.nodeType === 1) {
            const bg = parseRgba(getComputedStyle(cur).backgroundColor);
            if (bg[3] > 0) layers.push(bg);
            if (bg[3] >= 0.999) break;
            cur = cur.parentElement;
        }
        const isDarkAttr = (document.documentElement.getAttribute('data-theme') || '').toLowerCase() === 'dark';
        let acc = isDarkAttr ? [18, 18, 22, 1.0] : [255, 255, 255, 1.0];
        for (let i = layers.length - 1; i >= 0; i--) {
            acc = compositeOver(layers[i], acc);
        }
        return [Math.round(acc[0]), Math.round(acc[1]), Math.round(acc[2])];
    }

    function isVis(el) {
        if (!el) return false;
        const cs = getComputedStyle(el);
        if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) < 0.1) return false;
        const r = el.getBoundingClientRect();
        return r.width > 1 && r.height > 1;
    }

    function sampleOf(el, role) {
        if (!isVis(el)) return null;
        const cs = getComputedStyle(el);
        const fg = parseRgba(cs.color);
        const bg = effectiveBg(el);
        return {
            role,
            fg: [Math.round(fg[0]), Math.round(fg[1]), Math.round(fg[2])],
            bg
        };
    }

    const heroTitle = document.querySelector("[data-testid='hero-section'] h1, [data-testid='hero-section'] h2, h1");
    const bodyPara = document.querySelector("[data-testid='project-card'] p, [data-testid='article-card'] p, [data-testid='detail-body'] p");
    const mutedEl = document.querySelector("[data-testid='demo-notice'], time, small, [class*='meta'], [class*='muted']");
    const searchInput = document.querySelector("[data-testid='search-input']");
    const activeChip = document.querySelector(
        "[data-testid='category-option'][aria-pressed='true'], [data-testid='category-option'][data-active='true']"
    );
    const badgeEl = document.querySelector(
        "[data-testid='project-card'] [class*='badge'], [data-testid='project-card'] [class*='tag'], [data-testid='article-card'] [class*='badge']"
    );
    const estEl = document.querySelector("[data-testid='est-milestones'], [data-testid='est-result']");
    const codeEl = document.querySelector("[data-testid='detail-body'] pre code, [data-testid='detail-body'] pre");
    const errEl = Array.from(document.querySelectorAll("[data-testid='contact-error'], [data-testid='estimator-section'] [role='alert']")).find(
        e => isVis(e) && (e.innerText || '').trim().length > 0
    );

    return [
        sampleOf(heroTitle, 'heading'),
        sampleOf(bodyPara, 'body'),
        sampleOf(mutedEl, 'muted'),
        sampleOf(searchInput, 'input'),
        sampleOf(activeChip, 'active_chip'),
        sampleOf(badgeEl, 'badge'),
        sampleOf(estEl, 'estimator'),
        sampleOf(codeEl, 'code_block'),
        sampleOf(errEl, 'form_error')
    ].filter(Boolean);
}
"""

JS_DETECT_CLIPPED_CONTROLS = """
() => {
    const vw = window.innerWidth;
    const docOverflow = Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth);

    function hasScrollableXAncestor(el) {
        let cur = el.parentElement;
        while (cur && cur !== document.body && cur !== document.documentElement) {
            const ox = getComputedStyle(cur).overflowX;
            if ((ox === 'auto' || ox === 'scroll') && cur.scrollWidth > cur.clientWidth + 2) {
                return true;
            }
            cur = cur.parentElement;
        }
        return false;
    }

    const selectors = [
        "button",
        "[role='button']",
        "input",
        "select",
        "textarea",
        "svg[data-testid='compare-chart']",
        "[data-testid='est-result']",
        "[data-testid='est-milestones']",
        "[data-testid='detail-title']"
    ];
    const nodes = Array.from(document.querySelectorAll(selectors.join(',')));
    let clippedCount = 0;
    const samples = [];

    for (const el of nodes) {
        const cs = getComputedStyle(el);
        if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) < 0.1) continue;
        const r = el.getBoundingClientRect();
        if (r.width <= 0 || r.height <= 0) continue;
        if (hasScrollableXAncestor(el)) continue;

        let bad = false;
        let reason = '';
        if (r.right > vw + 4 || r.left < -4) {
            bad = true;
            reason = `viewport_clip(left=${Math.round(r.left)},right=${Math.round(r.right)},vw=${vw})`;
        } else {
            let p = el.parentElement;
            while (p && p !== document.body && p !== document.documentElement) {
                const pcs = getComputedStyle(p);
                if (pcs.overflowX === 'hidden' || pcs.overflowX === 'clip') {
                    const pr = p.getBoundingClientRect();
                    if (pr.width > 0 && (r.right > pr.right + 5 || r.left < pr.left - 5)) {
                        bad = true;
                        reason = `parent_hidden_clip(elR=${Math.round(r.right)},parentR=${Math.round(pr.right)})`;
                        break;
                    }
                }
                p = p.parentElement;
            }
        }

        if (bad) {
            clippedCount++;
            if (samples.length < 4) {
                samples.push((el.getAttribute('data-testid') || el.tagName.toLowerCase()) + ':' + reason);
            }
        }
    }

    return { docOverflowPx: docOverflow, clippedCount, samples };
}
"""

JS_DETECT_OCCLUSION_AND_OVERLAP = """
(cfg) => {
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    const allEls = Array.from(document.querySelectorAll('*'));
    let fixedHeight = 0;
    const countedRects = [];
    for (const el of allEls) {
        const cs = getComputedStyle(el);
        if ((cs.position === 'fixed' || cs.position === 'sticky') && cs.display !== 'none' && cs.visibility !== 'hidden' && parseFloat(cs.opacity) > 0.05) {
            const r = el.getBoundingClientRect();
            if (r.width > vw * 0.45 && r.height > 4 && r.height < vh * 0.75) {
                const nested = countedRects.some(cr => Math.abs(cr.top - r.top) < 6 && Math.abs(cr.bottom - r.bottom) < 6);
                if (!nested) {
                    fixedHeight += r.height;
                    countedRects.push(r);
                }
            }
        }
    }
    const fixedRatio = fixedHeight / Math.max(1, vh);

    const probeSelectors = [
        "[data-testid='search-input']",
        "[data-testid='project-open']",
        "[data-testid='est-apply-to-contact']",
        "[data-testid='contact-submit'], [data-testid='contact-generate']"
    ];
    let unoccluded = 0;
    let checkedTargets = 0;
    for (const sel of probeSelectors) {
        const candidates = Array.from(document.querySelectorAll(sel)).filter(e => e.offsetParent !== null);
        const el = candidates.length ? candidates[candidates.length - 1] : null;
        if (!el) continue;
        checkedTargets++;
        el.scrollIntoView({ block: 'center' });
        const r = el.getBoundingClientRect();
        const cx = Math.min(vw - 3, Math.max(3, r.left + r.width / 2));
        const cy = Math.min(vh - 3, Math.max(3, r.top + r.height / 2));
        const hit = document.elementFromPoint(cx, cy);
        if (hit && (el === hit || el.contains(hit) || hit.contains(el))) {
            unoccluded++;
        }
    }
    window.scrollTo(0, 0);

    const groupContainers = Array.from(document.querySelectorAll(
        "[data-testid='category-filter'], [data-testid='estimator-section'], [data-testid='project-card'], [data-testid='contact-section']"
    )).slice(0, 6);
    let overlapCount = 0;
    for (const grp of groupContainers) {
        const btns = Array.from(grp.querySelectorAll("button, [role='button']")).filter(b => b.offsetParent !== null);
        for (let i = 0; i < btns.length; i++) {
            for (let j = i + 1; j < btns.length; j++) {
                if (btns[i].contains(btns[j]) || btns[j].contains(btns[i])) continue;
                const a = btns[i].getBoundingClientRect();
                const b = btns[j].getBoundingClientRect();
                const ox = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));
                const oy = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
                if (ox > 4 && oy > 4) overlapCount++;
            }
        }
    }

    const tapTargets = Array.from(document.querySelectorAll(
        "[data-testid='theme-toggle'], [data-testid='workbench-undo'], [data-testid='workbench-redo'], " +
        "[data-testid='favorite-filter'], [data-testid='category-option'], " +
        "[data-testid='favorite-btn'], [data-testid='compare-toggle'], [data-testid='est-type'], " +
        "[data-testid='est-addon'], [data-testid='est-apply-to-contact'], [data-testid='contact-submit'], [data-testid='contact-generate']"
    )).filter(e => e.offsetParent !== null);
    let tapScoreSum = 0;
    for (const t of tapTargets) {
        const r = t.getBoundingClientRect();
        if (r.height >= cfg.idealPx && r.width >= cfg.minPx) tapScoreSum += 1.0;
        else if (r.height >= cfg.minPx && r.width >= cfg.minPx) tapScoreSum += 0.8;
        else if (r.height >= 26 && r.width >= 26) tapScoreSum += 0.35;
    }
    const tapRatio = tapTargets.length ? (tapScoreSum / tapTargets.length) : 0;

    const contentContainers = [
        document.querySelector("[data-testid='hero-section']"),
        document.querySelector("[data-testid='project-list']"),
        document.querySelector("[data-testid='estimator-section']"),
        document.querySelector("[data-testid='contact-section']")
    ].filter(e => e && e.offsetParent !== null);
    let minEdgeGap = 999;
    for (const c of contentContainers) {
        const r = c.getBoundingClientRect();
        const gap = Math.min(Math.max(0, r.left), Math.max(0, vw - r.right));
        if (gap < minEdgeGap) minEdgeGap = Math.round(gap);
    }
    if (minEdgeGap === 999) minEdgeGap = 0;

    return {
        fixedRatio: Math.round(fixedRatio * 1000) / 1000,
        unoccluded,
        checkedTargets,
        overlapCount,
        tapRatio: Math.round(tapRatio * 1000) / 1000,
        minEdgeGapPx: minEdgeGap
    };
}
"""

JS_IDLE_RAF_AND_STRESS_SEARCH = """
async (injectCount) => {
    let rafHits = 0;
    const origRaf = window.requestAnimationFrame;
    window.requestAnimationFrame = function(cb) {
        rafHits++;
        return origRaf.call(window, cb);
    };
    await new Promise(r => setTimeout(r, 200));
    window.requestAnimationFrame = origRaf;
    const hasIdleRafLoop = rafHits >= 8;

    const pList = document.querySelector("[data-testid='project-list']");
    const aList = document.querySelector("[data-testid='article-list']");
    const clones = [];
    const seedP = pList ? pList.querySelector("[data-testid='project-card']") : null;
    const seedA = aList ? aList.querySelector("[data-testid='article-card']") : null;
    const half = Math.floor((injectCount || 320) / 2);
    if (pList && seedP) {
        for (let i = 0; i < half; i++) {
            const c = seedP.cloneNode(true);
            c.setAttribute('data-stress-clone', '1');
            pList.appendChild(c);
            clones.push(c);
        }
    }
    if (aList && seedA) {
        for (let i = 0; i < half; i++) {
            const c = seedA.cloneNode(true);
            c.setAttribute('data-stress-clone', '1');
            aList.appendChild(c);
            clones.push(c);
        }
    }

    const input = document.querySelector("[data-testid='search-input']");
    const durs = [];
    if (input) {
        const queries = [
            '评', '评测', '评测 回归', '智能体', '智能体 状态', '工具', '离线 分块',
            '杭州', '不存在的词_zz', '', '顾问 原型', '表格', '模型', ''
        ];
        for (const q of queries) {
            const t0 = performance.now();
            input.value = q;
            input.dispatchEvent(new Event('input', { bubbles: true }));
            void document.body.offsetHeight;
            await new Promise(r => origRaf.call(window, r));
            durs.push(performance.now() - t0);
        }
    } else {
        durs.push(300.0);
    }

    for (const c of clones) {
        if (c.parentNode) c.parentNode.removeChild(c);
    }

    return { hasIdleRafLoop, rafHitsIn200ms: rafHits, searchDurations: durs };
}
"""
