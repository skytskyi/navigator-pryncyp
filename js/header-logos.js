(function () {
  var NAVIGATOR_LOGO = "/img/Logo_navigator.png";
  var PRYNCYP_LOGO = "/img/Logo_pryncyp.png";
  var FOREIGNERS_LABEL = "For Foreigners";
  var LANGUAGE_ICON = "/img/language.svg";

  function languageIconSrc() {
    return typeof siteUrl === "function" ? siteUrl(LANGUAGE_ICON) : LANGUAGE_ICON;
  }

  function foreignersLinkHtml() {
    return (
      '<div class="mantine-1uguyhf">' +
      '<img class="header-foreigners-link__icon" src="' +
      languageIconSrc() +
      '" width="18" height="18" alt="" aria-hidden="true"/>' +
      '<div class="mantine-Text-root mantine-ykctob">' +
      FOREIGNERS_LABEL +
      "</div></div>"
    );
  }
  var headerObserver = null;
  var headerPatchFrame = null;

  function homeHref() {
    return typeof siteUrl === "function" ? siteUrl("/") : "/";
  }

  function logosHtml() {
    return (
      '<div class="site-header-logos" style="display:flex !important;align-items:center;flex-shrink:0;">' +
      '<a class="site-header-logos__link" href="' +
      homeHref() +
      '">' +
      '<img alt="Правовий навігатор" height="30" decoding="async" ' +
      'style="height:30px;width:auto;display:block !important" src="' +
      NAVIGATOR_LOGO +
      '"/>' +
      '<span aria-hidden="true" class="site-header-logos__divider" style="width:1px;height:30px;background-color:#D9D9D9;' +
      'flex-shrink:0;display:block"></span>' +
      '<img alt="Принцип" height="30" decoding="async" ' +
      'style="height:30px;width:auto;display:block !important" src="' +
      PRYNCYP_LOGO +
      '"/>' +
      "</a></div>"
    );
  }

  function isOldLogoImg(img) {
    if (!img || img.tagName !== "IMG") return false;
    var src = img.getAttribute("src") || "";
    var alt = img.getAttribute("alt") || "";
    return (
      alt === "logo" ||
      /logo\.b15c3320|\/_next\/static\/media\/logo/.test(src)
    );
  }

  function isDirectLogoSrc(src) {
    return (
      !!src &&
      (src.indexOf(NAVIGATOR_LOGO) !== -1 || src.indexOf(PRYNCYP_LOGO) !== -1)
    );
  }

  function isOurLogosBlock(node) {
    if (!node || !node.classList || !node.classList.contains("site-header-logos")) {
      return false;
    }
    var link = node.querySelector(".site-header-logos__link");
    if (!link) {
      return false;
    }
    var nav = link.querySelector('img[alt="Правовий навігатор"]');
    var pry = link.querySelector('img[alt="Принцип"]');
    if (!nav || !pry) return false;
    var navSrc = nav.getAttribute("src") || nav.src || "";
    var prySrc = pry.getAttribute("src") || pry.src || "";
    return isDirectLogoSrc(navSrc) && isDirectLogoSrc(prySrc);
  }

  function repairHeaderNavCluster() {
    var headerBar = getHeaderBar();
    if (!headerBar) {
      return false;
    }

    var cluster = headerBar.querySelector(".css-zfqabr");
    if (!cluster) {
      return false;
    }

    var moved = false;
    var pastCluster = false;
    var children = Array.prototype.slice.call(headerBar.childNodes);
    for (var i = 0; i < children.length; i++) {
      var child = children[i];
      if (child === cluster) {
        pastCluster = true;
        continue;
      }
      if (!pastCluster) {
        continue;
      }
      cluster.appendChild(child);
      moved = true;
    }
    return moved;
  }

  function injectLogos() {
    var headerBar = getHeaderBar();
    if (!headerBar) return false;

    var existing = headerBar.querySelector(".site-header-logos");
    if (isOurLogosBlock(existing)) return true;

    if (existing) {
      existing.remove();
    }

    var oldAnchor = null;
    var imgs = headerBar.querySelectorAll("img");
    for (var i = 0; i < imgs.length; i++) {
      if (isOldLogoImg(imgs[i])) {
        oldAnchor = imgs[i].closest("a");
        break;
      }
    }

    var wrap = document.createElement("div");
    wrap.innerHTML = logosHtml();
    var block = wrap.firstElementChild;

    if (oldAnchor) {
      oldAnchor.replaceWith(block);
    } else {
      headerBar.insertBefore(block, headerBar.firstChild);
    }
    return true;
  }

  function fixHeaderDividers() {
    var style =
      "width:1px;height:30px;background-color:#D9D9D9;flex-shrink:0;display:block;align-self:center;";
    document.querySelectorAll(
      'header .site-header-logos__divider, header .site-header-logos > span[aria-hidden="true"]'
    ).forEach(function (el) {
      el.setAttribute("style", style);
    });
    document.querySelectorAll("header .css-1qav3gh").forEach(function (el) {
      el.setAttribute("style", style);
    });
  }

  function hideChatbotMenu() {
    document.querySelectorAll("header .mantine-c1sy14, header .mantine-ykctob").forEach(function (el) {
      var text = (el.textContent || "").trim();
      if (text !== "Чат-бот" && text !== "Навігатор") {
        return;
      }

      var trigger = el.closest('[aria-haspopup="menu"]');
      if (!trigger) {
        return;
      }

      var wrap = trigger.closest(".mantine-1xkg0b8");
      if (wrap && wrap.parentElement && wrap.parentElement.classList.contains("mantine-1xkg0b8")) {
        wrap.parentElement.remove();
        return;
      }

      if (wrap) {
        wrap.remove();
        return;
      }

      trigger.remove();
    });
  }

  function hideNavigatorMenu() {
    document.querySelectorAll("header .mantine-c1sy14").forEach(function (el) {
      if ((el.textContent || "").trim() !== "Навігатор") return;

      var trigger = el.closest('[aria-haspopup="menu"]');
      if (!trigger) return;

      var wrap = trigger.closest(".mantine-1xkg0b8");
      if (wrap && wrap.parentElement && wrap.parentElement.classList.contains("mantine-1xkg0b8")) {
        wrap.parentElement.remove();
        return;
      }

      if (wrap) {
        wrap.remove();
        return;
      }

      trigger.remove();
    });
  }

  function hideSearch() {
    document.querySelectorAll('header img[alt="search"]').forEach(function (img) {
      var box = img.closest(".mantine-6bln36");
      if (box) box.remove();
    });
    document.querySelectorAll("header .mantine-us64po").forEach(function (el) {
      el.remove();
    });
  }

  function updateForeignersLink() {
    document.querySelectorAll('header a[href*="foreigners.navigator"]').forEach(function (link) {
      link.classList.add("css-bho8e5");
      link.classList.remove("css-clvzh3", "internal-article-external-link");
      link.removeAttribute("target");
      link.removeAttribute("rel");
      link.querySelectorAll("svg").forEach(function (svg) {
        svg.remove();
      });
      var icon = link.querySelector(".header-foreigners-link__icon");
      var label = link.querySelector(".mantine-Text-root");
      if (
        icon &&
        label &&
        label.textContent.trim() === FOREIGNERS_LABEL &&
        icon.getAttribute("width") === "18" &&
        !link.querySelector(".internal-article-link__sr-only") &&
        !link.querySelector(".internal-article-external-link__icon")
      ) {
        return;
      }
      link.innerHTML = foreignersLinkHtml();
    });
  }

  function decodeChain(value) {
    var current = (value || "").replace(/&amp;/g, "&");
    for (var i = 0; i < 5; i++) {
      try {
        var decoded = decodeURIComponent(current.replace(/\+/g, " "));
        if (decoded === current) break;
        current = decoded;
      } catch (e) {
        break;
      }
    }
    return current;
  }

  function directUrlFromNextImage(src) {
    if (!src || src.indexOf("_next/image") === -1) return null;
    try {
      var url = new URL(src, window.location.origin);
      var param = url.searchParams.get("url");
      if (param) {
        var direct = decodeChain(param);
        if (direct.indexOf("http") === 0) return direct;
      }
    } catch (e) {}
    var match = src.match(/url=([^&]+)/);
    if (!match) return null;
    var direct = decodeChain(match[1]);
    if (direct.indexOf("http") === 0) return direct;
    return null;
  }

  function fixHeaderLogoImg(img) {
    if (!img || img.tagName !== "IMG") return false;
    var alt = img.getAttribute("alt") || "";
    var expected =
      alt === "Правовий навігатор"
        ? NAVIGATOR_LOGO
        : alt === "Принцип"
          ? PRYNCYP_LOGO
          : null;
    if (!expected) return false;

    var src = img.getAttribute("src") || img.src || "";
    if (isDirectLogoSrc(src)) return false;

    var direct = directUrlFromNextImage(src);
    if (direct && direct.indexOf(expected.slice(1)) !== -1) {
      img.src = direct;
    } else {
      img.src = expected;
    }
    img.removeAttribute("srcset");
    img.removeAttribute("srcSet");
    return true;
  }

  function fixHeaderLogos() {
    document.querySelectorAll('header img[alt="Правовий навігатор"], header img[alt="Принцип"]').forEach(fixHeaderLogoImg);
  }

  function fixImage(img) {
    if (!img || img.tagName !== "IMG") return false;

    var alt = img.getAttribute("alt") || "";
    if (alt === "Правовий навігатор" || alt === "Принцип") {
      return fixHeaderLogoImg(img);
    }

    var src = img.getAttribute("src") || img.src || "";
    if (src.indexOf("Logo_navigator") !== -1 || src.indexOf("Logo_pryncyp") !== -1) {
      return false;
    }

    var expected = img.dataset.navDirectSrc || "";
    if (expected && src === expected) return false;

    var direct = directUrlFromNextImage(src);
    if (!direct) {
      var srcset = img.getAttribute("srcset") || img.getAttribute("srcSet") || "";
      if (srcset.indexOf("_next/image") !== -1) {
        direct = directUrlFromNextImage(srcset.split(",")[0].trim().split(" ")[0]);
      }
    }

    if (!direct) return false;
    if (expected === direct && src === direct) return false;

    img.dataset.navDirectSrc = direct;
    img.src = direct;
    img.removeAttribute("srcset");
    img.removeAttribute("srcSet");
    return true;
  }

  function fixNextImages() {
    document.querySelectorAll("img").forEach(fixImage);
  }

  function scheduleHeaderPatch() {
    if (headerPatchFrame) {
      return;
    }
    headerPatchFrame = window.requestAnimationFrame(function () {
      headerPatchFrame = null;
      runPatch();
    });
  }

  function bindHeaderObserver() {
    var header = document.querySelector("header");
    if (!header || headerObserver) {
      return;
    }

    headerObserver = new MutationObserver(scheduleHeaderPatch);
    headerObserver.observe(header, {
      childList: true,
      subtree: true,
    });
  }

  function isHeaderBaked() {
    return document.documentElement.getAttribute("data-header-layout-baked") === "1";
  }

  function runPatch() {
    if (isHeaderBaked()) {
      repairHeaderNavCluster();
      updateForeignersLink();
      fixNextImages();
      return;
    }

    injectLogos();
    repairHeaderNavCluster();
    hideSearch();
    hideNavigatorMenu();
    hideChatbotMenu();
    updateForeignersLink();
    fixHeaderDividers();
    fixHeaderLogos();
    fixNextImages();
    bindHeaderObserver();
  }

  scheduleNavPatches(runPatch);
})();
