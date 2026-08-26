# Handover — session context (2026-08)

Read `agent-instructions.md` first for the durable project guide. This file captures
where the last working session ended and what to pick up next. Delete or rewrite it
once it goes stale.

## State at end of last session

Everything below is **implemented, migrated and covered by the test suite (50 tests,
all green)**:

1. **Auth**: SB Admin 2 login page, full forgot-password/reset flow (console email
   backend in dev), password change, logout via confirm modal (CSRF POST).
2. **Shell/UI**: vertical sidebar (club secondary color gradient, logo in brand slot)
   + topbar with search, alert center (placeholder), message center (links to
   notifications list) and profile dropdown showing username.
3. **Pages converted to SB Admin 2** cards/tables/buttons: dashboard, groups, schedule
   week view, template/season management, attendance grid, invoices, notifications,
   club settings, 404.
4. **Theming**: club settings page with color pickers + live preview, logo/background
   upload with instant preview, clear-buttons instead of checkboxes, filenames
   stripped of upload prefix and truncated to 25 chars.
5. **i18n**: custom JSON locale system (sv/en/nb/da/fi/is), Swedish canonical keys,
   all visible UI strings routed through `{% tr %}` / `translate()`.
6. **Public API**: `/api/clubs/<slug>/schedule|groups|seasons/` (read-only, throttled).

Demo data is seeded in the dev SQLite db (`seed_demo`): logins
`admin / demo1234!` (Anna, admin) and `trainer / demo1234!` (Erik).

## Things deliberately left unfinished / known rough edges

- The reference template copy lives at
  `templates/startbootstrap-sb-admin-2-gh-pages/` — excluded from git via
  `.gitignore`; safe to delete locally.
- Some Bootstrap-4-vs-5 cosmetic differences may remain; user asked to report any page
  that looks off (none reported yet).
- Finnish/Icelandic locale files are machine-translated, need native review.
- Search field in topbar is inert; alerts center is a placeholder ("no new alerts").
- Chart.js is bundled but unused until statistics work starts.

## Suggested next tasks (user's own shortlist)

1. Attendance statistics with real Chart.js charts (data exists: AttendanceRecord).
2. Member self-service pages (parents/members view schedule + invoices).
3. Personnummer encryption at rest (GDPR) before any real member data goes in.
4. Deployment hardening (Postgres, env settings, media serving outside DEBUG).
