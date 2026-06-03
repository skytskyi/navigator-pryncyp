(function () {
  var POST_HYDRATION_DELAYS = [100, 500, 1500];

  function isStaticPage() {
    return document.documentElement.getAttribute("data-static-page") === "1";
  }

  function run(fn) {
    try {
      fn();
    } catch (error) {
      console.error("[patch-runtime]", error);
    }
  }

  window.scheduleNavPatches = function scheduleNavPatches(fn) {
    run(fn);

    if (isStaticPage()) {
      if (document.readyState === "loading") {
        document.addEventListener(
          "DOMContentLoaded",
          function () {
            run(fn);
          },
          { once: true }
        );
      }
      return;
    }

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", function () {
        run(fn);
      });
    }

    window.addEventListener("load", function () {
      run(fn);
    });

    for (var i = 0; i < POST_HYDRATION_DELAYS.length; i++) {
      setTimeout(run, POST_HYDRATION_DELAYS[i], fn);
    }
  };
})();
