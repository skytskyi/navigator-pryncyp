(function () {
  var MERGED_HREF = "/injured/";
  var MERGED_TITLE = "Поранені";
  var CATEGORY_LABEL = "Оберіть тему правової допомоги:";
  var CARD_PALETTE = [
    "#686F4E",
    "#61523A",
    "#503334",
    "#47515A",
    "#434A3A",
    "#383C3B",
    "#37332E",
    "#151D23",
    "#2B3A62",
  ];
  var INJURED_SUB_RE = /injured-military|ingured-mia/i;
  var DESKTOP_COUNT = 5;
  var CATEGORY_HREFS = {
    "serviceman.html": "/serviceman/",
    "veterans.html": "/veterans/",
    "family.html": "/family/",
    "pow.html": "/pow/",
    "injured.html": "/injured/",
    "Військові": "/serviceman/",
    "Поранені": "/injured/",
    "Ветерани": "/veterans/",
    "Родини військових та ветеранів": "/family/",
    "Звільнені з полону": "/pow/",
  };

  function isHomePage() {
    if (typeof normalizeSitePath === "function") {
      return normalizeSitePath(window.location.pathname) === "/";
    }
    var path = window.location.pathname.replace(/\/+$/, "") || "/";
    return path === "" || path === "/" || path === "/index.html";
  }

  function getCardContainer() {
    return (
      document.querySelector(".css-1jbx5ca.mantine-17do081") ||
      document.querySelector(".css-1jbx5ca")
    );
  }

  function cardTitle(anchor) {
    var label = anchor.querySelector("p.css-6ixod5");
    return label ? label.textContent.trim() : "";
  }

  function cardHref(anchor) {
    return (anchor.getAttribute("href") || "").trim();
  }

  function normalizedCardPath(href) {
    var path = href || "/";
    if (typeof stripSiteBasePath === "function") {
      path = stripSiteBasePath(path);
    }
    return path;
  }

  function resolveCategoryHref(href) {
    return typeof siteUrl === "function" ? siteUrl(href) : href;
  }

  function isInjuredSubCard(anchor) {
    return INJURED_SUB_RE.test(cardHref(anchor));
  }

  function isMergedCard(anchor) {
    var href = cardHref(anchor);
    if (/\/injured\/?$/i.test(href) || href === "injured.html") {
      return true;
    }
    return cardTitle(anchor) === MERGED_TITLE && !isInjuredSubCard(anchor);
  }

  function setTitle(anchor, title) {
    var label = anchor.querySelector("p.css-6ixod5");
    if (label && label.textContent.trim() !== title) {
      label.textContent = title;
    }
  }

  function setHref(anchor, href) {
    var resolved = resolveCategoryHref(href);
    if (cardHref(anchor) !== resolved) {
      anchor.setAttribute("href", resolved);
    }
  }

  function setDesktopWidth(anchor) {
    if (anchor.classList.contains("css-1q51wqn")) {
      anchor.style.width = "calc(100% / " + DESKTOP_COUNT + ")";
    }
  }

  function cloneMergedFrom(template, href, title) {
    var clone = template.cloneNode(true);
    setHref(clone, href);
    setTitle(clone, title);
    return clone;
  }

  function insertMergedCards(container, links) {
    var mobileTemplate = links.find(function (anchor) {
      return anchor.classList.contains("css-1gooe0") && /serviceman/i.test(cardHref(anchor));
    });
    var desktopTemplate = links.find(function (anchor) {
      return anchor.classList.contains("css-1q51wqn") && /serviceman/i.test(cardHref(anchor));
    });

    if (mobileTemplate) {
      var mobileMerged = cloneMergedFrom(mobileTemplate, MERGED_HREF, MERGED_TITLE);
      mobileTemplate.insertAdjacentElement("afterend", mobileMerged);
    }

    if (desktopTemplate) {
      var desktopMerged = cloneMergedFrom(desktopTemplate, MERGED_HREF, MERGED_TITLE);
      desktopTemplate.insertAdjacentElement("afterend", desktopMerged);
    }
  }

  function injectCategoryLabel() {
    if (!isHomePage()) {
      return false;
    }

    var container = getCardContainer();
    if (!container) {
      return false;
    }

    var section = container.closest(".home-cards-section");
    if (!section) {
      section = document.querySelector(".home-cards-section");
    }

    if (!section) {
      section = document.createElement("div");
      section.className = "home-cards-section";
      container.parentNode.insertBefore(section, container);
      section.appendChild(container);
    } else if (!section.contains(container)) {
      section.appendChild(container);
    }

    var label = section.querySelector(":scope > .home-cards-label");
    if (!label) {
      label = document.querySelector(".home-cards-label");
    }

    if (!label) {
      label = document.createElement("p");
      label.className = "home-cards-label";
    }

    if (label.parentElement !== section) {
      section.insertBefore(label, container);
    } else if (section.firstChild !== label) {
      section.insertBefore(label, container);
    }

    if (label.textContent !== CATEGORY_LABEL) {
      label.textContent = CATEGORY_LABEL;
    }

    return true;
  }

  function mergeInjuredCards() {
    if (!isHomePage()) {
      return false;
    }

    var container = getCardContainer();
    if (!container) {
      return false;
    }

    var links = Array.from(
      container.querySelectorAll("a.css-1gooe0, a.css-1q51wqn")
    );
    if (!links.length) {
      return false;
    }

    links.filter(isInjuredSubCard).forEach(function (anchor) {
      anchor.remove();
    });

    links = Array.from(
      container.querySelectorAll("a.css-1gooe0, a.css-1q51wqn")
    );

    var merged = links.filter(isMergedCard);
    if (!merged.length) {
      insertMergedCards(container, links);
      links = Array.from(
        container.querySelectorAll("a.css-1gooe0, a.css-1q51wqn")
      );
      merged = links.filter(isMergedCard);
    }

    merged.forEach(function (anchor) {
      setHref(anchor, MERGED_HREF);
      setTitle(anchor, MERGED_TITLE);
    });

    links
      .filter(function (anchor) {
        return anchor.classList.contains("css-1q51wqn");
      })
      .forEach(setDesktopWidth);

    return true;
  }

  function applyHomeCardPalette() {
    if (!isHomePage()) {
      return false;
    }

    var container = getCardContainer();
    if (!container) {
      return false;
    }

    var links = Array.from(
      container.querySelectorAll("a.css-1gooe0, a.css-1q51wqn")
    );
    if (!links.length) {
      return false;
    }

    var seen = {};
    var order = [];
    links.forEach(function (anchor) {
      var href = normalizedCardPath(cardHref(anchor));
      if (!seen[href]) {
        seen[href] = true;
        order.push(href);
      }
    });

    var hrefColor = {};
    order.forEach(function (href, index) {
      hrefColor[href] = CARD_PALETTE[index % CARD_PALETTE.length];
    });

    var changed = false;
    links.forEach(function (anchor) {
      var href = normalizedCardPath(cardHref(anchor));
      var color = hrefColor[href];
      if (!color) {
        return;
      }
      var inner = anchor.querySelector(":scope > div");
      if (!inner) {
        return;
      }
      if (inner.style.getPropertyValue("background-color") !== color) {
        inner.style.setProperty("background", color, "important");
        changed = true;
      }
    });

    return changed;
  }

  function fixCategoryHrefs() {
    if (!isHomePage()) {
      return false;
    }

    var container = getCardContainer();
    if (!container) {
      return false;
    }

    var links = Array.from(
      container.querySelectorAll("a.css-1gooe0, a.css-1q51wqn")
    );
    if (!links.length) {
      return false;
    }

    links.forEach(function (anchor) {
      var href = normalizedCardPath(cardHref(anchor));
      var title = cardTitle(anchor);
      var target = CATEGORY_HREFS[href] || CATEGORY_HREFS[title];
      if (target) {
        setHref(anchor, target);
      }
    });

    return true;
  }

  function ensureDesktopCardCta() {
    if (!isHomePage() || !window.matchMedia("(min-width: 960px)").matches) {
      return false;
    }

    var arrowSrc =
      typeof siteUrl === "function" ? siteUrl("/img/Arrow.svg") : "/img/Arrow.svg";
    var changed = false;

    document.querySelectorAll("a.css-1q51wqn > div").forEach(function (card) {
      if (card.querySelector(".home-card-cta")) {
        return;
      }

      var cta = document.createElement("span");
      cta.className = "home-card-cta";
      cta.innerHTML =
        '<span class="home-card-cta__text">Перейти</span>' +
        '<img class="home-card-cta__arrow" src="' +
        arrowSrc +
        '" width="12" height="12" alt="" aria-hidden="true"/>';
      card.appendChild(cta);
      changed = true;
    });

    return changed;
  }

  function tick() {
    injectCategoryLabel();
    fixCategoryHrefs();
    mergeInjuredCards();
    applyHomeCardPalette();
    ensureDesktopCardCta();
  }

  scheduleNavPatches(tick);
})();
