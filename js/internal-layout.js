(function () {
  var TREE_URL = "/data/site-nav-tree.json?v=1";
  var TREE_CACHE_KEY = "site-nav-tree-v1";
  var HOME_LABEL = "Головна";
  var SUBCAT_LABEL = "Виберіть підкатегорію:";
  var CARD_PALETTE = ["#686F4E", "#908F8B", "#61523A", "#503334", "#B29069", "#7D997B"];
  var STANDALONE_PAGES = {
    "/about/": true,
    "/faq/": true,
    "/download/": true,
    "/search/": true,
    "/documents/": true,
    "/privacy-policy/": true,
  };
  var expandedManual = Object.create(null);
  var navTree = null;
  var applying = false;
  var articleTocSpyCleanup = null;
  var revealTimer = null;
  var mobileTocBound = false;

  try {
    var cachedTree = sessionStorage.getItem(TREE_CACHE_KEY);
    if (cachedTree) {
      navTree = JSON.parse(cachedTree);
    }
  } catch (error) {
    navTree = null;
  }

  function isLayoutBaked() {
    var main = getMainElement();
    return !!(main && main.dataset.internalLayoutBaked);
  }

  function markLayoutReady() {
    document.documentElement.classList.add("internal-layout-active");
    if (revealTimer) {
      window.clearTimeout(revealTimer);
    }
    if (isLayoutBaked()) {
      document.documentElement.classList.remove("internal-layout-pending");
      document.documentElement.classList.add("internal-layout-ready");
      revealTimer = null;
      return;
    }
    revealTimer = window.setTimeout(function () {
      document.documentElement.classList.remove("internal-layout-pending");
      document.documentElement.classList.add("internal-layout-ready");
      revealTimer = null;
    }, 180);
  }

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

  function isHomePage() {
    return normalizePath(window.location.pathname) === "/";
  }

  function isStandalonePage(path) {
    return !!STANDALONE_PAGES[normalizePath(path)];
  }

  function pathsEqual(a, b) {
    return normalizePath(a) === normalizePath(b);
  }

  function fetchTree() {
    if (navTree) {
      return Promise.resolve(navTree);
    }
    var treeUrl = typeof siteUrl === "function" ? siteUrl(TREE_URL) : TREE_URL;
    return fetch(treeUrl)
      .then(function (res) {
        return res.json();
      })
      .then(function (data) {
        navTree = data;
        try {
          sessionStorage.setItem(TREE_CACHE_KEY, JSON.stringify(data));
        } catch (error) {}
        return data;
      })
      .catch(function () {
        navTree = { categories: [] };
        return navTree;
      });
  }

  function pathInCategory(path, category) {
    if (pathsEqual(path, category.href)) {
      return true;
    }

    if (category.id === "injured") {
      var children = category.children || [];
      for (var i = 0; i < children.length; i++) {
        if (path.indexOf(children[i].href) === 0) {
          return true;
        }
      }
      return pathsEqual(path, category.href);
    }

    return path.indexOf(category.href) === 0;
  }

  function findCategoryByPath(path) {
    if (!navTree) {
      return null;
    }
    for (var i = 0; i < navTree.categories.length; i++) {
      var category = navTree.categories[i];
      if (pathInCategory(path, category)) {
        return category;
      }
    }
    return null;
  }

  function findTrail(nodes, path, trail) {
    trail = trail || [];
    for (var i = 0; i < nodes.length; i++) {
      var node = nodes[i];
      var nextTrail = trail.concat([node]);
      if (pathsEqual(node.href, path)) {
        return nextTrail;
      }
      if (node.children && node.children.length) {
        var found = findTrail(node.children, path, nextTrail);
        if (found) {
          return found;
        }
      }
    }
    return null;
  }

  function buildBreadcrumbTrail(category, path) {
    var trail = [{ label: HOME_LABEL, href: "/" }];
    if (!category) {
      return trail;
    }

    var nodeTrail = findTrail(category.children || [], path, []) || [];

    trail.push({ label: category.label, href: category.href });

    if (pathsEqual(path, category.href)) {
      trail[trail.length - 1].current = true;
      return trail;
    }

    for (var i = 0; i < nodeTrail.length; i++) {
      trail.push({
        label: nodeTrail[i].label,
        href: nodeTrail[i].href,
        current: i === nodeTrail.length - 1,
      });
    }

    return trail;
  }

  function breadcrumbsHtml(trail) {
    var parts = [];
    for (var i = 0; i < trail.length; i++) {
      var item = trail[i];
      if (i > 0) {
        parts.push(
          '<span class="internal-breadcrumbs__sep" aria-hidden="true">' +
            '<img src="/img/breadcrumbs_arrow.svg" alt="" width="7" height="11" />' +
            "</span>"
        );
      }
      if (item.current) {
        parts.push(
          '<span class="internal-breadcrumbs__item internal-breadcrumbs__item--current">' +
            item.label +
            "</span>"
        );
      } else {
        parts.push(
          '<a class="internal-breadcrumbs__item" href="' +
            item.href +
            '">' +
            item.label +
            "</a>"
        );
      }
    }
    return '<nav class="internal-breadcrumbs" aria-label="Breadcrumb">' + parts.join("") + "</nav>";
  }

  function mobileTocToggleMarkup() {
    return (
      '<div class="internal-toc-toggle-wrap">' +
      '<button type="button" class="internal-toc-toggle" aria-label="Зміст" aria-expanded="false">' +
      '<img class="internal-toc-toggle__icon" src="/img/toc_icon.svg" alt="" width="16" height="16" aria-hidden="true" />' +
      '<span class="internal-toc-toggle__label">Зміст</span>' +
      "</button>" +
      '<div class="internal-toc-dropdown" hidden>' +
      '<div class="internal-toc-dropdown__panel">' +
      '<h4 class="mantine-Text-root mantine-Title-root">Зміст сторінки</h4>' +
      '<ul class="mantine-List-root"></ul>' +
      "</div>" +
      "</div>" +
      "</div>"
    );
  }

  function breadcrumbsRowHtml(trail) {
    return (
      '<div class="internal-breadcrumbs-row">' +
      breadcrumbsHtml(trail) +
      mobileTocToggleMarkup() +
      "</div>"
    );
  }

  function collectTocLinksFromWrap(tocWrap) {
    var links = [];
    if (!tocWrap) {
      return links;
    }

    tocWrap.querySelectorAll(".mantine-List-item a[href*='#']").forEach(function (link) {
      var listItem = link.closest(".mantine-List-item");
      var depth = 0;
      var parent = listItem && listItem.parentElement;

      while (parent && parent !== tocWrap) {
        if (parent.classList && parent.classList.contains("mantine-List-item")) {
          depth += 1;
        }
        parent = parent.parentElement;
      }

      links.push({
        href: link.getAttribute("href") || "",
        title: link.textContent.trim(),
        depth: depth,
        badgeHtml: (function () {
          var container = getTocItemContainer(link);
          var badge = container && container.querySelector(".internal-toc-doc-badge");
          return badge ? badge.outerHTML : "";
        })(),
      });
    });

    return links;
  }

  function setMobileTocOpen(wrap, open) {
    if (!wrap) {
      return;
    }

    var btn = wrap.querySelector(".internal-toc-toggle");
    var dropdown = wrap.querySelector(".internal-toc-dropdown");
    if (!btn || !dropdown) {
      return;
    }

    btn.setAttribute("aria-expanded", open ? "true" : "false");
    btn.classList.toggle("internal-toc-toggle--active", open);
    dropdown.hidden = !open;
  }

  function syncMobileTocActiveState(contentHost, activeHref) {
    if (!contentHost) {
      return;
    }

    if (!activeHref) {
      var sidebarActive = contentHost.querySelector(
        ".internal-article-toc .internal-toc-item--active a"
      );
      activeHref = sidebarActive ? sidebarActive.getAttribute("href") : "";
    }

    contentHost.querySelectorAll(".internal-toc-dropdown .mantine-List-item").forEach(function (item) {
      var link = item.querySelector("a");
      item.classList.toggle(
        "internal-toc-item--active",
        !!(link && activeHref && link.getAttribute("href") === activeHref)
      );
    });
  }

  function syncMobileTocDropdown(contentHost) {
    if (!contentHost) {
      return;
    }

    var toggleWrap = contentHost.querySelector(".internal-toc-toggle-wrap");
    var tocWrap = contentHost.querySelector(".internal-article-toc");
    if (!toggleWrap || !tocWrap) {
      return;
    }

    var list = toggleWrap.querySelector(".internal-toc-dropdown .mantine-List-root");
    if (!list) {
      return;
    }

    var links = collectTocLinksFromWrap(tocWrap);
    if (!links.length) {
      toggleWrap.classList.add("internal-toc-toggle-wrap--empty");
      return;
    }

    toggleWrap.classList.remove("internal-toc-toggle-wrap--empty");
    list.innerHTML = links
      .map(function (link) {
        return (
          '<li class="mantine-List-item">' +
          '<div class="internal-toc-item-text">' +
          '<a class="css-16clbz5" href="' +
          escapeHtml(link.href) +
          '">' +
          escapeHtml(link.title) +
          "</a>" +
          (link.badgeHtml || "") +
          "</div></li>"
        );
      })
      .join("");

    syncMobileTocActiveState(contentHost);
  }

  function bindMobileTocEvents() {
    if (mobileTocBound) {
      return;
    }
    mobileTocBound = true;

    document.addEventListener("click", function (event) {
      var toggle = event.target.closest(".internal-toc-toggle");
      if (toggle) {
        event.preventDefault();
        event.stopPropagation();
        var wrap = toggle.closest(".internal-toc-toggle-wrap");
        var isOpen = toggle.getAttribute("aria-expanded") === "true";

        document.querySelectorAll(".internal-toc-toggle-wrap").forEach(function (item) {
          if (item !== wrap) {
            setMobileTocOpen(item, false);
          }
        });
        setMobileTocOpen(wrap, !isOpen);
        return;
      }

      if (event.target.closest(".internal-toc-dropdown a")) {
        var linkWrap = event.target.closest(".internal-toc-toggle-wrap");
        setMobileTocOpen(linkWrap, false);
        return;
      }

      if (!event.target.closest(".internal-toc-toggle-wrap")) {
        document.querySelectorAll(".internal-toc-toggle-wrap").forEach(function (item) {
          setMobileTocOpen(item, false);
        });
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        document.querySelectorAll(".internal-toc-toggle-wrap").forEach(function (item) {
          setMobileTocOpen(item, false);
        });
      }
    });
  }

  function ensureMobileTocUi(contentHost) {
    if (!contentHost) {
      return;
    }

    var tocWrap = contentHost.querySelector(".internal-article-toc");
    var hasTocItems = tocWrap && tocWrap.querySelector(".mantine-List-item");
    var row = contentHost.querySelector(".internal-breadcrumbs-row");

    if (!hasTocItems) {
      if (row) {
        var emptyWrap = row.querySelector(".internal-toc-toggle-wrap");
        if (emptyWrap) {
          emptyWrap.classList.add("internal-toc-toggle-wrap--empty");
        }
      }
      return;
    }

    if (!row) {
      var breadcrumbs = contentHost.querySelector(".internal-breadcrumbs");
      if (breadcrumbs) {
        row = document.createElement("div");
        row.className = "internal-breadcrumbs-row";
        breadcrumbs.parentNode.insertBefore(row, breadcrumbs);
        row.appendChild(breadcrumbs);
        row.insertAdjacentHTML("beforeend", mobileTocToggleMarkup());
      } else {
        var layout = contentHost.querySelector(
          ".internal-article-layout, .css-k1l4fw.internal-article-layout, .css-k1l4fw"
        );
        if (layout) {
          row = document.createElement("div");
          row.className = "internal-breadcrumbs-row internal-breadcrumbs-row--standalone";
          row.innerHTML = mobileTocToggleMarkup();
          layout.parentNode.insertBefore(row, layout);
        }
      }
    } else if (!row.querySelector(".internal-toc-toggle-wrap")) {
      row.insertAdjacentHTML("beforeend", mobileTocToggleMarkup());
    }

    syncMobileTocDropdown(contentHost);
    bindMobileTocEvents();
    syncMobileTocTogglePosition();
  }

  function syncMobileTocTogglePosition() {
    var isMobileToc = window.matchMedia("(max-width: 1279px)").matches;

    document.querySelectorAll(".internal-toc-toggle-wrap").forEach(function (wrap) {
      if (!isMobileToc || wrap.classList.contains("internal-toc-toggle-wrap--empty")) {
        wrap.style.removeProperty("right");
        return;
      }

      var row = wrap.closest(".internal-breadcrumbs-row");
      if (!row) {
        wrap.style.removeProperty("right");
        return;
      }

      var rowRect = row.getBoundingClientRect();
      wrap.style.right = Math.round(window.innerWidth - rowRect.right) + "px";
    });
  }

  function shouldExpandNode(href, path) {
    if (expandedManual[href]) {
      return true;
    }
    if (pathsEqual(href, path)) {
      return false;
    }
    return path.indexOf(href) === 0;
  }

  function renderTreeNodes(nodes, path) {
    var html = "";
    for (var i = 0; i < nodes.length; i++) {
      var node = nodes[i];
      var hasChildren = node.children && node.children.length;
      var isActive = pathsEqual(node.href, path);
      var isExpanded = hasChildren && shouldExpandNode(node.href, path);
      var toggleClass = hasChildren
        ? "internal-tree-toggle"
        : "internal-tree-toggle internal-tree-toggle--hidden";

      html +=
        '<li class="internal-tree-item">' +
        '<div class="internal-tree-row">' +
        '<button type="button" class="' +
        toggleClass +
        '" data-tree-href="' +
        node.href +
        '" aria-expanded="' +
        (isExpanded ? "true" : "false") +
        '">' +
        '<img class="internal-tree-toggle__icon" src="/img/arrow_down.svg" alt="" width="12" height="12" aria-hidden="true" />' +
        "</button>" +
        '<a class="internal-tree-link' +
        (isActive ? " internal-tree-link--active" : "") +
        '" href="' +
        node.href +
        '">' +
        node.label +
        "</a>" +
        "</div>";

      if (hasChildren && isExpanded) {
        html +=
          '<ul class="internal-tree-list">' +
          renderTreeNodes(node.children, path) +
          "</ul>";
      }

      html += "</li>";
    }
    return html;
  }

  function sidebarHtml(category, path) {
    return (
      '<aside class="internal-sidebar">' +
      '<div class="internal-sidebar__title">' +
      category.label +
      "</div>" +
      '<nav class="internal-sidebar__tree" aria-label="' +
      category.label +
      '">' +
      '<ul class="internal-tree-list">' +
      renderTreeNodes(category.children || [], path) +
      "</ul></nav></aside>"
    );
  }

  function getPageTitle() {
    var hero = document.querySelector(".css-16uvw1j h1");
    if (hero && hero.textContent.trim()) {
      return hero.textContent.trim();
    }
    var h1 = document.querySelector("main h1");
    if (h1 && h1.textContent.trim()) {
      return h1.textContent.trim();
    }
    var h2 = document.querySelector("main h2");
    if (h2 && h2.textContent.trim()) {
      return h2.textContent.trim();
    }
    return document.title.replace(" | Правовий навігатор", "").trim();
  }

  function extractCardsFromDom() {
    var container = document.querySelector(".css-1jbx5ca");
    if (!container) {
      return [];
    }

    var seen = Object.create(null);
    var cards = [];
    var links = container.querySelectorAll("a.css-1q51wqn, a.css-1gooe0");
    for (var i = 0; i < links.length; i++) {
      var link = links[i];
      var href = link.getAttribute("href") || "";
      if (!href || seen[href]) {
        continue;
      }
      seen[href] = true;

      var labelNode = link.querySelector("p.css-6ixod5, p.css-1nnvzuy");
      var iconNode = link.querySelector("img");
      var bgNode = link.querySelector(".css-bxqx5h, .css-5km5in");
      var color = "";
      if (bgNode) {
        color = getComputedStyle(bgNode).backgroundColor;
      }

      cards.push({
        href: href,
        label: labelNode ? labelNode.textContent.trim() : href,
        icon: iconNode ? iconNode.getAttribute("src") : "",
        color: color,
      });
    }
    return enrichCards(cards);
  }

  function enrichCards(cards) {
    return cards.map(function (card, index) {
      var item = {
        href: card.href,
        label: card.label,
        icon: card.icon || "",
        color: card.color || CARD_PALETTE[index % CARD_PALETTE.length],
      };
      return item;
    });
  }

  function cardsFromNodeData(nodes) {
    if (!nodes || !nodes.length) {
      return [];
    }
    return enrichCards(
      nodes.map(function (node) {
        return {
          href: node.href,
          label: node.label,
          icon: node.icon || "",
          color: node.color || "",
        };
      })
    );
  }

  function resolveCards(category, path, trail) {
    if (pathsEqual(path, category.href)) {
      return cardsFromNodeData(category.children);
    }

    var domCards = extractCardsFromDom();
    if (domCards.length) {
      return domCards;
    }

    if (trail && trail.length) {
      var current = trail[trail.length - 1];
      if (current.children && current.children.length) {
        return cardsFromNodeData(current.children);
      }
    }

    return [];
  }

  function stripHtml(cards) {
    if (!cards.length) {
      return "";
    }

    var items = cards
      .map(function (card) {
        var style = card.color ? ' style="background-color:' + card.color + '"' : "";
        var icon = card.icon
          ? '<img class="internal-strip__icon" src="' +
            card.icon +
            '" alt="" aria-hidden="true"/>'
          : "";
        return (
          '<a class="internal-strip"' +
          style +
          ' href="' +
          card.href +
            '">' +
          icon +
          '<span class="internal-strip__label">' +
          card.label +
          "</span></a>"
        );
      })
      .join("");

    return (
      '<div class="internal-subcats-panel">' +
      '<p class="internal-subcats__label">' +
      SUBCAT_LABEL +
      "</p>" +
      '<div class="internal-subcats__list">' +
      items +
      "</div></div>"
    );
  }

  function getMainElement() {
    return document.querySelector("main.css-yp9swi") || document.querySelector("main");
  }

  function getContentSection(root) {
    return (
      root.querySelector("section.css-1napgkq") ||
      root.querySelector("section.css-1m99gl8") ||
      root.querySelector("section.css-t97qev") ||
      root.querySelector("section")
    );
  }

  function bindTreeToggles(sidebar) {
    if (!sidebar) {
      return;
    }
    var buttons = sidebar.querySelectorAll(".internal-tree-toggle");
    for (var i = 0; i < buttons.length; i++) {
      var button = buttons[i];
      if (button.classList.contains("internal-tree-toggle--hidden")) {
        continue;
      }
      if (button.dataset.bound) {
        continue;
      }
      button.dataset.bound = "1";
      button.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        var treeItem = this.closest(".internal-tree-item");
        var childList = null;
        if (treeItem) {
          for (var ci = 0; ci < treeItem.children.length; ci++) {
            if (treeItem.children[ci].classList.contains("internal-tree-list")) {
              childList = treeItem.children[ci];
              break;
            }
          }
        }

        if (childList) {
          var expanded = this.getAttribute("aria-expanded") === "true";
          this.setAttribute("aria-expanded", expanded ? "false" : "true");
          childList.style.display = expanded ? "none" : "";
          return;
        }

        var href = this.getAttribute("data-tree-href");
        expandedManual[href] = !expandedManual[href];
        applyLayout(true);
      });
    }
  }

  function initBakedLayoutRuntime() {
    var main = getMainElement();
    if (!main) {
      return;
    }

    document.documentElement.classList.add("internal-layout-active");

    var shell = main.querySelector(".internal-page-shell");
    if (shell) {
      bindTreeToggles(shell.querySelector(".internal-sidebar"));
    }

    var tocScope = getTocScope();
    if (tocScope) {
      expandArticleAccordions(tocScope);
      fixArticleTocScroll(tocScope);
      bindArticleTocNavigation(tocScope);
      bindArticleFigureLightbox(tocScope);
      if (tocScope.querySelector(".internal-article-toc .mantine-List-item")) {
        bindArticleTocSpy(tocScope);
      }
      ensureMobileTocUi(tocScope);
    }

    bindMobileTocEvents();
    document.querySelectorAll(".internal-article-content").forEach(applyHeadingNormalization);
    normalizeDocumentDownloadBlocks();
    repairDashBulletLists();
    syncLayoutStickyOffset();
    markLayoutReady();
  }

  var DOCUMENT_DOWNLOAD_ICON = "/img/download_24dp.svg";
  var TOC_DOC_BADGE_ICON = "/img/paperclip.svg";
  var SECTION_H2_CLASS = "internal-section-h2";
  var SECTION_H3_CLASS = "internal-section-h3";

  function inAccordionLabel(node) {
    return !!node.closest(".mantine-Accordion-label");
  }

  function inTocWidget(node) {
    return !!node.closest(".internal-article-toc, .internal-toc-dropdown, .internal-toc-generated");
  }

  var SECTION_H4_CLASS = "internal-section-h4";

  function isAboutOrFaqPage() {
    var path = normalizePath(window.location.pathname);
    return path === "/about/" || path === "/faq/";
  }

  function inAboutCardTitle(node) {
    var parent = node.parentElement;
    if (!parent || node.tagName !== "H2") {
      return false;
    }
    return parent.classList.contains("css-sdnfq3") && parent.querySelector(":scope > h2") === node;
  }

  function ensureSectionH2(node) {
    var h2 = node;
    if (node.tagName !== "H2") {
      h2 = document.createElement("h2");
      h2.className = node.className;
      h2.innerHTML = node.innerHTML;
      node.replaceWith(h2);
    }
    h2.classList.remove(SECTION_H3_CLASS);
    h2.classList.add(SECTION_H2_CLASS);
    return h2;
  }

  function demoteAboutCardSubheadings(card, sectionH2) {
    Array.from(card.querySelectorAll("h2, h3, h4")).forEach(function (heading) {
      if (heading === sectionH2) {
        return;
      }
      var inLabel = !!heading.closest(".mantine-Accordion-label");
      if (inLabel) {
        if (heading.tagName !== "H3") {
          var labelH3 = document.createElement("h3");
          labelH3.className = heading.className;
          labelH3.classList.remove(SECTION_H2_CLASS, SECTION_H4_CLASS);
          labelH3.classList.add(SECTION_H3_CLASS);
          labelH3.innerHTML = heading.innerHTML;
          heading.replaceWith(labelH3);
        } else {
          heading.classList.remove(SECTION_H2_CLASS, SECTION_H4_CLASS);
          heading.classList.add(SECTION_H3_CLASS);
        }
        return;
      }
      if (heading.tagName === "H2") {
        var h3 = document.createElement("h3");
        h3.className = heading.className;
        h3.classList.remove(SECTION_H2_CLASS);
        h3.classList.add(SECTION_H3_CLASS);
        h3.innerHTML = heading.innerHTML;
        heading.replaceWith(h3);
        return;
      }
      if (heading.tagName === "H3") {
        var h4 = document.createElement("h4");
        h4.className = heading.className;
        h4.classList.remove(SECTION_H2_CLASS, SECTION_H3_CLASS);
        h4.classList.add(SECTION_H4_CLASS);
        h4.innerHTML = heading.innerHTML;
        heading.replaceWith(h4);
        return;
      }
      heading.classList.add(SECTION_H4_CLASS);
    });
  }

  function repairAboutCardLayout(root) {
    if (!root) {
      return;
    }

    root.querySelectorAll(".mantine-wnhdd8").forEach(function (block) {
      var card = block.querySelector(":scope > .css-sdnfq3");
      var header = block.querySelector(":scope > .mantine-j9g3bi");
      if (header && card) {
        var heading = header.querySelector("h2, h3, h4");
        if (heading) {
          card.insertBefore(ensureSectionH2(heading), card.firstChild);
        }
        if (!header.textContent.trim() && !header.querySelector("*")) {
          header.remove();
        }
      }
      if (!card) {
        return;
      }
      var sectionH2 = card.querySelector(":scope > h2.internal-section-h2, :scope > h2");
      if (sectionH2) {
        ensureSectionH2(sectionH2);
        demoteAboutCardSubheadings(card, sectionH2);
      }
    });
  }

  function isDocumentsPage() {
    return normalizePath(window.location.pathname) === "/documents/";
  }

  function repairDocumentsPageLayout(root) {
    if (!root) {
      return;
    }

    root.querySelectorAll(".mantine-Accordion-label h4").forEach(function (h4) {
      var h2 = document.createElement("h2");
      h2.className = h4.className;
      h2.classList.add(SECTION_H2_CLASS);
      h2.innerHTML = h4.innerHTML;
      h4.replaceWith(h2);
    });

    repairAboutCardLayout(root);

    var mainCol = root.querySelector(".css-7nll2u");
    if (mainCol) {
      var wrap = mainCol.querySelector(".mantine-1jhay8j");
      while (wrap) {
        while (wrap.firstElementChild) {
          wrap.parentNode.insertBefore(wrap.firstElementChild, wrap);
        }
        wrap.remove();
        wrap = mainCol.querySelector(".mantine-1jhay8j");
      }
    }

    root.querySelectorAll("[data-accordion-control]").forEach(function (control) {
      control.setAttribute("aria-expanded", "true");
      var panelId = control.getAttribute("aria-controls");
      if (!panelId) {
        return;
      }
      var panel = root.querySelector("#" + CSS.escape(panelId));
      if (panel) {
        panel.style.setProperty("display", "block", "important");
        panel.style.setProperty("height", "auto", "important");
        panel.style.setProperty("overflow", "visible", "important");
        panel.setAttribute("aria-hidden", "false");
      }
    });

    repairAboutCardLayout(root);
  }

  function repairAboutPageLayout(root) {
    if (!root) {
      return;
    }
    repairAboutCardLayout(root);
    var mainCol = root.querySelector(".css-7nll2u");
    if (mainCol) {
      var intros = mainCol.querySelectorAll(
        ":scope > p.css-tualuh.internal-article-intro:not(.about-page__lead), :scope > p.internal-article-intro:not(.about-page__lead)"
      );
      if (intros.length && !mainCol.querySelector(".internal-article-intro-card") && !mainCol.querySelector(".about-page__intro")) {
        var introCard = document.createElement("div");
        introCard.className = "css-sdnfq3 mantine-1hdrj7p internal-article-intro-card";
        mainCol.insertBefore(introCard, intros[0]);
        intros.forEach(function (paragraph) {
          introCard.appendChild(paragraph);
        });
      }
      var wrap = mainCol.querySelector(":scope > .mantine-1jhay8j");
      if (wrap) {
        while (wrap.firstElementChild) {
          mainCol.insertBefore(wrap.firstElementChild, wrap);
        }
        wrap.remove();
      }
    }
    repairAboutCardLayout(root);
  }

  function isDownloadPage() {
    return normalizePath(window.location.pathname) === "/download/";
  }

  function isSearchPage() {
    return normalizePath(window.location.pathname) === "/search/";
  }

  function applyHeadingNormalization(root) {
    if (isAboutOrFaqPage()) {
      repairAboutPageLayout(root);
      return;
    }
    if (isDocumentsPage()) {
      repairDocumentsPageLayout(root);
      return;
    }
    if (isDownloadPage() || isSearchPage()) {
      return;
    }
    normalizeHeadingLevels(root);
  }

  function isIntentionalSectionH2(node) {
    if (inAccordionLabel(node)) {
      return true;
    }
    if (node.classList.contains(SECTION_H2_CLASS)) {
      return true;
    }
    if (inAboutCardTitle(node)) {
      return true;
    }
    return false;
  }

  function normalizeHeadingLevels(root) {
    if (!root) {
      return;
    }

    root.querySelectorAll(".mantine-wnhdd8 > .mantine-j9g3bi > h2").forEach(function (h2) {
      if (!h2.classList.contains("css-o8yj4d")) {
        return;
      }
      var h3 = document.createElement("h3");
      h3.className = h2.className;
      h3.classList.remove(SECTION_H2_CLASS);
      h3.classList.add(SECTION_H3_CLASS);
      h3.innerHTML = h2.innerHTML;
      h2.replaceWith(h3);
    });

    root.querySelectorAll("h2").forEach(function (h2) {
      if (inTocWidget(h2) || isIntentionalSectionH2(h2)) {
        return;
      }
      var h3 = document.createElement("h3");
      h3.className = h2.className;
      h3.classList.add(SECTION_H3_CLASS);
      h3.innerHTML = h2.innerHTML;
      h2.replaceWith(h3);
    });

    root.querySelectorAll(".mantine-Accordion-label h4").forEach(function (h4) {
      var h2 = document.createElement("h2");
      h2.className = h4.className;
      h2.classList.add(SECTION_H2_CLASS);
      h2.innerHTML = h4.innerHTML;
      h4.replaceWith(h2);
    });

    root.querySelectorAll(".mantine-wnhdd8 > .mantine-j9g3bi > h3").forEach(function (h3) {
      if (!h3.classList.contains("css-su8tkm")) {
        return;
      }
      var h2 = document.createElement("h2");
      h2.className = h3.className;
      h2.classList.remove(SECTION_H3_CLASS);
      h2.classList.add(SECTION_H2_CLASS);
      h2.innerHTML = h3.innerHTML;
      h3.replaceWith(h2);
    });
  }

  function normalizeDocumentDownloadBlocks() {
    document
      .querySelectorAll('.internal-article-content a.css-uex5rt img[alt="file-icon"]')
      .forEach(function (img) {
        if (!img.getAttribute("src") || img.getAttribute("src").indexOf("download_24dp.svg") === -1) {
          img.setAttribute("src", DOCUMENT_DOWNLOAD_ICON);
        }
        img.removeAttribute("width");
        img.removeAttribute("height");
      });
  }

  var BULLET_PREFIX_RE = /^\s*(?:[\-–—−‐‒↓•]|[а-яіїєґa-zA-Z][\)\.])\s*/i;
  var NUMBERED_PREFIX_RE = /^\s*\d+[\)\.]\s*/;
  var ARTICLE_LIST_CLASS = "internal-article-list";
  var NUMBERED_LIST_CLASS = "internal-article-numbered-list";
  var LEADING_WS_RE = /^[\s\u00a0\t]+/;

  function segmentText(nodes) {
    var wrap = document.createElement("div");
    nodes.forEach(function (node) {
      wrap.appendChild(node.cloneNode(true));
    });
    return (wrap.textContent || "").replace(/\s+/g, " ").trim();
  }

  function isBulletSegment(nodes) {
    return BULLET_PREFIX_RE.test(segmentText(nodes));
  }

  function stripBulletPrefix(container) {
    var walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null);
    var node = walker.nextNode();
    while (node) {
      var next = walker.nextNode();
      var text = node.textContent || "";
      if (text.trim()) {
        node.textContent = text.replace(BULLET_PREFIX_RE, "");
        return;
      }
      node = next;
    }
  }

  function splitNodesByBr(nodes) {
    var segments = [[]];
    nodes.forEach(function (node) {
      if (node.nodeType === 1 && node.nodeName === "BR") {
        if (segments[segments.length - 1].length) {
          segments.push([]);
        }
        return;
      }
      segments[segments.length - 1].push(node);
    });
    return segments.filter(function (segment) {
      return segment.length;
    });
  }

  function appendNodes(parent, nodes) {
    nodes.forEach(function (node) {
      parent.appendChild(node);
    });
  }

  function makeBulletList(segments) {
    var ul = document.createElement("ul");
    ul.className = ARTICLE_LIST_CLASS;
    segments.forEach(function (segment) {
      var li = document.createElement("li");
      appendNodes(li, segment);
      stripBulletPrefix(li);
      ul.appendChild(li);
    });
    return ul;
  }

  function trimEdgeBreaks(nodes) {
    var trimmed = Array.prototype.slice.call(nodes);
    while (trimmed.length) {
      var last = trimmed[trimmed.length - 1];
      if (last.nodeType === 1 && last.nodeName === "BR") {
        trimmed.pop();
        continue;
      }
      if (last.nodeType === 3 && !last.textContent.trim()) {
        trimmed.pop();
        continue;
      }
      break;
    }
    while (trimmed.length) {
      var first = trimmed[0];
      if (first.nodeType === 1 && first.nodeName === "BR") {
        trimmed.shift();
        continue;
      }
      if (first.nodeType === 3 && !first.textContent.trim()) {
        trimmed.shift();
        continue;
      }
      break;
    }
    return trimmed;
  }

  function meaningfulBrCount(container) {
    return trimEdgeBreaks(container.childNodes).filter(function (node) {
      return node.nodeType === 1 && node.nodeName === "BR";
    }).length;
  }

  function divIsBulletOnly(div) {
    if (!div.classList.contains("mantine-172zsy7")) {
      return false;
    }
    if (div.querySelector("ul." + ARTICLE_LIST_CLASS)) {
      return false;
    }
    var text = (div.textContent || "").replace(/\s+/g, " ").trim();
    if (!BULLET_PREFIX_RE.test(text)) {
      return false;
    }
    return meaningfulBrCount(div) === 0;
  }

  function isAnnotationDiv(div) {
    if (!div.classList.contains("mantine-172zsy7")) {
      return false;
    }
    var text = (div.textContent || "").replace(/\s+/g, " ").trim();
    if (BULLET_PREFIX_RE.test(text)) {
      return false;
    }
    return text.indexOf("(") === 0 && text.indexOf(")") !== -1;
  }

  function convertSingletonBulletDivs(root) {
    var changed = false;
    Array.prototype.slice.call(root.querySelectorAll(".mantine-172zsy7")).forEach(function (div) {
      if (!divIsBulletOnly(div)) {
        return;
      }
      var ul = makeBulletList([trimEdgeBreaks(div.childNodes)]);
      div.parentNode.replaceChild(ul, div);
      changed = true;
    });
    return changed;
  }

  function mergeBulletListsAcrossAnnotations(root) {
    var changed = false;
    Array.prototype.slice.call(root.querySelectorAll("*")).forEach(function (parent) {
      var childTags = Array.prototype.slice.call(parent.children).filter(function (node) {
        return node.nodeType === 1;
      });
      var i = 0;
      while (i < childTags.length) {
        var child = childTags[i];
        if (child.nodeName !== "UL" || !child.classList.contains(ARTICLE_LIST_CLASS)) {
          i += 1;
          continue;
        }
        var group = [child];
        var j = i + 1;
        while (j < childTags.length) {
          var nxt = childTags[j];
          if (isAnnotationDiv(nxt)) {
            j += 1;
            continue;
          }
          if (nxt.nodeName === "UL" && nxt.classList.contains(ARTICLE_LIST_CLASS)) {
            group.push(nxt);
            j += 1;
            continue;
          }
          if (divIsBulletOnly(nxt)) {
            group.push(nxt);
            j += 1;
            continue;
          }
          break;
        }
        if (group.length < 2) {
          i += 1;
          continue;
        }
        var merged = document.createElement("ul");
        merged.className = ARTICLE_LIST_CLASS;
        group.forEach(function (item) {
          if (item.nodeName === "UL") {
            Array.prototype.slice.call(item.children).forEach(function (li) {
              if (li.nodeName === "LI") {
                merged.appendChild(li);
              }
            });
            return;
          }
          var li = document.createElement("li");
          appendNodes(li, trimEdgeBreaks(item.childNodes));
          stripBulletPrefix(li);
          merged.appendChild(li);
        });
        group[0].parentNode.insertBefore(merged, group[0]);
        group.forEach(function (item) {
          item.remove();
        });
        changed = true;
        childTags = Array.prototype.slice.call(parent.children).filter(function (node) {
          return node.nodeType === 1;
        });
        i = childTags.indexOf(merged) + 1;
      }
    });
    return changed;
  }

  function repairBulletDiv(div) {
    if (div.querySelector("ul." + ARTICLE_LIST_CLASS)) {
      return false;
    }
    if (!/<br\s*\/?>/i.test(div.innerHTML)) {
      return false;
    }
    var nodes = Array.prototype.slice.call(div.childNodes);
    var segments = splitNodesByBr(nodes);
    var bulletCount = segments.filter(isBulletSegment).length;
    if (bulletCount < 1 || segments.length < 2) {
      return false;
    }
    if (bulletCount >= 2) {
      var bulletIndices = segments.reduce(function (acc, segment, index) {
        if (isBulletSegment(segment)) {
          acc.push(index);
        }
        return acc;
      }, []);
      var firstBullet = bulletIndices[0];
      var lastBullet = bulletIndices[bulletIndices.length - 1];
      for (var index = firstBullet; index <= lastBullet; index += 1) {
        if (!isBulletSegment(segments[index])) {
          return false;
        }
      }
    }
    while (div.firstChild) {
      div.removeChild(div.firstChild);
    }
    var bulletBatch = [];
    var changed = false;
    function flushBatch() {
      if (!bulletBatch.length) {
        return;
      }
      div.appendChild(makeBulletList(bulletBatch));
      bulletBatch = [];
      changed = true;
    }
    segments.forEach(function (segment, segmentIndex) {
      if (isBulletSegment(segment)) {
        bulletBatch.push(segment);
        return;
      }
      flushBatch();
      appendNodes(div, segment);
      var nextSegment = segments[segmentIndex + 1];
      if (nextSegment && !isBulletSegment(nextSegment)) {
        div.appendChild(document.createElement("br"));
      }
    });
    flushBatch();
    return changed;
  }

  function directEdgeList(container, edge) {
    var childTags = Array.prototype.slice.call(container.children).filter(function (node) {
      return node.nodeType === 1;
    });
    if (!childTags.length) {
      return null;
    }
    var target = edge === "last" ? childTags[childTags.length - 1] : childTags[0];
    if (target.nodeName !== "UL" || !target.classList.contains(ARTICLE_LIST_CLASS)) {
      return null;
    }
    return target;
  }

  function mergeAdjacentDivBulletLists(root) {
    var changed = false;
    Array.prototype.slice.call(root.querySelectorAll("*")).forEach(function (parent) {
      var childTags = Array.prototype.slice.call(parent.children).filter(function (node) {
        return node.nodeType === 1;
      });
      var i = 0;
      while (i < childTags.length - 1) {
        var current = childTags[i];
        var nxt = childTags[i + 1];
        if (!current.classList.contains("mantine-172zsy7") || !nxt.classList.contains("mantine-172zsy7")) {
          i += 1;
          continue;
        }
        var trailing = directEdgeList(current, "last");
        var leading = directEdgeList(nxt, "first");
        if (!trailing || !leading) {
          i += 1;
          continue;
        }
        Array.prototype.slice.call(leading.children).forEach(function (li) {
          if (li.nodeName === "LI") {
            trailing.appendChild(li);
          }
        });
        leading.remove();
        changed = true;
        childTags = Array.prototype.slice.call(parent.children).filter(function (node) {
          return node.nodeType === 1;
        });
        i += 1;
      }
    });
    return changed;
  }

  function mergeConsecutiveBulletDivs(root) {
    var changed = false;
    Array.prototype.slice.call(root.querySelectorAll("*")).forEach(function (parent) {
      var childTags = Array.prototype.slice.call(parent.children).filter(function (node) {
        return node.nodeType === 1;
      });
      var i = 0;
      while (i < childTags.length) {
        if (!divIsBulletOnly(childTags[i])) {
          i += 1;
          continue;
        }
        var group = [childTags[i]];
        var j = i + 1;
        while (j < childTags.length && divIsBulletOnly(childTags[j])) {
          group.push(childTags[j]);
          j += 1;
        }
        var segments = group.map(function (item) {
          return Array.prototype.slice.call(item.childNodes);
        });
        var ul = makeBulletList(segments);
        group[0].parentNode.insertBefore(ul, group[0]);
        group.forEach(function (item) {
          item.remove();
        });
        changed = true;
        childTags = Array.prototype.slice.call(parent.children).filter(function (node) {
          return node.nodeType === 1;
        });
        i = childTags.indexOf(ul) + 1;
      }
    });
    return changed;
  }

  function divIsLoneBulletLiDiv(div) {
    if (!div.classList.contains("css-1vd3b3g") || !div.classList.contains("mantine-1jggmkl")) {
      return false;
    }
    if (div.querySelector("ul." + ARTICLE_LIST_CLASS) || div.querySelector("ol." + NUMBERED_LIST_CLASS)) {
      return false;
    }
    var lis = Array.prototype.slice.call(div.children).filter(function (node) {
      return node.nodeName === "LI";
    });
    if (lis.length !== 1) {
      return false;
    }
    var text = (lis[0].textContent || "").replace(/\s+/g, " ").trim();
    return BULLET_PREFIX_RE.test(text);
  }

  function liFromLoneBulletDiv(div) {
    var sourceLi = div.querySelector(":scope > li");
    var li = document.createElement("li");
    trimEdgeBreaks(sourceLi.childNodes).forEach(function (node) {
      li.appendChild(node);
    });
    stripBulletPrefix(li);
    while (li.lastChild) {
      var node = li.lastChild;
      if (node.nodeType === 3 && !node.textContent.trim()) {
        li.removeChild(node);
        continue;
      }
      if (node.nodeType === 1 && node.nodeName === "BR") {
        li.removeChild(node);
        continue;
      }
      break;
    }
    while (li.firstChild) {
      var leading = li.firstChild;
      if (leading.nodeType === 3 && !leading.textContent.trim()) {
        li.removeChild(leading);
        continue;
      }
      if (leading.nodeType === 1 && leading.nodeName === "BR") {
        li.removeChild(leading);
        continue;
      }
      break;
    }
    return li;
  }

  function mergeConsecutiveLoneLiBulletDivs(root) {
    var changed = false;
    Array.prototype.slice.call(root.querySelectorAll("*")).forEach(function (parent) {
      var childTags = Array.prototype.slice.call(parent.children).filter(function (node) {
        return node.nodeType === 1;
      });
      var i = 0;
      while (i < childTags.length) {
        if (!divIsLoneBulletLiDiv(childTags[i])) {
          i += 1;
          continue;
        }
        var group = [childTags[i]];
        var j = i + 1;
        while (j < childTags.length && divIsLoneBulletLiDiv(childTags[j])) {
          group.push(childTags[j]);
          j += 1;
        }
        var ul = document.createElement("ul");
        ul.className = ARTICLE_LIST_CLASS;
        group.forEach(function (item) {
          ul.appendChild(liFromLoneBulletDiv(item));
        });
        group[0].parentNode.insertBefore(ul, group[0]);
        group.forEach(function (item) {
          item.remove();
        });
        changed = true;
        childTags = Array.prototype.slice.call(parent.children).filter(function (node) {
          return node.nodeType === 1;
        });
        i = childTags.indexOf(ul) + 1;
      }
    });
    return changed;
  }

  function isNumberedSegment(nodes) {
    return NUMBERED_PREFIX_RE.test(segmentText(nodes));
  }

  function stripNumberedPrefix(container) {
    var walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null);
    var node = walker.nextNode();
    while (node) {
      var next = walker.nextNode();
      var text = node.textContent || "";
      if (text.trim()) {
        node.textContent = text.replace(NUMBERED_PREFIX_RE, "");
        return;
      }
      node = next;
    }
  }

  function makeNumberedList(segments) {
    var ol = document.createElement("ol");
    ol.className = NUMBERED_LIST_CLASS;
    segments.forEach(function (segment) {
      var li = document.createElement("li");
      appendNodes(li, segment);
      stripNumberedPrefix(li);
      ol.appendChild(li);
    });
    return ol;
  }

  function divIsNumberedOnly(div) {
    if (!div.classList.contains("mantine-172zsy7")) {
      return false;
    }
    if (div.querySelector("ul." + ARTICLE_LIST_CLASS) || div.querySelector("ol." + NUMBERED_LIST_CLASS)) {
      return false;
    }
    var text = (div.textContent || "").replace(/\s+/g, " ").trim();
    if (!NUMBERED_PREFIX_RE.test(text) || BULLET_PREFIX_RE.test(text)) {
      return false;
    }
    return meaningfulBrCount(div) === 0;
  }

  function repairNumberedDiv(div) {
    if (div.querySelector("ol." + NUMBERED_LIST_CLASS)) {
      return false;
    }
    if (!/<br\s*\/?>/i.test(div.innerHTML)) {
      return false;
    }
    var nodes = Array.prototype.slice.call(div.childNodes);
    var segments = splitNodesByBr(nodes);
    var numberedCount = segments.filter(isNumberedSegment).length;
    if (numberedCount < 2) {
      return false;
    }
    var numberedIndices = segments.reduce(function (acc, segment, index) {
      if (isNumberedSegment(segment)) {
        acc.push(index);
      }
      return acc;
    }, []);
    var firstNumbered = numberedIndices[0];
    var lastNumbered = numberedIndices[numberedIndices.length - 1];
    for (var index = firstNumbered; index <= lastNumbered; index += 1) {
      if (!isNumberedSegment(segments[index])) {
        return false;
      }
    }
    while (div.firstChild) {
      div.removeChild(div.firstChild);
    }
    var numberedBatch = [];
    var changed = false;
    function flushBatch() {
      if (!numberedBatch.length) {
        return;
      }
      div.appendChild(makeNumberedList(numberedBatch));
      numberedBatch = [];
      changed = true;
    }
    segments.forEach(function (segment, segmentIndex) {
      if (isNumberedSegment(segment)) {
        numberedBatch.push(segment);
        return;
      }
      flushBatch();
      appendNodes(div, segment);
      var nextSegment = segments[segmentIndex + 1];
      if (nextSegment && !isNumberedSegment(nextSegment)) {
        div.appendChild(document.createElement("br"));
      }
    });
    flushBatch();
    return changed;
  }

  function mergeConsecutiveNumberedDivs(root) {
    var changed = false;
    Array.prototype.slice.call(root.querySelectorAll("*")).forEach(function (parent) {
      var childTags = Array.prototype.slice.call(parent.children).filter(function (node) {
        return node.nodeType === 1;
      });
      var i = 0;
      while (i < childTags.length) {
        if (!divIsNumberedOnly(childTags[i])) {
          i += 1;
          continue;
        }
        var group = [childTags[i]];
        var j = i + 1;
        while (j < childTags.length && divIsNumberedOnly(childTags[j])) {
          group.push(childTags[j]);
          j += 1;
        }
        var segments = group.map(function (item) {
          return trimEdgeBreaks(item.childNodes);
        });
        var ol = makeNumberedList(segments);
        group[0].parentNode.insertBefore(ol, group[0]);
        group.forEach(function (item) {
          item.remove();
        });
        changed = true;
        childTags = Array.prototype.slice.call(parent.children).filter(function (node) {
          return node.nodeType === 1;
        });
        i = childTags.indexOf(ol) + 1;
      }
    });
    return changed;
  }

  function mergeNumberedListsAcrossAnnotations(root) {
    var changed = false;
    Array.prototype.slice.call(root.querySelectorAll("*")).forEach(function (parent) {
      var childTags = Array.prototype.slice.call(parent.children).filter(function (node) {
        return node.nodeType === 1;
      });
      var i = 0;
      while (i < childTags.length) {
        var child = childTags[i];
        if (child.nodeName !== "OL" || !child.classList.contains(NUMBERED_LIST_CLASS)) {
          i += 1;
          continue;
        }
        var group = [child];
        var j = i + 1;
        while (j < childTags.length) {
          var nxt = childTags[j];
          if (isAnnotationDiv(nxt)) {
            j += 1;
            continue;
          }
          if (nxt.nodeName === "OL" && nxt.classList.contains(NUMBERED_LIST_CLASS)) {
            group.push(nxt);
            j += 1;
            continue;
          }
          if (divIsNumberedOnly(nxt)) {
            group.push(nxt);
            j += 1;
            continue;
          }
          break;
        }
        if (group.length < 2) {
          i += 1;
          continue;
        }
        var merged = document.createElement("ol");
        merged.className = NUMBERED_LIST_CLASS;
        group.forEach(function (item) {
          if (item.nodeName === "OL") {
            Array.prototype.slice.call(item.children).forEach(function (li) {
              if (li.nodeName === "LI") {
                merged.appendChild(li);
              }
            });
            return;
          }
          var li = document.createElement("li");
          appendNodes(li, trimEdgeBreaks(item.childNodes));
          stripNumberedPrefix(li);
          merged.appendChild(li);
        });
        group[0].parentNode.insertBefore(merged, group[0]);
        group.forEach(function (item) {
          item.remove();
        });
        changed = true;
        childTags = Array.prototype.slice.call(parent.children).filter(function (node) {
          return node.nodeType === 1;
        });
        i = childTags.indexOf(merged) + 1;
      }
    });
    return changed;
  }

  function repairNumberedLists() {
    var content = document.querySelector(".internal-article-content");
    if (!content) {
      return;
    }
    Array.prototype.slice.call(content.querySelectorAll(".mantine-172zsy7")).forEach(function (div) {
      repairNumberedDiv(div);
    });
    mergeConsecutiveNumberedDivs(content);
    mergeNumberedListsAcrossAnnotations(content);
  }

  function stripEdgeBreaksFromTag(container) {
    var changed = false;
    while (container.lastChild) {
      var node = container.lastChild;
      if (node.nodeType === 1 && node.nodeName === "BR") {
        container.removeChild(node);
        changed = true;
        continue;
      }
      if (node.nodeType === 3 && !node.textContent.trim()) {
        container.removeChild(node);
        changed = true;
        continue;
      }
      break;
    }
    while (container.firstChild) {
      var first = container.firstChild;
      if (first.nodeType === 1 && first.nodeName === "BR") {
        container.removeChild(first);
        changed = true;
        continue;
      }
      if (first.nodeType === 3 && !first.textContent.trim()) {
        container.removeChild(first);
        changed = true;
        continue;
      }
      break;
    }
    return changed;
  }

  function collapseConsecutiveBreaks(container) {
    var changed = false;
    var previousWasBreak = false;
    Array.prototype.slice.call(container.childNodes).forEach(function (node) {
      if (node.nodeType === 1 && node.nodeName === "BR") {
        if (previousWasBreak) {
          node.remove();
          changed = true;
          return;
        }
        previousWasBreak = true;
        return;
      }
      if (node.nodeType === 3 && !node.textContent.trim()) {
        return;
      }
      previousWasBreak = false;
    });
    return changed;
  }

  function isEmptyTextContainer(el) {
    if ((el.textContent || "").trim()) {
      return false;
    }
    return !el.querySelector("img, a, table, ul, ol, iframe, svg, video, audio");
  }

  function removeParagraphSpacerBreaks() {
    var content = document.querySelector(".internal-article-content");
    if (!content) {
      return;
    }
    Array.prototype.slice.call(content.querySelectorAll(".mantine-172zsy7, p, .internal-article-intro")).forEach(function (el) {
      if (
        el.closest(".site-search-page") ||
        el.hasAttribute("data-site-search-meta") ||
        el.classList.contains("about-page__lead") ||
        el.closest(".about-page__intro")
      ) {
        return;
      }
      collapseConsecutiveBreaks(el);
      stripEdgeBreaksFromTag(el);
      if (isEmptyTextContainer(el)) {
        el.remove();
      }
    });
  }

  function trimLeadingText(container) {
    var changed = false;
    var walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null);
    var node = walker.nextNode();
    while (node) {
      var text = node.textContent || "";
      if (!text.trim()) {
        if (text) {
          node.textContent = "";
          changed = true;
        }
        node = walker.nextNode();
        continue;
      }
      var trimmed = text.replace(LEADING_WS_RE, "");
      if (trimmed !== text) {
        node.textContent = trimmed;
        changed = true;
      }
      return changed;
    }
    return changed;
  }

  function trimLeadingParagraphWhitespace() {
    var content = document.querySelector(".internal-article-content");
    if (!content) {
      return;
    }
    content.querySelectorAll(".mantine-172zsy7, p, .internal-article-intro").forEach(function (el) {
      trimLeadingText(el);
    });
  }

  function continuationStartsLowercase(text) {
    var stripped = (text || "").replace(/^\s+/, "");
    if (!stripped) {
      return false;
    }
    var ch = stripped.charAt(0);
    return ch === ch.toLowerCase() && ch !== ch.toUpperCase() || ch === "і" || ch === "ї" || ch === "є";
  }

  function liBoldLeadTag(li) {
    var node = li.firstChild;
    while (node) {
      if (node.nodeType === 3 && !node.textContent.trim()) {
        node = node.nextSibling;
        continue;
      }
      if (node.nodeType === 1 && (node.nodeName === "B" || node.nodeName === "STRONG") && node.textContent.trim()) {
        return node;
      }
      return null;
    }
    return null;
  }

  function liContinuationText(li, bold) {
    var parts = [];
    var afterBold = false;
    var node = li.firstChild;
    while (node) {
      if (node === bold) {
        afterBold = true;
        node = node.nextSibling;
        continue;
      }
      if (afterBold) {
        parts.push(node.nodeType === 3 ? node.textContent : node.textContent);
      }
      node = node.nextSibling;
    }
    return parts.join("");
  }

  function splitBoldLeadFromSingleItemList(ul) {
    if (!ul.classList.contains(ARTICLE_LIST_CLASS)) {
      return false;
    }
    var lis = Array.prototype.slice.call(ul.children).filter(function (node) {
      return node.nodeName === "LI";
    });
    if (lis.length !== 1) {
      return false;
    }
    var li = lis[0];
    var bold = liBoldLeadTag(li);
    if (!bold) {
      return false;
    }
    var boldText = (bold.textContent || "").trim();
    if (boldText.length < 15) {
      return false;
    }
    if (!continuationStartsLowercase(liContinuationText(li, bold))) {
      return false;
    }
    var continuationNodes = [];
    var afterBold = false;
    Array.prototype.slice.call(li.childNodes).forEach(function (node) {
      if (node === bold) {
        afterBold = true;
        return;
      }
      if (afterBold) {
        continuationNodes.push(node);
      }
    });
    var div = document.createElement("div");
    div.className = "mantine-Text-root mantine-172zsy7";
    div.appendChild(bold);
    ul.parentNode.insertBefore(div, ul);
    while (li.firstChild) {
      li.removeChild(li.firstChild);
    }
    continuationNodes.forEach(function (node) {
      li.appendChild(node);
    });
    if (li.firstChild && li.firstChild.nodeType === 3) {
      li.firstChild.textContent = li.firstChild.textContent.replace(/^\s+/, "");
    }
    return true;
  }

  function stripLeadingBreaksFromLi(li) {
    var changed = false;
    while (li.firstChild) {
      var node = li.firstChild;
      if (node.nodeType === 3 && !node.textContent.trim()) {
        li.removeChild(node);
        changed = true;
        continue;
      }
      if (node.nodeType === 1 && node.nodeName === "BR") {
        li.removeChild(node);
        changed = true;
        continue;
      }
      if (node.nodeType === 1 && (node.nodeName === "B" || node.nodeName === "STRONG") && !node.textContent.trim()) {
        li.removeChild(node);
        changed = true;
        continue;
      }
      break;
    }
    return changed;
  }

  function stripTrailingBreaksFromLi(li) {
    var changed = false;
    while (li.lastChild) {
      var node = li.lastChild;
      if (node.nodeType === 3 && !node.textContent.trim()) {
        li.removeChild(node);
        changed = true;
        continue;
      }
      if (node.nodeType === 1 && node.nodeName === "BR") {
        li.removeChild(node);
        changed = true;
        continue;
      }
      break;
    }
    return changed;
  }

  function collapseArticleWhitespace() {
    var content = document.querySelector(".internal-article-content");
    if (!content) {
      return;
    }
    var walker = document.createTreeWalker(content, NodeFilter.SHOW_TEXT, null);
    var node = walker.nextNode();
    while (node) {
      var parent = node.parentNode;
      if (parent && (parent.nodeName === "SCRIPT" || parent.nodeName === "STYLE")) {
        node = walker.nextNode();
        continue;
      }
      var text = node.textContent || "";
      if (!text) {
        node = walker.nextNode();
        continue;
      }
      var normalized = text.replace(/[ \u00a0\t]+/g, " ");
      if (!normalized.trim()) {
        if (text) {
          node.textContent = "";
        }
      } else if (normalized !== text) {
        node.textContent = normalized;
      }
      node = walker.nextNode();
    }
  }

  function repairSplitListLeads() {
    var content = document.querySelector(".internal-article-content");
    if (!content) {
      return;
    }
    Array.prototype.slice.call(content.querySelectorAll("ul." + ARTICLE_LIST_CLASS)).forEach(function (ul) {
      splitBoldLeadFromSingleItemList(ul);
    });
    content.querySelectorAll("ul." + ARTICLE_LIST_CLASS + " > li, ol." + NUMBERED_LIST_CLASS + " > li").forEach(function (li) {
      stripLeadingBreaksFromLi(li);
      stripTrailingBreaksFromLi(li);
    });
  }

  function repairDashBulletLists() {
    var content = document.querySelector(".internal-article-content");
    if (!content) {
      return;
    }
    mergeConsecutiveLoneLiBulletDivs(content);
    Array.prototype.slice.call(content.querySelectorAll(".mantine-172zsy7")).forEach(function (div) {
      repairBulletDiv(div);
    });
    mergeConsecutiveBulletDivs(content);
    mergeAdjacentDivBulletLists(content);
    convertSingletonBulletDivs(content);
    mergeBulletListsAcrossAnnotations(content);
    trimLeadingParagraphWhitespace();
    removeParagraphSpacerBreaks();
    repairNumberedLists();
    repairSplitListLeads();
    collapseArticleWhitespace();
  }

  function hideStageInterlinks() {
    document.querySelectorAll(".css-1sz33jp").forEach(function (wrap) {
      wrap.querySelectorAll(
        ":scope > .css-1tq4v0d, :scope > .mantine-Carousel-root, :scope > [class*='mantine-Carousel-root']"
      ).forEach(function (el) {
        el.style.setProperty("display", "none", "important");
      });
    });

    document.querySelectorAll("a.css-lnlfjp, a.css-1wi3il6").forEach(function (link) {
      var row = link.closest(".css-1tq4v0d, .mantine-Carousel-root, [class*='mantine-Carousel-root']");
      if (row) {
        row.style.setProperty("display", "none", "important");
      }
    });

    document.querySelectorAll(".css-1iehrax, .mantine-73o8aw.css-1iehrax").forEach(function (el) {
      el.style.setProperty("display", "none", "important");
    });

    document.querySelectorAll(".internal-main").forEach(function (contentHost) {
      if (!contentHost.querySelector(".internal-article-toc")) {
        return;
      }
      contentHost.querySelectorAll(":scope > section.css-1napgkq, :scope > section.css-1m99gl8").forEach(function (section) {
        if (section.querySelector(".css-2y3zsr, .css-1sz33jp")) {
          section.remove();
        }
      });
      contentHost.querySelectorAll(":scope > .css-12mrpgq, :scope > .css-gfn0ts, :scope > .css-2y3zsr").forEach(function (node) {
        node.remove();
      });
    });
  }

  function removeDuplicateArticleTitle(mainCol, titleText) {
    if (!mainCol || !titleText) {
      return;
    }

    var titleBlock = mainCol.querySelector(".css-153xe5m");
    if (titleBlock) {
      titleBlock.remove();
    }

    mainCol.querySelectorAll("h2, h3").forEach(function (heading) {
      if (heading.textContent.trim() === titleText) {
        heading.remove();
      }
    });
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/"/g, "&quot;");
  }

  function getSectionTitle(sectionEl) {
    var heading = sectionEl.querySelector(
      ".mantine-Accordion-label h2, .mantine-Accordion-label h4, .mantine-Accordion-label .mantine-Title-root, .mantine-Accordion-label .mantine-Text-root"
    );
    if (heading) {
      var title = heading.textContent.trim();
      if (title) {
        return title;
      }
    }

    var id = sectionEl.getAttribute("id");
    return id ? id.replace(/_/g, " ") : "";
  }

  var tocEntrySelector =
    ".css-sdnfq3[id], section[id], .mantine-wnhdd8[id], " +
    ".mantine-1ng34cm[id], .css-g0tr8[id], h2[id], h3[id]";

  function getTocEntryTitle(el) {
    if (el.classList.contains("mantine-wnhdd8")) {
      var stageHeading = el.querySelector(
        ".css-sdnfq3 > h2.internal-section-h2, .css-sdnfq3 > h2, .mantine-j9g3bi > h2, h2, h3"
      );
      if (stageHeading && stageHeading.textContent.trim()) {
        return stageHeading.textContent.trim();
      }
    }

    var title = getSectionTitle(el);
    if (title) {
      return title;
    }

    var heading = el.querySelector("h2, h3, h4");
    if (heading && heading.textContent.trim()) {
      return heading.textContent.trim();
    }

    if (el.matches("h2, h3, h4") && el.textContent.trim()) {
      return el.textContent.trim();
    }

    var id = el.getAttribute("id");
    return id ? id.replace(/_/g, " ") : "";
  }

  function collectTocEntries(mainCol) {
    var entries = [];
    var seen = Object.create(null);

    mainCol.querySelectorAll(tocEntrySelector).forEach(function (el) {
      var id = el.getAttribute("id");
      if (!id || seen[id]) {
        return;
      }
      seen[id] = true;
      var title = getTocEntryTitle(el);
      if (!title) {
        return;
      }
      entries.push({
        id: id,
        title: title,
        docCount: countSectionDownloads(el),
      });
    });

    return entries;
  }

  function ukrainianDocumentCountLabel(count) {
    if (count === 1) {
      return "1 документ";
    }
    if (count >= 2 && count <= 4) {
      return count + " документи";
    }
    return count + " документів";
  }

  function normalizeSectionId(value) {
    return String(value || "")
      .replace(/«|»/g, '"')
      .replace(/\u201c|\u201d/g, '"');
  }

  function countSectionDownloads(section) {
    if (!section) {
      return 0;
    }
    var scope = section;
    if (
      section.matches("h2, h3") ||
      section.classList.contains("internal-section-h2")
    ) {
      var card = section.closest(".css-sdnfq3");
      if (card) {
        scope = card;
      }
    }
    return scope.querySelectorAll('a.css-uex5rt img[alt="file-icon"]').length;
  }

  function parseLegacyTocDocCount(node) {
    if (!node) {
      return 0;
    }
    var match = String(node.textContent || "").match(/(\d+)/);
    return match ? parseInt(match[1], 10) : 0;
  }

  function buildTocDocBadgeHtml(count) {
    if (!count || count <= 0) {
      return "";
    }
    var label = ukrainianDocumentCountLabel(count);
    var aria =
      count === 1
        ? "1 документ для завантаження"
        : count <= 4
          ? count + " документи для завантаження"
          : count + " документів для завантаження";
    return (
      '<span class="internal-toc-doc-badge" aria-label="' +
      escapeHtml(aria) +
      '">' +
      '<img src="' +
      TOC_DOC_BADGE_ICON +
      '" alt="" width="12" height="12" aria-hidden="true" />' +
      '<span class="internal-toc-doc-badge__text">' +
      escapeHtml(label) +
      "</span></span>"
    );
  }

  function getTocItemContainer(link) {
    return (
      link.closest(".internal-toc-item-text, .mantine-12e74aa") || link.parentElement
    );
  }

  function normalizeTocDocumentBadges(tocWrap, mainCol) {
    if (!tocWrap) {
      return false;
    }

    var changed = false;
    tocWrap.querySelectorAll(".mantine-List-item").forEach(function (item) {
      var link = item.querySelector("a[href*='#']");
      if (!link) {
        return;
      }

      var container = getTocItemContainer(link);
      if (!container) {
        return;
      }

      var legacy = container.querySelector(".mantine-16hexn0");
      if (legacy) {
        legacy.remove();
        changed = true;
      }

      var docCount = 0;
      if (mainCol) {
        var sectionId = getTocHashId(link.getAttribute("href"));
        var section = findSectionById(mainCol, sectionId);
        if (section) {
          var actualId = section.getAttribute("id");
          if (actualId && actualId !== sectionId) {
            link.setAttribute("href", "#" + actualId);
            changed = true;
          }
          docCount = countSectionDownloads(section);
        }
      }

      var title = link.textContent.trim().replace(/\s*x\s*\d+\s*$/i, "").trim();
      if (title !== link.textContent.trim()) {
        link.textContent = title;
        changed = true;
      }

      if (!container.classList.contains("internal-toc-item-text")) {
        container.classList.add("internal-toc-item-text");
        changed = true;
      }

      var existingBadge = container.querySelector(".internal-toc-doc-badge");
      if (existingBadge) {
        existingBadge.remove();
        changed = true;
      }

      var badgeHtml = buildTocDocBadgeHtml(docCount);
      if (badgeHtml) {
        container.insertAdjacentHTML("beforeend", badgeHtml);
        changed = true;
      }
    });

    return changed;
  }

  function collectTocDocCountsFromWrap(tocWrap) {
    var counts = [];
    if (!tocWrap) {
      return counts;
    }
    tocWrap.querySelectorAll(".mantine-List-item").forEach(function (item) {
      var badgeText = item.querySelector(".internal-toc-doc-badge__text");
      counts.push(parseLegacyTocDocCount(badgeText));
    });
    return counts;
  }

  function buildGeneratedTocHtml(entries) {
    var items = entries
      .map(function (entry) {
        var badge = buildTocDocBadgeHtml(entry.docCount || 0);
        return (
          '<li class="mantine-List-item mantine-riob0u" data-with-icon="true">' +
          '<div class="___ref-itemWrapper mantine-iwg4hh mantine-List-itemWrapper">' +
          '<span class="mantine-uezznj mantine-List-itemIcon">' +
          '<div class="mantine-ThemeIcon-root mantine-1tnkqq"></div></span>' +
          '<span><div class="internal-toc-item-text mantine-12e74aa"><a class="css-16clbz5" href="#' +
          encodeURIComponent(entry.id) +
          '">' +
          escapeHtml(entry.title) +
          "</a>" +
          badge +
          "</div></span></div></li>"
        );
      })
      .join("");

    return (
      '<div class="css-gfn0ts mantine-1fr50if internal-toc-generated">' +
      '<div class="mantine-1fr50if">' +
      '<h4 class="mantine-Text-root mantine-Title-root mantine-1pop5c3">Зміст сторінки</h4>' +
      '<ul class="mantine-List-root mantine-e6qakj">' +
      items +
      "</ul></div></div>"
    );
  }

  function generatedTocNeedsUpgrade(tocWrap) {
    var generated = tocWrap && tocWrap.querySelector(".internal-toc-generated");
    if (!generated) {
      return true;
    }
    if (
      !(
        generated.querySelector("h4.mantine-1pop5c3") &&
        generated.querySelector("ul.mantine-e6qakj") &&
        generated.querySelector(".mantine-List-item.mantine-riob0u")
      )
    ) {
      return true;
    }
    if (tocWrap.querySelector(".mantine-16hexn0")) {
      return true;
    }
    if (!generated.querySelector(".internal-toc-item-text")) {
      return true;
    }
    return false;
  }

  function tocWrapMatchesEntries(tocWrap, entries) {
    var links = [];
    tocWrap.querySelectorAll(".mantine-List-item a[href*='#']").forEach(function (link) {
      links.push({
        id: getTocHashId(link.getAttribute("href")),
        title: link.textContent.trim(),
      });
    });
    if (links.length !== entries.length) {
      return false;
    }
    for (var i = 0; i < entries.length; i += 1) {
      if (links[i].id !== entries[i].id || links[i].title !== entries[i].title) {
        return false;
      }
      if (collectTocDocCountsFromWrap(tocWrap)[i] !== (entries[i].docCount || 0)) {
        return false;
      }
    }
    return true;
  }

  function ensureGeneratedToc(tocWrap, mainCol) {
    if (!tocWrap || !mainCol) {
      return false;
    }

    if (
      tocWrap.querySelector(".css-gfn0ts:not(.internal-toc-generated)") ||
      tocWrap.querySelector(".css-12mrpgq")
    ) {
      return false;
    }

    var entries = collectTocEntries(mainCol);
    if (!entries.length) {
      return false;
    }

    var generated = tocWrap.querySelector(".internal-toc-generated");
    if (
      generated &&
      tocWrapMatchesEntries(tocWrap, entries) &&
      !generatedTocNeedsUpgrade(tocWrap)
    ) {
      return true;
    }
    if (generated) {
      generated.outerHTML = buildGeneratedTocHtml(entries);
      return true;
    }

    if (!tocWrap.querySelector(".css-gfn0ts, .css-12mrpgq")) {
      tocWrap.insertAdjacentHTML("beforeend", buildGeneratedTocHtml(entries));
      return true;
    }

    return false;
  }

  function findSectionById(root, id) {
    if (!id || !root) {
      return null;
    }

    if (typeof CSS !== "undefined" && CSS.escape) {
      var byQuery = root.querySelector("#" + CSS.escape(id));
      if (byQuery) {
        return byQuery;
      }
    }

    var sections = root.querySelectorAll(
      ".css-sdnfq3[id], section[id], .mantine-wnhdd8[id], h2[id], h3[id]"
    );
    var target = normalizeSectionId(id);
    for (var i = 0; i < sections.length; i++) {
      var sectionId = sections[i].getAttribute("id") || "";
      if (sectionId === id || normalizeSectionId(sectionId) === target) {
        return sections[i];
      }
    }

    var byId = document.getElementById(id);
    if (byId) {
      return byId;
    }

    return null;
  }

  function getTocHashId(href) {
    if (!href) {
      return "";
    }

    var hashIndex = href.indexOf("#");
    if (hashIndex === -1) {
      return "";
    }

    try {
      return decodeURIComponent(href.slice(hashIndex + 1));
    } catch (error) {
      return href.slice(hashIndex + 1);
    }
  }

  function getScrollSpyOffset() {
    var raw = getComputedStyle(document.documentElement)
      .getPropertyValue("--internal-toc-sticky-top")
      .trim();
    var parsed = parseInt(raw, 10);
    return Number.isFinite(parsed) ? parsed + 8 : 168;
  }

  function scrollToTocSection(section) {
    if (!section) {
      return;
    }

    var offset = getScrollSpyOffset();
    var top = section.getBoundingClientRect().top + window.pageYOffset - offset;
    window.scrollTo({
      top: Math.max(0, top),
      behavior: "smooth",
    });
  }

  var figureLightboxEl = null;
  var figureLightboxEscapeHandler = null;
  var figureLightboxPreviousOverflow = "";

  function ensureFigureLightbox() {
    if (figureLightboxEl) {
      return figureLightboxEl;
    }

    figureLightboxEl = document.createElement("div");
    figureLightboxEl.className = "internal-figure-lightbox";
    figureLightboxEl.hidden = true;
    figureLightboxEl.setAttribute("role", "dialog");
    figureLightboxEl.setAttribute("aria-modal", "true");
    figureLightboxEl.setAttribute("aria-label", "Перегляд зображення");
    figureLightboxEl.innerHTML =
      '<button type="button" class="internal-figure-lightbox__close" aria-label="Закрити">×</button>' +
      '<div class="internal-figure-lightbox__backdrop" aria-hidden="true"></div>' +
      '<img class="internal-figure-lightbox__image" alt="" decoding="async" />';

    var closeButton = figureLightboxEl.querySelector(".internal-figure-lightbox__close");
    closeButton.addEventListener("click", function (event) {
      event.preventDefault();
      closeFigureLightbox();
    });

    document.body.appendChild(figureLightboxEl);
    return figureLightboxEl;
  }

  function closeFigureLightbox() {
    if (!figureLightboxEl || figureLightboxEl.hidden) {
      return;
    }

    figureLightboxEl.hidden = true;
    document.body.style.overflow = figureLightboxPreviousOverflow;
    if (figureLightboxEscapeHandler) {
      document.removeEventListener("keydown", figureLightboxEscapeHandler);
      figureLightboxEscapeHandler = null;
    }
  }

  function openFigureLightbox(src, alt) {
    if (!src) {
      return;
    }

    var lightbox = ensureFigureLightbox();
    var image = lightbox.querySelector(".internal-figure-lightbox__image");
    image.src = src;
    image.alt = alt || "";
    figureLightboxPreviousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    lightbox.hidden = false;

    var closeButton = lightbox.querySelector(".internal-figure-lightbox__close");
    if (closeButton) {
      closeButton.focus();
    }

    if (!figureLightboxEscapeHandler) {
      figureLightboxEscapeHandler = function (event) {
        if (event.key === "Escape") {
          closeFigureLightbox();
        }
      };
      document.addEventListener("keydown", figureLightboxEscapeHandler);
    }
  }

  function bindArticleFigureLightbox(contentHost) {
    if (!contentHost || contentHost.dataset.figureLightboxBound) {
      return;
    }

    contentHost.dataset.figureLightboxBound = "1";
    contentHost.addEventListener("click", function (event) {
      var trigger = event.target.closest(
        ".internal-article-figure__trigger, .internal-article-figure img"
      );
      if (!trigger || !trigger.closest(".internal-article-content")) {
        return;
      }

      var img = trigger.matches("img") ? trigger : trigger.querySelector("img");
      if (!img) {
        return;
      }

      event.preventDefault();
      openFigureLightbox(img.getAttribute("src"), img.getAttribute("alt") || "");
    });
  }

  function bindArticleTocNavigation(contentHost) {
    if (!contentHost || contentHost.dataset.tocNavBound) {
      return;
    }

    var mainCol =
      contentHost.querySelector(".internal-article-content .css-7nll2u") ||
      contentHost.querySelector(".css-7nll2u");
    if (!mainCol) {
      return;
    }

    contentHost.dataset.tocNavBound = "1";
    contentHost.addEventListener("click", function (event) {
      var link = event.target.closest(
        ".internal-article-toc a[href*='#'], .internal-toc-dropdown a[href*='#']"
      );
      if (!link) {
        return;
      }

      var id = getTocHashId(link.getAttribute("href"));
      var section = findSectionById(mainCol, id);
      if (!section) {
        return;
      }

      event.preventDefault();
      var href = link.getAttribute("href") || "";
      if (href.indexOf("#") === 0) {
        history.pushState(null, "", href);
      }
      scrollToTocSection(section);
    });
  }

  function bindArticleTocSpy(contentHost) {
    if (articleTocSpyCleanup) {
      articleTocSpyCleanup();
      articleTocSpyCleanup = null;
    }

    if (!contentHost) {
      return;
    }

    var tocWrap = contentHost.querySelector(".internal-article-toc");
    var mainCol =
      contentHost.querySelector(".internal-article-content .css-7nll2u") ||
      contentHost.querySelector(".css-7nll2u");
    if (!tocWrap || !mainCol) {
      return;
    }

    var links = tocWrap.querySelectorAll(".mantine-List-item a[href*='#']");
    var items = [];

    links.forEach(function (link) {
      var id = getTocHashId(link.getAttribute("href"));
      var section = findSectionById(mainCol, id);
      var listItem = link.closest(".mantine-List-item");
      if (section && listItem) {
        items.push({ section: section, listItem: listItem });
      }
    });

    if (!items.length) {
      var sections = mainCol.querySelectorAll(".css-sdnfq3[id], section[id]");
      Array.prototype.forEach.call(sections, function (section, index) {
        var listItem = links[index] && links[index].closest(".mantine-List-item");
        if (listItem) {
          items.push({ section: section, listItem: listItem });
        }
      });
    }

    if (!items.length) {
      return;
    }

    function setActive(activeItem) {
      var activeHref = "";
      items.forEach(function (item) {
        var isActive = item === activeItem;
        item.listItem.classList.toggle("internal-toc-item--active", isActive);
        if (isActive) {
          var activeLink = item.listItem.querySelector("a[href*='#']");
          activeHref = activeLink ? activeLink.getAttribute("href") : "";
        }
      });
      syncMobileTocActiveState(contentHost, activeHref);
    }

    function updateActiveSection() {
      var marker = getScrollSpyOffset();
      var activeItem = items[0];

      for (var i = 0; i < items.length; i++) {
        if (items[i].section.getBoundingClientRect().top <= marker) {
          activeItem = items[i];
        }
      }

      setActive(activeItem);
    }

    var onScroll = function () {
      updateActiveSection();
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    updateActiveSection();

    articleTocSpyCleanup = function () {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      items.forEach(function (item) {
        item.listItem.classList.remove("internal-toc-item--active");
      });
    };
  }

  function markArticleIntroText(mainCol) {
    if (!mainCol) {
      return;
    }

    mainCol.querySelectorAll(".internal-article-intro").forEach(function (el) {
      el.classList.remove("internal-article-intro");
    });

    function isIntroElement(el) {
      return (
        (el.matches(".mantine-Text-root") ||
          el.matches("p") ||
          el.matches(".css-tualuh, .css-1xvvgf7")) &&
        !el.classList.contains("css-370pco") &&
        !el.classList.contains("mantine-172zsy7") &&
        !!el.textContent.trim()
      );
    }

    [mainCol].concat(Array.from(mainCol.querySelectorAll(".mantine-1fr50if"))).forEach(
      function (wrapper) {
        Array.from(wrapper.children).forEach(function (child) {
          if (child.classList.contains("css-sdnfq3")) {
            return;
          }

          if (
            isIntroElement(child) &&
            !child.classList.contains("about-page__lead") &&
            !child.closest(".about-page__intro")
          ) {
            child.classList.add("internal-article-intro");
          }
        });
      }
    );
  }

  function fixArticleTocScroll(contentHost) {
    if (!contentHost) {
      return;
    }

    contentHost
      .querySelectorAll(
        ".internal-article-toc .css-gfn0ts, .internal-article-toc .css-12mrpgq, .internal-article-toc .css-gfn0ts > div, .internal-article-toc .css-12mrpgq > div, .internal-article-toc .mantine-List-root"
      )
      .forEach(function (el) {
        el.style.removeProperty("height");
        el.style.removeProperty("max-height");
        el.style.setProperty("overflow", "visible", "important");
        el.style.setProperty("overflow-y", "visible", "important");
      });

    var tocHeading = contentHost.querySelector(".internal-article-toc h4.mantine-Title-root");
    if (tocHeading && tocHeading.textContent.trim() === "Зміст") {
      tocHeading.textContent = "Зміст сторінки";
    }

    contentHost.querySelectorAll(".internal-article-toc a[href*='#']").forEach(function (link) {
      var id = getTocHashId(link.getAttribute("href"));
      if (id) {
        link.setAttribute("href", "#" + id);
      }
    });

    var tocWrap = contentHost.querySelector(".internal-article-toc");
    var mainCol =
      contentHost.querySelector(".css-7nll2u") ||
      contentHost.querySelector(".internal-article-content");
    if (tocWrap && mainCol) {
      normalizeTocDocumentBadges(tocWrap, mainCol);
    }
  }

  function expandArticleAccordions(contentHost) {
    if (!contentHost) {
      return;
    }

    contentHost.querySelectorAll("[data-accordion-control]").forEach(function (control) {
      control.setAttribute("aria-expanded", "true");
      control.setAttribute("data-active", "true");

      var panelId = control.getAttribute("aria-controls");
      var panel = null;
      if (panelId) {
        if (typeof CSS !== "undefined" && CSS.escape) {
          panel = contentHost.querySelector("#" + CSS.escape(panelId));
        }
        if (!panel) {
          panel = document.getElementById(panelId);
        }
      }

      if (panel) {
        panel.style.setProperty("display", "block", "important");
        panel.style.setProperty("height", "auto", "important");
        panel.style.setProperty("overflow", "visible", "important");
        panel.setAttribute("aria-hidden", "false");

        panel.querySelectorAll('[style*="opacity"]').forEach(function (node) {
          node.style.opacity = "1";
        });
      }
    });

    contentHost.querySelectorAll(".mantine-Accordion-item").forEach(function (item) {
      item.setAttribute("data-active", "true");
    });

    contentHost.querySelectorAll(".mantine-Accordion-chevron, [class*='Accordion-chevron']").forEach(
      function (chevron) {
        chevron.setAttribute("data-rotate", "true");
      }
    );
  }

  function restructureArticleContent(contentHost, pageTitle) {
    var bodyRow = contentHost.querySelector(".css-2y3zsr, .css-k1l4fw");
    if (!bodyRow) {
      return false;
    }

    var mainCol = bodyRow.querySelector(".css-7nll2u");
    var tocCol = bodyRow.querySelector(":scope > .css-gfn0ts, :scope > .css-12mrpgq");
    if (!mainCol) {
      return false;
    }

    if (bodyRow.classList.contains("css-k1l4fw")) {
      bodyRow.classList.add("internal-article-layout");

      var standaloneTocWrap = bodyRow.querySelector(".internal-article-toc");
      if (!standaloneTocWrap) {
        standaloneTocWrap = document.createElement("div");
        standaloneTocWrap.className = "internal-article-toc";
        if (tocCol) {
          bodyRow.replaceChild(standaloneTocWrap, tocCol);
          standaloneTocWrap.appendChild(tocCol);
        } else {
          bodyRow.appendChild(standaloneTocWrap);
        }
      } else if (tocCol && !standaloneTocWrap.contains(tocCol)) {
        standaloneTocWrap.appendChild(tocCol);
      }

      if (!tocCol) {
        ensureGeneratedToc(standaloneTocWrap, mainCol);
      }

      expandArticleAccordions(contentHost);
      markArticleIntroText(mainCol);
      fixArticleTocScroll(contentHost);
      bindArticleTocNavigation(contentHost);
      bindArticleFigureLightbox(contentHost);
      bindArticleTocSpy(contentHost);
      ensureMobileTocUi(contentHost);
      return true;
    }

    var layoutRow = contentHost.querySelector(".internal-article-layout");
    if (!layoutRow) {
      layoutRow = document.createElement("div");
      layoutRow.className = "internal-article-layout";
      var headerWrap = contentHost.querySelector(".internal-main-header");
      if (headerWrap) {
        headerWrap.insertAdjacentElement("afterend", layoutRow);
      } else {
        contentHost.appendChild(layoutRow);
      }
    }

    var whitePanel = layoutRow.querySelector(".internal-article-content");
    if (!whitePanel) {
      whitePanel = document.createElement("div");
      whitePanel.className = "internal-article-content";
      layoutRow.appendChild(whitePanel);
    }

    var tocWrap = layoutRow.querySelector(".internal-article-toc");
    if (!tocWrap) {
      tocWrap = document.createElement("div");
      tocWrap.className = "internal-article-toc";
      layoutRow.appendChild(tocWrap);
    }

    removeDuplicateArticleTitle(mainCol, pageTitle);

    if (!whitePanel.contains(mainCol)) {
      whitePanel.appendChild(mainCol);
    }

    if (tocCol && !tocWrap.contains(tocCol)) {
      tocWrap.appendChild(tocCol);
    } else {
      ensureGeneratedToc(tocWrap, mainCol);
    }

    var oldSection = bodyRow.closest("section");
    if (oldSection && !whitePanel.contains(oldSection) && !tocWrap.contains(oldSection)) {
      oldSection.style.display = "none";
    }

    expandArticleAccordions(contentHost);
    markArticleIntroText(mainCol);
    fixArticleTocScroll(contentHost);
    bindArticleTocNavigation(contentHost);
    bindArticleFigureLightbox(contentHost);
    bindArticleTocSpy(contentHost);
    ensureMobileTocUi(contentHost);

    return true;
  }

  function applyStandalonePage(path, force) {
    var main = getMainElement();
    if (!main) {
      return;
    }

    if (main.dataset.internalLayout === path && !force) {
      var cachedSection = getContentSection(main);
      if (cachedSection) {
        restructureArticleContent(cachedSection, getPageTitle());
      }
      markLayoutReady();
      return;
    }

    document.documentElement.classList.add("internal-layout-active");

    var section = getContentSection(main);
    if (section) {
      restructureArticleContent(section, getPageTitle());
      ensureMobileTocUi(section);
    } else {
      ensureMobileTocUi(main);
    }

    main.dataset.internalLayout = path;
    markLayoutReady();
  }

  function applyLayout(force) {
    if (applying || isHomePage()) {
      return;
    }

    applying = true;

    fetchTree()
      .then(function () {
        var path = normalizePath(window.location.pathname);
        var category = findCategoryByPath(path);
        var standalone = isStandalonePage(path);

        if (!category && !standalone) {
          return;
        }

        if (standalone) {
          applyStandalonePage(path, force);
          return;
        }

        var main = getMainElement();
        if (!main) {
          return;
        }

        var shell = main.querySelector(".internal-page-shell");
        if (!shell) {
          shell = document.createElement("div");
          shell.className = "internal-page-shell";
          while (main.firstChild) {
            shell.appendChild(main.firstChild);
          }
          main.appendChild(shell);
        }

        var contentHost = shell.querySelector(".internal-main");
        if (!contentHost) {
          contentHost = document.createElement("div");
          contentHost.className = "internal-main";
          shell.appendChild(contentHost);
        }

        var trailNodes = findTrail(category.children || [], path, []) || [];
        var breadcrumbTrail = buildBreadcrumbTrail(category, path);
        var pageTitle = getPageTitle();
        var cards = resolveCards(category, path, trailNodes);
        var hubPage = cards.length > 0;

        if (main.dataset.internalLayout === path && !force) {
          hideStageInterlinks();
          if (!hubPage) {
            restructureArticleContent(contentHost, pageTitle);
          }
          markLayoutReady();
          return;
        }

        document.documentElement.classList.add("internal-layout-active");

        var headerHtml =
          breadcrumbsRowHtml(breadcrumbTrail) +
          '<h1 class="internal-page-title">' +
          pageTitle +
          "</h1>" +
          (hubPage ? stripHtml(cards) : "");

        var oldSidebar = shell.querySelector(".internal-sidebar");
        var sidebarMarkup = sidebarHtml(category, path);
        if (oldSidebar) {
          oldSidebar.outerHTML = sidebarMarkup;
        } else {
          shell.insertAdjacentHTML("afterbegin", sidebarMarkup);
        }
        bindTreeToggles(shell.querySelector(".internal-sidebar"));

        if (hubPage) {
          Array.from(shell.children).forEach(function (child) {
            if (
              !child.classList.contains("internal-sidebar") &&
              !child.classList.contains("internal-main")
            ) {
              child.style.display = "none";
            }
          });
          contentHost.innerHTML = headerHtml;
        } else {
          var headerWrap = contentHost.querySelector(".internal-main-header");
          if (!headerWrap) {
            headerWrap = document.createElement("div");
            headerWrap.className = "internal-main-header";
            contentHost.appendChild(headerWrap);
          }
          headerWrap.innerHTML = headerHtml;

          var section = getContentSection(shell);
          if (section && !contentHost.contains(section)) {
            contentHost.appendChild(section);
          }

          restructureArticleContent(contentHost, pageTitle);
        }

        main.dataset.internalLayout = path;
        hideStageInterlinks();
      })
      .finally(function () {
        applying = false;
        if (!isHomePage()) {
          markLayoutReady();
        }
      });
  }

  function syncLayoutStickyOffset() {
    var header =
      document.querySelector("header.css-9r8uj3") || document.querySelector("header");
    if (!header) {
      return;
    }

    var categoryChrome = document.querySelector(".category-nav-chrome");
    var categoryNav = document.querySelector(".category-nav");
    var headerHeight = Math.round(header.getBoundingClientRect().height);
    var categoryNavHeight = categoryChrome
      ? Math.round(categoryChrome.getBoundingClientRect().height)
      : categoryNav
        ? Math.round(categoryNav.getBoundingClientRect().height)
        : 48;

    document.documentElement.style.setProperty("--site-header-height", headerHeight + "px");
    document.documentElement.style.setProperty(
      "--internal-toc-sticky-top",
      headerHeight + categoryNavHeight + 40 + "px"
    );
    if (typeof window.syncCategoryNavLayout === "function") {
      window.syncCategoryNavLayout();
    }
    syncMobileTocTogglePosition();
  }

  function getTocScope() {
    return (
      document.querySelector(".internal-main") ||
      getContentSection(getMainElement()) ||
      null
    );
  }

  function tick() {
    if (isLayoutBaked()) {
      initBakedLayoutRuntime();
      return;
    }

    syncLayoutStickyOffset();
    hideStageInterlinks();
    document.querySelectorAll(".internal-article-content").forEach(applyHeadingNormalization);
    normalizeDocumentDownloadBlocks();
    repairDashBulletLists();
    var tocScope = getTocScope();
    if (tocScope) {
      expandArticleAccordions(tocScope);
      fixArticleTocScroll(tocScope);
      bindArticleTocNavigation(tocScope);
      bindArticleFigureLightbox(tocScope);
      if (tocScope.querySelector(".internal-article-toc .mantine-List-item")) {
        bindArticleTocSpy(tocScope);
      }
      ensureMobileTocUi(tocScope);
    }
    applyLayout(false);
  }

  scheduleNavPatches(tick);

  window.addEventListener("resize", syncLayoutStickyOffset);
})();
