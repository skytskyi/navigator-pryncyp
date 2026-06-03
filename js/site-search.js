(function () {
  var INDEX_URL = "/data/search-index.json?v=1";
  var EXCERPT_RADIUS = 90;

  var SEARCH_TABS = [
    { key: "all", label: "Всі результати" },
    { key: "Військові", label: "Військові" },
    { key: "Поранені", label: "Поранені" },
    { key: "Ветерани", label: "Ветерани" },
    { key: "Звільнені з полону", label: "Звільнені з полону" },
    { key: "Родини військових та ветеранів", label: "Родини військових та ветеранів" },
  ];

  var indexPromise = null;
  var searchState = {
    query: "",
    results: [],
    activeTab: "all",
  };

  function normalizePath(pathname) {
    var path = pathname || "/";
    if (typeof stripSiteBasePath === "function") {
      path = stripSiteBasePath(path);
    }
    if (path.endsWith("/index.html")) {
      path = path.slice(0, -"/index.html".length) || "/";
    }
    if (path.endsWith(".html")) {
      path = path.slice(0, -".html".length);
    }
    if (path !== "/" && !path.endsWith("/")) {
      path += "/";
    }
    return path;
  }

  function isSearchPage() {
    return normalizePath(window.location.pathname) === "/search/";
  }

  function getQueryParam() {
    return (new URLSearchParams(window.location.search).get("q") || "").trim();
  }

  function normalizeText(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/\u2019/g, "'")
      .replace(/ё/g, "е")
      .replace(/\s+/g, " ")
      .trim();
  }

  function tokenize(value) {
    var normalized = normalizeText(value);
    if (!normalized) {
      return [];
    }
    return normalized
      .split(/[^0-9a-z\u0430-\u044f\u0454\u0456\u0457\u0491]+/i)
      .filter(function (token) {
        return token.length > 1;
      });
  }

  function indexUrl() {
    return typeof siteUrl === "function" ? siteUrl(INDEX_URL) : INDEX_URL;
  }

  function searchPageUrl() {
    return typeof siteUrl === "function" ? siteUrl("/search/") : "/search/";
  }

  function loadIndex() {
    if (!indexPromise) {
      indexPromise = fetch(indexUrl())
        .then(function (response) {
          if (!response.ok) {
            throw new Error("search index fetch failed");
          }
          return response.json();
        })
        .then(function (data) {
          return data.documents || [];
        });
    }
    return indexPromise;
  }

  function scoreDocument(doc, tokens) {
    var title = normalizeText(doc.title);
    var text = normalizeText(doc.text);
    var score = 0;
    var matched = 0;

    tokens.forEach(function (token) {
      var inTitle = title.indexOf(token) !== -1;
      var inText = text.indexOf(token) !== -1;
      if (inTitle) {
        score += 12;
        matched += 1;
      } else if (inText) {
        score += 3;
        matched += 1;
      }
    });

    if (!matched) {
      return 0;
    }

    if (matched === tokens.length) {
      score += 4;
    }

    return score;
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function highlightExcerpt(text, tokens) {
    var source = text || "";
    var lower = normalizeText(source);
    var matchIndex = -1;
    var matchToken = "";

    for (var i = 0; i < tokens.length; i++) {
      var idx = lower.indexOf(tokens[i]);
      if (idx !== -1 && (matchIndex === -1 || idx < matchIndex)) {
        matchIndex = idx;
        matchToken = tokens[i];
      }
    }

    if (matchIndex === -1) {
      var snippet = source.slice(0, EXCERPT_RADIUS * 2);
      if (source.length > snippet.length) {
        snippet += "…";
      }
      return escapeHtml(snippet);
    }

    var start = Math.max(0, matchIndex - EXCERPT_RADIUS);
    var end = Math.min(source.length, matchIndex + matchToken.length + EXCERPT_RADIUS);
    var excerpt = source.slice(start, end);
    if (start > 0) {
      excerpt = "…" + excerpt;
    }
    if (end < source.length) {
      excerpt += "…";
    }

    var pattern = new RegExp("(" + matchToken.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "gi");
    return escapeHtml(excerpt).replace(pattern, "<mark>$1</mark>");
  }

  function searchDocuments(documents, query) {
    var tokens = tokenize(query);
    if (!tokens.length) {
      return [];
    }

    return documents
      .map(function (doc) {
        return {
          doc: doc,
          score: scoreDocument(doc, tokens),
          excerpt: highlightExcerpt(doc.text, tokens),
        };
      })
      .filter(function (item) {
        return item.score > 0;
      })
      .sort(function (a, b) {
        return b.score - a.score || a.doc.title.localeCompare(b.doc.title, "uk");
      });
  }

  function getSearchUi() {
    var page = document.querySelector(".site-search-page");
    var container =
      document.querySelector("[data-site-search-results]") ||
      (page ? page.querySelector(".site-search-page__results") : null);
    if (!container) {
      return null;
    }

    var meta =
      document.querySelector("[data-site-search-meta]") ||
      (page ? page.querySelector(".site-search-page__meta") : null);
    if (!meta && page) {
      meta = document.createElement("p");
      meta.className = "site-search-page__meta is-hidden";
      meta.setAttribute("data-site-search-meta", "");
      container.insertAdjacentElement("beforebegin", meta);
    }

    var tabs =
      document.querySelector("[data-site-search-tabs]") ||
      (page ? page.querySelector("[data-site-search-tabs]") : null);
    if (!tabs && page) {
      tabs = document.createElement("div");
      tabs.className = "site-search-page__tabs is-hidden";
      tabs.setAttribute("data-site-search-tabs", "");
      tabs.setAttribute("role", "tablist");
      tabs.setAttribute("aria-label", "Фільтр результатів пошуку");
      container.insertAdjacentElement("beforebegin", tabs);
    }

    return { meta: meta, tabs: tabs, container: container };
  }

  function setMetaVisible(meta, visible) {
    if (!meta) {
      return;
    }
    meta.hidden = !visible;
    meta.classList.toggle("is-hidden", !visible);
  }

  function setTabsVisible(tabs, visible) {
    if (!tabs) {
      return;
    }
    tabs.hidden = !visible;
    tabs.classList.toggle("is-hidden", !visible);
  }

  function formatCountLabel(count) {
    if (count === 1) {
      return "1 результат";
    }
    if (count > 1 && count < 5) {
      return count + " результати";
    }
    return count + " результатів";
  }

  function countResultsByTab(results) {
    var counts = { all: results.length };
    SEARCH_TABS.forEach(function (tab) {
      if (tab.key !== "all") {
        counts[tab.key] = 0;
      }
    });
    results.forEach(function (item) {
      var category = item.doc.category;
      if (category && counts[category] !== undefined) {
        counts[category] += 1;
      }
    });
    return counts;
  }

  function filterResultsByTab(results, tabKey) {
    if (tabKey === "all") {
      return results;
    }
    return results.filter(function (item) {
      return item.doc.category === tabKey;
    });
  }

  function resolveActiveTab(counts, preferredTab) {
    if (preferredTab && (counts[preferredTab] || 0) > 0) {
      return preferredTab;
    }
    return "all";
  }

  function getTabLabel(tabKey) {
    for (var i = 0; i < SEARCH_TABS.length; i++) {
      if (SEARCH_TABS[i].key === tabKey) {
        return SEARCH_TABS[i].label;
      }
    }
    return tabKey;
  }

  function renderResultCards(container, results) {
    container.innerHTML = "";
    results.forEach(function (item) {
      var link = document.createElement("a");
      link.className = "site-search-result";
      link.href =
        typeof siteUrl === "function" ? siteUrl(item.doc.url) : item.doc.url;
      link.innerHTML =
        '<h2 class="site-search-result__title">' +
        escapeHtml(item.doc.title) +
        "</h2>" +
        (item.doc.category
          ? '<span class="site-search-result__badge">' + escapeHtml(item.doc.category) + "</span>"
          : "") +
        '<p class="site-search-result__excerpt">' +
        item.excerpt +
        "</p>";
      container.appendChild(link);
    });
  }

  function renderTabs(ui, counts) {
    var tabs = ui.tabs;
    if (!tabs) {
      return;
    }

    tabs.innerHTML = "";
    SEARCH_TABS.forEach(function (tab) {
      var count = counts[tab.key] || 0;
      var disabled = tab.key !== "all" && count === 0;
      var isActive = searchState.activeTab === tab.key;

      var button = document.createElement("button");
      button.type = "button";
      button.className = "site-search-page__tab";
      if (isActive) {
        button.classList.add("site-search-page__tab--active");
      }
      if (disabled) {
        button.classList.add("site-search-page__tab--disabled");
        button.disabled = true;
      }
      button.setAttribute("role", "tab");
      button.setAttribute("aria-selected", isActive ? "true" : "false");
      button.setAttribute("aria-controls", "site-search-results-panel");
      button.setAttribute("data-search-tab", tab.key);
      button.textContent = tab.label;

      if (!disabled) {
        button.addEventListener("click", function () {
          if (searchState.activeTab === tab.key) {
            return;
          }
          searchState.activeTab = tab.key;
          renderResults(searchState.query, searchState.results);
        });
      }

      tabs.appendChild(button);
    });
  }

  function updateMetaText(meta, query, filteredCount, tabKey) {
    var countLabel = formatCountLabel(filteredCount);
    if (tabKey === "all") {
      meta.textContent = countLabel + ' за запитом «' + query + '».';
      return;
    }
    meta.textContent =
      countLabel + ' у розділі «' + getTabLabel(tabKey) + '» за запитом «' + query + '».';
  }

  function renderResults(query, results) {
    var ui = getSearchUi();
    if (!ui) {
      return;
    }

    var meta = ui.meta;
    var container = ui.container;
    searchState.query = query;
    searchState.results = results;

    container.innerHTML = "";
    setTabsVisible(ui.tabs, false);

    if (!query) {
      setMetaVisible(meta, false);
      searchState.activeTab = "all";
      container.innerHTML =
        '<p class="site-search-page__empty">Введіть запит, щоб знайти матеріали на сайті.</p>';
      return;
    }

    setMetaVisible(meta, true);

    if (!results.length) {
      searchState.activeTab = "all";
      meta.textContent = 'За запитом «' + query + '» нічого не знайдено.';
      container.innerHTML =
        '<p class="site-search-page__empty">Спробуйте інші ключові слова або перевірте правопис.</p>';
      return;
    }

    var counts = countResultsByTab(results);
    searchState.activeTab = resolveActiveTab(counts, searchState.activeTab);

    setTabsVisible(ui.tabs, true);
    renderTabs(ui, counts);

    var filtered = filterResultsByTab(results, searchState.activeTab);
    updateMetaText(meta, query, filtered.length, searchState.activeTab);
    container.id = "site-search-results-panel";
    container.setAttribute("role", "tabpanel");

    if (!filtered.length) {
      container.innerHTML =
        '<p class="site-search-page__empty">У цьому розділі немає результатів для вашого запиту.</p>';
      return;
    }

    renderResultCards(container, filtered);
  }

  function bindSearchForm() {
    var form = document.querySelector(".site-search-page__form");
    if (!form || form.dataset.siteSearchBound === "1") {
      return;
    }
    form.dataset.siteSearchBound = "1";
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var input = form.querySelector('input[name="q"]');
      var query = input ? input.value.trim() : "";
      var target = searchPageUrl();
      if (query) {
        target += "?q=" + encodeURIComponent(query);
      }
      window.location.href = target;
    });
  }

  function initSearchPage() {
    if (!isSearchPage()) {
      return;
    }

    bindSearchForm();

    var query = getQueryParam();
    var input = document.querySelector(".site-search-page__input");
    if (input) {
      input.value = query;
      if (!query) {
        window.requestAnimationFrame(function () {
          input.focus();
        });
      }
    }

    if (query !== searchState.query) {
      searchState.activeTab = "all";
    }

    loadIndex()
      .then(function (documents) {
        renderResults(query, searchDocuments(documents, query));
      })
      .catch(function () {
        var ui = getSearchUi();
        if (!ui) {
          return;
        }
        setTabsVisible(ui.tabs, false);
        setMetaVisible(ui.meta, true);
        ui.meta.textContent = "Не вдалося завантажити індекс пошуку.";
        ui.container.innerHTML =
          '<p class="site-search-page__empty">Спробуйте оновити сторінку пізніше.</p>';
      });
  }

  function scheduleSearchInit() {
    var run = function () {
      initSearchPage();
    };
    var schedule = window.scheduleNavPatches || function (fn) {
      if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", fn);
      } else {
        fn();
      }
    };
    schedule(run);
    window.setTimeout(run, 200);
    window.setTimeout(run, 600);
  }

  scheduleSearchInit();
})();
