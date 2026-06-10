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
  var staticDrawerRoot = null;
  var staticDrawerOpen = false;
  var staticDrawerListenersBound = false;
  var isPatchingDrawer = false;
  var patchDrawersFrame = null;
  var patchDrawerQueue = [];
  var lastSyncedPath = null;

  var DRAWER_MENU_ITEMS = [
    { href: "/about/", label: "Про нас" },
    { href: "/faq/", label: "FAQ" },
    { href: "/documents/", label: "Документи" },
    { href: "/search/", label: "Пошук", icon: "/img/search.svg" },
    { href: "/download/", label: "Завантажити додаток" },
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

  function findActiveCategoryLink(content, activeId) {
    if (!activeId) {
      return null;
    }

    var linksRoot = content.querySelector(".mobile-menu-categories__links");
    if (!linksRoot) {
      return null;
    }

    var link = linksRoot.querySelector('[data-category-id="' + activeId + '"]');
    if (link) {
      return link;
    }

    for (var i = 0; i < CATEGORIES.length; i++) {
      if (CATEGORIES[i].id === activeId) {
        return linksRoot.querySelector('a[href="' + resolveSiteUrl(CATEGORIES[i].href) + '"]');
      }
    }

    return null;
  }

  function placeMobileMenuTree(activeLink, existingTree, treeHtml) {
    if (existingTree) {
      if (existingTree.dataset.mobileMenuTreeHtml === treeHtml) {
        if (existingTree.previousElementSibling !== activeLink) {
          activeLink.insertAdjacentElement("afterend", existingTree);
        }
        return existingTree;
      }

      existingTree.outerHTML = treeHtml;
      var tree = activeLink.nextElementSibling;
      if (!tree || !tree.matches("[data-mobile-menu-tree]")) {
        tree = activeLink.parentElement.querySelector("[data-mobile-menu-tree]");
        if (tree && tree.previousElementSibling !== activeLink) {
          activeLink.insertAdjacentElement("afterend", tree);
        }
      }
      return tree;
    }

    activeLink.insertAdjacentHTML("afterend", treeHtml);
    return activeLink.nextElementSibling;
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

    var existingTree = content.querySelector("[data-mobile-menu-tree]");

    if (!shouldShowMobileMenuTree()) {
      if (existingTree) {
        existingTree.remove();
      }
      return;
    }
    var category = findNavCategory(activeId);
    var path = normalizePath(window.location.pathname);
    var treeHtml = category ? mobileMenuTreeHtml(category, path) : "";

    if (!treeHtml) {
      if (existingTree) {
        existingTree.remove();
      }
      return;
    }

    var activeLink = findActiveCategoryLink(content, activeId);
    if (!activeLink) {
      if (existingTree) {
        existingTree.remove();
      }
      return;
    }

    var tree = placeMobileMenuTree(activeLink, existingTree, treeHtml);
    if (tree) {
      tree.dataset.mobileMenuTreeHtml = treeHtml;
      bindMobileTreeToggles(tree);
      scrollActiveTreeLinkIntoView(tree);
    }
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

  function categoriesHtml(activeId) {
    var html =
      '<div class="mobile-menu-categories" data-mobile-menu-categories="1">' +
      '<div class="mobile-menu-categories__label">' +
      LABEL +
      "</div>" +
      '<div class="mobile-menu-categories__links">';

    for (var i = 0; i < CATEGORIES.length; i++) {
      var category = CATEGORIES[i];
      var className = "mobile-menu-categories__link";
      if (category.id === activeId) {
        className += " mobile-menu-categories__link--active";
      }
      html +=
        '<a class="' +
        className +
        '" href="' +
        escapeHtml(resolveSiteUrl(category.href)) +
        '" data-category-id="' +
        category.id +
        '">' +
        category.label +
        "</a>";
    }

    html += "</div></div>";
    return html;
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

      var inner = link.querySelector(".mobile-menu-item__inner, .mantine-1xkg0b8");
      if (!inner) {
        inner = document.createElement("span");
        inner.className = "mantine-1xkg0b8 mobile-menu-item__inner";
        link.textContent = "";
        link.appendChild(inner);
      } else {
        inner.classList.add("mobile-menu-item__inner");
      }

      var icon = inner.querySelector(".header-foreigners-link__icon");
      var label = inner.querySelector(".mobile-menu-item__label");
      if (icon && label && label.textContent.trim() === FOREIGNERS_LABEL) {
        return;
      }

      inner.innerHTML =
        '<img class="header-foreigners-link__icon" src="' +
        languageIconSrc() +
        '" width="18" height="18" alt="" aria-hidden="true"/>' +
        '<span class="mobile-menu-item__label">' +
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
    block.querySelectorAll(".mobile-menu-categories__link").forEach(function (link) {
      var href = link.getAttribute("href") || "";
      var isActive = false;
      for (var i = 0; i < CATEGORIES.length; i++) {
        if (CATEGORIES[i].id === activeId && resolveSiteUrl(CATEGORIES[i].href) === href) {
          isActive = true;
          break;
        }
      }
      if (isActive) {
        link.classList.add("mobile-menu-categories__link--active");
      } else {
        link.classList.remove("mobile-menu-categories__link--active");
      }
    });
  }

  function markDrawerMenuSpacing(content) {
    content.querySelectorAll('a.css-noumbc[href*="pryncyp_bot"]').forEach(function (link) {
      link.classList.remove("mobile-menu-item--spaced-top");
    });

    content.querySelectorAll('a.css-noumbc[href="' + resolveSiteUrl("/about/") + '"]').forEach(function (link) {
      link.classList.remove("mobile-menu-item--spaced-top");
      if (!link.classList.contains("mobile-menu-item--about-top")) {
        link.classList.add("mobile-menu-item--about-top");
      }
    });

    content.querySelectorAll('a.css-noumbc[href="' + resolveSiteUrl("/faq/") + '"]').forEach(function (link) {
      link.classList.remove("mobile-menu-item--spaced-top");
      link.classList.remove("mobile-menu-item--about-top");
      if (!link.classList.contains("mobile-menu-item--menu-gap")) {
        link.classList.add("mobile-menu-item--menu-gap");
      }
    });

    content.querySelectorAll('a.css-noumbc[href="' + resolveSiteUrl("/documents/") + '"]').forEach(function (link) {
      if (!link.classList.contains("mobile-menu-item--menu-gap")) {
        link.classList.add("mobile-menu-item--menu-gap");
      }
    });

    content.querySelectorAll('a.css-noumbc[href="' + resolveSiteUrl("/search/") + '"]').forEach(function (link) {
      if (!link.classList.contains("mobile-menu-item--menu-gap")) {
        link.classList.add("mobile-menu-item--menu-gap");
      }
    });

    content.querySelectorAll('a.header-download-btn[href="' + resolveSiteUrl("/download/") + '"]').forEach(function (link) {
      link.classList.remove("css-noumbc");
      if (!link.classList.contains("mobile-menu-item--spaced-top")) {
        link.classList.add("mobile-menu-item--spaced-top");
      }
    });

    content.querySelectorAll('a.css-noumbc[href="' + resolveSiteUrl("/download/") + '"]').forEach(function (link) {
      link.classList.remove("css-noumbc");
      link.classList.add("header-download-btn");
      if (!link.classList.contains("mobile-menu-item--spaced-top")) {
        link.classList.add("mobile-menu-item--spaced-top");
      }
    });

    var foreignersLink = content.querySelector('a[href*="foreigners.navigator"]');
    if (!foreignersLink) {
      return;
    }

    var foreignersWrap =
      foreignersLink.closest(".mantine-Stack-root") || foreignersLink;
    if (!foreignersWrap.classList.contains("mobile-menu-item--spaced-top")) {
      foreignersWrap.classList.add("mobile-menu-item--spaced-top");
    }
  }

  function drawerMenuLinkHtml(item) {
    var itemHref = resolveSiteUrl(item.href);

    if (item.href === "/download/") {
      return (
        '<a class="header-download-btn mobile-menu-item--spaced-top" href="' +
        escapeHtml(itemHref) +
        '">' +
        escapeHtml(item.label) +
        "</a>"
      );
    }

    var className = "css-noumbc";
    if (item.href === "/about/") {
      className += " mobile-menu-item--about-top";
    } else if (item.href === "/faq/" || item.href === "/documents/" || item.href === "/search/") {
      className += " mobile-menu-item--menu-gap";
    }

    var html =
      '<a class="' + className + '" href="' + escapeHtml(itemHref) + '"';
    if (item.target) {
      html += ' target="' + item.target + '"';
    }
    html += ">";

    if (item.icon) {
      var iconSize = item.href === "/search/" ? 18 : 28;
      html +=
        '<span class="mantine-1xkg0b8">' +
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
        html += escapeHtml(item.label);
      }
      html += "</span>";
    } else {
      html += escapeHtml(item.label);
    }

    html += "</a>";
    return html;
  }

  function drawerMenuLinksHtml() {
    var html = "";
    for (var i = 0; i < DRAWER_MENU_ITEMS.length; i++) {
      html += drawerMenuLinkHtml(DRAWER_MENU_ITEMS[i]);
    }
    html +=
      '<div class="mantine-Stack-root">' +
      '<a class="css-noumbc" href="https://foreigners.navigator.pryncyp.org">' +
      '<span class="mantine-1xkg0b8 mobile-menu-item__inner">' +
      '<img class="header-foreigners-link__icon" src="' +
      languageIconSrc() +
      '" width="18" height="18" alt="" aria-hidden="true"/>' +
      '<span class="mobile-menu-item__label">' +
      FOREIGNERS_LABEL +
      "</span></span></a></div>";
    return html;
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
    var existing = content.querySelector("[data-mobile-menu-categories]");

    if (existing) {
      updateActiveLinks(existing, activeId);
    }

    fetchNavTree().then(function () {
      withDrawerPatch(function () {
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
      '<div class="mantine-w2f2ab">' +
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
    reorderDrawerMenuIcons(content);
    markDrawerMenuSpacing(content);

    var activeCategory = getActiveCategory();
    var activeId = activeCategory ? activeCategory.id : null;
    var existing = content.querySelector("[data-mobile-menu-categories]");

    if (!existing) {
      var firstLink = content.querySelector("a.css-noumbc");
      var wrap = document.createElement("div");
      wrap.innerHTML = categoriesHtml(activeId);
      var block = wrap.firstElementChild;
      if (firstLink) {
        content.insertBefore(block, firstLink);
      } else {
        content.insertBefore(block, content.firstChild);
      }
    } else {
      updateActiveLinks(existing, activeId);
    }

    refreshDrawerNavigation(drawerBody);
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
      if (!shouldShowMobileMenuTree()) {
        removeMobileMenuTrees();
        return;
      }
      document.querySelectorAll(".mantine-Drawer-body .mantine-w2f2ab").forEach(function (content) {
        var activeCategory = getActiveCategory();
        syncMobileMenuTree(content, activeCategory ? activeCategory.id : null);
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
