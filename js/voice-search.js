(function () {
  var MIC_INPUT_SRC = "/img/microphone-dark.svg";
  var MIC_OVERLAY_SRC = "/img/microphone-inverted.svg";
  var OVERLAY_ID = "voice-dictation-overlay";
  var OPEN_CLASS = "voice-dictation-overlay--open";
  var BODY_CLASS = "voice-dictation-open";
  var FORM_SELECTOR = ".home-hero-search__form, .site-search-page__form";
  var lastFocus = null;

  function micSrc(path) {
    return typeof siteUrl === "function" ? siteUrl(path) : path;
  }

  function getOverlay() {
    var overlay = document.getElementById(OVERLAY_ID);
    if (overlay) {
      return overlay;
    }

    overlay = document.createElement("div");
    overlay.id = OVERLAY_ID;
    overlay.className = "voice-dictation-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-label", "Голосовий ввід");
    overlay.setAttribute("aria-hidden", "true");
    overlay.innerHTML =
      '<button type="button" class="voice-dictation-overlay__close" aria-label="Закрити">&times;</button>' +
      '<div class="voice-dictation-overlay__panel">' +
      '<p class="voice-dictation-overlay__label">Диктуйте</p>' +
      '<div class="voice-dictation-overlay__mic-wrap">' +
      '<span class="voice-dictation-overlay__pulse" aria-hidden="true"></span>' +
      '<span class="voice-dictation-overlay__pulse voice-dictation-overlay__pulse--delay" aria-hidden="true"></span>' +
      '<span class="voice-dictation-overlay__circle">' +
      '<img src="' +
      micSrc(MIC_OVERLAY_SRC) +
      '" width="36" height="36" alt="" aria-hidden="true"/>' +
      "</span>" +
      "</div>" +
      "</div>";

    document.body.appendChild(overlay);

    overlay.querySelector(".voice-dictation-overlay__close").addEventListener("click", closeOverlay);
    overlay.addEventListener("click", function (event) {
      if (event.target === overlay) {
        closeOverlay();
      }
    });

    return overlay;
  }

  function openOverlay() {
    lastFocus = document.activeElement;
    var overlay = getOverlay();
    overlay.classList.add(OPEN_CLASS);
    overlay.setAttribute("aria-hidden", "false");
    document.body.classList.add(BODY_CLASS);
    var closeBtn = overlay.querySelector(".voice-dictation-overlay__close");
    if (closeBtn) {
      closeBtn.focus();
    }
  }

  function closeOverlay() {
    var overlay = document.getElementById(OVERLAY_ID);
    if (!overlay) {
      return;
    }
    overlay.classList.remove(OPEN_CLASS);
    overlay.setAttribute("aria-hidden", "true");
    document.body.classList.remove(BODY_CLASS);
    if (lastFocus && typeof lastFocus.focus === "function") {
      lastFocus.focus();
    }
    lastFocus = null;
  }

  function onDocumentKeydown(event) {
    if (event.key === "Escape") {
      closeOverlay();
    }
  }

  function createMicButton(form) {
    var button = document.createElement("button");
    button.type = "button";
    button.className = form.classList.contains("home-hero-search__form")
      ? "home-hero-search__mic"
      : "site-search-page__mic";
    button.setAttribute("aria-label", "Голосовий ввід");
    button.innerHTML =
      '<img src="' + micSrc(MIC_INPUT_SRC) + '" width="24" height="24" alt="" aria-hidden="true"/>';
    button.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      openOverlay();
    });
    return button;
  }

  function enhanceForm(form) {
    if (!form || form.dataset.voiceMicBound === "1") {
      return;
    }

    var anchor =
      form.querySelector(".app-search-form__divider") ||
      form.querySelector('[type="submit"]');
    var mic = createMicButton(form);
    if (anchor) {
      form.insertBefore(mic, anchor);
    } else {
      form.appendChild(mic);
    }
    form.dataset.voiceMicBound = "1";
  }

  function init() {
    document.querySelectorAll(FORM_SELECTOR).forEach(enhanceForm);
  }

  document.addEventListener("keydown", onDocumentKeydown);

  var schedule = window.scheduleNavPatches || function (fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  };

  schedule(init);
  window.setTimeout(init, 200);
  window.setTimeout(init, 600);
})();
