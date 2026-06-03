(function () {
  if (document.documentElement.getAttribute("data-header-layout-baked") === "1") {
    return;
  }

  var STORAGE_KEY = "nav-header-persist-v1";

  function isInternalLink(anchor, event) {
    if (!anchor || anchor.hasAttribute("download")) {
      return false;
    }
    if (event) {
      if (event.defaultPrevented || event.button !== 0) {
        return false;
      }
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
        return false;
      }
    }

    var target = (anchor.getAttribute("target") || "").toLowerCase();
    if (target && target !== "_self") {
      return false;
    }

    var href = anchor.getAttribute("href");
    if (!href || href.charAt(0) === "#") {
      return false;
    }

    try {
      var url = new URL(href, window.location.href);
      return url.origin === window.location.origin;
    } catch (error) {
      return false;
    }
  }

  function measureSnapshotHtml(html) {
    var measure = document.createElement("div");
    measure.style.cssText = "position:absolute;left:-9999px;top:0;width:100%;visibility:hidden;pointer-events:none";
    measure.innerHTML = html;
    document.body.appendChild(measure);
    var height = Math.ceil(measure.getBoundingClientRect().height);
    measure.remove();
    return height;
  }

  function snapshotHeader() {
    var header = document.querySelector("header.css-9r8uj3, header");
    if (!header) {
      return;
    }

    var categoryNav = document.querySelector(".category-nav");
    var html = header.outerHTML;
    if (categoryNav) {
      html += categoryNav.outerHTML;
    }

    var height = measureSnapshotHtml(html);
    try {
      sessionStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          html: html,
          height: height,
        })
      );
    } catch (error) {}
  }

  function restoreHeaderSnapshot() {
    var raw = null;
    try {
      raw = sessionStorage.getItem(STORAGE_KEY);
    } catch (error) {
      return false;
    }
    if (!raw) {
      return false;
    }

    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch (error) {}

    var data;
    try {
      data = JSON.parse(raw);
    } catch (error) {
      return false;
    }
    if (!data || !data.html) {
      return false;
    }

    if (document.getElementById("nav-header-persist")) {
      return true;
    }

    var shell = document.createElement("div");
    shell.id = "nav-header-persist";
    shell.setAttribute("aria-hidden", "true");
    shell.style.cssText =
      "position:fixed;top:0;left:0;right:0;z-index:10001;pointer-events:none;background:#fff";
    shell.innerHTML = data.html;

    if (document.body) {
      document.body.insertBefore(shell, document.body.firstChild);
    } else {
      document.documentElement.appendChild(shell);
    }

    var height = data.height || Math.ceil(shell.getBoundingClientRect().height);
    document.documentElement.classList.add("nav-header-persist");
    document.documentElement.style.setProperty("--nav-persist-height", height + "px");
    return true;
  }

  window.dismissNavHeaderPersist = function dismissNavHeaderPersist() {
    var shell = document.getElementById("nav-header-persist");
    if (!shell) {
      return false;
    }
    shell.remove();
    document.documentElement.classList.remove("nav-header-persist");
    document.documentElement.style.removeProperty("--nav-persist-height");
    return true;
  };

  restoreHeaderSnapshot();

  document.addEventListener(
    "click",
    function (event) {
      var anchor =
        event.target && event.target.closest ? event.target.closest("a[href]") : null;
      if (!isInternalLink(anchor, event)) {
        return;
      }

      try {
        var next = new URL(anchor.href, window.location.href);
        var current = new URL(window.location.href);
        if (
          next.pathname === current.pathname &&
          next.search === current.search &&
          !next.hash
        ) {
          return;
        }
      } catch (error) {
        return;
      }

      snapshotHeader();
    },
    true
  );

  function isHomePage() {
    var path = window.location.pathname.replace(/\/index\.html$/, "").replace(/\/+$/, "");
    return path === "" || path === "/";
  }

  function tryDismissPersistShell() {
    if (!document.getElementById("nav-header-persist")) {
      return;
    }

    var header = document.querySelector("header .site-header-logos");
    if (!header) {
      return;
    }

    if (!isHomePage() && !document.querySelector(".category-nav")) {
      return;
    }

    window.dismissNavHeaderPersist();
  }

  window.tryDismissNavHeaderPersist = tryDismissPersistShell;

  function scheduleDismissAttempts() {
    var delays = [0, 50, 150, 400];
    for (var i = 0; i < delays.length; i++) {
      setTimeout(tryDismissPersistShell, delays[i]);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", scheduleDismissAttempts);
  } else {
    scheduleDismissAttempts();
  }

  window.addEventListener("load", scheduleDismissAttempts);
  window.addEventListener("pageshow", function (event) {
    if (event.persisted) {
      window.dismissNavHeaderPersist();
    }
  });
})();
