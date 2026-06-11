(function () {
  var LABEL = "Теми правової допомоги:";
  var TREE_URL = "/data/site-nav-tree.json?v=1";
  var TREE_CACHE_KEY = "site-nav-tree-v1";
  var MOBILE_TREE_MAX_WIDTH = 960;
  var CATEGORIES = [
    {
      id: "serviceman",
      label: "Військові",
      href: "/serviceman/",
      prefixes: ["/serviceman"],
    },
    {
      id: "injured",
      label: "Поранені",
      href: "/injured/",
      prefixes: ["/injured", "/injured-military", "/ingured-mia"],
    },
    {
      id: "veterans",
      label: "Ветерани",
      href: "/veterans/",
      prefixes: ["/veterans"],
    },
    {
      id: "pow",
      label: "Звільнені з полону",
      href: "/pow/",
      prefixes: ["/pow"],
    },
    {
      id: "family",
      label: "Родини військових та ветеранів",
      href: "/family/",
      prefixes: ["/family"],
    },
  ];

  var bodyObserver = null;
  var navTree = null;
  var navTreePromise = null;
  var expandedManual = Object.create(null);
  var expandedCategoryManual = Object.create(null);
  var staticDrawerRoot = null;
  var staticDrawerOpen = false;
  var staticDrawerListenersBound = false;
  var isPatchingDrawer = false;
  var patchDrawersFrame = null;
  var patchDrawerQueue = [];
  var lastSyncedPath = null;

  var SITE_DRAWER_ITEMS = [
    { href: "/about/", label: "Про нас" },
    { href: "/faq/", label: "FAQ" },
    { href: "/documents/", label: "Документи" },
    { href: "/search/", label: "Пошук", icon: "/img/search.svg", iconAlt: "search" },
  ];
  var TREE_TOGGLE_ICON = "/img/arrow_down.svg";

  function resolveSiteUrl(path) {
    return typeof siteUrl === "function" ? siteUrl(path) : path;
  }

  function treeToggleIconSrc() {
    return resolveSiteUrl(TREE_TOGGLE_ICON);
  }

  try {
    var cachedTree = sessionStorage.getItem(TREE_CACHE_KEY);
    if (cachedTree) {
      navTree = JSON.parse(cachedTree);
    }
  } catch (error) {
    navTree = null;
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

  function pathsEqual(a, b) {
    return normalizePath(a) === normalizePath(b);
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/"/g, "&quot;");
  }

  function fetchNavTree() {
    if (navTree) {
      return Promise.resolve(navTree);
    }
    if (navTreePromise) {
      return navTreePromise;
    }

    var treeUrl = typeof siteUrl === "function" ? siteUrl(TREE_URL) : TREE_URL;
    navTreePromise = fetch(treeUrl)
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
      })
      .finally(function () {
        navTreePromise = null;
      });

    return navTreePromise;
  }

  function getActiveCategory() {
    var path = normalizePath(window.location.pathname);
    for (var i = 0; i < CATEGORIES.length; i++) {
      var category = CATEGORIES[i];
      for (var j = 0; j < category.prefixes.length; j++) {
        if (path.indexOf(category.prefixes[j]) === 0) {
          return category;
        }
      }
    }
    return null;
  }

  function findNavCategory(activeId) {
    if (!navTree || !activeId) {
      return null;
    }

    for (var i = 0; i < navTree.categories.length; i++) {
      if (navTree.categories[i].id === activeId) {
        return navTree.categories[i];
      }
    }

    return null;
  }

  function shouldExpandNode(href, path) {
    var normalizedHref = normalizePath(href);
    if (expandedManual[href] || expandedManual[normalizedHref]) {
      return true;
    }
    if (pathsEqual(normalizedHref, path)) {
      return false;
    }
    return path.indexOf(normalizedHref) === 0;
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
        escapeHtml(node.href) +
        '" aria-expanded="' +
        (isExpanded ? "true" : "false") +
        '">' +
        '<img class="internal-tree-toggle__icon" src="' +
        escapeHtml(treeToggleIconSrc()) +
        '" alt="" width="12" height="12" aria-hidden="true" />' +
        "</button>" +
        '<a class="internal-tree-link' +
        (isActive ? " internal-tree-link--active" : "") +
        '" href="' +
        escapeHtml(resolveSiteUrl(node.href)) +
        '">' +
        escapeHtml(node.label) +
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

  function mobileMenuTreeHtml(category, path) {
    if (!category || !category.children || !category.children.length) {
      return "";
    }

    return (
      '<nav class="mobile-menu-tree" data-mobile-menu-tree="1" aria-label="' +
      escapeHtml(category.label) +
      '">' +
      '<ul class="internal-tree-list">' +
      renderTreeNodes(category.children, path) +
      "</ul></nav>"
    );
  }

  function bindMobileTreeToggles(treeRoot) {
    if (!treeRoot) {
      return;
    }

    treeRoot.querySelectorAll(".internal-tree-toggle").forEach(function (button) {
      if (button.classList.contains("internal-tree-toggle--hidden")) {
        return;
      }
      if (button.dataset.mobileTreeBound) {
        return;
      }
      button.dataset.mobileTreeBound = "1";
      button.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        var href = this.getAttribute("data-tree-href");
        expandedManual[href] = !expandedManual[href];
        var content = treeRoot.closest(".mantine-w2f2ab");
        var activeCategory = getActiveCategory();
        withDrawerPatch(function () {
          syncMobileMenuTree(content, activeCategory ? activeCategory.id : null);
        });
      });
    });
  }

  function isCategoryExpanded(categoryId, activeId) {
    if (Object.prototype.hasOwnProperty.call(expandedCategoryManual, categoryId)) {
      return expandedCategoryManual[categoryId];
    }
    return categoryId === activeId;
  }

  function categoryHasTreeChildren(categoryId) {
    if (!navTree) {
      return true;
    }
    var navCategory = findNavCategory(categoryId);
    return !!(navCategory && navCategory.children && navCategory.children.length);
  }

  function shouldShowMobileMenuTree() {
    return window.innerWidth <= MOBILE_TREE_MAX_WIDTH;
  }

  function removeMobileMenuTrees() {
    document.querySelectorAll("[data-mobile-menu-tree]").forEach(function (tree) {
      tree.remove();
    });
  }

  function syncMobileMenuTree(content, activeId) {
    if (!content) {
      return;
    }

    if (!shouldShowMobileMenuTree()) {
      removeMobileMenuTrees();
      return;
    }

    var path = normalizePath(window.location.pathname);

    content.querySelectorAll(".mobile-menu-category[data-category-id]").forEach(function (item) {
      var categoryId = item.getAttribute("data-category-id");
      var panel = item.querySelector("[data-category-panel]");
      if (!panel) {
        return;
      }

      var isExpanded = isCategoryExpanded(categoryId, activeId);
      panel.hidden = !isExpanded;
      panel.classList.toggle("mobile-menu-category__panel--open", isExpanded);

      var toggle = item.querySelector("[data-category-toggle]");
      if (toggle) {
        toggle.setAttribute("aria-expanded", isExpanded ? "true" : "false");
        var icon = toggle.querySelector(".mobile-menu-category__toggle-icon");
        if (icon) {
          icon.classList.toggle("mobile-menu-category__toggle-icon--expanded", isExpanded);
        }
      }

      var existingTree = panel.querySelector("[data-mobile-menu-tree]");
      if (!isExpanded) {
        if (existingTree) {
          existingTree.remove();
        }
        return;
      }

      var navCategory = findNavCategory(categoryId);
      var treeHtml = navCategory ? mobileMenuTreeHtml(navCategory, path) : "";
      if (!treeHtml) {
        if (existingTree) {
          existingTree.remove();
        }
        return;
      }

      if (existingTree && existingTree.dataset.mobileMenuTreeHtml === treeHtml) {
        bindMobileTreeToggles(existingTree);
        if (categoryId === activeId) {
          scrollActiveTreeLinkIntoView(existingTree);
        }
        return;
      }

      panel.innerHTML = treeHtml;
      var tree = panel.querySelector("[data-mobile-menu-tree]");
      if (tree) {
        tree.dataset.mobileMenuTreeHtml = treeHtml;
        bindMobileTreeToggles(tree);
        if (categoryId === activeId) {
          scrollActiveTreeLinkIntoView(tree);
        }
      }
    });
  }

  function bindCategoryAccordionToggles(content, activeId) {
    if (!content) {
      return;
    }

    content.querySelectorAll("[data-category-toggle]").forEach(function (button) {
      if (button.dataset.categoryToggleBound) {
        return;
      }
      button.dataset.categoryToggleBound = "1";
      button.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        var categoryId = this.getAttribute("data-category-toggle");
        var currentlyExpanded = isCategoryExpanded(
          categoryId,
          activeId || (getActiveCategory() ? getActiveCategory().id : null)
        );

        for (var i = 0; i < CATEGORIES.length; i++) {
          expandedCategoryManual[CATEGORIES[i].id] = false;
        }
        expandedCategoryManual[categoryId] = !currentlyExpanded;

        var drawerContent = this.closest(".mantine-w2f2ab");
        var activeCategory = getActiveCategory();
        withDrawerPatch(function () {
          syncMobileMenuTree(drawerContent, activeCategory ? activeCategory.id : null);
        });
      });
    });
  }

  function scrollActiveTreeLinkIntoView(treeRoot) {
    if (!treeRoot || !staticDrawerOpen) {
      return;
    }

    var activeLink = treeRoot.querySelector(".internal-tree-link--active");
    if (!activeLink) {
      return;
    }

    window.requestAnimationFrame(function () {
      activeLink.scrollIntoView({ block: "nearest", inline: "nearest" });
    });
  }

  function categoriesAccordionHtml(activeId) {
    var showTree = shouldShowMobileMenuTree();
    var html =
      '<div class="mobile-menu-categories" data-mobile-menu-categories="1">' +
      '<div class="mobile-menu-categories__accordion" data-mobile-menu-accordion="1">';

    for (var i = 0; i < CATEGORIES.length; i++) {
      var category = CATEGORIES[i];
      var isActive = category.id === activeId;
      var hasChildren = showTree && categoryHasTreeChildren(category.id);
      var isExpanded = hasChildren && isCategoryExpanded(category.id, activeId);
      var linkClass = "mobile-menu-category__link";
      if (isActive) {
        linkClass += " mobile-menu-category__link--active";
      }

      html +=
        '<div class="mobile-menu-category" data-category-id="' +
        category.id +
        '">' +
        '<div class="mobile-menu-category__header">' +
        '<a class="' +
        linkClass +
        '" href="' +
        escapeHtml(resolveSiteUrl(category.href)) +
        '" data-category-id="' +
        category.id +
        '">' +
        escapeHtml(category.label) +
        "</a>";

      if (hasChildren) {
        html +=
          '<button type="button" class="mobile-menu-category__toggle" data-category-toggle="' +
          category.id +
          '" aria-expanded="' +
          (isExpanded ? "true" : "false") +
          '" aria-label="Розгорнути ' +
          escapeHtml(category.label) +
          '">' +
          '<img class="mobile-menu-category__toggle-icon' +
          (isExpanded ? " mobile-menu-category__toggle-icon--expanded" : "") +
          '" src="' +
          escapeHtml(treeToggleIconSrc()) +
          '" alt="" width="12" height="12" aria-hidden="true" />' +
          "</button>";
      }

      html += "</div>";

      if (hasChildren) {
        html +=
          '<div class="mobile-menu-category__panel' +
          (isExpanded ? " mobile-menu-category__panel--open" : "") +
          '" data-category-panel="' +
          category.id +
          '"' +
          (isExpanded ? "" : " hidden") +
          "></div>";
      }

      html += "</div>";
    }

    html += "</div></div>";
    return html;
  }

  function drawerFooterHtml() {
    var downloadHref = resolveSiteUrl("/download/");
    return (
      '<footer class="mobile-menu-drawer__footer" data-mobile-menu-footer="1">' +
      '<a class="header-download-btn" href="' +
      escapeHtml(downloadHref) +
      '">' +
      escapeHtml("Завантажити додаток") +
      "</a>" +
      '<a class="mobile-menu-foreigners-btn" href="https://foreigners.navigator.pryncyp.org">' +
      '<img class="header-foreigners-link__icon" src="' +
      languageIconSrc() +
      '" width="18" height="18" alt="" aria-hidden="true"/>' +
      "<span>" +
      FOREIGNERS_LABEL +
      "</span></a></footer>"
    );
  }

  function buildDrawerContentHtml(activeId) {
    var html =
      '<section class="mobile-menu-section mobile-menu-section--site">' +
      '<div class="mobile-menu-section__links" data-mobile-menu-site="1">';

    for (var i = 0; i < SITE_DRAWER_ITEMS.length; i++) {
      html += drawerMenuLinkHtml(SITE_DRAWER_ITEMS[i]);
    }

    html +=
      "</div></section>" +
      '<section class="mobile-menu-section mobile-menu-section--topics">' +
      '<h2 class="mobile-menu-section__label">' +
      LABEL +
      "</h2>" +
      categoriesAccordionHtml(activeId) +
      "</section>" +
      drawerFooterHtml();

    return html;
  }

  function hasDrawerLayout(content) {
    return !!(content && content.getAttribute("data-mobile-menu-layout") === "1");
  }

  function applyDrawerLayout(content, activeId) {
    if (!content) {
      return;
    }

    content.innerHTML = buildDrawerContentHtml(activeId);
    content.setAttribute("data-mobile-menu-layout", "1");
    reorderDrawerMenuIcons(content);
    bindCategoryAccordionToggles(content, activeId);
  }

  function isNavigatorAccordionControl(control) {
    var label =
      control.querySelector(".mantine-Accordion-label") ||
      control.querySelector(".mantine-Text-root");
    if (!label) {
      return false;
    }
    return (label.textContent || "").trim() === "Навігатор";
  }

  function removeNavigatorAccordion(content) {
    content.querySelectorAll("[data-accordion-control]").forEach(function (control) {
      if (!isNavigatorAccordionControl(control)) {
        return;
      }

      var accordionRoot = control.closest("[data-accordion]");
      if (accordionRoot) {
        accordionRoot.remove();
        return;
      }

      var item = control.closest(".mantine-Accordion-item");
      if (item) {
        item.remove();
      }
    });
  }

  var FOREIGNERS_LABEL = "For Foreigners";
  var LANGUAGE_ICON = "/img/language.svg";
  var EXIT_MENU_ICON = "/img/exit-menu.svg";

  function languageIconSrc() {
    return typeof siteUrl === "function" ? siteUrl(LANGUAGE_ICON) : LANGUAGE_ICON;
  }

  function exitMenuIconSrc() {
    return typeof siteUrl === "function" ? siteUrl(EXIT_MENU_ICON) : EXIT_MENU_ICON;
  }

  function removeForeignersDrawerIcon(drawerBody) {
    drawerBody.querySelectorAll('a[href*="foreigners.navigator"]').forEach(function (link) {
      link.querySelectorAll("svg").forEach(function (svg) {
        svg.remove();
      });
    });
  }

  function ensureForeignersDrawerLink(drawerBody) {
    drawerBody.querySelectorAll('a[href*="foreigners.navigator"]').forEach(function (link) {
      link.querySelectorAll("svg").forEach(function (svg) {
        svg.remove();
      });

      link.classList.remove("css-noumbc");
      link.classList.add("mobile-menu-foreigners-btn");

      var icon = link.querySelector(".header-foreigners-link__icon");
      var label = link.querySelector("span");
      if (
        link.classList.contains("mobile-menu-foreigners-btn") &&
        icon &&
        label &&
        label.textContent.trim() === FOREIGNERS_LABEL
      ) {
        return;
      }

      link.innerHTML =
        '<img class="header-foreigners-link__icon" src="' +
        languageIconSrc() +
        '" width="18" height="18" alt="" aria-hidden="true"/>' +
        "<span>" +
        FOREIGNERS_LABEL +
        "</span>";
    });
  }

  function resolveDrawerLinkLabel(link, img, wrap) {
    var label = "";

    if (wrap) {
      label = (wrap.textContent || "").trim();
    } else {
      label = (link.textContent || "").trim();
    }

    if (label) {
      return label;
    }

    var existingLabel = link.querySelector(".mobile-menu-item__label");
    if (existingLabel) {
      label = (existingLabel.textContent || "").trim();
      if (label) {
        return label;
      }
    }

    var href = link.getAttribute("href") || "";
    if (href.indexOf("pryncyp_bot") !== -1) {
      return "Чат-бот";
    }

    var alt = (img.getAttribute("alt") || "").toLowerCase();
    if (alt === "ios") {
      return "IOS";
    }
    if (alt === "android") {
      return "Android";
    }
    if (alt === "telegram") {
      return "Чат-бот";
    }

    return "";
  }

  function reorderDrawerMenuIcons(content) {
    content.querySelectorAll("a.css-noumbc").forEach(function (link) {
      var img = link.querySelector("img");
      if (!img) {
        return;
      }

      var existingLabelEl = link.querySelector(".mobile-menu-item__label");
      if (
        link.dataset.mobileIconLeft === "1" &&
        existingLabelEl &&
        (existingLabelEl.textContent || "").trim()
      ) {
        return;
      }

      var wrap = link.querySelector(".mobile-menu-item__inner") || link.querySelector(".mantine-1xkg0b8");
      var label = resolveDrawerLinkLabel(link, img, wrap);

      if (!wrap || !wrap.classList.contains("mobile-menu-item__inner")) {
        if (wrap) {
          wrap.textContent = "";
          wrap.classList.add("mobile-menu-item__inner");
        } else {
          link.textContent = "";
          wrap = document.createElement("span");
          wrap.className = "mobile-menu-item__inner";
          link.appendChild(wrap);
        }
      } else {
        wrap.textContent = "";
      }

      var labelEl = document.createElement("span");
      labelEl.className = "mobile-menu-item__label";
      labelEl.textContent = label;
      wrap.appendChild(img);
      wrap.appendChild(labelEl);
      link.dataset.mobileIconLeft = "1";
    });
  }

  function fixDrawerCloseIcon(drawerBody) {
    var scope =
      drawerBody.closest(".static-mobile-drawer__content, .mantine-Drawer-content") ||
      drawerBody;
    scope.querySelectorAll('img[alt="exit-menu"]').forEach(function (img) {
      img.src = exitMenuIconSrc();
      img.removeAttribute("srcset");
      img.removeAttribute("srcSet");
      img.setAttribute("width", "24");
      img.setAttribute("height", "24");
      img.style.width = "24px";
      img.style.height = "24px";

      var button = img.closest("button");
      if (button) {
        button.style.width = "34px";
        button.style.height = "34px";
        button.style.minWidth = "34px";
        button.style.minHeight = "34px";
        button.style.display = "inline-flex";
        button.style.alignItems = "center";
        button.style.justifyContent = "center";
        button.style.padding = "0";
      }
    });
  }

  function hideDrawerSearch(drawerBody) {
    drawerBody.querySelectorAll('img[alt="search"]').forEach(function (img) {
      var box = img.closest(".mantine-6bln36");
      if (box) {
        box.remove();
        return;
      }
      img.remove();
    });

    drawerBody.querySelectorAll(".mantine-us64po").forEach(function (el) {
      el.remove();
    });
  }

  function updateActiveLinks(block, activeId) {
    if (!block) {
      return;
    }

    block.querySelectorAll(".mobile-menu-category__link").forEach(function (link) {
      var categoryId = link.getAttribute("data-category-id");
      if (categoryId === activeId) {
        link.classList.add("mobile-menu-category__link--active");
      } else {
        link.classList.remove("mobile-menu-category__link--active");
      }
    });
  }

  function drawerMenuLinkHtml(item) {
    var itemHref = resolveSiteUrl(item.href);
    var className = "css-noumbc";

    var html =
      '<a class="' + className + '" href="' + escapeHtml(itemHref) + '"';
    if (item.target) {
      html += ' target="' + item.target + '"';
    }
    html += ">";

    if (item.icon) {
      var iconSize = item.href === "/search/" ? 18 : 28;
      html +=
        '<span class="mantine-1xkg0b8 mobile-menu-item__inner">' +
        '<img alt="' +
        escapeHtml(item.iconAlt || "") +
        '" src="' +
        escapeHtml(resolveSiteUrl(item.icon)) +
        '" width="' +
        iconSize +
        '" height="' +
        iconSize +
        '" />';
      if (item.label) {
        html += '<span class="mobile-menu-item__label">' + escapeHtml(item.label) + "</span>";
      }
      html += "</span>";
    } else {
      html += escapeHtml(item.label);
    }

    html += "</a>";
    return html;
  }

  function drawerMenuLinksHtml() {
    return buildDrawerContentHtml(getActiveCategory() ? getActiveCategory().id : null);
  }

  function setBurgerOpened(opened) {
    document.querySelectorAll(".mantine-Burger-burger").forEach(function (burger) {
      if (opened) {
        burger.setAttribute("data-opened", "");
      } else {
        burger.removeAttribute("data-opened");
      }
    });
  }

  function bindStaticDrawerListeners(root) {
    if (staticDrawerListenersBound) {
      return;
    }
    staticDrawerListenersBound = true;

    root.addEventListener("click", function (event) {
      if (event.target.closest("[data-static-drawer-close]")) {
        event.preventDefault();
        closeDrawer();
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && staticDrawerOpen) {
        closeDrawer();
      }
    });
  }

  function withDrawerPatch(fn) {
    if (isPatchingDrawer) {
      patchDrawerQueue.push(fn);
      return;
    }

    isPatchingDrawer = true;
    if (bodyObserver) {
      bodyObserver.disconnect();
    }

    try {
      fn();
    } finally {
      isPatchingDrawer = false;
      if (bodyObserver) {
        bodyObserver.observe(document.body, {
          childList: true,
          subtree: true,
        });
      }
      if (patchDrawerQueue.length) {
        var queued = patchDrawerQueue.shift();
        withDrawerPatch(queued);
      }
    }
  }

  function resetTreeExpansionState() {
    expandedManual = Object.create(null);
    expandedCategoryManual = Object.create(null);
  }

  function refreshDrawerNavigation(drawerBody) {
    if (!drawerBody) {
      return;
    }

    var content = drawerBody.querySelector(".mantine-w2f2ab");
    if (!content) {
      return;
    }

    var path = normalizePath(window.location.pathname);
    if (path !== lastSyncedPath) {
      resetTreeExpansionState();
      lastSyncedPath = path;
    }

    var activeCategory = getActiveCategory();
    var activeId = activeCategory ? activeCategory.id : null;
    var categoriesBlock = content.querySelector("[data-mobile-menu-categories]");

    if (categoriesBlock) {
      updateActiveLinks(categoriesBlock, activeId);
    }

    fetchNavTree().then(function () {
      withDrawerPatch(function () {
        if (!hasDrawerLayout(content)) {
          applyDrawerLayout(content, activeId);
        } else {
          bindCategoryAccordionToggles(content, activeId);
        }
        syncMobileMenuTree(content, activeId);
      });
    });
  }

  function ensureStaticDrawer() {
    if (staticDrawerRoot) {
      return staticDrawerRoot;
    }

    var existing = document.querySelector(
      '.mantine-Drawer-root[data-static-mobile-drawer="1"]'
    );
    if (existing) {
      staticDrawerRoot = existing;
      bindStaticDrawerListeners(existing);
      return existing;
    }

    if (document.querySelector(".mantine-Drawer-body")) {
      return null;
    }

    var root = document.createElement("div");
    root.className = "mantine-Drawer-root static-mobile-drawer";
    root.setAttribute("data-static-mobile-drawer", "1");
    root.setAttribute("aria-hidden", "true");
    root.innerHTML =
      '<div class="mantine-Drawer-overlay static-mobile-drawer__overlay" data-static-drawer-close="1"></div>' +
      '<div class="mantine-Drawer-inner static-mobile-drawer__inner">' +
      '<div class="mantine-Drawer-content static-mobile-drawer__content" role="dialog" aria-modal="true">' +
      '<div class="mantine-Drawer-header static-mobile-drawer__header">' +
      '<button type="button" class="static-mobile-drawer__close mantine-UnstyledButton-root" data-static-drawer-close="1" aria-label="Закрити меню">' +
      '<img alt="exit-menu" src="' +
      exitMenuIconSrc() +
      '" width="24" height="24" />' +
      "</button></div>" +
      '<div class="mantine-Drawer-body static-mobile-drawer__body">' +
      '<div class="mantine-w2f2ab" data-mobile-menu-layout="1">' +
      drawerMenuLinksHtml() +
      "</div></div></div></div>";

    withDrawerPatch(function () {
      document.body.appendChild(root);
      patchDrawer(root.querySelector(".mantine-Drawer-body"));
    });
    staticDrawerRoot = root;
    bindStaticDrawerListeners(root);
    return root;
  }

  function openDrawer() {
    var root = ensureStaticDrawer();
    if (!root) {
      return;
    }

    staticDrawerOpen = true;
    root.classList.add("static-mobile-drawer--open");
    root.setAttribute("aria-hidden", "false");
    document.body.classList.add("static-mobile-drawer-open");
    setBurgerOpened(true);
    refreshDrawerNavigation(root.querySelector(".mantine-Drawer-body"));
  }

  function closeDrawer() {
    if (!staticDrawerRoot || !staticDrawerOpen) {
      return;
    }

    staticDrawerOpen = false;
    staticDrawerRoot.classList.remove("static-mobile-drawer--open");
    staticDrawerRoot.setAttribute("aria-hidden", "true");
    document.body.classList.remove("static-mobile-drawer-open");
    setBurgerOpened(false);
  }

  function toggleDrawer() {
    if (staticDrawerOpen) {
      closeDrawer();
      return;
    }
    openDrawer();
  }

  function patchDrawer(drawerBody) {
    if (!drawerBody) {
      return false;
    }

    hideDrawerSearch(drawerBody);
    fixDrawerCloseIcon(drawerBody);
    removeForeignersDrawerIcon(drawerBody);
    ensureForeignersDrawerLink(drawerBody);

    var content = drawerBody.querySelector(".mantine-w2f2ab");
    if (!content) {
      return false;
    }

    removeNavigatorAccordion(content);

    var activeCategory = getActiveCategory();
    var activeId = activeCategory ? activeCategory.id : null;

    fetchNavTree().then(function () {
      withDrawerPatch(function () {
        if (!hasDrawerLayout(content)) {
          applyDrawerLayout(content, activeId);
        } else {
          reorderDrawerMenuIcons(content);
          updateActiveLinks(content.querySelector("[data-mobile-menu-categories]"), activeId);
          bindCategoryAccordionToggles(content, activeId);
        }
        ensureForeignersDrawerLink(drawerBody);
        syncMobileMenuTree(content, activeId);
      });
    });

    return true;
  }

  function patchAllDrawersImmediate() {
    withDrawerPatch(function () {
      document.querySelectorAll(".mantine-Drawer-body").forEach(function (drawerBody) {
        patchDrawer(drawerBody);
      });
    });
  }

  function schedulePatchAllDrawers() {
    if (patchDrawersFrame) {
      return;
    }
    patchDrawersFrame = window.requestAnimationFrame(function () {
      patchDrawersFrame = null;
      patchAllDrawersImmediate();
    });
  }

  function patchAllDrawers() {
    schedulePatchAllDrawers();
  }

  function handleBurgerClick(event) {
    var burger = event.target.closest(".mantine-Burger-root");
    if (!burger) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    toggleDrawer();
  }

  function bindBurger() {
    if (document.documentElement.dataset.mobileMenuDelegated) {
      return;
    }
    document.documentElement.dataset.mobileMenuDelegated = "1";
    document.addEventListener("click", handleBurgerClick);
  }

  function bindObserver() {
    if (bodyObserver) {
      return;
    }

    bodyObserver = new MutationObserver(function () {
      if (isPatchingDrawer) {
        return;
      }
      schedulePatchAllDrawers();
      bindBurger();
    });

    bodyObserver.observe(document.body, {
      childList: true,
      subtree: true,
    });
  }

  function tick() {
    lastSyncedPath = normalizePath(window.location.pathname);
    patchAllDrawers();
    bindBurger();
    bindObserver();
    if (!shouldShowMobileMenuTree()) {
      removeMobileMenuTrees();
    }
  }

  window.addEventListener("pageshow", function (event) {
    lastSyncedPath = normalizePath(window.location.pathname);
    resetTreeExpansionState();

    if (event.persisted && staticDrawerRoot) {
      withDrawerPatch(function () {
        refreshDrawerNavigation(staticDrawerRoot.querySelector(".mantine-Drawer-body"));
      });
      return;
    }

    if (staticDrawerOpen && staticDrawerRoot) {
      refreshDrawerNavigation(staticDrawerRoot.querySelector(".mantine-Drawer-body"));
    }
  });

  var mobileTreeResizeTimer = null;
  window.addEventListener("resize", function () {
    if (mobileTreeResizeTimer) {
      window.clearTimeout(mobileTreeResizeTimer);
    }
    mobileTreeResizeTimer = window.setTimeout(function () {
      mobileTreeResizeTimer = null;
      document.querySelectorAll(".mantine-Drawer-body .mantine-w2f2ab").forEach(function (content) {
        var activeCategory = getActiveCategory();
        var activeId = activeCategory ? activeCategory.id : null;
        if (hasDrawerLayout(content)) {
          withDrawerPatch(function () {
            applyDrawerLayout(content, activeId);
            syncMobileMenuTree(content, activeId);
          });
          return;
        }
        syncMobileMenuTree(content, activeId);
      });
    }, 150);
  });

  var schedule = window.scheduleNavPatches || function scheduleNavPatchesFallback(fn) {
    fn();
    if (document.readyState === "loading") {
      document.addEventListener(
        "DOMContentLoaded",
        function () {
          fn();
        },
        { once: true }
      );
    }
  };

  schedule(tick);
})();
