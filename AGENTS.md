# ClubHub — Agent Instructions

Instructions for AI agents (and humans) working on this repository.

## What this is

ClubHub is a sport club administration web app, built **Django-first** with the goal of
starting as an internal tool for a Swedish boxing club and growing into a commercial
multi-tenant SaaS product (competitor reference: Sportadmin.se).

Feature scope implemented so far: people/members/guardians/staff management (incl.
Sportadmin "Personregister" xlsx import with preview/confirm), groups,
seasons, recurring schedules, attendance tracking, per-season fees + invoices with manual
payment registration, email notifications, public read-only schedule API, club branding
(colors/logo/background) and full UI theming on top of the SB Admin 2 template.

## Tech stack

| Component | Version / choice |
|---|---|
| Python | 3.14 (3.14.7 on the dev machine — install via `winget install Python.Python.3.14`, create the venv with `py -3.14 -m venv .venv`) |
| Django | 6.1 (latest stable) |
| Database | SQLite (dev). Postgres intended for production |
| REST API | Django REST Framework 3.18 |
| Front-end | SB Admin 2 look on Bootstrap 5.3.8 (vendored dist, no jQuery) + FontAwesome 5, server-rendered Django templates |
| Interactivity | HTMX 2 (vendored in `static/vendor/htmx/`) — attendance grid + `hx-boost` page navigation |
| Static serving | whitenoise 6 + Brotli: hashed filenames, gzip/br precompression, far-future `Cache-Control` (after `collectstatic`) |
| Fonts | Nunito self-hosted woff2 (`static/vendor/fonts/nunito/`), `@font-face` at the top of the ClubHub custom layer in `clubhub.css` |
| Recurrence | python-dateutil `rrule` |
| Images | Pillow |

`requirements.txt` is pinned. Dev happens on Windows / PowerShell.

## Setup

```powershell
cd clubhub
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo      # idempotent demo data
.\.venv\Scripts\python.exe manage.py createsuperuser # optional, for /admin/
.\.venv\Scripts\python.exe manage.py runserver
```

Demo logins after seeding: `admin / demo1234!` (club admin Anna) and
`trainer / demo1234!` (trainer Erik — sees less than the admin).

Run tests before every commit:

```powershell
.\.venv\Scripts\python.exe manage.py test
```

## Project layout

```
clubhub/
├── config/          settings.py, urls.py, views.py (handler404), wsgi/asgi
├── clubs/           Club model (multi-tenancy root), dashboard, settings page,
│                    theming utils + context processor, JSON i18n engine,
│                    seed_demo management command
├── people/          Person, Membership, GuardianRelation, StaffProfile, AdminGroup;
│                    personnummer validation (people/personnummer.py);
│                    permission services (people/services.py) + view mixins;
│                    Sportadmin xlsx import (people/sportadmin.py)
├── groups/          Group + GroupMembership (role member/trainer through-model)
├── scheduling/      Season, ActivityTemplate -> Activity occurrences;
│                    services.generate_occurrences / regenerate_occurrences
├── attendance/      AttendanceRecord (present/late/absent/excused) + HTMX grid
├── payments/        Fee, Invoice, Payment; generate_invoices command
├── notifications/   Notification + recipients, email sending service
├── api/             DRF read-only public endpoints (schedule/groups/seasons)
├── locales/         sv-SE.json, en-GB.json, nb-NO.json, da-DK.json, fi-FI.json, is-IS.json
├── templates/       base.html (app shell), auth_base.html, shared/, registration/,
│                    404.html  (startbootstrap-sb-admin-2-gh-pages/ is only a
│                    third-party reference copy — do not edit or depend on it)
└── static/          clubhub.css is a spliced file: stock Bootstrap 5.3.8 dist CSS,
                     then the SB Admin 2 component layer (sidebar/topbar/gradients,
                     starts right after the BS5 print-media block), then ClubHub
                     custom styles (ch-*, table sorting/pagination, self-hosted
                     Nunito @font-face). Custom rules go in those later layers,
                     never into the BS5 core. vendor/ holds bootstrap/,
                     fontawesome-free/ (all.min.css + woff2 fonts only),
                     htmx/ and fonts/nunito/; static/js/clubhub.js is vanilla JS
                     (sidebar toggle, scroll-to-top, table scrollbars) written to
                     be safe under hx-boost re-execution
```

## Architecture decisions (keep these)

1. **No model inheritance for roles.** One `Person` + separate role records:
   `Membership` (athlete), `StaffProfile` (staff; `is_admin` flag = admin powers),
   `GuardianRelation` (parent↔child, both are Persons). A person can hold any
   combination simultaneously. Trainer status = active `GroupMembership(role=TRAINER)`
   and requires a `StaffProfile`.
