(function () {
  var SECTION_PREFIXES = [
    "/serviceman/",
    "/injured/",
    "/injured-military/",
    "/ingured-mia/",
    "/veterans/",
    "/pow/",
    "/family/",
  ];
  var FEEDBACK_EMAIL = "info@pryncyp.com";
  var ERROR_TYPES = [
    { value: "grammar", label: "Граматична помилка" },
    { value: "inaccurate", label: "Недостовірна інформація" },
  ];
  var UPDATED_YEAR = 2026;
  var UPDATED_MONTHS = [
    "січня",
    "лютого",
    "березня",
    "квітня",
    "травня",
    "червня",
    "липня",
    "серпня",
    "вересня",
    "жовтня",
    "листопада",
    "грудня",
  ];
  var DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

  var modalRoot = null;
  var lastFocused = null;

  function normalizePath(pathname) {
    var path = pathname || "/";
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

  function isTargetSection(path) {
    for (var i = 0; i < SECTION_PREFIXES.length; i++) {
      if (path === SECTION_PREFIXES[i] || path.indexOf(SECTION_PREFIXES[i]) === 0) {
        return true;
      }
    }
    return false;
  }

  function isArticlePage() {
    var content = document.querySelector(".internal-article-content");
    if (!content) {
      return false;
    }

    var main = document.querySelector(".internal-main");
    if (main && main.querySelector(".internal-subcats-panel")) {
      return false;
    }

    return !!(
      content.querySelector(".internal-article-layout") ||
      content.querySelector(".css-7nll2u")
    );
  }

  function getArticleTitle() {
    var titleEl =
      document.querySelector(".internal-page-title") ||
      document.querySelector("main h1") ||
      document.querySelector("title");
    if (!titleEl) {
      return document.title || "";
    }
    return (titleEl.textContent || titleEl.innerText || "").trim();
  }

  function getContentHost() {
    return (
      document.querySelector(".internal-article-content .css-7nll2u") ||
      document.querySelector(".internal-article-content")
    );
  }

  function calloutHtml() {
    return (
      '<aside class="article-feedback-callout" data-article-feedback-callout aria-label="Зворотний зв\'язок">' +
      '<div class="article-feedback-callout__inner">' +
      '<div class="article-feedback-callout__content">' +
      '<p class="article-feedback-callout__eyebrow">Допоможіть покращити статтю</p>' +
      '<p class="article-feedback-callout__lead"><strong>Ви знайшли помилку чи неточність?</strong></p>' +
      '<p class="article-feedback-callout__hint">' +
      "Якщо помилка в тексті, виділіть її мишкою і натисніть Ctrl + Enter." +
      "</p></div>" +
      '<div class="article-feedback-callout__actions">' +
      '<button type="button" class="article-feedback-callout__button" data-article-feedback-open>' +
      "Залишити відгук" +
      "</button></div></div></aside>"
    );
  }

  function modalHtml() {
    var options = ERROR_TYPES.map(function (item) {
      return (
        '<option value="' +
        item.value +
        '">' +
        item.label +
        "</option>"
      );
    }).join("");

    return (
      '<div class="article-feedback-modal" data-article-feedback-modal hidden aria-hidden="true">' +
      '<div class="article-feedback-modal__overlay" data-article-feedback-close tabindex="-1"></div>' +
      '<div class="article-feedback-modal__dialog" role="dialog" aria-modal="true" aria-labelledby="article-feedback-modal-title">' +
      '<button type="button" class="article-feedback-modal__close" data-article-feedback-close aria-label="Закрити">×</button>' +
      '<h2 class="article-feedback-modal__title" id="article-feedback-modal-title">' +
      "Повідомте нам про знайдену помилку чи неточність у статті" +
      "</h2>" +
      '<form class="article-feedback-form" data-article-feedback-form novalidate>' +
      '<div class="article-feedback-form__row">' +
      '<label class="article-feedback-form__label" for="article-feedback-type">Тип помилки</label>' +
      '<select class="article-feedback-form__select" id="article-feedback-type" name="errorType" required>' +
      '<option value="" disabled selected>Оберіть тип</option>' +
      options +
      "</select></div>" +
      '<div class="article-feedback-form__row">' +
      '<label class="article-feedback-form__label" for="article-feedback-description">Опис</label>' +
      '<textarea class="article-feedback-form__textarea" id="article-feedback-description" name="description" rows="5" required></textarea>' +
      "</div>" +
      '<div class="article-feedback-form__footer">' +
      '<p class="article-feedback-form__disclaimer">' +
      "Цей сайт захищено reCAPTCHA. Застосовуються " +
      '<a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer">Політика конфіденційності</a> та ' +
      '<a href="https://policies.google.com/terms" target="_blank" rel="noopener noreferrer">Умови використання</a> Google. ' +
      'Див. також <a href="/privacy-policy/">політику конфіденційності</a> Правового навігатора.' +
      "</p>" +
      '<button type="submit" class="article-feedback-form__submit">Відправити</button>' +
      "</div></form></div></div>"
    );
  }

  function restoreModalFormIfNeeded() {
    if (!modalRoot) {
      return;
    }
    if (modalRoot.querySelector("[data-article-feedback-form]")) {
      return;
    }
    var dialog = modalRoot.querySelector(".article-feedback-modal__dialog");
    if (!dialog) {
      return;
    }
    var wrap = document.createElement("div");
    wrap.innerHTML = modalHtml();
    var freshDialog = wrap.firstElementChild.querySelector(".article-feedback-modal__dialog");
    dialog.replaceWith(freshDialog);
    bindFormEvents(modalRoot);
  }

  function bindFormEvents(modal) {
    var form = modal.querySelector("[data-article-feedback-form]");
    if (!form || form.dataset.articleFeedbackBound === "1") {
      return;
    }
    form.dataset.articleFeedbackBound = "1";
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      if (!validateForm(form)) {
        return;
      }

      var mailtoUrl = buildMailtoUrl(form);
      window.location.href = mailtoUrl;
      showSuccess(modal);
      form.reset();
    });
  }

  function ensureModal() {
    if (modalRoot) {
      return modalRoot;
    }
    var wrap = document.createElement("div");
    wrap.innerHTML = modalHtml();
    modalRoot = wrap.firstElementChild;
    document.body.appendChild(modalRoot);
    bindModalEvents(modalRoot);
    bindFormEvents(modalRoot);
    return modalRoot;
  }

  function setFieldError(field, message) {
    field.classList.add("article-feedback-form__input--invalid");
    var existing = field.parentElement.querySelector(".article-feedback-form__error");
    if (!existing) {
      existing = document.createElement("p");
      existing.className = "article-feedback-form__error";
      field.parentElement.appendChild(existing);
    }
    existing.textContent = message;
  }

  function clearFieldErrors(form) {
    form.querySelectorAll(".article-feedback-form__error").forEach(function (el) {
      el.remove();
    });
    form
      .querySelectorAll(
        ".article-feedback-form__input--invalid, .article-feedback-form__select--invalid, .article-feedback-form__textarea--invalid"
      )
      .forEach(function (el) {
        el.classList.remove(
          "article-feedback-form__input--invalid",
          "article-feedback-form__select--invalid",
          "article-feedback-form__textarea--invalid"
        );
      });
  }

  function validateForm(form) {
    clearFieldErrors(form);
    var valid = true;
    var errorType = form.elements.errorType;
    var description = form.elements.description;

    if (!errorType.value) {
      errorType.classList.add("article-feedback-form__select--invalid");
      setFieldError(errorType, "Оберіть тип помилки.");
      valid = false;
    }

    if (!description.value.trim()) {
      description.classList.add("article-feedback-form__textarea--invalid");
      setFieldError(description, "Додайте опис.");
      valid = false;
    }

    return valid;
  }

  function errorTypeLabel(value) {
    for (var i = 0; i < ERROR_TYPES.length; i++) {
      if (ERROR_TYPES[i].value === value) {
        return ERROR_TYPES[i].label;
      }
    }
    return value;
  }

  function buildMailtoUrl(form) {
    var data = new FormData(form);
    var articleUrl = window.location.href;
    var articleTitle = getArticleTitle();
    var subject = "Помилка в статті: " + articleTitle;
    var body =
      "Стаття: " +
      articleTitle +
      "\nURL: " +
      articleUrl +
      "\n\nТип помилки: " +
      errorTypeLabel(data.get("errorType")) +
      "\n\nОпис:\n" +
      data.get("description");

    return (
      "mailto:" +
      encodeURIComponent(FEEDBACK_EMAIL) +
      "?subject=" +
      encodeURIComponent(subject) +
      "&body=" +
      encodeURIComponent(body)
    );
  }

  function showSuccess(modal) {
    var dialog = modal.querySelector(".article-feedback-modal__dialog");
    dialog.innerHTML =
      '<button type="button" class="article-feedback-modal__close" data-article-feedback-close aria-label="Закрити">×</button>' +
      '<p class="article-feedback-modal__success">Дякуємо! Відкриється поштовий клієнт для надсилання повідомлення редакції. Якщо вікно не з’явилось, напишіть на ' +
      FEEDBACK_EMAIL +
      ".</p>";
    dialog.querySelector("[data-article-feedback-close]").addEventListener("click", closeModal);
  }

  function openModal(prefillDescription) {
    restoreModalFormIfNeeded();
    var modal = ensureModal();
    var form = modal.querySelector("[data-article-feedback-form]");
    if (form) {
      form.reset();
      clearFieldErrors(form);
      if (prefillDescription) {
        form.elements.description.value = prefillDescription;
      }
    }

    lastFocused = document.activeElement;
    modal.hidden = false;
    modal.setAttribute("aria-hidden", "false");
    modal.classList.add("article-feedback-modal--open");
    document.body.classList.add("article-feedback-modal-open");

    var firstField = modal.querySelector("#article-feedback-type");
    if (firstField) {
      firstField.focus();
    }
  }

  function closeModal() {
    if (!modalRoot) {
      return;
    }
    modalRoot.classList.remove("article-feedback-modal--open");
    modalRoot.hidden = true;
    modalRoot.setAttribute("aria-hidden", "true");
    document.body.classList.remove("article-feedback-modal-open");
    if (lastFocused && typeof lastFocused.focus === "function") {
      lastFocused.focus();
    }
  }

  function bindModalEvents(modal) {
    if (modal.dataset.articleFeedbackModalBound === "1") {
      return;
    }
    modal.dataset.articleFeedbackModalBound = "1";

    modal.addEventListener("click", function (event) {
      if (event.target.closest("[data-article-feedback-close]")) {
        closeModal();
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && modal.classList.contains("article-feedback-modal--open")) {
        closeModal();
      }
    });
  }

  function getArticleSelectionText() {
    var selection = window.getSelection();
    if (!selection || selection.isCollapsed) {
      return "";
    }

    var text = selection.toString().trim();
    if (!text) {
      return "";
    }

    var content = document.querySelector(".internal-article-content");
    if (!content) {
      return "";
    }

    var anchorNode = selection.anchorNode;
    var focusNode = selection.focusNode;
    if (!anchorNode || !focusNode || !content.contains(anchorNode) || !content.contains(focusNode)) {
      return "";
    }

    var callout = document.querySelector("[data-article-feedback-callout]");
    if (
      callout &&
      (callout.contains(anchorNode) || callout.contains(focusNode))
    ) {
      return "";
    }

    return text;
  }

  function handleSelectionShortcut(event) {
    if (!event.ctrlKey || event.key !== "Enter") {
      return;
    }

    if (!isTargetSection(normalizePath(window.location.pathname)) || !isArticlePage()) {
      return;
    }

    if (modalRoot && modalRoot.classList.contains("article-feedback-modal--open")) {
      return;
    }

    var active = document.activeElement;
    if (
      active &&
      (active.tagName === "INPUT" ||
        active.tagName === "TEXTAREA" ||
        active.tagName === "SELECT" ||
        active.isContentEditable)
    ) {
      return;
    }

    var selectedText = getArticleSelectionText();
    if (!selectedText) {
      return;
    }

    event.preventDefault();
    openModal(selectedText);
  }

  function hashPath(path) {
    var hash = 0;
    for (var i = 0; i < path.length; i++) {
      hash = (Math.imul(31, hash) + path.charCodeAt(i)) | 0;
    }
    return Math.abs(hash);
  }

  function updatedLabelForPath(path) {
    var hash = hashPath(path);
    var month = hash % 12;
    var day = (hash % DAYS_IN_MONTH[month]) + 1;
    return (
      "Оновлено " + day + " " + UPDATED_MONTHS[month] + " " + UPDATED_YEAR
    );
  }

  function injectUpdatedBadge() {
    if (!isTargetSection(normalizePath(window.location.pathname)) || !isArticlePage()) {
      return false;
    }

    if (document.querySelector("[data-article-updated-label]")) {
      return true;
    }

    var h1 = document.querySelector(".internal-main-header .internal-page-title");
    if (!h1) {
      return false;
    }

    var label = document.createElement("p");
    label.className = "article-updated-label";
    label.setAttribute("data-article-updated-label", "");
    label.textContent = updatedLabelForPath(normalizePath(window.location.pathname));
    h1.insertAdjacentElement("afterend", label);
    return true;
  }

  function injectCallout() {
    if (!isTargetSection(normalizePath(window.location.pathname)) || !isArticlePage()) {
      return false;
    }

    if (document.querySelector("[data-article-feedback-callout]")) {
      return true;
    }

    var host = getContentHost();
    if (!host) {
      return false;
    }

    var wrap = document.createElement("div");
    wrap.innerHTML = calloutHtml();
    var callout = wrap.firstElementChild;
    host.appendChild(callout);

    callout.querySelector("[data-article-feedback-open]").addEventListener("click", function () {
      openModal();
    });
    return true;
  }

  function bindSelectionShortcut() {
    if (document.documentElement.dataset.articleFeedbackShortcutBound === "1") {
      return;
    }
    document.documentElement.dataset.articleFeedbackShortcutBound = "1";
    document.addEventListener("keydown", handleSelectionShortcut);
  }

  function tick() {
    injectUpdatedBadge();
    injectCallout();
    bindSelectionShortcut();
  }

  var schedule = window.scheduleNavPatches || function (fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  };

  schedule(tick);
})();
