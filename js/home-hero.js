(function () {
  var HOME_TITLE = "Отримайте правову допомогу, яка вам потрібна";
  var SEARCH_PLACEHOLDER = "Пошук за темою або послугою";

  function isHomePage() {
    var path = window.location.pathname.replace(/\/+$/, "") || "/";
    return path === "" || path === "/" || path === "/index.html";
  }

  function getHeroBlock() {
    return (
      document.querySelector(".css-ux95hh .css-16uvw1j") ||
      document.querySelector(".css-16uvw1j")
    );
  }

  function searchHtml() {
    return (
      '<div class="home-hero-search">' +
      '<form class="home-hero-search__form" role="search" action="/search/" method="get">' +
      '<img class="home-hero-search__icon" src="/_next/static/media/search.1af3630f.svg" alt="" aria-hidden="true"/>' +
      '<input type="search" class="home-hero-search__input" name="q" ' +
      'placeholder="' +
      SEARCH_PLACEHOLDER +
      '" aria-label="' +
      SEARCH_PLACEHOLDER +
      '"/>' +
      "</form>" +
      "</div>"
    );
  }

  function bindSearchForm(search) {
    var form = search.querySelector("form");
    if (form && !form.dataset.navBound) {
      form.dataset.navBound = "1";
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var input = form.querySelector('input[name="q"]');
        var query = input ? input.value.trim() : "";
        var target = "/search/";
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
      removeSearchOutsideHome();
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
