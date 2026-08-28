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
})();
