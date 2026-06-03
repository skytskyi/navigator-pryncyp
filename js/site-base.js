(function () {
  var cachedBase = null;

  function readMetaBasePath() {
    var meta = document.querySelector('meta[name="site-base-path"]');
    if (meta && meta.getAttribute("content")) {
      return meta.getAttribute("content").replace(/\/+$/, "");
    }
    return "";
  }

  function detectBaseFromPathname() {
    if (typeof window === "undefined" || !window.location) {
      return "";
    }
    var host = window.location.hostname || "";
    if (!host.endsWith("github.io")) {
      return "";
    }
    var segments = window.location.pathname.split("/").filter(Boolean);
    if (!segments.length) {
      return "";
    }
    return "/" + segments[0];
  }

  function getSiteBasePath() {
    if (cachedBase !== null) {
      return cachedBase;
    }
    var fromDataset = document.documentElement.dataset.siteBasePath;
    if (fromDataset) {
      cachedBase = String(fromDataset).replace(/\/+$/, "");
      return cachedBase;
    }
    var fromMeta = readMetaBasePath();
    if (fromMeta) {
      cachedBase = fromMeta;
      return cachedBase;
    }
    cachedBase = detectBaseFromPathname();
    return cachedBase;
  }

  function stripSiteBasePath(pathname) {
    var path = pathname || "/";
    var base = getSiteBasePath();
    if (!base) {
      return path;
    }
    if (path === base || path === base + "/") {
      return "/";
    }
    if (path.indexOf(base + "/") === 0) {
      return path.slice(base.length) || "/";
    }
    return path;
  }

  function siteUrl(path) {
    var base = getSiteBasePath();
    if (!path) {
      return base ? base + "/" : "/";
    }
    if (path.charAt(0) !== "/") {
      path = "/" + path;
    }
    if (!base) {
      return path;
    }
    if (path === base || path.indexOf(base + "/") === 0) {
      return path;
    }
    return base + path;
  }

  function normalizeSitePath(pathname) {
    var path = stripSiteBasePath(pathname || "/");
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

  window.getSiteBasePath = getSiteBasePath;
  window.stripSiteBasePath = stripSiteBasePath;
  window.siteUrl = siteUrl;
  window.normalizeSitePath = normalizeSitePath;
})();
