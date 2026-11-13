# SkillSync frontend

Laravel 13, Filament 5, and Livewire 4 render the public directory and customer,
worker, and administrator workspaces. Business data comes from the FastAPI service
in ../backend and its PostgreSQL database. The frontend has no demo data mode,
fixture accounts, role shortcuts, or reset action.

Updated for the code as of **13 November 2026**. For clone instructions and database initialization, follow the [root setup guide](../README.md#fresh-clone-complete-windows-setup). Exact dependency versions are recorded in the lockfiles.

## Run this workspace

From the repository root, start the backend in one PowerShell terminal:

~~~powershell
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
~~~

From the repository root, start the frontend in another:

~~~powershell
cd frontend
php artisan serve --host=127.0.0.1 --port=8000
~~~

Open http://127.0.0.1:8000. Both servers and PostgreSQL must be running. The ignored
frontend .env sets FASTAPI_BASE_URL=http://127.0.0.1:8001. Do not overwrite an existing
.env. PHP does not need a PostgreSQL driver: Laravel calls the API over HTTP.

Sign in with an account created in the backend, or register through the website.
New workers go directly to their profile to set categories, service towns, rate,
biography, experience, and availability. Administrator accounts are created with
the backend command python -m app.cli create-admin; there is no shared admin login.

## Storage and authentication

PostgreSQL is the authority for users, workers, requests, bookings, reviews,
notifications, categories, and administration. Laravel's SQLite database stores
local session identities, sessions, and framework data only. A backend user ID
links a local identity to PostgreSQL; local passwords do not authenticate users.

Login and registration use the backend. Each access token is encrypted with the
Laravel application key before being stored in the server-side session. It is never
placed in browser storage, page markup, or a public JavaScript variable. Authenticated
page requests and Livewire updates verify the identity with /api/v1/me. Role checks
are applied in both Laravel and FastAPI. Logout revokes the current backend token
and clears the local session. Expired tokens require signing in again.

The migration replace_demo_storage_with_backend_identity removes the old frontend
demo accounts, demo JSON store, and old sessions. It does not alter PostgreSQL.
DatabaseSeeder intentionally creates no business records.

## Implemented flows

- Public categories, filtered/paginated workers, and worker details/reviews.
- Backend login, customer/worker registration, logout, and profile editing.
- Service requests with manual category selection and future appointments.
- Location map, manual address search, optional worker GPS and service radius; town matching when coordinates are absent.
- Approved workers matched by category, radius/town, availability, and optional rate.
- Booking start/end and deadline, overlapping booking protection, worker acceptance/rejection and cancellation with reasons.
- Worker completion reporting followed by customer confirmation or dispute; customer cancellation with a reason.
- One customer review per completed booking, persisted ratings and job counts.
- Notifications, dashboard totals, worker performance/history.
- Administrator profile approval, pending-change comparisons, category descriptions, and audit notes.
- Customer complaints and administrator resolution with notifications to both parties.

Workers must complete their profiles and receive administrator approval before appearing in matching. Material profile edits require another review. Maps and address search require internet access; coordinate entry and town matching remain available without them. Browser tests stub external map tiles and address lookup, while controller tests verify lookup validation and error handling.

AI classification, skill scores, match scores, and reliability predictions remain
unavailable. Missing scores are displayed as unavailable, never fabricated. Matching
is rule-based and alphabetical, not a learned quality ranking.

All business calls go through SkillSyncGateway and FastApiSkillSyncGateway.
Customer and worker profile pages share `app/Filament/Shared/ProfilePage.php` for mounting, form state and save feedback; neither role's page inherits the other role's page. Their role-specific fields and worker photo controls stay in the corresponding page classes.
BackendClient maps API errors, transports per-user tokens, and follows pagination
for workspace lists. Workspace tables currently collect all API pages for their
local filters; the public directory uses server pagination. There is no automatic
retry of booking or review submissions and no fallback dataset.

## Fresh installation

Requirements: PHP 8.4 with Laravel's extensions including curl, OpenSSL, intl,
mbstring, XML and PDO SQLite; Composer 2; Node 22.12+ or 24 and npm. Dependencies
are locked in composer.lock and package-lock.json.

Run these commands from `frontend/` after configuring the backend:

~~~powershell
composer install
npm.cmd ci
if (!(Test-Path .env)) { Copy-Item .env.example .env }
if (!(Test-Path database\database.sqlite)) { New-Item -ItemType File -Path database\database.sqlite | Out-Null }
php artisan key:generate
php artisan migrate --force
php artisan filament:assets
npm.cmd run build
~~~

Generate the application key only on a new installation. Preserve existing keys and database files. Routine startup does not require seeding or rebuilding.

## Checks

~~~powershell
php vendor/bin/phpunit tests/Feature/ApiIntegrationTest.php
php vendor/bin/phpunit tests/Feature/WorkerPhotoTest.php
npm.cmd run build
~~~

HTTP contract tests use Laravel HTTP fakes and an in-memory session database;
they do not insert fake business data into the application.

The full browser test uses real FastAPI, a disposable PostgreSQL schema, and a
temporary Laravel SQLite session database. It covers registration, profile editing,
matching, booking transitions, review, admin updates, and public responsive pages:

~~~powershell
cd ..\backend
$env:RUN_FRONTEND_BROWSER='1'
$env:PHP_BINARY=(Get-Command php).Source
.venv\Scripts\python.exe -m pytest tests/test_frontend_browser.py -q -s
~~~

The runner starts hidden local test servers on free ports, then stops them and removes
only the isolated PostgreSQL schema. Microsoft Edge is used on Windows by default.
The browser suite skips when run directly without this isolated backend runner.

If Chrome is installed instead of Edge, set `$env:PLAYWRIGHT_CHANNEL='chrome'` before running the browser workflow. Set `$env:TEST_BROWSER_GREP='worker photo upload'` to run only the photo/crop workflow; remove that variable with `Remove-Item Env:TEST_BROWSER_GREP` before running the full suite again.

## Loading states

The customer and worker dashboards share `app/Filament/Shared/WorkspaceStats.php`. Its initial lazy-load placeholder uses `resources/views/filament/shared/workspace-stats-placeholder.blade.php` to show three responsive skeleton cards until the statistics request completes.

Directory filtering/pagination, booking/job filters, recommendations, notifications and admin record filters also use loading placeholders. Styles in `resources/css/skillsync.css` respect reduced-motion preferences. Skeletons indicate a pending request; they do not speed up backend responses or impose a minimum loading delay.


## Worker photos

My profile includes a separate optional photo editor with a square canvas preview, zoom and position sliders, reset, cancel, Save photo and confirmed removal. The browser exports the selected square as a 512 x 512 PNG; the backend validates and converts it to JPEG. Uploads go from Livewire temporary storage through the backend gateway; the backend validates and resizes the full image without adding padding; the saved square fills the shared avatar frame. The shared `worker-avatar` component displays the current photo with an initials fallback. Public image requests are proxied by `WorkerPhotoController` to the configured backend, so backend URLs/tokens are not embedded in browser markup.

See [limits, storage and migration steps](../README.md#worker-profile-photos). No Laravel storage symlink is needed for the saved worker images. Run `php vendor/bin/phpunit tests/Feature/WorkerPhotoTest.php` for photo UI/transport coverage.
