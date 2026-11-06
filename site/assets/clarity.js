// Session replay starts only after opt-in. Consent APIs alone can leave
// Clarity running in cookieless mode, so withdrawal also stops the recorder.
(function () {
  // A copied deployment or local preview must not send visits to production.
  if (window.location.hostname !== "benchmark-radar.org") return;
  const STORAGE_KEY = "benchmark-radar:analytics-consent";
  const PROJECT_ID = "ya4h95jvfj";

  function readChoice() {
    try {
      return window.localStorage.getItem(STORAGE_KEY);
    } catch {
      return null;
    }
  }

  function storeChoice(value) {
    try {
      if (value === null) window.localStorage.removeItem(STORAGE_KEY);
      else window.localStorage.setItem(STORAGE_KEY, value);
    } catch {
      // Quota failures can leave an old grant readable. Removing it uses no
      // space and makes withdrawal fail closed on the next page load.
      if (value === "denied") {
        try {
          window.localStorage.removeItem(STORAGE_KEY);
        } catch {
          // Storage inaccessible: readChoice also falls back to no consent.
        }
      }
    }
  }

  function loadClarity() {
    if (window.clarity) return;
    (function (c, l, a, r, i, t, y) {
      c[a] =
        c[a] ||
        function () {
          (c[a].q = c[a].q || []).push(arguments);
        };
      t = l.createElement(r);
      t.async = 1;
      t.src = `https://www.clarity.ms/tag/${i}`;
      y = l.getElementsByTagName(r)[0];
      y.parentNode.insertBefore(t, y);
    })(window, document, "clarity", "script", PROJECT_ID);
    window.clarity("consentv2", { ad_Storage: "denied", analytics_Storage: "granted" });
  }

  function closeBanner() {
    document.getElementById("analytics-consent")?.remove();
  }

  function stopClarity() {
    if (window.clarity) {
      window.clarity("consentv2", { ad_Storage: "denied", analytics_Storage: "denied" });
      window.clarity("consent", false);
      window.clarity("stop");
    }
    // Older visits have cookies but no consent key or loaded SDK. Expire both
    // host-only and parent-domain cookies without requesting the tracking tag.
    const domains = window.location.hostname.split(".");
    for (const name of ["_clck", "_clsk"]) {
      document.cookie = `${name}=; Max-Age=0; Path=/`;
      for (let i = 0; i < domains.length; i += 1) {
        document.cookie = `${name}=; Max-Age=0; Path=/; Domain=${domains.slice(i).join(".")}`;
      }
    }
    // Clarity can restart asynchronously in cookieless mode after denial.
    // Discard that runtime and any pending tag before it can record again.
    if (window.clarity) window.location.reload();
  }

  function choose(value) {
    storeChoice(value);
    closeBanner();
    if (value === "granted") loadClarity();
    else stopClarity();
  }

  // Maintainers can bookmark this URL once per browser. Reuse the persisted
  // denial so ordinary navigation stays excluded without recording an ID/IP.
  if (new URLSearchParams(window.location.search).get("analytics") === "off") {
    storeChoice("denied");
    stopClarity();
    return;
  }

  function showBanner() {
    if (document.getElementById("analytics-consent")) return;
    const banner = document.createElement("section");
    banner.id = "analytics-consent";
    banner.className = "analytics-consent";
    banner.setAttribute("role", "region");
    banner.setAttribute("aria-label", "Analytics consent");
    banner.innerHTML = `
      <p data-i18n="analytics-consent-text">
        May we use Microsoft Clarity to record session replays and heatmaps of your visit? They help us
        improve navigation. Nothing is recorded unless you accept.
        <a href="https://privacy.microsoft.com/privacystatement">Microsoft Privacy Statement</a>
      </p>
      <div class="analytics-consent-actions">
        <button type="button" data-consent="denied" data-i18n="Decline">Decline</button>
        <button type="button" data-consent="granted" data-i18n="Accept">Accept</button>
      </div>`;
    banner.addEventListener("click", (event) => {
      const button = event.target.closest("[data-consent]");
      if (button) choose(button.dataset.consent);
    });
    document.body.append(banner);
    document.dispatchEvent(new Event("analytics-consent-shown"));
  }

  document.addEventListener("click", (event) => {
    if (event.target.closest("[data-analytics-consent-reset]")) {
      event.preventDefault();
      showBanner();
    }
  });

  // Every entry point that loads the recorder must let visitors withdraw.
  if (!document.querySelector("[data-analytics-consent-reset]")) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "privacy-choice";
    button.dataset.analyticsConsentReset = "";
    button.dataset.i18n = "Change analytics choice";
    button.textContent = "Change analytics choice";
    document.querySelector(".privacy-note")?.append(button);
  }

  function syncChoice() {
    const value = readChoice();
    closeBanner();
    if (value === "granted") loadClarity();
    else {
      stopClarity();
      if (value !== "denied") showBanner();
    }
  }

  window.addEventListener("storage", (event) => {
    if (event.storageArea !== window.localStorage) return;
    if (event.key !== STORAGE_KEY && event.key !== null) return;
    // Read the current value: a queued event may describe an older choice.
    syncChoice();
  });
  window.addEventListener("pageshow", (event) => {
    // A restored page can have missed withdrawal while it was in the back cache.
    if (event.persisted) syncChoice();
  });

  const choice = readChoice();
  if (choice !== "granted") stopClarity();
  if (choice === "granted") loadClarity();
  else if (choice !== "denied") showBanner();
})();
