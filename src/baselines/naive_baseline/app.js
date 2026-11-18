(function () {
  var api = window.LincheMockAPI;

  // 典型弱模型缺陷：直接读取并信任 JSON 类型，遇到异构脏数据或禁用存储时直接抛错崩溃
  var favs = JSON.parse(localStorage.getItem("naive_favs") || "[]");
  var draft = JSON.parse(localStorage.getItem("naive_draft") || "{}");
  var savedTheme = localStorage.getItem("naive_theme") || "light";
  document.documentElement.setAttribute("data-theme", savedTheme);

  var currentCat = "all";
  var onlyFav = false;
  var currentQuery = "";
  var sortMode = "featured";
  var compared = [];
  var cachedProjects = [];
  var planCfg = { modeId: "diag", addonIds: [], scaleId: "standard", startWeek: "2026-W49" };
  var defaultPlan = { modeId: "diag", addonIds: [], scaleId: "standard", startWeek: "2026-W49" };
  var prevArtId = "";
  var nextArtId = "";

  var cName = document.getElementById("cName");
  var cEmail = document.getElementById("cEmail");
  var cMsg = document.getElementById("cMsg");
  if (draft.name) cName.value = draft.name;
  if (draft.email) cEmail.value = draft.email;
  if (draft.msg) cMsg.value = draft.msg;

  function saveDraft() {
    localStorage.setItem("naive_draft", JSON.stringify({ name: cName.value, email: cEmail.value, msg: cMsg.value }));
  }
  cName.oninput = saveDraft;
  cEmail.oninput = saveDraft;
  cMsg.oninput = saveDraft;

  document.getElementById("themeBtn").onclick = function () {
    var next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("naive_theme", next);
  };

  function updateCompareBar() {
    var bar = document.getElementById("compareBar");
    document.getElementById("compareCount").textContent = "已选 " + compared.length + " 项";
    if (compared.length > 0) bar.classList.remove("hidden");
    else bar.classList.add("hidden");
  }

  // 典型弱模型缺陷：无 AbortController 或请求序号锁，慢速旧请求晚到时直接覆盖新结果！
  function reloadCatalog() {
    api.queryCatalog({
      query: currentQuery,
      category: currentCat,
      sortBy: sortMode,
      favoritesOnly: onlyFav,
      favoriteIds: favs
    }).then(function (res) {
      cachedProjects = res.projects || [];
      var pList = document.getElementById("projectList");
      var aList = document.getElementById("articleList");
      pList.innerHTML = "";
      aList.innerHTML = "";

      (res.projects || []).forEach(function (p) {
        var isFav = favs.indexOf(p.id) >= 0;
        var isCmp = compared.indexOf(p.id) >= 0;
        var div = document.createElement("div");
        div.className = "card";
        div.setAttribute("data-testid", "project-card");
        div.setAttribute("data-id", p.id);
        div.innerHTML =
          "<h3>" + p.title + "</h3><p>" + p.summary + "</p>" +
          "<button type='button' data-testid='project-open'>查看详情</button> " +
          "<button type='button' data-testid='favorite-btn' aria-pressed='" + (isFav ? "true" : "false") + "'>" + (isFav ? "已收藏" : "收藏") + "</button> " +
          "<button type='button' data-testid='compare-toggle' aria-pressed='" + (isCmp ? "true" : "false") + "'>对比</button>";
        div.querySelector("[data-testid='project-open']").onclick = function () { openProject(p.id); };
        div.querySelector("[data-testid='favorite-btn']").onclick = function () {
          var i = favs.indexOf(p.id);
          if (i >= 0) favs.splice(i, 1); else favs.push(p.id);
          localStorage.setItem("naive_favs", JSON.stringify(favs));
          reloadCatalog();
        };
        div.querySelector("[data-testid='compare-toggle']").onclick = function () {
          var ci = compared.indexOf(p.id);
          if (ci >= 0) compared.splice(ci, 1); else compared.push(p.id);
          updateCompareBar();
          reloadCatalog();
        };
        pList.appendChild(div);
      });

      var arts = onlyFav ? [] : (res.articles || []);
      arts.forEach(function (a) {
        var div = document.createElement("div");
        div.className = "card";
        div.setAttribute("data-testid", "article-card");
        div.setAttribute("data-id", a.id);
        div.innerHTML = "<h3>" + a.title + "</h3><p>" + a.summary + "</p><button type='button' data-testid='article-open'>阅读全文</button>";
        div.querySelector("[data-testid='article-open']").onclick = function () { openArticle(a.id); };
        aList.appendChild(div);
      });

      var emp = document.getElementById("emptyState");
      if ((res.projects || []).length === 0 && arts.length === 0) emp.classList.remove("hidden");
      else emp.classList.add("hidden");
    });
  }

  // 典型弱模型缺陷：evaluatePlan 无请求时序保护，多选模块慢请求会覆盖随后的重置结果
  function refreshEstimate() {
    api.evaluatePlan(planCfg).then(function (res) {
      document.getElementById("estResult").textContent =
        "预计 " + res.totalWeeks + " 周，参考预算 " + res.budgetMinK + "k-" + res.budgetMaxK + "k";
      document.getElementById("estMilestones").innerHTML = (res.milestones || []).map(function (m) {
        return "<div>" + m.phase + "：" + m.title + "（" + m.weekRangeLabel + "）</div>";
      }).join("");
      document.getElementById("estWarn").textContent = res.conflict && res.conflict.hasConflict ? res.conflict.message : "";
    });
  }

  function openProject(id) {
    api.getDetail({ type: "project", id: id }).then(function (res) {
      var p = res.item;
      document.getElementById("listView").classList.add("hidden");
      document.getElementById("detailView").classList.remove("hidden");
      document.getElementById("articleToc").classList.add("hidden");
      document.getElementById("articleNav").classList.add("hidden");
      document.getElementById("detailTitle").textContent = p.title;
      document.getElementById("detailBody").textContent = (p.detailParagraphs || []).join("\n\n");
      window.scrollTo(0, 0);
    });
  }

  // 典型弱模型缺陷：快速切换文章时无取消或序号保护，前一篇慢文章晚到时覆盖后一篇
  function openArticle(id) {
    api.getDetail({ type: "article", id: id }).then(function (res) {
      var a = res.item;
      prevArtId = a.prevArticle ? a.prevArticle.id : "";
      nextArtId = a.nextArticle ? a.nextArticle.id : "";
      document.getElementById("listView").classList.add("hidden");
      document.getElementById("detailView").classList.remove("hidden");
      document.getElementById("articleToc").classList.remove("hidden");
      document.getElementById("articleNav").classList.remove("hidden");
      document.getElementById("detailTitle").textContent = a.title;
      document.getElementById("detailBody").innerHTML = a.bodyHtml;
      var toc = document.getElementById("articleToc");
      toc.innerHTML = "";
      (a.toc || []).forEach(function (t) {
        var link = document.createElement("a");
        link.href = "#" + t.id;
        link.textContent = t.title;
        link.style.marginRight = "8px";
        toc.appendChild(link);
      });
      window.scrollTo(0, 0);
    });
  }

  document.getElementById("detailBack").onclick = function () {
    document.getElementById("detailView").classList.add("hidden");
    document.getElementById("listView").classList.remove("hidden");
    window.scrollTo(0, 0);
  };
  document.getElementById("artPrev").onclick = function () {
    if (prevArtId) openArticle(prevArtId);
  };
  document.getElementById("artNext").onclick = function () {
    if (nextArtId) openArticle(nextArtId);
  };

  document.getElementById("compareOpen").onclick = function () {
    var box = document.getElementById("compareBody");
    box.innerHTML = compared.map(function (id) {
      var p = cachedProjects.filter(function (x) { return x.id === id; })[0];
      return p ? "<div><strong>" + p.title + "</strong>：" + p.summary + "</div>" : "";
    }).join("");
    document.getElementById("comparePanel").classList.remove("hidden");
  };
  document.getElementById("compareClose").onclick = function () {
    document.getElementById("comparePanel").classList.add("hidden");
  };
  document.getElementById("compareClear").onclick = function () {
    compared = [];
    document.getElementById("comparePanel").classList.add("hidden");
    updateCompareBar();
    reloadCatalog();
  };

  document.getElementById("searchInput").oninput = function (e) {
    currentQuery = e.target.value;
    reloadCatalog();
  };
  document.getElementById("sortSelect").onchange = function (e) {
    sortMode = e.target.value;
    reloadCatalog();
  };
  document.getElementById("favFilter").onclick = function () {
    onlyFav = !onlyFav;
    this.setAttribute("aria-pressed", onlyFav ? "true" : "false");
    reloadCatalog();
  };

  document.getElementById("estReset").onclick = function () {
    planCfg = {
      modeId: defaultPlan.modeId,
      addonIds: [],
      scaleId: defaultPlan.scaleId,
      startWeek: defaultPlan.startWeek
    };
    document.getElementById("estScale").value = planCfg.scaleId;
    document.getElementById("estStartWeek").value = planCfg.startWeek;
    Array.from(document.querySelectorAll("[data-testid='est-type']")).forEach(function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-id") === planCfg.modeId ? "true" : "false");
    });
    Array.from(document.querySelectorAll("[data-testid='est-addon']")).forEach(function (b) {
      b.setAttribute("aria-pressed", "false");
    });
    refreshEstimate();
  };

  document.getElementById("estApply").onclick = function () {
    // 典型弱模型缺陷：粗暴覆盖访客已填留言
    cMsg.value = "意向方案：" + document.getElementById("estResult").textContent;
  };

  // 典型弱模型缺陷：提交无防并发重入锁，且遇到 503 异常时未保留优雅重试体验
  document.getElementById("cSub").onclick = function () {
    var err = document.getElementById("cErr");
    api.submitInquiry({
      name: cName.value,
      email: cEmail.value,
      message: cMsg.value,
      comparedProjectIds: compared,
      planSnapshot: planCfg
    }).then(function (res) {
      err.classList.add("hidden");
      document.getElementById("cOut").textContent = res.formattedSummary;
    }).catch(function (e) {
      err.textContent = e && e.message ? e.message : "提交失败";
      err.classList.remove("hidden");
    });
  };

  document.getElementById("cCopy").onclick = function () {
    var txt = document.getElementById("cOut").textContent;
    if (navigator.clipboard && txt) navigator.clipboard.writeText(txt);
  };

  api.getBootstrap().then(function (boot) {
    var prof = boot.profile || {};
    document.getElementById("heroName").textContent = (prof.name || "林澈") + " · " + (prof.title || "");
    document.getElementById("heroBio").textContent = prof.bio || "";
    document.getElementById("demoNotice").textContent = prof.demoNotice || "";
    document.getElementById("contactMail").textContent = "联系邮箱：" + (prof.contactEmail || "linche@example.com") + "（演示邮箱）";

    defaultPlan = boot.defaultPlan || defaultPlan;
    planCfg = {
      modeId: defaultPlan.modeId,
      addonIds: (defaultPlan.addonIds || []).slice(),
      scaleId: defaultPlan.scaleId,
      startWeek: defaultPlan.startWeek
    };

    var sortSel = document.getElementById("sortSelect");
    sortSel.innerHTML = (boot.sortOptions || []).map(function (s) {
      return "<option value='" + s.id + "'>" + s.label + "</option>";
    }).join("");

    var catBox = document.getElementById("catBox");
    catBox.innerHTML = (boot.categories || []).map(function (c) {
      var act = c.id === "all" ? "true" : "false";
      return "<button type='button' data-testid='category-option' data-category='" + c.id + "' aria-pressed='" + act + "'>" + c.label + "</button>";
    }).join(" ");
    Array.from(catBox.querySelectorAll("[data-testid='category-option']")).forEach(function (btn) {
      btn.onclick = function () {
        currentCat = btn.getAttribute("data-category");
        Array.from(catBox.querySelectorAll("[data-testid='category-option']")).forEach(function (b) {
          b.setAttribute("aria-pressed", b === btn ? "true" : "false");
        });
        reloadCatalog();
      };
    });

    var pcat = boot.plannerCatalog || {};
    var modesEl = document.getElementById("estModes");
    modesEl.innerHTML = (pcat.modes || []).map(function (m) {
      var on = m.id === planCfg.modeId ? "true" : "false";
      return "<button type='button' data-testid='est-type' data-id='" + m.id + "' aria-pressed='" + on + "'>" + m.label + "</button>";
    }).join(" ");
    Array.from(modesEl.querySelectorAll("[data-testid='est-type']")).forEach(function (btn) {
      btn.onclick = function () {
        planCfg.modeId = btn.getAttribute("data-id");
        Array.from(modesEl.querySelectorAll("[data-testid='est-type']")).forEach(function (b) {
          b.setAttribute("aria-pressed", b === btn ? "true" : "false");
        });
        refreshEstimate();
      };
    });

    var addonsEl = document.getElementById("estAddons");
    addonsEl.innerHTML = (pcat.addons || []).map(function (a) {
      return "<button type='button' data-testid='est-addon' data-id='" + a.id + "' aria-pressed='false'>" + a.label + "</button>";
    }).join(" ");
    Array.from(addonsEl.querySelectorAll("[data-testid='est-addon']")).forEach(function (btn) {
      btn.onclick = function () {
        var id = btn.getAttribute("data-id");
        var idx = planCfg.addonIds.indexOf(id);
        if (idx >= 0) planCfg.addonIds.splice(idx, 1); else planCfg.addonIds.push(id);
        btn.setAttribute("aria-pressed", idx >= 0 ? "false" : "true");
        refreshEstimate();
      };
    });

    var scEl = document.getElementById("estScale");
    scEl.innerHTML = (pcat.scales || []).map(function (s) {
      return "<option value='" + s.id + "'>" + s.label + "</option>";
    }).join("");
    scEl.value = planCfg.scaleId;
    scEl.onchange = function () {
      planCfg.scaleId = scEl.value;
      refreshEstimate();
    };

    var wkEl = document.getElementById("estStartWeek");
    wkEl.innerHTML = (pcat.calendarWeeks || []).filter(function (w) { return w.selectableAsStart; }).map(function (w) {
      return "<option value='" + w.week + "'>" + w.label + "</option>";
    }).join("");
    wkEl.value = planCfg.startWeek;
    wkEl.onchange = function () {
      planCfg.startWeek = wkEl.value;
      refreshEstimate();
    };

    reloadCatalog();
    refreshEstimate();
  });
})();
