CLUBHUB — README
====================================================================

Sport club administration web app (started for a Swedish boxing club,
built to grow into a multi-tenant SaaS). Everything is server-rendered
by Django templates on a Bootstrap-based UI — there is no single-page
front-end framework, and no caching or speed technique needs one.

Feature scope: people/members/guardians/staff, groups, seasons,
recurring schedules, attendance, per-season fees + invoices with
manual payment registration, email notifications, a public read-only
schedule API, and per-club branding/theming.

--------------------------------------------------------------------
PACKAGES & FRAMEWORKS
--------------------------------------------------------------------

Backend
  Python 3.14           Runtime.
  Django 6.1            Web framework (the big one). Renders every
                        page from HTML templates; the ORM handles all
                        database access; the middleware stack handles
                        sessions, auth, CSRF, compression.
  SQLite (dev)          Single-file database, WAL journal mode enabled.
                        Postgres is intended for production.
  Django REST
  Framework 3.18        JSON API toolkit. Powers the public read-only
                        endpoints under /api/ (clubs, seasons, groups,
                        schedule) — anonymous but rate-limited.
  whitenoise 6.12       Serves static files directly from Django. On
                        deploy, collectstatic fingerprints every asset
                        (clubhub.f2c3b82d.css), precompresses it to
                        .gz and .br, and whitenoise answers with
                        far-future Cache-Control: immutable — each
                        browser downloads each asset exactly once.
  Brotli 1.2            Better compression than gzip. Used via
                        whitenoise for static files; Django's
                        GZipMiddleware compresses dynamic HTML/JSON.
  Pillow                Image handling (club logo/background uploads).
  openpyxl 3.1          Excel read/write — the Sportadmin
                        "Personregister" xlsx import (with preview)
                        and the register export.
  python-dateutil       rrule: expands recurring schedule templates
                        ("every Tuesday 18:00") into dated Activity
                        rows within season bounds.

Front-end
  Bootstrap 5.3.8       The one CSS framework (vendored, no CDN, and
                        no jQuery anywhere).
  SB Admin 2 skin       The admin-dashboard look: a component layer
                        spliced on top of Bootstrap inside
                        static/css/clubhub.css. Layer order: Bootstrap
                        core -> SB Admin 2 -> ClubHub custom styles.
                        Custom rules only go in the later layers.
  FontAwesome 5         Icon font, vendored. Only the woff2 webfont
                        is kept; its CSS is trimmed to woff2-only.
  Nunito                App font, self-hosted woff2 files in
                        static/vendor/fonts/nunito/ with @font-face
                        rules in clubhub.css. font-display: swap shows
                        text immediately in a fallback font; disjoint
                        unicode-range subsets mean browsers download
                        only the weights/subsets a page uses.
  HTMX 2.0              Tiny JS library (vendored in
                        static/vendor/htmx/) that lets ordinary HTML
                        attributes fetch a partial response and swap
                        it into the page — interactivity without
                        custom JS or a framework.
  Vanilla JS            static/js/clubhub.js: sidebar toggle,
                        scroll-to-top, synced table scrollbars. No
                        jQuery, no build step.

--------------------------------------------------------------------
TECHNIQUES — HOW IT WORKS
--------------------------------------------------------------------

Template inheritance (and what it does NOT do)
  App pages extend templates/base.html (sidebar, topbar, scripts);
  login pages extend auth_base.html. Inheritance is purely a
  server-side render-time concept: the shell is re-rendered into every
  page's HTML. It does not reduce downloads — but it doesn't inflate
  them either: CSS/JS/fonts are separate files the browser caches
  after the first visit, so navigating re-downloads only the (small)
  HTML document.

Caching without a SPA
  Caching never requires a front-end framework. It lives in two
  places:
  1. Browser/HTTP caching — hashed static filenames + immutable
     Cache-Control headers mean assets are fetched once, ever.
  2. Server-side caching — Django's cache framework (in-process
     LocMem by default; swap for Redis with multiple workers): the
     public API responses are cached per URL for 60 s (cache_page),
     and the computed club theme is cached per club and invalidated
     by a post_save signal when club settings change.
  Authenticated pages are deliberately not cached — their content is
  per-user.

hx-boost navigation
  base.html sets hx-boost="true": ordinary links and forms are fetched
  via XHR and only <body> is swapped in, with pushState URLs —
  app-like navigation without re-parsing CSS/JS. Consequences that the
  code respects:
    - Body scripts re-execute on every navigation, so they must be
      idempotent (clubhub.js uses replaceable window listeners and
      timers that tear themselves down when their element is gone).
    - Auth redirects are converted to full-page navigations by
      clubs/middleware.HtmxAuthRedirectMiddleware (HX-Redirect), so
      the login layout never lands inside the app shell.
  The attendance grid uses plain HTMX partial swaps (hx-post returning
  one table row); file downloads (register export) use direct
  window.location navigation, which hx-boost leaves alone.

Multi-tenancy & permissions
  Every core model carries a Club FK from day one. Querysets are
  always scoped through people/services.py (visible_groups /
  visible_activities): trainers see only their groups, club admins
  see the whole club. Never trust user.is_staff.

Personnummer (Swedish identity number)
  Optional and maskable for imports; full values are Luhn-checked
  (including samordningsnummer) and unique per club. Still stored in
  plaintext — encryption at rest is a known pre-launch TODO.

Custom i18n (no gettext)
  Swedish strings are the canonical keys; {% tr "Spara" %} in
  templates looks up the active language, falls back to sv-SE, then to
  the raw key (missing translations degrade, never crash). Locales:
  sv-SE, en-GB, nb-NO, da-DK, fi-FI, is-IS.

Theming
  clubs/utils.py derives hover/active shades and readable text colors
  from the club's primary/secondary hex colors; base.html emits a
  small inline <style> block (cached per club).

Query hygiene
  List views use select_related/prefetch_related/annotate so a page
  renders in a handful of queries regardless of row count (the invoice
  list used to run one SUM per row — now a single annotation). Season
  occurrence generation is one bulk_create; bulk attendance marking is
  transactional; hot filters are indexed.

--------------------------------------------------------------------
PRODUCTION DEPLOY (short version)
--------------------------------------------------------------------

  1. pip install -r requirements.txt
  2. manage.py migrate
  3. manage.py collectstatic     # fingerprint + compress static files
  4. gunicorn + nginx; Postgres; Redis for the cache when running
     multiple workers. (whitenoise already handles static serving.)

Development setup, demo logins, architecture decisions and coding
conventions: see AGENTS.md.

Tests before every commit:
  .\.venv\Scripts\python.exe manage.py test
