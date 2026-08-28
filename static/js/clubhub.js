/*
 * ClubHub theme JS: sidebar toggle, sidebar auto-collapse and
 * scroll-to-top. Vanilla rewrite of SB Admin 2's sb-admin-2.js after
 * the Bootstrap 5 migration (no jQuery, no Bootstrap JS dependency
 * except the optional sidebar accordion collapse).
 */

(function () {

  "use strict";

  // Toggle the side navigation
  document.querySelectorAll("#sidebarToggle, #sidebarToggleTop").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var sidebar = document.querySelector(".sidebar");
      if (!sidebar) return;
      document.body.classList.toggle("sidebar-toggled");
      sidebar.classList.toggle("toggled");
      // Collapse any open sidebar accordions (Bootstrap 5 API)
      if (sidebar.classList.contains("toggled") && window.bootstrap) {
        sidebar.querySelectorAll(".collapse.show").forEach(function (el) {
          bootstrap.Collapse.getOrCreateInstance(el).hide();
        });
      }
    });
  });

  // Collapse sidebar accordions below 768px and auto-toggle the
  // collapsed state below 480px
  window.addEventListener("resize", function () {
    var sidebar = document.querySelector(".sidebar");
    if (!sidebar) return;
    if (window.innerWidth < 768 && window.bootstrap) {
      sidebar.querySelectorAll(".collapse.show").forEach(function (el) {
        bootstrap.Collapse.getOrCreateInstance(el).hide();
      });
    }
    if (window.innerWidth < 480 && !sidebar.classList.contains("toggled")) {
      document.body.classList.add("sidebar-toggled");
      sidebar.classList.add("toggled");
    }
  });

  // Scroll to top button appear / smooth scroll
  var scrollToTop = document.querySelector(".scroll-to-top");
  if (scrollToTop) {
    window.addEventListener("scroll", function () {
      scrollToTop.style.display = window.scrollY > 100 ? "block" : "none";
    });
    scrollToTop.addEventListener("click", function (e) {
      e.preventDefault();
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  /*
   * Horizontal scrolling for data tables: the paginated table cards
   * (.ch-table-card, header/footer bars) get a synced scrollbar above
   * their .table-responsive (.ch-hscroll-proxy), so a wide table can be
   * scrolled from the top without walking down to its own bottom
   * scrollbar. Other tables keep only their native bottom scrollbar.
   * The proxy is only shown while the table actually overflows, and
   * its height matches the native scrollbar (which is zero on
   * overlay-scrollbar platforms, where it would be invisible).
   */
  function enhanceTableScroll(container) {
    if (container.dataset.chHscroll) return;
    container.dataset.chHscroll = "1";

    var proxy = document.createElement("div");
    proxy.className = "ch-hscroll-proxy";
    proxy.setAttribute("aria-hidden", "true");
    var spacer = document.createElement("div");
    proxy.appendChild(spacer);
    container.parentNode.insertBefore(proxy, container);

    var lastHeight = null;
    var lastSpacer = null;

    function update() {
      var overflowing = container.scrollWidth > container.clientWidth + 1;
      var height = overflowing
        ? (container.offsetHeight - container.clientHeight) + "px"
        : "0px";
      var spacerWidth = overflowing ? container.scrollWidth + "px" : null;
      if (height === lastHeight && spacerWidth === lastSpacer) return;
      lastHeight = height;
      lastSpacer = spacerWidth;
      // scrollWidth is the scrollable extent — exactly what the proxy
      // must mirror (a fractionally wide table rounds the same way).
      if (spacerWidth) spacer.style.width = spacerWidth;
      proxy.style.height = height;
      proxy.scrollLeft = container.scrollLeft;
    }

    container.addEventListener("scroll", function () {
      if (proxy.scrollLeft !== container.scrollLeft) {
        proxy.scrollLeft = container.scrollLeft;
      }
    });
    proxy.addEventListener("scroll", function () {
      if (container.scrollLeft !== proxy.scrollLeft) {
        container.scrollLeft = proxy.scrollLeft;
      }
    });

    // Container size changes (window, sidebar toggle), table size changes
    // (HTMX row swaps) and late font loads all need a re-measure. The
    // interval is a safety net for contexts that change layout without
    // firing resize or ResizeObserver callbacks.
    if (window.ResizeObserver) {
      var observer = new ResizeObserver(update);
      observer.observe(container);
      var table = container.querySelector("table");
      if (table) observer.observe(table);
    }
    window.addEventListener("resize", update);
    window.addEventListener("load", update);
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(update);
    }
    setInterval(update, 800);
    update();
  }

  /*
   * Phone-width header columns are sized by their data cells only (CSS
   * takes .th-label out of flow, see clubhub.css). That needs the label
   * inside an element, so wrap plain-text header cells once. Structured
   * headers (sortable .th-sort-link) already have the right shape and
   * are left alone, as are cells mixing text with elements.
   */
  function wrapHeaderLabels() {
    document.querySelectorAll("#page-top table thead th").forEach(function (th) {
      if (th.querySelector(".th-sort-link, .th-label")) return;
      for (var i = 0; i < th.childNodes.length; i++) {
        if (th.childNodes[i].nodeType === 1) return;
      }
      if (!th.textContent.trim()) return;
      var label = document.createElement("span");
      label.className = "th-label";
      while (th.firstChild) {
        label.appendChild(th.firstChild);
      }
      th.appendChild(label);
    });
  }

  function enhanceAllTableScrolls() {
    // Only the paginated table cards get the synced top scrollbar.
    document.querySelectorAll(".ch-table-card .table-responsive").forEach(enhanceTableScroll);
  }
  wrapHeaderLabels();
  enhanceAllTableScrolls();
  document.body.addEventListener("htmx:afterSwap", function () {
    wrapHeaderLabels();
    enhanceAllTableScrolls();
  });
})();
