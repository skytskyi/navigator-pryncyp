(function () {
  var HOME_TITLE = "Знайдіть відповіді на свої правові питання";
  var SEARCH_PLACEHOLDER = "Пошук за темою або послугою";

  function isHomePage() {
    if (typeof normalizeSitePath === "function") {
      return normalizeSitePath(window.location.pathname) === "/";
    }
    var path = window.location.pathname.replace(/\/+$/, "") || "/";
    return path === "" || path === "/" || path === "/index.html";
  }

  function searchActionUrl() {
    return typeof siteUrl === "function" ? siteUrl("/search/") : "/search/";
  }

  function searchIconUrl() {
    return typeof siteUrl === "function" ? siteUrl("/img/search.svg") : "/img/search.svg";
  }

  function getHeroBlock() {
    return (
      document.querySelector(".css-ux95hh .css-16uvw1j") ||
      document.querySelector(".css-16uvw1j")
    );
  }

  function submitActionsHtml() {
    return (
      '<span class="app-search-form__divider" aria-hidden="true"></span>' +
      '<button type="submit" class="home-hero-search__submit app-search-form__submit">' +
      '<img class="app-search-form__submit-icon" src="' +
      searchIconUrl() +
      '" width="20" height="20" alt="" aria-hidden="true"/>' +
      '<span class="app-search-form__submit-label">Шукати</span>' +
      "</button>"
    );
  }

  function searchHtml() {
    return (
      '<div class="home-hero-search">' +
      '<form class="home-hero-search__form app-search-form" role="search" action="' +
      searchActionUrl() +
      '" method="get">' +
      '<input type="search" class="home-hero-search__input app-search-form__input" name="q" ' +
      'placeholder="' +
      SEARCH_PLACEHOLDER +
      '" aria-label="' +
      SEARCH_PLACEHOLDER +
      '"/>' +
      submitActionsHtml() +
      "</form>" +
      "</div>"
    );
  }

  function upgradeSearchForm(search) {
    var form = search.querySelector("form");
    if (!form) {
      return;
    }

    form.classList.add("app-search-form");

    var icon = form.querySelector(".home-hero-search__icon");
    if (icon) {
      icon.remove();
    }

    var input = form.querySelector(".home-hero-search__input");
    if (input) {
      input.classList.add("app-search-form__input");
    }

    if (!form.querySelector(".app-search-form__submit")) {
      var wrap = document.createElement("div");
      wrap.innerHTML = submitActionsHtml();
      while (wrap.firstChild) {
        form.appendChild(wrap.firstChild);
      }
    }
  }

  function bindSearchForm(search) {
    var form = search.querySelector("form");
    if (form && !form.dataset.navBound) {
      form.dataset.navBound = "1";
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var input = form.querySelector('input[name="q"]');
        var query = input ? input.value.trim() : "";
        var target = searchActionUrl();
        if (query) {
          target += "?q=" + encodeURIComponent(query);
        }
        window.location.href = target;
      });
    }
  }

  function injectSearch(block) {
    var search = block.querySelector(".home-hero-search");
    if (!search) {
      var h1 = block.querySelector("h1");
      var wrap = document.createElement("div");
      wrap.innerHTML = searchHtml();
      search = wrap.firstElementChild;
      if (h1) {
        h1.insertAdjacentElement("afterend", search);
      } else {
        block.insertBefore(search, block.firstChild);
      }
    } else {
      upgradeSearchForm(search);
    }

    var input = search.querySelector(".home-hero-search__input");
    if (input && input.getAttribute("placeholder") !== SEARCH_PLACEHOLDER) {
      input.setAttribute("placeholder", SEARCH_PLACEHOLDER);
      input.setAttribute("aria-label", SEARCH_PLACEHOLDER);
    }

    bindSearchForm(search);
    return true;
  }

  function removeSearchOutsideHome() {
    document.querySelectorAll(".home-hero-search").forEach(function (search) {
      search.remove();
    });
  }

  function applyHero() {
    if (!isHomePage()) {
      if (typeof normalizeSitePath === "function") {
        removeSearchOutsideHome();
      }
      return false;
    }

    var block = getHeroBlock();
    if (!block) return false;

    var h1 = block.querySelector("h1");
    if (h1 && h1.textContent !== HOME_TITLE) {
      h1.textContent = HOME_TITLE;
    }

    return injectSearch(block);
  }

  function tick() {
    applyHero();
  }

  scheduleNavPatches(tick);
})();