1a. **Personnummer is optional and may be masked.** Sportadmin exports mask the last
   four digits (`20041003-****`) or omit the tail entirely, so `Person.personnummer`
   is nullable/blank. Normalization (`people/personnummer.py`) accepts full values
   (Luhn-checked, stored `YYYYMMDDXXXX`) and masked/partial values (date-validated
   only, stored `YYYYMMDD****`). The per-club unique constraint applies **only to
   full values** (conditional `UniqueConstraint`); masked duplicates are allowed
   (same-birthdate siblings). `birth_date`/`is_minor` still work from the date part;
   `has_full_personnummer` flags incomplete numbers.
1b. **Member number is club-scoped.** `Person.member_number` ("MedlemsNr") auto-assigns
   `0001`, `0002`, … per club on create when empty (fills gaps after deletes) and is
   unique per club via conditional constraint — deliberately NOT globally unique.
1c. **Guardian relations carry free-form relation text.** `GuardianRelation.relation`
   stores the raw import string ("Mamma", "Pappa", …); guardians imported from
   Sportadmin are Person rows without personnummer.
2. **Every core model carries a `Club` FK** from day one (multi-tenancy later). Views
   always scope querysets via `people.services.visible_groups(user)` /
   `visible_activities(user)` — trainers see only their own groups, admins see the
   whole club.
3. **Login**: Django `User` linked via nullable `Person.user` OneToOne. Members do not
   get accounts yet, but the door is open. Permission helpers live in
   `people/services.py`, mixins (`StaffRequiredMixin`, `AdminRequiredMixin`) in
   `people/mixins.py`. Never trust `user.is_staff`; use these helpers.
4. **Personnummer** is sensitive GDPR data: validated with Luhn checksum (incl.
   samordningsnummer) when full; optional/masked values allowed for imports (see 1a).
   Unique per club for full values only. **Still stored in plaintext — encryption at
   rest is a known pre-launch TODO.**
5. **Schedules**: `ActivityTemplate` holds recurrence; dated `Activity` rows are
   generated within season bounds (`services.generate_occurrences`, idempotent).
   Editing a template triggers `regenerate_occurrences`, which deletes/recreates future
   occurrences **except** those with registered attendance or flagged
   `is_manually_edited`.
6. **Attendance** rows carry status + `registered_by` + timestamps; unique per
   (activity, person); `club` is auto-derived in `save()`.
7. **Payments**: Fee (per season) → invoices generated per active member via
   `manage.py generate_invoices --fee <id>` (idempotent) → manual Payment registration
   recalculates invoice status automatically (unpaid/partly/paid).
8. **i18n is custom, not gettext**: keys are canonical **Swedish** strings grouped in
   context areas in `locales/<lang>.json`. Lookup chain: active language → `sv-SE` →
   raw key (so missing translations degrade gracefully, never crash). Use
   `{% tr "Spara" %}` / `{% tr "Titel" "Schema" %}` in templates and
   `translate("...", "<Area>")` from `clubs.translations` in Python. Language is
   resolved in ONE place: `clubs/translations.py:get_language()` — the signed-in
   user's `UserProfile.language` (editable on `/settings/`) when set, otherwise
   `settings.CLUBHUB_LANGUAGE`. `clubs.middleware.CurrentRequestMiddleware` binds the
   request to a contextvar so `get_language()` can see the user without threading the
   request through every call; the result is cached per request (use
   `reset_language_cache()` after changing the preference mid-request).
9. **Theming**: `clubs/utils.py:build_theme(club)` computes shades/contrast from
   `Club.primary_color`/`secondary_color`; `clubs/context_processors.club_context`
   injects `current_club` + `theme` into every response; `base.html` emits CSS
   overrides. Convention: **primary** = buttons/links/badges/login gradient,
   **secondary** = sidebar gradient. Colors are sanitized defensively in `build_theme`
   (a bad value must never 500 pages).
10. **Front-end**: Bootstrap 5.3.8 under an SB Admin 2 skin (migrated from BS4 in
    2026-08; no jQuery anywhere — Bootstrap bundle + vanilla JS only). Use BS5 syntax:
    `me-*`/`ms-*` spacing, `fw-bold`, `badge bg-success`, `form-select`, `btn-close`,
    `g-0`, `data-bs-toggle/-dismiss/-target`, `bootstrap.Modal.getOrCreateInstance(el)`.
    Do not use removed BS4 classes (`mr-/ml-`, `font-weight-*`, `badge badge-success`,
    `custom-select`, `form-group`, `btn-block`, `no-gutters`, `dropdown-menu-right`,
    `.close`, `input-group-append`).
