/* 异步状态、时序防竞态、跨模块历史栈与容错逻辑中心（app.js · xiaonuo-v4.0 黄金参考基线） */
(function () {
  "use strict";

  const API = window.LincheMockAPI;

  const UI_CONFIG = {
    maxCompare: 3,
    maxHistory: 30,
    searchDebounceMs: 50,
    recommendedKeywords: ["回归门禁", "状态机", "混合检索"],
    radarColorsLight: [
      { stroke: "#144d60", fill: "rgba(20, 77, 96, 0.22)" },
      { stroke: "#b45309", fill: "rgba(180, 83, 9, 0.20)" },
      { stroke: "#6d28d9", fill: "rgba(109, 40, 217, 0.18)" }
    ],
    radarColorsDark: [
      { stroke: "#5eead4", fill: "rgba(94, 234, 212, 0.22)" },
      { stroke: "#fbbf24", fill: "rgba(251, 191, 36, 0.20)" },
      { stroke: "#c084fc", fill: "rgba(192, 132, 252, 0.20)" }
    ]
  };

  const STORAGE_KEYS = {
    theme: "linche_v4_theme",
    favorites: "linche_v4_favorites",
    compare: "linche_v4_compare",
    estimator: "linche_v4_estimator",
    draft: "linche_v4_contact_draft",
    recent: "linche_v4_recent_items"
  };

  const WORKBENCH_BLOCK_REGEX = /【(?:工作台选型与排期方案|估算方案摘要)】[\s\S]*?【\/(?:工作台选型与排期方案|估算方案摘要)】\n?/g;
  const CMP_BLOCK_REGEX = /【对比候选项目】[\s\S]*?【\/对比候选项目】\n?/g;

  const memoryStore = Object.create(null);
  let storageDegraded = false;

  /* ==================== 1. 安全持久化与异构脏数据校验层 ==================== */
  function markStorageDegraded() {
    if (storageDegraded) return;
    storageDegraded = true;
    const banner = document.getElementById("storageDegradeBanner");
    if (banner) banner.classList.remove("hidden");
  }

  function safeGetRaw(key) {
    try {
      const val = window.localStorage.getItem(key);
      return val !== null ? val : (key in memoryStore ? memoryStore[key] : null);
    } catch (_err) {
      markStorageDegraded();
      return key in memoryStore ? memoryStore[key] : null;
    }
  }

  function safeSetRaw(key, strVal) {
    memoryStore[key] = strVal;
    try {
      window.localStorage.setItem(key, strVal);
      return true;
    } catch (_err) {
      markStorageDegraded();
      return false;
    }
  }

  function safeRemoveRaw(key) {
    delete memoryStore[key];
    try {
      window.localStorage.removeItem(key);
    } catch (_err) {
      markStorageDegraded();
    }
  }

  function readSafeStringArray(key, allowedSet, maxLen) {
    const raw = safeGetRaw(key);
    if (!raw) return [];
    try {
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return [];
      const clean = [];
      const seen = new Set();
      for (const item of parsed) {
        if (typeof item === "string" && item.trim() && (!allowedSet || allowedSet.has(item)) && !seen.has(item)) {
          seen.add(item);
          clean.push(item);
          if (maxLen && clean.length >= maxLen) break;
        }
      }
      return clean;
    } catch (_err) {
      return [];
    }
  }

  function readValidatedDraft() {
    const raw = safeGetRaw(STORAGE_KEYS.draft);
    const fallback = { name: "", email: "", message: "" };
    if (!raw) return fallback;
    try {
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return fallback;
      return {
        name: typeof parsed.name === "string" ? parsed.name : "",
        email: typeof parsed.email === "string" ? parsed.email : "",
        message: typeof parsed.message === "string" ? parsed.message : ""
      };
    } catch (_err) {
      return fallback;
    }
  }

  function readValidatedRecent() {
    const raw = safeGetRaw(STORAGE_KEYS.recent);
    if (!raw) return [];
    try {
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return [];
      return parsed
        .filter(
          (it) =>
            it &&
            typeof it === "object" &&
            (it.kind === "project" || it.kind === "article") &&
            typeof it.id === "string" &&
            typeof it.title === "string"
        )
        .slice(0, 4);
    } catch (_err) {
      return [];
    }
  }

  /* ==================== 2. 全局状态树、异步并发控制器与跨模块历史栈 ==================== */
  const projectCacheById = new Map();
  let allArticlesOrder = [];

  const validSets = {
    projects: null,
    modes: new Set(),
    addons: new Set(),
    scales: new Set(),
    startWeeks: new Set()
  };

  const state = {
    bootstrapped: false,
    profile: {},
    categories: [{ id: "all", label: "全部方向" }],
    sortOptions: [{ id: "featured", label: "综合推荐顺序" }],
    defaultPlan: { modeId: "diag", addonIds: [], scaleId: "standard", startWeek: "2026-W49" },
    plannerCatalog: { modes: [], addons: [], scales: [], calendarWeeks: [] },

    theme: "light",
    searchQuery: "",
    isComposing: false,
    activeCategory: "all",
    onlyFavorites: false,
    sortBy: "featured",
    favorites: [],
    compareIds: [],
    recentItems: readValidatedRecent(),

    catalogProjects: [],
    catalogArticles: [],

    estimator: { modeId: "diag", addonIds: [], scaleId: "standard", startWeek: "2026-W49" },
    planEval: null,

    route: { view: "home", id: "" },
    savedListScrollY: 0,
    lastListTriggerEl: null,
    lastListItemId: "",
    compareOriginEl: null,
    formSubmittedOnce: false
  };

  // 三条核心读取链路的独立 AbortController 与单调递增请求令牌（彻底阻断慢请求倒灌覆盖）
  let catalogAbortCtrl = null;
  let catalogReqSeq = 0;

  let planAbortCtrl = null;
  let planReqSeq = 0;

  let detailAbortCtrl = null;
  let detailReqSeq = 0;

  // 提交表单飞行中防并发锁
  let submitInFlight = false;

  const undoStack = [];
  const redoStack = [];

  function cloneEstimator(est) {
    return {
      modeId: est.modeId,
      addonIds: (est.addonIds || []).slice(),
      scaleId: est.scaleId,
      startWeek: est.startWeek
    };
  }

  function getDefaultEstimatorState() {
    return cloneEstimator(state.defaultPlan);
  }

  function readValidatedEstimatorFromStorage() {
    const fallback = getDefaultEstimatorState();
    const raw = safeGetRaw(STORAGE_KEYS.estimator);
    if (!raw) return fallback;
    try {
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return fallback;
      const addons = Array.isArray(parsed.addonIds)
        ? Array.from(new Set(parsed.addonIds.filter((x) => typeof x === "string" && validSets.addons.has(x))))
        : [];
      return {
        modeId: typeof parsed.modeId === "string" && validSets.modes.has(parsed.modeId) ? parsed.modeId : fallback.modeId,
        addonIds: addons,
        scaleId: typeof parsed.scaleId === "string" && validSets.scales.has(parsed.scaleId) ? parsed.scaleId : fallback.scaleId,
        startWeek:
          typeof parsed.startWeek === "string" && validSets.startWeeks.has(parsed.startWeek)
            ? parsed.startWeek
            : fallback.startWeek
      };
    } catch (_err) {
      return fallback;
    }
  }

  function saveEstimatorState() {
    safeSetRaw(STORAGE_KEYS.estimator, JSON.stringify(state.estimator));
  }

  function captureWorkbenchSnapshot() {
    return {
      compareIds: state.compareIds.slice(),
      estimator: cloneEstimator(state.estimator),
      cachedPlanEval: state.planEval ? JSON.parse(JSON.stringify(state.planEval)) : null
    };
  }

  function snapshotsMeaningfullyEqual(a, b) {
    if (!a || !b) return false;
    return (
      JSON.stringify(a.compareIds) === JSON.stringify(b.compareIds) &&
      JSON.stringify(a.estimator) === JSON.stringify(b.estimator)
    );
  }

  function syncHistoryButtons() {
    const uBtn = document.getElementById("workbenchUndoBtn");
    const rBtn = document.getElementById("workbenchRedoBtn");
    if (uBtn) {
      uBtn.disabled = undoStack.length === 0;
      uBtn.setAttribute("aria-disabled", undoStack.length === 0 ? "true" : "false");
    }
    if (rBtn) {
      rBtn.disabled = redoStack.length === 0;
      rBtn.setAttribute("aria-disabled", redoStack.length === 0 ? "true" : "false");
    }
  }

  function pushHistoryBeforeMutation() {
    const snap = captureWorkbenchSnapshot();
    const top = undoStack[undoStack.length - 1];
    if (!snapshotsMeaningfullyEqual(top, snap)) {
      undoStack.push(snap);
      if (undoStack.length > UI_CONFIG.maxHistory) undoStack.shift();
    }
    redoStack.length = 0;
    syncHistoryButtons();
  }

  function restoreWorkbenchSnapshot(snap) {
    state.compareIds = snap.compareIds.slice(0, UI_CONFIG.maxCompare);
    state.estimator = cloneEstimator(snap.estimator);
    safeSetRaw(STORAGE_KEYS.compare, JSON.stringify(state.compareIds));
    saveEstimatorState();

    renderCompareBar();
    syncCardCompareButtonsInPlace();
    renderEstimatorControls();

    if (snap.cachedPlanEval) {
      state.planEval = JSON.parse(JSON.stringify(snap.cachedPlanEval));
      renderEstimatorSummary();
    }
    runPlanEvaluation();

    if (state.route.view === "project") {
      renderDetailActionButtons(state.route.id);
    }
    if (!document.getElementById("compareBackdrop").classList.contains("hidden")) {
      if (state.compareIds.length === 0) {
        closeCompareModal();
      } else {
        renderCompareTable();
      }
    }
    syncHistoryButtons();
  }

  function performUndo() {
    if (!undoStack.length) return;
    const current = captureWorkbenchSnapshot();
    const prev = undoStack.pop();
    redoStack.push(current);
    restoreWorkbenchSnapshot(prev);
  }

  function performRedo() {
    if (!redoStack.length) return;
    const current = captureWorkbenchSnapshot();
    const next = redoStack.pop();
    undoStack.push(current);
    restoreWorkbenchSnapshot(next);
  }

  /* ==================== 3. 字符串转义与高亮工具 ==================== */
  function escapeHtml(str) {
    return String(str ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function escapeRegExp(str) {
    return String(str ?? "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function parseQueryTokens(q) {
    const trimmed = String(q || "").trim();
    if (!trimmed) return [];
    return trimmed.split(/\s+/).map((t) => t.trim()).filter(Boolean);
  }

  function highlightTextHtml(rawText, tokens) {
    const text = String(rawText ?? "");
    if (!tokens.length) return escapeHtml(text);
    const sorted = Array.from(new Set(tokens)).sort((a, b) => b.length - a.length);
    const pattern = sorted.map(escapeRegExp).filter(Boolean).join("|");
    if (!pattern) return escapeHtml(text);
    const regex = new RegExp(`(${pattern})`, "gi");
    return text
      .split(regex)
      .map((part, idx) => (idx % 2 === 1 ? `<mark>${escapeHtml(part)}</mark>` : escapeHtml(part)))
      .join("");
  }

  let toastTimer = null;
  function showToast(msg) {
    const el = document.getElementById("globalToast");
    if (!el) return;
    el.textContent = msg;
    el.classList.remove("hidden");
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      el.classList.add("hidden");
    }, 3200);
  }

  /* ==================== 4. 主题系统（系统偏好跟随 + 持久化记忆） ==================== */
  function resolveInitialTheme() {
    const saved = safeGetRaw(STORAGE_KEYS.theme);
    if (saved === "light" || saved === "dark") return saved;
    try {
      if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
        return "dark";
      }
    } catch (_err) {
      /* 忽略环境限制 */
    }
    return "light";
  }

  function applyTheme(theme, persist) {
    state.theme = theme === "dark" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", state.theme);
    const btn = document.getElementById("themeToggleBtn");
    if (btn) {
      btn.textContent = state.theme === "dark" ? "☀ 浅色" : "☾ 深色";
      btn.setAttribute("aria-pressed", state.theme === "dark" ? "true" : "false");
    }
    if (persist) {
      safeSetRaw(STORAGE_KEYS.theme, state.theme);
    }
    if (!document.getElementById("compareBackdrop").classList.contains("hidden")) {
      renderCompareTable();
    }
  }

  /* ==================== 5. 首屏名片与筛选控制栏渲染 ==================== */
  function renderProfileAndToolbar() {
    const p = state.profile || {};
    document.getElementById("heroLocation").textContent = p.location || "中国 · 杭州";
    document.getElementById("heroTitle").textContent = `${p.name || "林澈"} — ${p.title || ""}`;
    document.getElementById("heroTagline").textContent = p.tagline || "";
    document.getElementById("heroBio").textContent = p.bio || "";
    document.getElementById("demoNotice").textContent = p.demoNotice || "";
    document.getElementById("contactEmailText").textContent = p.contactEmail || "linche@example.com";
    document.getElementById("contactEmailNote").textContent = p.contactEmailNote || "演示占位邮箱";

    const metricsWrap = document.getElementById("heroMetrics");
    metricsWrap.innerHTML = (p.metrics || [])
      .map(
        (m) => `
        <div class="metric-item">
          <div class="metric-label">${escapeHtml(m.label)}</div>
          <div class="metric-value">${escapeHtml(m.value)}</div>
        </div>`
      )
      .join("");

    const sortSelect = document.getElementById("sortControl");
    sortSelect.innerHTML = (state.sortOptions || [])
      .map((opt) => `<option value="${escapeHtml(opt.id)}">${escapeHtml(opt.label)}</option>`)
      .join("");
    sortSelect.value = state.sortBy;

    renderCategoryButtons();
    updateFavFilterButton();
  }

  function renderCategoryButtons() {
    const wrap = document.getElementById("categoryFilter");
    wrap.innerHTML = (state.categories || [])
      .map((cat) => {
        const active = state.activeCategory === cat.id;
        return `<button
          type="button"
          class="chip-btn"
          data-testid="category-option"
          data-category="${escapeHtml(cat.id)}"
          data-active="${active ? "true" : "false"}"
          aria-pressed="${active ? "true" : "false"}"
        >${escapeHtml(cat.label)}</button>`;
      })
      .join("");
  }

  function updateFavFilterButton() {
    const btn = document.getElementById("favFilterBtn");
    if (!btn) return;
    const n = state.favorites.length;
    btn.textContent = `${state.onlyFavorites ? "★" : "☆"} 只看已收藏（${n}）`;
    btn.setAttribute("aria-pressed", state.onlyFavorites ? "true" : "false");
    btn.setAttribute("data-active", state.onlyFavorites ? "true" : "false");
  }

  function renderRecentTray() {
    const tray = document.getElementById("recentTray");
    if (!tray) return;
    if (!state.recentItems.length) {
      tray.classList.add("hidden");
      tray.innerHTML = "";
      return;
    }
    tray.classList.remove("hidden");
    tray.innerHTML =
      `<span>最近翻阅：</span>` +
      state.recentItems
        .map(
          (it) =>
            `<button type="button" class="recent-chip" data-recent-kind="${escapeHtml(it.kind)}" data-recent-id="${escapeHtml(it.id)}">${escapeHtml(it.title)}</button>`
        )
        .join("");
  }

  /* ==================== 6. 异步目录检索（AbortController + 请求代际锁） ==================== */
  async function runCatalogQuery() {
    if (!API || typeof API.queryCatalog !== "function") return;

    if (catalogAbortCtrl) {
      try {
        catalogAbortCtrl.abort();
      } catch (_e) {}
    }
    const ctrl = typeof AbortController === "function" ? new AbortController() : null;
    catalogAbortCtrl = ctrl;
    const mySeq = ++catalogReqSeq;

    const clearBtn = document.getElementById("clearSearchBtn");
    if (clearBtn) {
      clearBtn.classList.toggle("hidden", state.searchQuery.length === 0);
    }
    renderCategoryButtons();
    updateFavFilterButton();

    const pListEl = document.getElementById("projectList");
    const aListEl = document.getElementById("articleList");
    if (pListEl) pListEl.setAttribute("aria-busy", "true");
    if (aListEl) aListEl.setAttribute("aria-busy", "true");

    try {
      const res = await API.queryCatalog(
        {
          query: state.searchQuery,
          category: state.activeCategory,
          sortBy: state.sortBy,
          favoritesOnly: state.onlyFavorites,
          favoriteIds: state.favorites.slice()
        },
        ctrl ? { signal: ctrl.signal } : undefined
      );

      // 核心时序门禁：若期间已有更新的检索发起，直接丢弃过期的慢响应
      if (mySeq !== catalogReqSeq) return;

      const projs = res.projects || [];
      const arts = res.articles || [];
      projs.forEach((p) => projectCacheById.set(p.id, p));
      if (!state.searchQuery.trim() && state.activeCategory === "all" && arts.length >= 2) {
        allArticlesOrder = arts.slice();
      }

      if (!validSets.projects && !state.searchQuery.trim() && state.activeCategory === "all" && !state.onlyFavorites && projs.length > 0) {
        validSets.projects = new Set(projs.map((p) => p.id));
        state.favorites = state.favorites.filter((id) => validSets.projects.has(id));
        state.compareIds = state.compareIds.filter((id) => validSets.projects.has(id)).slice(0, UI_CONFIG.maxCompare);
        safeSetRaw(STORAGE_KEYS.favorites, JSON.stringify(state.favorites));
        safeSetRaw(STORAGE_KEYS.compare, JSON.stringify(state.compareIds));
        updateFavFilterButton();
        renderCompareBar();
      }

      state.catalogProjects = projs;
      state.catalogArticles = state.onlyFavorites ? [] : arts;
      renderCatalogLists();
    } catch (err) {
      if (err && (err.name === "AbortError" || err.code === "ABORTED")) return;
      if (mySeq !== catalogReqSeq) return;
      const statusEl = document.getElementById("filterStatusBar");
      if (statusEl) statusEl.textContent = "检索服务暂时繁忙，已保留当前列表视图。";
    } finally {
      if (mySeq === catalogReqSeq) {
        if (pListEl) pListEl.removeAttribute("aria-busy");
        if (aListEl) aListEl.removeAttribute("aria-busy");
      }
    }
  }

  function renderCatalogLists() {
    const tokens = parseQueryTokens(state.searchQuery);
    const filteredProjects = state.catalogProjects || [];
    const filteredArticles = state.onlyFavorites ? [] : (state.catalogArticles || []);

    const projectSection = document.getElementById("projects-anchor");
    const articleSection = document.getElementById("articles-anchor");
    const projectListEl = document.getElementById("projectList");
    const articleListEl = document.getElementById("articleList");

    projectListEl.innerHTML = filteredProjects
      .map((p) => {
        const isFav = state.favorites.includes(p.id);
        const isCmp = state.compareIds.includes(p.id);
        const delivText = Array.isArray(p.deliverables) ? p.deliverables[0] || "" : String(p.deliverables || "");

        return `
        <article class="project-card" data-testid="project-card" data-id="${escapeHtml(p.id)}" data-category="${escapeHtml(p.category)}">
          <div>
            <div class="card-meta">
              <span class="badge">${escapeHtml(p.categoryLabel)}</span>
              <time>${escapeHtml(p.date)}</time>
              <span>${escapeHtml(p.durationHint || "")}</span>
            </div>
            <h3 class="card-title">${highlightTextHtml(p.title, tokens)}</h3>
            <p class="card-summary">${highlightTextHtml(p.summary, tokens)}</p>
            <div class="card-Specs">核心交付：${highlightTextHtml(delivText, tokens)}</div>
            <div class="tag-row">
              ${(p.tags || []).map((t) => `<span class="tag-pill">${highlightTextHtml(t, tokens)}</span>`).join("")}
            </div>
          </div>
          <div class="card-actions">
            <button type="button" class="btn btn-primary" data-testid="project-open" data-project-id="${escapeHtml(p.id)}">
              查看方案详情 →
            </button>
            <button
              type="button"
              class="btn"
              data-testid="favorite-btn"
              data-fav-id="${escapeHtml(p.id)}"
              data-favorited="${isFav ? "true" : "false"}"
              aria-pressed="${isFav ? "true" : "false"}"
            >${isFav ? "★ 已收藏" : "☆ 收藏"}</button>
            <button
              type="button"
              class="btn"
              data-testid="compare-toggle"
              data-compare-id="${escapeHtml(p.id)}"
              data-compared="${isCmp ? "true" : "false"}"
              aria-pressed="${isCmp ? "true" : "false"}"
            >${isCmp ? "✓ 已在对比篮" : "+ 加入对比"}</button>
          </div>
        </article>`;
      })
      .join("");

    articleListEl.innerHTML = filteredArticles
      .map((a) => {
        return `
        <article class="article-card" data-testid="article-card" data-id="${escapeHtml(a.id)}">
          <div>
            <div class="card-meta">
              <span class="badge">${escapeHtml(a.category)}</span>
              <time>${escapeHtml(a.date)}</time>
              <span>约 ${escapeHtml(a.readingMinutes)} 分钟阅读</span>
            </div>
            <h3 class="card-title">${highlightTextHtml(a.title, tokens)}</h3>
            <p class="card-summary">${highlightTextHtml(a.summary, tokens)}</p>
            <div class="tag-row">
              ${(a.tags || []).map((t) => `<span class="tag-pill">${highlightTextHtml(t, tokens)}</span>`).join("")}
            </div>
          </div>
          <div class="card-actions">
            <button type="button" class="btn btn-primary" data-testid="article-open" data-article-id="${escapeHtml(a.id)}">
              阅读全文与目录 →
            </button>
          </div>
        </article>`;
      })
      .join("");

    const totalKnownProjs = Math.max(projectCacheById.size, filteredProjects.length);
    const totalKnownArts = Math.max(allArticlesOrder.length, filteredArticles.length);
    document.getElementById("projectCountHint").textContent = `当前显示 ${filteredProjects.length} / ${totalKnownProjs} 个项目`;
    document.getElementById("articleCountHint").textContent = `当前显示 ${filteredArticles.length} / ${totalKnownArts} 篇手记`;

    const totalVisible = filteredProjects.length + filteredArticles.length;
    const emptyEl = document.getElementById("emptyState");
    const statusEl = document.getElementById("filterStatusBar");

    if (totalVisible === 0) {
      emptyEl.classList.remove("hidden");
      projectSection.classList.add("hidden");
      articleSection.classList.add("hidden");

      const emptyTitle = document.getElementById("emptyTitle");
      const emptyDesc = document.getElementById("emptyDesc");
      const emptyActions = document.getElementById("emptyActions");

      if (state.onlyFavorites && state.favorites.length === 0) {
        emptyTitle.textContent = "收藏夹目前还是空的";
        emptyDesc.textContent = "您尚未收藏任何代表项目，或刚刚取消了最后一项收藏。可一键退出“只看已收藏”恢复完整列表。";
        emptyActions.innerHTML = `
          <button type="button" class="btn btn-primary" data-empty-act="exit-fav">退出“只看已收藏”返回全部</button>
          <button type="button" class="btn" data-empty-act="reset-all">重置全部筛选与搜索词</button>
        `;
      } else {
        emptyTitle.textContent = "没有找到同时满足条件的内容";
        emptyDesc.textContent = `未检索到与“${state.searchQuery.trim() || "当前组合筛选"}”完全匹配的项目或手记。您可以清空搜索词，或点选下方高频工程词直达：`;
        const kwBtns = UI_CONFIG.recommendedKeywords
          .map(
            (kw) =>
              `<button type="button" class="btn btn-subtle" data-empty-kw="${escapeHtml(kw)}">试试搜“${escapeHtml(kw)}”</button>`
          )
          .join("");
        emptyActions.innerHTML = `
          <button type="button" class="btn btn-primary" data-empty-act="clear-query">清空搜索词</button>
          ${state.activeCategory !== "all" || state.onlyFavorites ? `<button type="button" class="btn" data-empty-act="reset-filters">解除分类与收藏过滤</button>` : ""}
          ${kwBtns}
        `;
      }
      statusEl.textContent = "当前共匹配 0 条记录，请使用下方快捷恢复出口继续浏览。";
    } else {
      emptyEl.classList.add("hidden");
      projectSection.classList.toggle("hidden", filteredProjects.length === 0);
      articleSection.classList.toggle("hidden", filteredArticles.length === 0);
      statusEl.textContent = tokens.length
        ? `全文交集检索（关键词：${tokens.join(" + ")}）共命中 ${filteredProjects.length} 个项目、${filteredArticles.length} 篇长文。`
        : `当前展示 ${filteredProjects.length} 个代表项目、${filteredArticles.length} 篇实测长文。`;
    }
  }

  /* ==================== 7. 收藏同步与横向对比面板（原生 SVG 零重叠雷达图 + 焦点锁） ==================== */
  function syncFavoriteButtonsInPlace() {
    document.querySelectorAll("[data-testid='favorite-btn']").forEach((btn) => {
      const pid = btn.getAttribute("data-fav-id");
      if (!pid) return;
      const on = state.favorites.includes(pid);
      btn.setAttribute("aria-pressed", on ? "true" : "false");
      btn.setAttribute("data-favorited", on ? "true" : "false");
      btn.textContent = btn.closest("#detailActionGroup")
        ? on ? "★ 已收藏该项目" : "☆ 收藏该项目"
        : on ? "★ 已收藏" : "☆ 收藏";
    });
  }

  function toggleFavorite(projId) {
    if (!projId || (validSets.projects && !validSets.projects.has(projId))) return;
    const idx = state.favorites.indexOf(projId);
    if (idx >= 0) {
      state.favorites.splice(idx, 1);
    } else {
      state.favorites.push(projId);
    }
    state.favorites = Array.from(new Set(state.favorites));
    safeSetRaw(STORAGE_KEYS.favorites, JSON.stringify(state.favorites));

    updateFavFilterButton();
    syncFavoriteButtonsInPlace();

    if (state.onlyFavorites) {
      runCatalogQuery();
    }
  }

  function syncCardCompareButtonsInPlace() {
    document.querySelectorAll("[data-testid='compare-toggle']").forEach((btn) => {
      const pid = btn.getAttribute("data-compare-id");
      if (!pid) return;
      const on = state.compareIds.includes(pid);
      btn.setAttribute("aria-pressed", on ? "true" : "false");
      btn.setAttribute("data-compared", on ? "true" : "false");
      btn.textContent = btn.closest("#detailActionGroup")
        ? on ? "✓ 已在对比篮" : "+ 加入对比篮"
        : on ? "✓ 已在对比篮" : "+ 加入对比";
    });
  }

  function toggleCompare(projId) {
    if (!projId || (validSets.projects && !validSets.projects.has(projId))) return;
    const idx = state.compareIds.indexOf(projId);
    if (idx < 0 && state.compareIds.length >= UI_CONFIG.maxCompare) {
      showToast(`对比篮最多同时容纳 ${UI_CONFIG.maxCompare} 个项目，请先移除一项后再添加。`);
      return;
    }
    pushHistoryBeforeMutation();
    if (idx >= 0) {
      state.compareIds.splice(idx, 1);
    } else {
      state.compareIds.push(projId);
    }
    state.compareIds = Array.from(new Set(state.compareIds)).slice(0, UI_CONFIG.maxCompare);
    safeSetRaw(STORAGE_KEYS.compare, JSON.stringify(state.compareIds));

    renderCompareBar();
    syncCardCompareButtonsInPlace();
    if (!document.getElementById("compareBackdrop").classList.contains("hidden")) {
      if (state.compareIds.length === 0) {
        closeCompareModal();
      } else {
        renderCompareTable();
      }
    }
  }

  function clearCompareAll() {
    if (!state.compareIds.length) return;
    pushHistoryBeforeMutation();
    state.compareIds = [];
    safeSetRaw(STORAGE_KEYS.compare, "[]");
    closeCompareModal();
    renderCompareBar();
    syncCardCompareButtonsInPlace();
  }

  function renderCompareBar() {
    const bar = document.getElementById("compareBar");
    const title = document.getElementById("compareBarTitle");
    const chips = document.getElementById("compareBarChips");
    if (!bar) return;

    if (state.compareIds.length === 0) {
      bar.classList.add("hidden");
      chips.innerHTML = "";
      return;
    }

    bar.classList.remove("hidden");
    title.textContent = `对比篮已选（${state.compareIds.length}/${UI_CONFIG.maxCompare}）`;
    chips.innerHTML = state.compareIds
      .map((id) => {
        const p = projectCacheById.get(id);
        return p ? `<span class="badge">${escapeHtml(p.title.slice(0, 14))}</span>` : "";
      })
      .join("");
  }

  function renderCompareRadarChart(items) {
    const svg = document.getElementById("compareChartSvg");
    const legend = document.getElementById("compareChartLegend");
    if (!svg || !legend) return;

    const axes =
      items[0] && Array.isArray(items[0].radarAxes) && items[0].radarAxes.length >= 3
        ? items[0].radarAxes
        : ["回归覆盖度", "接入轻量度", "排障可解释性", "交付敏捷度"];

    const isDark = state.theme === "dark";
    const gridStroke = isDark ? "#334155" : "#cbc5b5";
    const labelFill = isDark ? "#e2e8f0" : "#1e293b";
    const palette = isDark ? UI_CONFIG.radarColorsDark : UI_CONFIG.radarColorsLight;

    const cx = 220;
    const cy = 132;
    const maxR = 76;
    const n = axes.length;

    const rings = [0.35, 0.68, 1.0]
      .map(
        (ratio) =>
          `<circle cx="${cx}" cy="${cy}" r="${Math.round(maxR * ratio * 10) / 10}" fill="none" stroke="${gridStroke}" stroke-dasharray="${ratio < 1 ? "3 3" : "none"}" stroke-width="1" />`
      )
      .join("");

    const axisLinesAndLabels = axes
      .map((axisName, i) => {
        const angle = -Math.PI / 2 + (i * 2 * Math.PI) / n;
        const x2 = Math.round((cx + maxR * Math.cos(angle)) * 10) / 10;
        const y2 = Math.round((cy + maxR * Math.sin(angle)) * 10) / 10;
        const lx = Math.round((cx + (maxR + 26) * Math.cos(angle)) * 10) / 10;
        const ly = Math.round((cy + (maxR + 20) * Math.sin(angle)) * 10) / 10;
        const cosV = Math.cos(angle);
        const anchor = Math.abs(cosV) < 0.2 ? "middle" : cosV > 0 ? "start" : "end";
        return `
          <line x1="${cx}" y1="${cy}" x2="${x2}" y2="${y2}" stroke="${gridStroke}" stroke-width="1" />
          <text x="${lx}" y="${ly + 4}" text-anchor="${anchor}" fill="${labelFill}" font-size="12" font-weight="600">${escapeHtml(axisName)}</text>
        `;
      })
      .join("");

    const seriesPolygons = items
      .map((proj, sIdx) => {
        const style = palette[sIdx % palette.length];
        const m = proj.metrics || {};
        const pts = [];
        const dots = [];
        axes.forEach((axisName, i) => {
          const val = Math.max(15, Math.min(100, Number(m[axisName]) || 70));
          const r = (val / 100) * maxR;
          const angle = -Math.PI / 2 + (i * 2 * Math.PI) / n;
          const px = Math.round((cx + r * Math.cos(angle)) * 10) / 10;
          const py = Math.round((cy + r * Math.sin(angle)) * 10) / 10;
          pts.push(`${px},${py}`);
          dots.push(`<circle cx="${px}" cy="${py}" r="3.5" fill="${style.stroke}" />`);
        });
        return `
          <polygon points="${pts.join(" ")}" fill="${style.fill}" stroke="${style.stroke}" stroke-width="2.2" />
          ${dots.join("")}
        `;
      })
      .join("");

    svg.innerHTML = `${rings}${axisLinesAndLabels}${seriesPolygons}`;
    legend.innerHTML = items
      .map((proj, sIdx) => {
        const style = palette[sIdx % palette.length];
        return `<span class="legend-item"><span class="legend-swatch" style="background:${style.stroke}"></span>${escapeHtml(proj.title)}</span>`;
      })
      .join("");
  }

  function renderCompareTable() {
    const wrap = document.getElementById("compareTableWrap");
    const items = state.compareIds
      .map((id) => projectCacheById.get(id))
      .filter(Boolean);

    renderCompareRadarChart(items);

    if (!items.length) {
      wrap.innerHTML = `<p>暂无已选对比项目。</p>`;
      return;
    }

    const rows = [
      { label: "项目名称", render: (p) => `<strong>${escapeHtml(p.title)}</strong>` },
      { label: "所属方向", render: (p) => `<span class="badge">${escapeHtml(p.categoryLabel)}</span>` },
      { label: "周期参考", render: (p) => escapeHtml(p.durationHint || "") },
      { label: "工程深度分", render: (p) => `${escapeHtml(p.depthScore)} / 100` },
      {
        label: "核心交付物",
        render: (p) =>
          Array.isArray(p.deliverables)
            ? p.deliverables.map((d) => `• ${escapeHtml(d)}`).join("<br/>")
            : escapeHtml(p.deliverables || "")
      },
      { label: "典型适用场景", render: (p) => escapeHtml(p.scenario || "") },
      {
        label: "移出对比",
        render: (p) =>
          `<button type="button" class="btn btn-subtle" data-remove-cmp="${escapeHtml(p.id)}">移出此项</button>`
      }
    ];

    wrap.innerHTML = `
      <table class="data-table">
        <thead>
          <tr>
            <th>对比维度</th>
            ${items.map((p) => `<th>${escapeHtml(p.title)}</th>`).join("")}
          </tr>
        </thead>
        <tbody>
          ${rows
            .map(
              (r) => `
            <tr>
              <th>${escapeHtml(r.label)}</th>
              ${items.map((p) => `<td>${r.render(p)}</td>`).join("")}
            </tr>`
            )
            .join("")}
        </tbody>
      </table>
    `;
  }

  function openCompareModal(triggerEl) {
    if (!state.compareIds.length) return;
    state.compareOriginEl = triggerEl || document.activeElement;
    renderCompareTable();
    const backdrop = document.getElementById("compareBackdrop");
    backdrop.classList.remove("hidden");
    const closeBtn = document.getElementById("compareCloseBtn");
    if (closeBtn) closeBtn.focus();
  }

  function closeCompareModal() {
    const backdrop = document.getElementById("compareBackdrop");
    if (backdrop.classList.contains("hidden")) return;
    backdrop.classList.add("hidden");
    const origin = state.compareOriginEl;
    state.compareOriginEl = null;
    if (origin && origin.isConnected && origin.offsetParent !== null) {
      origin.focus({ preventScroll: true });
    } else {
      const openBtn = document.getElementById("compareOpenBtn");
      if (openBtn && openBtn.offsetParent !== null) openBtn.focus({ preventScroll: true });
    }
  }

  /* ==================== 8. 异步排期测算（防竞态锁 + 14周连续空闲求解 + 非破坏带入） ==================== */
  function renderEstimatorControls() {
    const pcat = state.plannerCatalog || { modes: [], addons: [], scales: [], calendarWeeks: [] };
    const typeWrap = document.getElementById("estTypeGroup");
    const addonWrap = document.getElementById("estAddonGroup");
    const scaleWrap = document.getElementById("estScaleGroup");
    const weekWrap = document.getElementById("estStartWeekGroup");

    typeWrap.innerHTML = (pcat.modes || [])
      .map((m) => {
        const active = state.estimator.modeId === m.id;
        return `<button
          type="button"
          class="est-option-btn"
          data-testid="est-type"
          data-mode-id="${escapeHtml(m.id)}"
          data-active="${active ? "true" : "false"}"
          aria-pressed="${active ? "true" : "false"}"
        >
          <span class="est-option-title">${escapeHtml(m.label)}</span>
          <span class="est-option-sub">${escapeHtml(m.description)}</span>
        </button>`;
      })
      .join("");

    addonWrap.innerHTML = (pcat.addons || [])
      .map((a) => {
        const active = state.estimator.addonIds.includes(a.id);
        return `<button
          type="button"
          class="est-option-btn"
          data-testid="est-addon"
          data-addon-id="${escapeHtml(a.id)}"
          data-active="${active ? "true" : "false"}"
          aria-pressed="${active ? "true" : "false"}"
        >
          <span class="est-option-title">${active ? "✓ " : "+ "}${escapeHtml(a.label)}</span>
          <span class="est-option-sub">+${escapeHtml(a.addWeeks)} 周 · +${escapeHtml(a.addMinK)}k～${escapeHtml(a.addMaxK)}k</span>
        </button>`;
      })
      .join("");

    scaleWrap.innerHTML = (pcat.scales || [])
      .map((s) => {
        const active = state.estimator.scaleId === s.id;
        return `<button
          type="button"
          class="chip-btn"
          data-scale="${escapeHtml(s.id)}"
          data-active="${active ? "true" : "false"}"
          aria-pressed="${active ? "true" : "false"}"
        >${escapeHtml(s.label)}</button>`;
      })
      .join("");

    const selectableWeeks = (pcat.calendarWeeks || []).filter((w) => w.selectableAsStart);
    weekWrap.innerHTML = selectableWeeks
      .map((w) => {
        const active = state.estimator.startWeek === w.week;
        return `<button
          type="button"
          class="est-week-btn"
          data-week="${escapeHtml(w.week)}"
          data-busy="${w.busy ? "true" : "false"}"
          data-active="${active ? "true" : "false"}"
          aria-pressed="${active ? "true" : "false"}"
        >
          <span class="est-week-label">${escapeHtml(w.label)}</span>
          <span class="est-week-tag">${w.busy ? "⚠ 已约满" : "✓ 空闲可约"}</span>
        </button>`;
      })
      .join("");
  }

  function renderEstimatorSummary() {
    const resBox = document.getElementById("estResultBox");
    const conflictBanner = document.getElementById("plannerConflictBanner");
    const conflictText = document.getElementById("plannerConflictText");
    const milestonesBox = document.getElementById("estMilestonesBox");
    const ev = state.planEval;

    if (!ev) return;

    const addonSummary = ev.addonLabels && ev.addonLabels.length
      ? ev.addonLabels.join("、")
      : "未叠加额外模块（纯基础闭环）";

    resBox.innerHTML = `
      <div class="est-price-main">参考预算 ${ev.budgetMinK}k ～ ${ev.budgetMaxK}k RMB</div>
      <div class="est-meta-line">预计投入周期：<strong>${ev.totalWeeks} 周</strong>（${escapeHtml(ev.startWeekLabel)} → ${escapeHtml(ev.endWeekLabel)}）</div>
      <div class="est-meta-line">合作模式：${escapeHtml(ev.modeLabel)} · ${escapeHtml(ev.scaleLabel)}</div>
      <div class="est-deliverable-box">
        <div>叠加模块：${escapeHtml(addonSummary)}</div>
      </div>
    `;

    if (ev.conflict && ev.conflict.hasConflict) {
      conflictText.textContent = ev.conflict.message || "所选排期窗口内存在已约满繁忙周，建议顺延至连续空闲周启动。";
      conflictBanner.classList.remove("hidden");
    } else {
      conflictText.textContent = "";
      conflictBanner.classList.add("hidden");
    }

    milestonesBox.innerHTML = (ev.milestones || [])
      .map(
        (m) => `
        <li class="est-milestone-item">
          <span class="est-milestone-phase">${escapeHtml(m.phase)} · ${escapeHtml(m.title)}</span>
          <span class="est-milestone-meta">${escapeHtml(m.weekRangeLabel)}（${m.weeks} 周）</span>
        </li>`
      )
      .join("");
  }

  async function runPlanEvaluation() {
    if (!API || typeof API.evaluatePlan !== "function") return;

    if (planAbortCtrl) {
      try {
        planAbortCtrl.abort();
      } catch (_e) {}
    }
    const ctrl = typeof AbortController === "function" ? new AbortController() : null;
    planAbortCtrl = ctrl;
    const mySeq = ++planReqSeq;

    const card = document.getElementById("estimatorSummaryCard");
    if (card) card.setAttribute("aria-busy", "true");

    try {
      const res = await API.evaluatePlan(cloneEstimator(state.estimator), ctrl ? { signal: ctrl.signal } : undefined);
      if (mySeq !== planReqSeq) return;
      state.planEval = res;
      renderEstimatorSummary();
    } catch (err) {
      if (err && (err.name === "AbortError" || err.code === "ABORTED")) return;
    } finally {
      if (mySeq === planReqSeq && card) {
        card.removeAttribute("aria-busy");
      }
    }
  }

  function findNextConflictFreeStartWeek(currentStartWeek, totalWeeksSpan) {
    const weeks = (state.plannerCatalog && state.plannerCatalog.calendarWeeks) || [];
    const selectable = weeks.filter((w) => w.selectableAsStart);
    if (!selectable.length) return currentStartWeek;

    const span = Math.max(1, Number(totalWeeksSpan) || 2);
    const curSelIdx = selectable.findIndex((w) => w.week === currentStartWeek);

    for (let offset = 1; offset <= selectable.length; offset++) {
      const cand = selectable[(Math.max(0, curSelIdx) + offset) % selectable.length];
      const fullIdx = weeks.findIndex((w) => w.week === cand.week);
      if (fullIdx < 0 || fullIdx + span > weeks.length) continue;
      const windowSlice = weeks.slice(fullIdx, fullIdx + span);
      if (windowSlice.every((slot) => !slot.busy)) {
        return cand.week;
      }
    }
    return selectable[selectable.length - 1].week;
  }

  function resolveScheduleConflict() {
    const span = (state.planEval && state.planEval.totalWeeks) || 2;
    const nextWeek = findNextConflictFreeStartWeek(state.estimator.startWeek, span);
    if (nextWeek && nextWeek !== state.estimator.startWeek) {
      pushHistoryBeforeMutation();
      state.estimator.startWeek = nextWeek;
      saveEstimatorState();
      renderEstimatorControls();
      runPlanEvaluation();
    }
  }

  function mergeStructuredBlockIntoMessage(blockRegex, newBlockText) {
    const msgInput = document.getElementById("contactMessage");
    const existing = msgInput.value || "";
    const stripped = existing.replace(blockRegex, "").trim();
    let combined = stripped ? `${stripped}\n${newBlockText}` : newBlockText;
    if (combined.length > 495) {
      const budgetForNote = Math.max(0, 490 - newBlockText.length);
      combined = stripped
        ? `${stripped.slice(0, budgetForNote)}\n${newBlockText}`
        : newBlockText.slice(0, 495);
    }
    msgInput.value = combined;
    updateCharCounterAndSaveDraft();
    if (state.formSubmittedOnce) {
      validateSingleField("message");
    }
  }

  function applyEstimatorToContact() {
    const ev = state.planEval;
    if (!ev) return;

    const addonsText = ev.addonLabels && ev.addonLabels.length ? ev.addonLabels.join("+") : "基础标准范围";
    const cmpTitles = state.compareIds
      .map((id) => projectCacheById.get(id))
      .filter(Boolean)
      .map((p) => p.title);
    const cmpPart = cmpTitles.length ? `参考项目：${cmpTitles.join("、")}｜` : "";
    const msSummary = (ev.milestones || []).map((m) => `${m.phase}(${m.weeks}周)`).join("→");

    const msgInput = document.getElementById("contactMessage");
    msgInput.value = (msgInput.value || "").replace(CMP_BLOCK_REGEX, "").trim();

    const summaryBlock =
      `【工作台选型与排期方案】${cmpPart}模式：${ev.modeLabel}｜叠加：${addonsText}｜规模：${ev.scaleLabel}｜期望启动：${ev.startWeekLabel}（${msSummary}，共${ev.totalWeeks}周 / ${ev.budgetMinK}k-${ev.budgetMaxK}k）【/工作台选型与排期方案】`;

    mergeStructuredBlockIntoMessage(WORKBENCH_BLOCK_REGEX, summaryBlock);
    const fb = document.getElementById("estHandoffFeedback");
    if (fb) {
      fb.textContent = "✓ 已将已选对比项目与排期里程碑方案合并带入下方留言框（原有备注完整保留）。";
    }
  }

  function applyComparedProjectsToContact() {
    const titles = state.compareIds
      .map((id) => projectCacheById.get(id))
      .filter(Boolean)
      .map((p) => p.title);
    if (!titles.length) return;
    const cmpBlock = `【对比候选项目】我们对以下参考方案感兴趣：${titles.join("、")}【/对比候选项目】`;
    mergeStructuredBlockIntoMessage(CMP_BLOCK_REGEX, cmpBlock);
    closeCompareModal();
    const contactSec = document.getElementById("contact-anchor");
    if (contactSec) contactSec.scrollIntoView({ block: "start" });
  }

  /* ==================== 9. 异步详情加载（防慢详情倒灌 + Hash 历史栈 + 目录防遮挡定位） ==================== */
  function recordRecentItem(kind, id, title) {
    state.recentItems = [
      { kind, id, title: String(title || "").slice(0, 22) },
      ...state.recentItems.filter((x) => !(x.kind === kind && x.id === id))
    ].slice(0, 4);
    safeSetRaw(STORAGE_KEYS.recent, JSON.stringify(state.recentItems));
    renderRecentTray();
  }

  function renderDetailActionButtons(projId) {
    const wrap = document.getElementById("detailActionGroup");
    if (!wrap) return;
    if (!projId) {
      wrap.innerHTML = "";
      return;
    }
    const isFav = state.favorites.includes(projId);
    const isCmp = state.compareIds.includes(projId);
    wrap.innerHTML = `
      <button
        type="button"
        class="btn"
        data-testid="favorite-btn"
        data-fav-id="${escapeHtml(projId)}"
        data-favorited="${isFav ? "true" : "false"}"
        aria-pressed="${isFav ? "true" : "false"}"
      >${isFav ? "★ 已收藏该项目" : "☆ 收藏该项目"}</button>
      <button
        type="button"
        class="btn"
        data-testid="compare-toggle"
        data-compare-id="${escapeHtml(projId)}"
        data-compared="${isCmp ? "true" : "false"}"
        aria-pressed="${isCmp ? "true" : "false"}"
      >${isCmp ? "✓ 已在对比篮" : "+ 加入对比篮"}</button>
    `;
  }

  function updateArticlePagerButtons(curArtId, prevObj, nextObj) {
    const pager = document.getElementById("articlePager");
    const prevBtn = document.getElementById("articlePrevBtn");
    const nextBtn = document.getElementById("articleNextBtn");

    let pItem = prevObj;
    let nItem = nextObj;
    if ((!pItem || !nItem) && allArticlesOrder.length >= 2) {
      const idx = allArticlesOrder.findIndex((a) => a.id === curArtId);
      if (idx >= 0) {
        pItem = pItem || allArticlesOrder[(idx - 1 + allArticlesOrder.length) % allArticlesOrder.length];
        nItem = nItem || allArticlesOrder[(idx + 1) % allArticlesOrder.length];
      }
    }

    if (pItem && nItem) {
      pager.classList.remove("hidden");
      prevBtn.setAttribute("data-target-art", pItem.id);
      prevBtn.textContent = `← 上一篇：${String(pItem.title || "").slice(0, 12)}…`;
      nextBtn.setAttribute("data-target-art", nItem.id);
      nextBtn.textContent = `下一篇：${String(nItem.title || "").slice(0, 12)}… →`;
    } else {
      pager.classList.add("hidden");
    }
  }

  function renderProjectDetailPayload(proj) {
    projectCacheById.set(proj.id, proj);
    document.getElementById("detailLayout").classList.add("single-col");
    document.getElementById("articleToc").classList.add("hidden");
    document.getElementById("articlePager").classList.add("hidden");

    renderDetailActionButtons(proj.id);
    document.getElementById("detailMeta").innerHTML = `
      <span class="badge">${escapeHtml(proj.categoryLabel)}</span>
      <time>${escapeHtml(proj.date)}</time>
      <span>${escapeHtml(proj.durationHint || "")}</span>
      <span>工程深度分 ${escapeHtml(proj.depthScore)}</span>
    `;
    document.getElementById("detailTitle").textContent = proj.title;

    const delivHtml = Array.isArray(proj.deliverables)
      ? `<ul>${proj.deliverables.map((d) => `<li>${escapeHtml(d)}</li>`).join("")}</ul>`
      : `<p>${escapeHtml(proj.deliverables || "")}</p>`;

    document.getElementById("detailBody").innerHTML = `
      <div class="card-Specs">
        <strong>适用业务场景：</strong>${escapeHtml(proj.scenario || "")}
      </div>
      <h2>核心交付清单</h2>
      ${delivHtml}
      <h2>方案设计与实践细节</h2>
      ${(proj.detailParagraphs || []).map((para) => `<p>${escapeHtml(para)}</p>`).join("")}
      ${proj.architectureNotes ? `<blockquote>架构注记：${escapeHtml(proj.architectureNotes)}</blockquote>` : ""}
      <div class="tag-row">
        ${(proj.tags || []).map((t) => `<span class="tag-pill">${escapeHtml(t)}</span>`).join("")}
      </div>
    `;
    recordRecentItem("project", proj.id, proj.title);
  }

  function renderArticleDetailPayload(art) {
    document.getElementById("detailLayout").classList.remove("single-col");
    const tocAside = document.getElementById("articleToc");
    const tocList = document.getElementById("articleTocList");

    renderDetailActionButtons("");
    document.getElementById("detailMeta").innerHTML = `
      <span class="badge">${escapeHtml(art.category)}</span>
      <time>${escapeHtml(art.date)}</time>
      <span>预计阅读 ${escapeHtml(art.readingMinutes)} 分钟</span>
    `;
    document.getElementById("detailTitle").textContent = art.title;

    const bodyEl = document.getElementById("detailBody");
    bodyEl.innerHTML = art.bodyHtml || "";
    // 将长文内的数据表格包裹进局部横向滚动容器，保证 320px/375px 窄屏零横向撑破
    bodyEl.querySelectorAll("table").forEach((tbl) => {
      tbl.classList.add("data-table");
      if (!tbl.parentElement || !tbl.parentElement.classList.contains("table-scroll-wrap")) {
        const wrapper = document.createElement("div");
        wrapper.className = "table-scroll-wrap";
        tbl.parentNode.insertBefore(wrapper, tbl);
        wrapper.appendChild(tbl);
      }
    });

    const tocItems = art.toc || [];
    if (tocItems.length >= 2) {
      tocAside.classList.remove("hidden");
      tocList.innerHTML = tocItems
        .map(
          (sec, idx) => `
          <button
            type="button"
            class="toc-link ${idx === 0 ? "active" : ""}"
            data-toc-target="${escapeHtml(sec.id)}"
            aria-current="${idx === 0 ? "true" : "false"}"
          >${escapeHtml(sec.title)}</button>`
        )
        .join("");
    } else {
      tocAside.classList.add("hidden");
      tocList.innerHTML = "";
    }

    updateArticlePagerButtons(art.id, art.prevArticle, art.nextArticle);
    recordRecentItem("article", art.id, art.title);
  }

  function parseLocationHash() {
    const raw = (window.location.hash || "").replace(/^#/, "").trim();
    if (raw.startsWith("project/")) {
      const id = decodeURIComponent(raw.slice("project/".length));
      if (id) return { view: "project", id };
    }
    if (raw.startsWith("article/")) {
      const id = decodeURIComponent(raw.slice("article/".length));
      if (id) return { view: "article", id };
    }
    return { view: "home", id: "" };
  }

  async function syncRouteFromHash() {
    const prevView = state.route.view;
    const next = parseLocationHash();
    const homeEl = document.getElementById("homeView");
    const detailEl = document.getElementById("detailView");
    const detailBody = document.getElementById("detailBody");

    if (next.view === "home") {
      if (detailAbortCtrl) {
        try {
          detailAbortCtrl.abort();
        } catch (_e) {}
      }
      detailReqSeq++;
      detailEl.removeAttribute("aria-busy");
      detailBody.removeAttribute("aria-busy");

      state.route = { view: "home", id: "" };
      renderDetailActionButtons("");
      detailEl.classList.add("hidden");
      homeEl.classList.remove("hidden");
      document.getElementById("readingProgressBar").style.width = "0%";

      if (prevView !== "home") {
        const targetY = state.savedListScrollY || 0;
        window.scrollTo(0, targetY);
        requestAnimationFrame(() => {
          window.scrollTo(0, targetY);
          restoreListOriginFocus();
        });
      }
      return;
    }

    if (prevView === "home") {
      state.savedListScrollY = window.scrollY || window.pageYOffset || 0;
    }

    const activeBefore = document.activeElement;
    const wasOnPager =
      activeBefore && (activeBefore.id === "articleNextBtn" || activeBefore.id === "articlePrevBtn");
    const pagerIdToKeep = wasOnPager ? activeBefore.id : "";

    state.route = { view: next.view, id: next.id };
    homeEl.classList.add("hidden");
    detailEl.classList.remove("hidden");

    if (next.view === "article") {
      updateArticlePagerButtons(next.id, null, null);
    } else {
      document.getElementById("articlePager").classList.add("hidden");
    }

    if (detailAbortCtrl) {
      try {
        detailAbortCtrl.abort();
      } catch (_e) {}
    }
    const ctrl = typeof AbortController === "function" ? new AbortController() : null;
    detailAbortCtrl = ctrl;
    const mySeq = ++detailReqSeq;

    detailEl.setAttribute("aria-busy", "true");
    detailBody.setAttribute("aria-busy", "true");

    try {
      const res = await API.getDetail(
        { type: next.view, id: next.id },
        ctrl ? { signal: ctrl.signal } : undefined
      );
      // 严防快速切篇或后退时慢速旧文档晚到覆盖当前详情页
      if (mySeq !== detailReqSeq) return;

      if (res.type === "project") {
        renderProjectDetailPayload(res.item);
      } else {
        renderArticleDetailPayload(res.item);
      }

      window.scrollTo(0, 0);
      updateScrollProgressAndToc();

      if (pagerIdToKeep) {
        const btnKeep = document.getElementById(pagerIdToKeep);
        if (btnKeep && btnKeep.offsetParent !== null) btnKeep.focus({ preventScroll: true });
      } else {
        const backBtn = document.getElementById("detailBackBtn");
        if (backBtn && backBtn.offsetParent !== null) backBtn.focus({ preventScroll: true });
      }
    } catch (err) {
      if (err && (err.name === "AbortError" || err.code === "ABORTED")) return;
      if (mySeq !== detailReqSeq) return;
      document.getElementById("detailTitle").textContent = "未找到对应内容";
      detailBody.innerHTML = `<p>${escapeHtml((err && err.message) || "目标条目不存在或已被移除，请返回主页列表。")}</p>`;
    } finally {
      if (mySeq === detailReqSeq) {
        detailEl.removeAttribute("aria-busy");
        detailBody.removeAttribute("aria-busy");
      }
    }
  }

  function restoreListOriginFocus() {
    if (state.lastListTriggerEl && state.lastListTriggerEl.isConnected && state.lastListTriggerEl.offsetParent !== null) {
      state.lastListTriggerEl.focus({ preventScroll: true });
      return;
    }
    if (state.lastListItemId) {
      const escId = typeof CSS !== "undefined" && CSS.escape ? CSS.escape(state.lastListItemId) : state.lastListItemId;
      const fallback = document.querySelector(`[data-project-id="${escId}"], [data-article-id="${escId}"]`);
      if (fallback && fallback.offsetParent !== null) {
        fallback.focus({ preventScroll: true });
      }
    }
  }

  function navigateToItem(kind, id, triggerEl) {
    if (!id) return;
    if (state.route.view === "home") {
      state.savedListScrollY = window.scrollY || window.pageYOffset || 0;
      state.lastListTriggerEl = triggerEl || document.activeElement;
      state.lastListItemId = id;
    }
    window.location.hash = `#${kind}/${encodeURIComponent(id)}`;
  }

  function navigateBackToHome() {
    if (window.location.hash && window.location.hash !== "#home") {
      window.location.hash = "#home";
    } else {
      syncRouteFromHash();
    }
  }

  /* ==================== 10. 单帧节流滚动监听（进度条 + 目录高亮，零空闲空转 rAF） ==================== */
  let scrollTicking = false;

  function getStickyHeaderBottom() {
    const header = document.querySelector(".top-bar");
    if (!header) return 0;
    const r = header.getBoundingClientRect();
    return Math.max(0, r.bottom);
  }

  function updateScrollProgressAndToc() {
    const docEl = document.documentElement;
    const maxScroll = Math.max(1, docEl.scrollHeight - docEl.clientHeight);
    const curY = window.scrollY || window.pageYOffset || 0;
    const pct = state.route.view === "home" ? 0 : Math.min(100, Math.max(0, Math.round((curY / maxScroll) * 100)));
    const bar = document.getElementById("readingProgressBar");
    if (bar) {
      bar.style.width = `${pct}%`;
      bar.setAttribute("aria-valuenow", String(pct));
    }

    if (state.route.view !== "article") return;
    const headings = Array.from(document.querySelectorAll("#detailBody h2[id], #detailBody h3[id]"));
    if (!headings.length) return;

    const threshold = Math.max(getStickyHeaderBottom() + 90, window.innerHeight * 0.36);
    let activeId = headings[0].id;
    for (const h of headings) {
      if (h.getBoundingClientRect().top <= threshold) {
        activeId = h.id;
      }
    }
    if (curY + docEl.clientHeight >= docEl.scrollHeight - 16) {
      activeId = headings[headings.length - 1].id;
    }

    document.querySelectorAll("#articleTocList .toc-link").forEach((link) => {
      const match = link.getAttribute("data-toc-target") === activeId;
      link.classList.toggle("active", match);
      link.setAttribute("aria-current", match ? "true" : "false");
    });
  }

  window.addEventListener(
    "scroll",
    () => {
      if (scrollTicking) return;
      scrollTicking = true;
      window.requestAnimationFrame(() => {
        scrollTicking = false;
        updateScrollProgressAndToc();
      });
    },
    { passive: true }
  );

  /* ==================== 11. 合作咨询校验、防连点并发锁、503 自动退避保底与一键复制 ==================== */
  function hydrateContactDraft() {
    const draft = readValidatedDraft();
    document.getElementById("contactName").value = draft.name;
    document.getElementById("contactEmail").value = draft.email;
    document.getElementById("contactMessage").value = draft.message;
    updateCharCounterOnly();
  }

  function updateCharCounterOnly() {
    const msg = document.getElementById("contactMessage").value || "";
    const len = msg.trim().length;
    const counter = document.getElementById("charCounter");
    if (!counter) return;
    if (len === 0) {
      counter.textContent = "当前 0 / 500 字（至少 10 字）";
    } else if (len < 10) {
      counter.textContent = `当前 ${len} / 500 字（还差 ${10 - len} 字达标）`;
    } else if (len > 500) {
      counter.textContent = `当前 ${len} / 500 字（已超出 ${len - 500} 字）`;
    } else {
      counter.textContent = `当前 ${len} / 500 字 ✓`;
    }
  }

  function updateCharCounterAndSaveDraft() {
    updateCharCounterOnly();
    const draft = {
      name: document.getElementById("contactName").value || "",
      email: document.getElementById("contactEmail").value || "",
      message: document.getElementById("contactMessage").value || ""
    };
    safeSetRaw(STORAGE_KEYS.draft, JSON.stringify(draft));
  }

  function getFieldError(field) {
    if (field === "name") {
      const v = (document.getElementById("contactName").value || "").trim();
      if (!v) return "请填写您的姓名或团队称呼。";
      if (v.length < 2) return "称呼至少需要 2 个字符。";
      if (v.length > 60) return "称呼请控制在 60 个字符以内。";
      return "";
    }
    if (field === "email") {
      const v = (document.getElementById("contactEmail").value || "").trim();
      if (!v) return "请填写用于接收回复的邮箱地址。";
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v)) return "邮箱格式有误（示例：name@company.com）。";
      return "";
    }
    if (field === "message") {
      const v = (document.getElementById("contactMessage").value || "").trim();
      if (!v) return "请简述您的合作背景与需求（10～500 字）。";
      if (v.length < 10) return `需求描述至少需 10 个字（当前仅 ${v.length} 字）。`;
      if (v.length > 500) return `需求描述不能超过 500 字（当前 ${v.length} 字，请精简 ${v.length - 500} 字）。`;
      return "";
    }
    return "";
  }

  function renderFieldError(field, msg) {
    const map = {
      name: { input: "contactName", err: "errName" },
      email: { input: "contactEmail", err: "errEmail" },
      message: { input: "contactMessage", err: "errMessage" }
    };
    const item = map[field];
    if (!item) return;
    const inputEl = document.getElementById(item.input);
    const errEl = document.getElementById(item.err);
    if (msg) {
      inputEl.setAttribute("aria-invalid", "true");
      errEl.textContent = msg;
      errEl.classList.remove("hidden");
    } else {
      inputEl.removeAttribute("aria-invalid");
      errEl.textContent = "";
      errEl.classList.add("hidden");
    }
  }

  function validateSingleField(field) {
    const err = getFieldError(field);
    renderFieldError(field, err);
    return !err;
  }

  async function handleSubmitInquiry() {
    if (submitInFlight) return;

    state.formSubmittedOnce = true;
    const svcBanner = document.getElementById("contactServiceBanner");
    const svcBannerText = document.getElementById("contactServiceBannerText");
    svcBanner.classList.add("hidden");

    const fields = ["name", "email", "message"];
    let firstInvalidInput = null;
    for (const f of fields) {
      const ok = validateSingleField(f);
      if (!ok && !firstInvalidInput) {
        firstInvalidInput = document.getElementById(
          f === "name" ? "contactName" : f === "email" ? "contactEmail" : "contactMessage"
        );
      }
    }

    if (firstInvalidInput) {
      document.getElementById("contactOutputPanel").classList.add("hidden");
      document.getElementById("contactCopyBtn").classList.add("hidden");
      firstInvalidInput.focus();
      return;
    }

    const submitBtn = document.getElementById("contactSubmitBtn");
    const live = document.getElementById("copyStatusLive");
    const payload = {
      name: document.getElementById("contactName").value.trim(),
      email: document.getElementById("contactEmail").value.trim(),
      message: document.getElementById("contactMessage").value.trim(),
      comparedProjectIds: state.compareIds.slice(),
      planSnapshot: cloneEstimator(state.estimator)
    };

    submitInFlight = true;
    submitBtn.disabled = true;
    submitBtn.setAttribute("aria-busy", "true");
    submitBtn.textContent = "正在提交校验…";
    live.textContent = "";

    async function attemptOnce(isAutoRetry) {
      try {
        const res = await API.submitInquiry(payload);
        svcBanner.classList.add("hidden");

        const receiptArea = document.getElementById("contactReceiptArea");
        receiptArea.value = res.formattedSummary || "";
        document.getElementById("contactOutputPanel").classList.remove("hidden");

        const copyBtn = document.getElementById("contactCopyBtn");
        copyBtn.textContent = "复制回执全文";
        copyBtn.classList.remove("hidden");
        live.textContent = isAutoRetry
          ? `瞬时拥塞已自动恢复，回执单 ${res.inquiryId} 已生成。`
          : `回执单 ${res.inquiryId} 已生成，可一键复制全文。`;
      } catch (err) {
        if (!isAutoRetry && err && (err.retryable || err.code === "SERVICE_BUSY")) {
          svcBannerText.textContent = "网关瞬时繁忙（503），已保护您的填写内容，正在自动退避重试…";
          svcBanner.classList.remove("hidden");
          submitBtn.textContent = "瞬时繁忙重试中…";
          await new Promise((r) => setTimeout(r, 65));
          return attemptOnce(true);
        }

        if (err && err.code === "SCHEDULE_CONFLICT") {
          svcBannerText.textContent = err.message || "所选启动周存在繁忙冲突，请先在上方规划台顺延至空闲周后再提交。";
          svcBanner.classList.remove("hidden");
          return;
        }

        if (err && err.code === "VALIDATION_ERROR" && err.field) {
          renderFieldError(err.field, err.message);
          return;
        }

        svcBannerText.textContent = (err && err.message) || "服务暂时繁忙，您填写的内容已完整保留，可点击右侧按钮重试。";
        svcBanner.classList.remove("hidden");
      }
    }

    try {
      await attemptOnce(false);
    } finally {
      submitInFlight = false;
      submitBtn.disabled = false;
      submitBtn.removeAttribute("aria-busy");
      submitBtn.textContent = "提交咨询并生成回执";
    }
  }

  async function handleCopyReceipt() {
    const outArea = document.getElementById("contactReceiptArea");
    const copyBtn = document.getElementById("contactCopyBtn");
    const live = document.getElementById("copyStatusLive");
    const text = outArea.value || "";
    if (!text) return;

    // 先在 16ms 内给出即时确定性视觉反馈，兼容无系统剪贴板权限的受限沙盒环境
    copyBtn.textContent = "✓ 已复制回执";
    live.textContent = "回执单已复制到剪贴板，可直接粘贴发送。";

    let copiedOk = false;
    try {
      if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
        await navigator.clipboard.writeText(text);
        copiedOk = true;
      }
    } catch (_err) {
      copiedOk = false;
    }

    if (!copiedOk) {
      try {
        outArea.focus();
        outArea.select();
        copiedOk = Boolean(document.execCommand && document.execCommand("copy"));
      } catch (_err2) {
        copiedOk = false;
      }
    }

    if (!copiedOk) {
      outArea.focus();
      outArea.select();
      copyBtn.textContent = "已全选回执（请按 Ctrl+C）";
      live.textContent = "当前环境限制自动写入剪贴板，已自动选中全文，请按 Ctrl+C（或 Cmd+C）复制。";
    }
  }

  /* ==================== 12. 事件委托、IME 拼字防抖与双向焦点锁 ==================== */
  function bindEvents() {
    document.getElementById("themeToggleBtn").addEventListener("click", () => {
      applyTheme(state.theme === "dark" ? "light" : "dark", true);
    });

    const searchInput = document.getElementById("searchInput");
    let searchTimer = null;

    searchInput.addEventListener("compositionstart", () => {
      state.isComposing = true;
    });

    searchInput.addEventListener("compositionend", () => {
      state.isComposing = false;
      state.searchQuery = searchInput.value;
      runCatalogQuery();
    });

    searchInput.addEventListener("input", (e) => {
      if (state.isComposing) return;
      state.searchQuery = searchInput.value;
      if (searchTimer) clearTimeout(searchTimer);
      if (e && e.isTrusted) {
        searchTimer = setTimeout(() => {
          runCatalogQuery();
        }, UI_CONFIG.searchDebounceMs);
      } else {
        runCatalogQuery();
      }
    });

    document.getElementById("clearSearchBtn").addEventListener("click", () => {
      searchInput.value = "";
      state.searchQuery = "";
      runCatalogQuery();
      searchInput.focus();
    });

    document.getElementById("favFilterBtn").addEventListener("click", () => {
      state.onlyFavorites = !state.onlyFavorites;
      runCatalogQuery();
    });

    document.getElementById("sortControl").addEventListener("change", (e) => {
      state.sortBy = e.target.value;
      runCatalogQuery();
    });

    document.addEventListener("click", (e) => {
      const catBtn = e.target.closest("[data-testid='category-option']");
      if (catBtn) {
        state.activeCategory = catBtn.getAttribute("data-category") || "all";
        runCatalogQuery();
        return;
      }

      const projOpenBtn = e.target.closest("[data-testid='project-open']");
      if (projOpenBtn) {
        navigateToItem("project", projOpenBtn.getAttribute("data-project-id"), projOpenBtn);
        return;
      }

      const artOpenBtn = e.target.closest("[data-testid='article-open']");
      if (artOpenBtn) {
        navigateToItem("article", artOpenBtn.getAttribute("data-article-id"), artOpenBtn);
        return;
      }

      const favBtn = e.target.closest("[data-testid='favorite-btn']");
      if (favBtn) {
        toggleFavorite(favBtn.getAttribute("data-fav-id"));
        return;
      }

      const cmpBtn = e.target.closest("[data-testid='compare-toggle']");
      if (cmpBtn) {
        toggleCompare(cmpBtn.getAttribute("data-compare-id"));
        return;
      }

      const rmCmpBtn = e.target.closest("[data-remove-cmp]");
      if (rmCmpBtn) {
        toggleCompare(rmCmpBtn.getAttribute("data-remove-cmp"));
        return;
      }

      const recentBtn = e.target.closest("[data-recent-id]");
      if (recentBtn) {
        navigateToItem(recentBtn.getAttribute("data-recent-kind"), recentBtn.getAttribute("data-recent-id"), recentBtn);
        return;
      }

      const emptyAct = e.target.closest("[data-empty-act]");
      if (emptyAct) {
        const act = emptyAct.getAttribute("data-empty-act");
        if (act === "exit-fav") {
          state.onlyFavorites = false;
        } else if (act === "clear-query") {
          state.searchQuery = "";
          searchInput.value = "";
        } else if (act === "reset-filters") {
          state.activeCategory = "all";
          state.onlyFavorites = false;
        } else {
          state.searchQuery = "";
          searchInput.value = "";
          state.activeCategory = "all";
          state.onlyFavorites = false;
        }
        runCatalogQuery();
        return;
      }

      const emptyKw = e.target.closest("[data-empty-kw]");
      if (emptyKw) {
        const kw = emptyKw.getAttribute("data-empty-kw") || "";
        state.activeCategory = "all";
        state.onlyFavorites = false;
        state.searchQuery = kw;
        searchInput.value = kw;
        runCatalogQuery();
        return;
      }

      const estType = e.target.closest("[data-testid='est-type']");
      if (estType) {
        const nextMode = estType.getAttribute("data-mode-id") || state.defaultPlan.modeId;
        if (nextMode !== state.estimator.modeId) {
          pushHistoryBeforeMutation();
          state.estimator.modeId = nextMode;
          saveEstimatorState();
          renderEstimatorControls();
          runPlanEvaluation();
        }
        return;
      }

      const estAddon = e.target.closest("[data-testid='est-addon']");
      if (estAddon) {
        const aid = estAddon.getAttribute("data-addon-id");
        if (aid) {
          pushHistoryBeforeMutation();
          const i = state.estimator.addonIds.indexOf(aid);
          if (i >= 0) state.estimator.addonIds.splice(i, 1);
          else state.estimator.addonIds.push(aid);
          saveEstimatorState();
          renderEstimatorControls();
          runPlanEvaluation();
        }
        return;
      }

      const estScale = e.target.closest("#estScaleGroup [data-scale]");
      if (estScale) {
        const nextScale = estScale.getAttribute("data-scale") || state.defaultPlan.scaleId;
        if (nextScale !== state.estimator.scaleId) {
          pushHistoryBeforeMutation();
          state.estimator.scaleId = nextScale;
          saveEstimatorState();
          renderEstimatorControls();
          runPlanEvaluation();
        }
        return;
      }

      const estWeek = e.target.closest("#estStartWeekGroup [data-week]");
      if (estWeek) {
        const nextWeek = estWeek.getAttribute("data-week") || state.defaultPlan.startWeek;
        if (nextWeek !== state.estimator.startWeek && validSets.startWeeks.has(nextWeek)) {
          pushHistoryBeforeMutation();
          state.estimator.startWeek = nextWeek;
          saveEstimatorState();
          renderEstimatorControls();
          runPlanEvaluation();
        }
        return;
      }

      const tocLink = e.target.closest("#articleTocList [data-toc-target]");
      if (tocLink) {
        const hid = tocLink.getAttribute("data-toc-target");
        const headingEl = hid ? document.getElementById(hid) : null;
        if (headingEl) {
          const offset = getStickyHeaderBottom() + 22;
          const y = (window.scrollY || window.pageYOffset || 0) + headingEl.getBoundingClientRect().top - offset;
          window.scrollTo(0, Math.max(0, y));
          updateScrollProgressAndToc();
        }
        return;
      }
    });

    document.getElementById("estResetBtn").addEventListener("click", () => {
      const def = getDefaultEstimatorState();
      if (JSON.stringify(state.estimator) !== JSON.stringify(def)) {
        pushHistoryBeforeMutation();
        state.estimator = def;
        saveEstimatorState();
      }
      document.getElementById("estHandoffFeedback").textContent = "";
      renderEstimatorControls();
      runPlanEvaluation();
    });

    document.getElementById("plannerShiftFreeWeekBtn").addEventListener("click", resolveScheduleConflict);
    document.getElementById("estApplyBtn").addEventListener("click", applyEstimatorToContact);
    document.getElementById("workbenchUndoBtn").addEventListener("click", performUndo);
    document.getElementById("workbenchRedoBtn").addEventListener("click", performRedo);

    document.getElementById("compareOpenBtn").addEventListener("click", (e) => openCompareModal(e.currentTarget));
    document.getElementById("compareClearBtn").addEventListener("click", clearCompareAll);
    document.getElementById("compareCloseBtn").addEventListener("click", closeCompareModal);
    document.getElementById("compareApplyContactBtn").addEventListener("click", applyComparedProjectsToContact);
    document.getElementById("compareBackdrop").addEventListener("click", (e) => {
      if (e.target === e.currentTarget) closeCompareModal();
    });

    document.getElementById("detailBackBtn").addEventListener("click", navigateBackToHome);
    document.getElementById("brandHomeLink").addEventListener("click", (e) => {
      if (state.route.view !== "home") {
        e.preventDefault();
        navigateBackToHome();
      }
    });

    document.getElementById("articlePrevBtn").addEventListener("click", (e) => {
      const tid = e.currentTarget.getAttribute("data-target-art");
      if (tid) window.location.hash = `#article/${encodeURIComponent(tid)}`;
    });
    document.getElementById("articleNextBtn").addEventListener("click", (e) => {
      const tid = e.currentTarget.getAttribute("data-target-art");
      if (tid) window.location.hash = `#article/${encodeURIComponent(tid)}`;
    });

    ["contactName", "contactEmail", "contactMessage"].forEach((id) => {
      const fieldKey = id === "contactName" ? "name" : id === "contactEmail" ? "email" : "message";
      document.getElementById(id).addEventListener("input", () => {
        updateCharCounterAndSaveDraft();
        if (state.formSubmittedOnce || document.getElementById(id).getAttribute("aria-invalid") === "true") {
          validateSingleField(fieldKey);
        }
      });
    });

    document.getElementById("contactSubmitBtn").addEventListener("click", handleSubmitInquiry);
    document.getElementById("contactRetryNowBtn").addEventListener("click", handleSubmitInquiry);
    document.getElementById("contactCopyBtn").addEventListener("click", handleCopyReceipt);
    document.getElementById("contactClearDraftBtn").addEventListener("click", () => {
      document.getElementById("contactName").value = "";
      document.getElementById("contactEmail").value = "";
      document.getElementById("contactMessage").value = "";
      state.formSubmittedOnce = false;
      ["name", "email", "message"].forEach((f) => renderFieldError(f, ""));
      document.getElementById("contactServiceBanner").classList.add("hidden");
      document.getElementById("contactOutputPanel").classList.add("hidden");
      document.getElementById("contactCopyBtn").classList.add("hidden");
      document.getElementById("copyStatusLive").textContent = "";
      safeRemoveRaw(STORAGE_KEYS.draft);
      updateCharCounterOnly();
    });

    document.addEventListener("keydown", (e) => {
      const backdrop = document.getElementById("compareBackdrop");
      const modalOpen = backdrop && !backdrop.classList.contains("hidden");

      if (modalOpen) {
        if (e.key === "Escape") {
          e.preventDefault();
          closeCompareModal();
          return;
        }
        if (e.key === "Tab") {
          const panel = document.getElementById("comparePanel");
          const focusables = Array.from(
            panel.querySelectorAll("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])")
          ).filter((el) => !el.disabled && el.offsetParent !== null);

          if (!focusables.length) {
            e.preventDefault();
            return;
          }
          const first = focusables[0];
          const last = focusables[focusables.length - 1];
          const cur = document.activeElement;

          if (e.shiftKey) {
            if (cur === first || !panel.contains(cur)) {
              e.preventDefault();
              last.focus();
            }
          } else {
            if (cur === last || !panel.contains(cur)) {
              e.preventDefault();
              first.focus();
            }
          }
        }
        return;
      }

      if (e.key === "Escape" && state.route.view !== "home") {
        e.preventDefault();
        navigateBackToHome();
        return;
      }

      if ((e.ctrlKey || e.metaKey) && !e.altKey) {
        const tgt = e.target || document.activeElement;
        const tag = tgt && tgt.tagName ? tgt.tagName.toUpperCase() : "";
        const isEditable =
          tag === "INPUT" ||
          tag === "TEXTAREA" ||
          tag === "SELECT" ||
          Boolean(tgt && tgt.isContentEditable);
        if (isEditable) {
          return;
        }
        const keyLower = (e.key || "").toLowerCase();
        if (keyLower === "z" && !e.shiftKey) {
          e.preventDefault();
          performUndo();
          return;
        }
        if (keyLower === "y" || (keyLower === "z" && e.shiftKey)) {
          e.preventDefault();
          performRedo();
        }
      }
    });

    window.addEventListener("hashchange", syncRouteFromHash);
  }

  /* ==================== 13. 异步首屏引导流水线 ==================== */
  async function bootstrap() {
    applyTheme(resolveInitialTheme(), false);
    hydrateContactDraft();
    renderRecentTray();
    bindEvents();

    if (!API || typeof API.getBootstrap !== "function") return;

    try {
      const boot = await API.getBootstrap();
      state.bootstrapped = true;
      state.profile = boot.profile || {};
      state.categories = boot.categories || state.categories;
      state.sortOptions = boot.sortOptions || state.sortOptions;
      state.defaultPlan = boot.defaultPlan || state.defaultPlan;
      state.plannerCatalog = boot.plannerCatalog || state.plannerCatalog;

      (state.plannerCatalog.modes || []).forEach((m) => validSets.modes.add(m.id));
      (state.plannerCatalog.addons || []).forEach((a) => validSets.addons.add(a.id));
      (state.plannerCatalog.scales || []).forEach((s) => validSets.scales.add(s.id));
      (state.plannerCatalog.calendarWeeks || [])
        .filter((w) => w.selectableAsStart)
        .forEach((w) => validSets.startWeeks.add(w.week));

      state.favorites = readSafeStringArray(STORAGE_KEYS.favorites, null, 50);
      state.compareIds = readSafeStringArray(STORAGE_KEYS.compare, null, UI_CONFIG.maxCompare);
      state.estimator = readValidatedEstimatorFromStorage();

      renderProfileAndToolbar();
      renderEstimatorControls();
      syncHistoryButtons();

      await Promise.all([runCatalogQuery(), runPlanEvaluation()]);
      renderCompareBar();
      syncRouteFromHash();
    } catch (_err) {
      const statusEl = document.getElementById("filterStatusBar");
      if (statusEl) statusEl.textContent = "本地顾问模拟服务初始化异常，请刷新页面重试。";
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootstrap);
  } else {
    bootstrap();
  }
})();
