(function () {
  var PAGE_TITLE = "Поранені";
  var MOU_HREF = "/injured-military/";
  var MOU_TITLE = "Поранені із системи МОУ";
  var MIA_HREF = "/ingured-mia/";
  var MIA_TITLE = "Поранені із системи МВС";
  var ICON =
    "https://storage.googleapis.com/b-legal-navigator/treatment_b5a48a52c9/treatment_b5a48a52c9.svg";

  function isInjuredSelectPage() {
    var path = window.location.pathname.replace(/\/+$/, "");
    return path === "/injured" || path === "/injured/index.html";
  }

  function getHeroBlock() {
    return (
      document.querySelector(".css-ux95hh .css-16uvw1j") ||
      document.querySelector(".css-16uvw1j")
    );
  }

  function getCardContainer() {
    return (
      document.querySelector(".css-1jbx5ca.mantine-17do081") ||
      document.querySelector(".css-1jbx5ca")
    );
  }

  function cardHtml(href, title, mobileClass, desktopClass, desktopInnerClass) {
    return (
      '<a style="width:100%" class="css-1gooe0" href="' +
      href +
      '"><div class="css-bxqx5h ' +
      mobileClass +
      '"><img alt="role-icon" loading="lazy" width="226" height="226" decoding="async" data-nimg="1" class="css-4gnbsq" style="color:transparent" src="' +
      ICON +
      '"/><p class="css-6ixod5">' +
      title +
      "</p></div></a>" +
      '<a style="width:calc(100% / 2)" class="css-1q51wqn" href="' +
      href +
      '"><div class="css-5km5in ' +
      desktopInnerClass +
      '" style="padding:28px 24px"><img alt="role-icon" loading="lazy" width="226" height="226" decoding="async" data-nimg="1" class="css-4gnbsq" style="color:transparent" src="' +
      ICON +
      '"/><p class="css-6ixod5">' +
      title +
      "</p></div></a>"
    );
  }

  function selectionCardsHtml() {
    return (
      cardHtml(MOU_HREF, MOU_TITLE, "mantine-1rrwkei", "css-1q51wqn", "mantine-1yhtny1") +
      cardHtml(MIA_HREF, MIA_TITLE, "mantine-1bjr6m8", "css-1q51wqn", "mantine-19v1wa0")
    );
  }

  function cardTitles(container) {
    return Array.from(container.querySelectorAll("p.css-6ixod5")).map(function (node) {
      return node.textContent.trim();
    });
  }

  function isSelectionCards(container) {
    var titles = cardTitles(container);
    return titles.indexOf(MOU_TITLE) !== -1 && titles.indexOf(MIA_TITLE) !== -1;
  }

  function applySelectionPage() {
    if (!isInjuredSelectPage()) {
      return false;
    }

    var changed = false;
    var hero = getHeroBlock();
    if (hero) {
      var h1 = hero.querySelector("h1");
      if (h1 && h1.textContent.trim() !== PAGE_TITLE) {
        h1.textContent = PAGE_TITLE;
        changed = true;
      }
    }

    var container = getCardContainer();
    if (container && !isSelectionCards(container)) {
      container.innerHTML = selectionCardsHtml();
      changed = true;
    }

    return changed;
  }

  function tick() {
    applySelectionPage();
  }

  scheduleNavPatches(tick);
})();