11. **Static assets & caching (2026-08)**: static files go through whitenoise with a
    manifest storage subclass (`config/storage.py`) — hashed filenames, gzip/brotli
    precompression, `Cache-Control: immutable` after `collectstatic`. There is NO
    manual cache-busting anymore (`?v=` query strings are gone); after changing any
    static file just run `collectstatic` when deploying — dev/tests fall back to
    unhashed URLs automatically because the manifest is optional there. Fonts are
    self-hosted (no font CDN in templates). The public `api/` endpoints are
    `cache_page(60)`-cached and the club theme dict is cached per club
    (`clubs/utils.get_theme`, invalidated by the Club `post_save` signal).
12. **hx-boost navigation**: `base.html` sets `hx-boost="true"`, so every link/form
    in the app shell swaps `<body>` via XHR with pushState. Consequences: scripts
    inside `<body>` are **re-executed on every navigation** — they must be idempotent
    (see `static/js/clubhub.js`: replaceable window listeners, self-tearing-down
    intervals, bind-once guards). Auth redirects (login required / logout) are
    converted to `HX-Redirect` full-page navigations by
    `clubs.middleware.HtmxAuthRedirectMiddleware` so the login layout never gets
    swapped into the app shell. `auth_base.html` deliberately has no hx-boost.

## Known gotchas (learned the hard way)

- **ModelForm mutates the instance with raw POST values even when validation fails**
  (Django 6). This once poisoned the cached Club instance and crashed theme rendering
  site-wide. Hence the defensive sanitization in `build_theme`. Keep that pattern for
  any data used outside the request cycle.
- `ProtectedError` imports from `django.db.models`, not `django.core.exceptions`.
- `ActivityType`, `Weekday` etc. live at module level in `scheduling.models`, NOT nested
  on `ActivityTemplate`.
- Python's `round()` banker-rounds (e.g. `round(127.5) == 128`) — relevant in
  color-shading math and its tests.
- Custom 404 handler only renders when `DEBUG=False`; tests use
  `@override_settings(DEBUG=False)` and `assertContains(..., status_code=404)`.
- Media files are served by Django only while `DEBUG=True`. Production needs
  nginx/S3-style serving.
- **Static files with a manifest storage**: tests never run `collectstatic`, so
  {% static %} would raise "missing manifest entry" with the stock manifest storage.
  `config.storage.StaticStorage` falls back to the unhashed URL whenever the manifest
  can't answer — keep that fallback. Also: deleting a vendor file that some vendored
  CSS still references (e.g. FontAwesome legacy webfont formats) breaks
  `collectstatic` post-processing with a hard CommandError — trim the `@font-face`
  src lists when pruning formats.
- **hx-boost + scripts**: anything added to `base.html` scripts must tolerate being
  re-run after every navigation (see decision 12). `window.location.href` downloads
  (the person-register export button) are immune to hx-boost — keep using direct
  navigation for file downloads, not boosted forms.
- Attendance HTMX endpoints return 404 (not 403) for groups the caller cannot manage —
  deliberate (no existence leak).

## Conventions

- All new user-facing strings go through the i18n system with **Swedish** as the key.
  Add missing keys to all six locale files (en-GB fully translated; nb/da good;
  fi/is machine-quality, needs native review eventually).
- Tests live next to code (`<app>/tests.py`); helper `complete_pnr(nine_digits)` in
  `people.tests` generates valid personnummer for fixtures.
- Admin (`/admin/`) is functional for all models and used for data entry shortcuts
  (e.g. the "create login" action on Person).
- Commit style: short imperative summaries.

## Roadmap / open items

- Member self-service pages (parents see schedule, invoices, their kids)
- Attendance statistics with Chart.js (vendor it — Chart.js 4 — when implementing;
  the old bundled Chart.js 2 was removed with the BS5 migration)
- Personnummer encryption at rest + audit logging (GDPR)
- Template-edit regeneration UX (currently regenerates on save)
- Deployment hardening: Postgres (swap the LocMem cache default for Redis when
  multi-process), env-based settings, gunicorn/nginx + `collectstatic` (whitenoise
  already covers static compression/caching), media storage, API versioning
- SMS notifications (deliberately deferred)
- Online payments (Swish/Stripe) — decided to defer; manual registration for now

## Git

Remote: https://github.com/sletten93/ClubHub.git (branch `main`).
Local git identity was set with repo-local config (`user.name sletten93`,
`user.email sletten93@users.noreply.github.com`) — adjust if you commit as someone else.
