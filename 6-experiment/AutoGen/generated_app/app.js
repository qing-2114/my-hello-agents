(function () {
  "use strict";

  var REFRESH_INTERVAL_MS = 30000;

  var priceEl = document.getElementById("price");
  var badgeEl = document.getElementById("state-badge");
  var updatedEl = document.getElementById("last-updated");
  var errorEl = document.getElementById("error");
  var refreshBtn = document.getElementById("refresh");

  var lastPrice = null; // keeps last good value for "stale" display
  var firstLoad = true;

  function pad(n) {
    return n < 10 ? "0" + n : String(n);
  }

  function formatTime(d) {
    return (
      pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds())
    );
  }

  function setStatus(mode) {
    badgeEl.classList.remove("badge-loading", "badge-success", "badge-error");

    if (mode === "loading") {
      badgeEl.textContent = "Loading…";
      badgeEl.classList.add("badge-loading");
    } else if (mode === "success") {
      badgeEl.textContent = "Live";
      badgeEl.classList.add("badge-success");
    } else if (mode === "error") {
      badgeEl.textContent = "Unavailable";
      badgeEl.classList.add("badge-error");
    }
  }

  function renderPrice(usd) {
    // en-US guarantees the thousands separator & two decimals.
    priceEl.textContent = "$" + usd.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
    priceEl.classList.add("is-fresh");
    priceEl.classList.remove("is-stale");
  }

  function showLoading() {
    refreshBtn.disabled = true;
    errorEl.hidden = true;
    setStatus("loading");

    if (lastPrice === null) {
      // First request: skeleton screen.
      priceEl.textContent = "";
      priceEl.classList.remove("is-stale", "is-fresh");
      var skeleton = document.createElement("span");
      skeleton.className = "skeleton skeleton-lg";
      skeleton.setAttribute("aria-hidden", "true");
      priceEl.appendChild(skeleton);
    }
    // Subsequent refreshes keep the previous price visible (no flicker).
  }

  function showError(reason) {
    refreshBtn.disabled = false;
    setStatus("error");
    errorEl.textContent = reason;
    errorEl.hidden = false;

    if (lastPrice !== null) {
      priceEl.classList.add("is-stale");
      priceEl.classList.remove("is-fresh");
    } else {
      priceEl.textContent = "—";
      priceEl.classList.add("is-stale");
    }
  }

  function showSuccess(usd) {
    lastPrice = usd;
    refreshBtn.disabled = false;
    errorEl.hidden = true;
    setStatus("success");
    renderPrice(usd);
    updatedEl.textContent = "Last update: " + formatTime(new Date());
  }

  function friendlyError(err) {
    if (err && err.name === "AbortError") {
      return "Request timed out. Please check your connection.";
    }
    if (err && err.limit) {
      return "Rate limited by the API. Retrying automatically…";
    }
    if (!navigator.onLine) {
      return "Network unavailable. Please check your internet connection.";
    }
    return "Something went wrong while fetching the price.";
  }

  function fetchPrice(signal) {
    return fetch(
      "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&x_cg_demo_api_key=false&_t=" +
        Date.now(),
      { signal: signal }
    ).then(function (res) {
      if (res.status === 429) {
        var e = new Error("Rate limited");
        e.limit = true;
        throw e;
      }
      if (!res.ok) {
        throw new Error("HTTP " + res.status);
      }
      return res.json();
    });
  }

  var abortController = null;

  function refresh() {
    if (abortController) {
      abortController.abort();
    }
    abortController = new AbortController();
    var first = firstLoad;
    firstLoad = false;
    if (first) {
      showLoading();
    }
    refreshBtn.disabled = true;

    fetchPrice(abortController.signal)
      .then(function (data) {
        var usd = data && data.bitcoin && data.bitcoin.usd;
        if (typeof usd !== "number" || !isFinite(usd)) {
          throw new Error("Unexpected response shape");
        }
        showSuccess(usd);
      })
      .catch(function (err) {
        if (err && err.name === "AbortError") {
          return; // superseded by a newer request
        }
        showError(friendlyError(err));
      });
  }

  // Manual refresh is only allowed after the first load has settled.
  refreshBtn.addEventListener("click", function () {
    if (!refreshBtn.disabled) {
      refresh();
    }
  });

  window.addEventListener("online", function () {
    refreshBtn.disabled = false;
    refresh();
  });

  // Kick off the first request immediately.
  refresh();

  // Automatic refresh every 30s (±1s). On failure the previous value is kept
  // (greyed) and the next tick simply retries again at the same interval.
  setInterval(function () {
    if (navigator.onLine) {
      refresh();
    }
  }, REFRESH_INTERVAL_MS);
})();
