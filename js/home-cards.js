(function () {
  var MERGED_HREF = "/injured/";
  var MERGED_TITLE = "Поранені";
  var CATEGORY_LABEL = "або ж виберіть потрібну вам категорію:";
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
    if (cardHref(anchor) !== href) {
      anchor.setAttribute("href", href);
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
      var inner = anchor.querySelector(":scope > div");
      if (inner) {
        inner.style.setProperty("background", "#908F8B", "important");
      }
    });

    links
      .filter(function (anchor) {
        return anchor.classList.contains("css-1q51wqn");
      })
      .forEach(setDesktopWidth);

    return true;
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
      var href = cardHref(anchor);
      var title = cardTitle(anchor);
      var target = CATEGORY_HREFS[href] || CATEGORY_HREFS[title];
      if (target) {
        setHref(anchor, target);
      }
    });

    return true;
  }

  function tick() {
    injectCategoryLabel();
    fixCategoryHrefs();
    mergeInjuredCards();
  }

  scheduleNavPatches(tick);
})();
