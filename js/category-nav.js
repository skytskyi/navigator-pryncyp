(function () {
  var LABEL = "Теми правової допомоги:";
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
  var GLOBAL_NAV_PATHS = ["/about/", "/faq/", "/documents/", "/download/", "/privacy-policy/"];
  var SIDEBAR_WIDTH = 275;
  var SIDEBAR_CONTENT_GAP = 40;
  var DEFAULT_SITE_GUTTER = 40;

  function getSiteGutter() {
    var value = getComputedStyle(document.documentElement)
      .getPropertyValue("--site-gutter")
      .trim();
    var parsed = parseFloat(value);
    return isNaN(parsed) ? DEFAULT_SITE_GUTTER : parsed;
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
    var path = normalizePath(window.location.pathname);
    return path === "/";
  }

  function isGlobalNavPage() {
    return GLOBAL_NAV_PATHS.indexOf(normalizePath(window.location.pathname)) !== -1;
  }

  function shouldShowCategoryNav() {
    return !isHomePage() && (getActiveCategory() || isGlobalNavPage());
  }

  function getActiveCategory() {
    var path = window.location.pathname;
    if (typeof stripSiteBasePath === "function") {
      path = stripSiteBasePath(path);
    }
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

  function linksHtml(activeId) {
    var html = "";
    for (var i = 0; i < CATEGORIES.length; i++) {
      var category = CATEGORIES[i];
      var className = "category-nav__link";
      if (activeId && category.id === activeId) {
        className += " category-nav__link--active";
      }
      html +=
        '<a class="' +
        className +
        '" href="' +
        category.href +
        '">' +
        category.label +
        "</a>";
    }
    return html;
  }

  function chromeHtml(activeId) {
    return (
      '<div class="category-nav-chrome">' +
      '<nav class="category-nav" aria-label="' +
      LABEL +
      '">' +
      '<p class="category-nav__label">' +
      LABEL +
      "</p>" +
      '<div class="category-nav__inner">' +
      '<div class="category-nav__links">' +
      linksHtml(activeId) +
      "</div>" +
      "</div></nav></div>"
    );
  }

  function updateActiveState(nav, activeCategory) {
    var links = nav.querySelectorAll(".category-nav__link");
    for (var i = 0; i < links.length; i++) {
      var link = links[i];
      var isActive = link.getAttribute("href") === activeCategory.href;
      if (isActive) {
        link.classList.add("category-nav__link--active");
      } else {
        link.classList.remove("category-nav__link--active");
      }
    }
  }

  function getHeader() {
    return document.querySelector("header.css-9r8uj3") || document.querySelector("header");
  }

  function getCategoryChrome() {
    return document.querySelector(".category-nav-chrome");
  }

  function getCategoryNav() {
    return document.querySelector(".category-nav");
  }

  function ensureCategoryChromeStructure() {
    var nav = getCategoryNav();
    if (!nav) {
      return null;
    }

    var chrome = nav.closest(".category-nav-chrome");
    if (!chrome) {
      chrome = document.createElement("div");
      chrome.className = "category-nav-chrome";
      nav.parentNode.insertBefore(chrome, nav);
      chrome.appendChild(nav);
    }

    var label = nav.querySelector(":scope > .category-nav__label");
    if (!label) {
      label = chrome.querySelector(":scope > .category-nav__label");
      if (label) {
        nav.insertBefore(label, nav.firstChild);
      } else {
        label = document.createElement("p");
        label.className = "category-nav__label";
        nav.insertBefore(label, nav.firstChild);
      }
    }
    label.textContent = LABEL;

    var outerLabel = chrome.querySelector(":scope > .category-nav__label");
    if (outerLabel && outerLabel !== label) {
      outerLabel.remove();
    }

    nav.setAttribute("aria-label", LABEL);
    return chrome;
  }

  function isStandaloneInternalPage() {
    return !!document.querySelector(".internal-page-shell--standalone");
  }

  function getCategoryNavMinPadding() {
    var label = document.querySelector(".category-nav__label");
    var nav = document.querySelector(".category-nav");
    if (!label || !nav) {
      return null;
    }

    var navRect = nav.getBoundingClientRect();
    var labelRect = label.getBoundingClientRect();
    return Math.round(labelRect.right - navRect.left + 40);
  }

  function getVirtualSidebarOffset() {
    var nav = document.querySelector(".category-nav");
    var shell = document.querySelector(".internal-page-shell");
    if (!nav || !shell) {
      return null;
    }

    var navRect = nav.getBoundingClientRect();
    var shellRect = shell.getBoundingClientRect();
    var gutter = getSiteGutter();
    var shellContentLeft = shellRect.left + gutter;
    return Math.round(
      shellContentLeft - navRect.left + SIDEBAR_WIDTH + SIDEBAR_CONTENT_GAP
    );
  }

  function getInternalContentOffset() {
    if (isStandaloneInternalPage() || isGlobalNavPage()) {
      return getVirtualSidebarOffset();
    }

    var mainHeader = document.querySelector(".internal-main-header");
    if (mainHeader) {
      return mainHeader.getBoundingClientRect().left;
    }

    var breadcrumbs = document.querySelector(
      ".internal-breadcrumbs-row, .internal-breadcrumbs"
    );
    if (breadcrumbs) {
      return breadcrumbs.getBoundingClientRect().left;
    }

    var shell = document.querySelector(".internal-page-shell");
    if (!shell) {
      return null;
    }

    var sidebar = shell.querySelector(".internal-sidebar");
    if (sidebar) {
      return sidebar.getBoundingClientRect().right + 40;
    }

    return shell.getBoundingClientRect().left;
  }

  function syncContentOffset() {
    var inner = document.querySelector(".category-nav__inner");
    if (!inner) {
      return false;
    }

    var offset = getInternalContentOffset();
    var minPadding = getCategoryNavMinPadding();
    if (offset === null && minPadding === null) {
      inner.style.paddingLeft = "";
      return false;
    }

    var padding = offset !== null ? offset : 0;
    if (minPadding !== null) {
      padding = Math.max(padding, minPadding);
    }

    inner.style.paddingLeft = Math.max(0, Math.round(padding)) + "px";
    return true;
  }

  function injectCategoryNav() {
    if (!shouldShowCategoryNav()) {
      return false;
    }

    var activeCategory = getActiveCategory();
    var activeId = activeCategory ? activeCategory.id : null;

    var header = getHeader();
    if (!header) {
      return false;
    }

    var chrome = ensureCategoryChromeStructure();
    if (chrome) {
      var nav = chrome.querySelector(".category-nav");
      if (activeCategory) {
        updateActiveState(nav, activeCategory);
      }
      if (chrome.previousElementSibling !== header) {
        header.insertAdjacentElement("afterend", chrome);
      }
      return true;
    }

    header.insertAdjacentHTML("afterend", chromeHtml(activeId));
    return true;
  }

  function syncStickyOffset() {
    var header = getHeader();
    if (!header) {
      return false;
    }

    document.documentElement.style.setProperty(
      "--site-header-height",
      Math.round(header.getBoundingClientRect().height) + "px"
    );

    var chrome = getCategoryChrome();
    var categoryNav = getCategoryNav();
    var chromeHeight = chrome
      ? Math.round(chrome.getBoundingClientRect().height)
      : categoryNav
        ? Math.round(categoryNav.getBoundingClientRect().height)
        : 48;
    document.documentElement.style.setProperty(
      "--internal-toc-sticky-top",
      Math.round(header.getBoundingClientRect().height + chromeHeight + 40) + "px"
    );
    return true;
  }

  function isHeaderBaked() {
    return document.documentElement.getAttribute("data-header-layout-baked") === "1";
  }

  function syncCategoryNavLayout() {
    ensureCategoryChromeStructure();
    syncStickyOffset();
    syncContentOffset();
  }

  window.syncCategoryNavLayout = syncCategoryNavLayout;

  function tick() {
    if (isHeaderBaked()) {
      if (shouldShowCategoryNav() && !getCategoryNav()) {
        injectCategoryNav();
      }
      syncCategoryNavLayout();
      return;
    }

    var injected = injectCategoryNav();
    if (injected) {
      syncCategoryNavLayout();
      if (typeof window.tryDismissNavHeaderPersist === "function") {
        window.tryDismissNavHeaderPersist();
      }
    }
  }

  window.addEventListener("resize", syncCategoryNavLayout);

  scheduleNavPatches(tick);
})();
