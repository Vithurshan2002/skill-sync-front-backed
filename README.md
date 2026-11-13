# SkillSync

SkillSync connects customers with local service professionals in Sri Lanka. It includes a public worker directory and separate customer, worker, and administrator workspaces.

This README describes the current implementation as of **13 November 2026**. Business data is read from and written to PostgreSQL through the FastAPI backend. AI classification and trained predictions are not implemented in this workspace.

## Architecture

```text
Browser -> Laravel / Livewire / Filament -> FastAPI -> PostgreSQL
                       |
                 SQLite sessions
```

| Area | Technology / responsibility |
| --- | --- |
| `frontend/` | PHP 8.4, Laravel 13, Filament 5, Livewire 4 |
| Frontend assets | Vite 8, Tailwind CSS 4, Manrope, Heroicons, Leaflet |
| Profile photos | Browser square-crop editor, Pillow validation/JPEG processing, backend file storage |
| `backend/` | Python 3.12+, FastAPI, SQLAlchemy, Alembic |
| Business database | PostgreSQL; default project database: `skillsync_backend` |
| Frontend database | `frontend/database/database.sqlite`: local identities, sessions and framework data |
| Tests | PHPUnit, pytest and opt-in Playwright browser coverage |

Dependency versions are pinned in `frontend/composer.lock`, `frontend/package-lock.json`, and `backend/uv.lock`.

Laravel calls the API over HTTP; it does not connect directly to PostgreSQL. Backend access tokens are encrypted in server-side Laravel sessions. The backend enforces role and record-ownership checks.

### Code organization

- Frontend pages depend on the `SkillSyncGateway` contract. `FastApiSkillSyncGateway` implements it, and `BackendClient` handles HTTP transport, authentication and API errors.
- Customer and worker profile pages both extend `Filament/Shared/ProfilePage`; shared loading/saving behavior is separate from each role's form fields.
- Backend business operations in `backend/app/services/` are grouped into `account_service.py`, `profile_service.py`, `request_service.py`, `booking_service.py`, `matching_service.py` and `notification_service.py`.
- `service_queries.py` provides shared pagination, eligible-worker queries and ownership-scoped record lookup. `workflows.py` contains shared approval and location rules.
- API routers import feature services directly. Package initializers avoid eager service imports and circular dependencies.
- `admin_service.py` owns administrative writes/audit events; `photo_service.py` owns image processing and transactional file replacement.
- Write operations in these services own their commits; query helpers and notification creation participate in the caller's transaction. Booking lock order and conflict checks are preserved.

This is a layered application with incremental refactoring, not a strict Clean Architecture implementation. Admin writes and photo processing/storage use dedicated services. Gateway responses remain arrays; this is not a full domain/entity abstraction.

## Fresh clone: complete Windows setup

Follow these steps in **PowerShell**. The commands below start from the repository root unless stated otherwise. A Git clone does not include your PostgreSQL records, private environment files or installed dependencies.

### 1. Install prerequisites

- Git.
- PHP 8.4 with cURL, OpenSSL, intl, mbstring, XML/DOM, PDO SQLite and the other extensions required by Composer.
- Composer 2.
- Node.js 22.12+ or 24 and npm.
- Python 3.12+ and uv.
- A running PostgreSQL server. This workspace was developed with PostgreSQL 18. pgAdmin is optional.

Ensure the tools are on PATH, then open a new terminal and check:

```powershell
git --version
php -v
php -m
composer --version
node --version
npm.cmd --version
python --version
uv --version
```

If Python is installed through the Windows launcher, check it with `py --version`. Keep your PostgreSQL username and password available for step 3.

### 2. Clone the repository

Replace `YOUR_REPOSITORY_URL` with the HTTPS or SSH URL from your repository's **Code** button. This workspace has no configured Git remote, so the actual URL is not available here.

```powershell
git clone YOUR_REPOSITORY_URL skillsync
cd skillsync
```

The `skillsync` directory containing `frontend/` and `backend/` is now your repository root. Private repositories require Git authentication and permission to access the repository.

### 3. Install and configure the backend

From the repository root:

```powershell
cd backend
uv sync --frozen
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Open `backend/.env` in your editor and set the following, using your own PostgreSQL credentials:

```dotenv
APP_ENV=local
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=skillsync_backend
DB_USER=postgres
DB_PASSWORD="replace-with-your-postgresql-password"
TOKEN_TTL_MINUTES=480
```

Leave `DATABASE_URL` unset unless deliberately using a full connection URL; it overrides the separate database settings. Do not commit or share `.env` files.

Ensure PostgreSQL is running. From the same `backend/` terminal:

```powershell
.venv\Scripts\python.exe -m app.cli init-db
.venv\Scripts\python.exe -m app.cli check-db
```

Expected result: `skillsync_backend` is created if absent, migrations are applied, categories are inserted, and the connection check succeeds. No sample accounts or bookings are created by these commands.

If your PostgreSQL account cannot create databases, have the database administrator create `skillsync_backend` and grant the application user permission to create its tables. Then use:

```powershell
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\python.exe -m app.cli seed-categories
.venv\Scripts\python.exe -m app.cli check-db
```

### 4. Install and configure the frontend

From the `backend/` directory used in step 3:

```powershell
cd ..\frontend
composer install
npm.cmd ci
if (!(Test-Path .env)) { Copy-Item .env.example .env }
if (!(Test-Path database\database.sqlite)) { New-Item -ItemType File -Path database\database.sqlite | Out-Null }
```

Open `frontend/.env` and confirm:

```dotenv
APP_NAME=SkillSync
APP_ENV=local
APP_DEBUG=true
APP_URL=http://127.0.0.1:8000
DB_CONNECTION=sqlite
SESSION_DRIVER=database
SESSION_DOMAIN=null
CACHE_STORE=database
FASTAPI_BASE_URL=http://127.0.0.1:8001
```

Leave `DB_DATABASE` commented out or absent: Laravel defaults to `frontend/database/database.sqlite`. Do not put the PostgreSQL database name in the frontend SQLite configuration.

For this **new installation**, run:

```powershell
php artisan key:generate
php artisan migrate --force
php artisan filament:assets
npm.cmd run build
```

Composer validates PHP extension requirements. Resolve missing extensions instead of bypassing platform checks. Keep the generated application key for future runs.

### 5. Create an administrator and optionally load sample records

From `frontend/`:

```powershell
cd ..\backend
.venv\Scripts\python.exe -m app.cli create-admin
```

Enter the requested name, email, town and password. This account uses the normal website login page. Existing accounts are not promoted or overwritten.

For local demonstration data, optionally run:

```powershell
.venv\Scripts\python.exe -m app.cli seed-samples
```

Save the generated sample credentials printed in your terminal. There is no fixed sample password in this README. Skip seeding to start with an empty marketplace and register customers/workers yourself. See [Sample data](#sample-data) for restrictions and rerun behavior.

### 6. Start both servers

Open two new terminals at the repository root and follow [Start the application](#start-the-application) below. Keep PostgreSQL running as well.

### 7. Verify the installation

1. Open `/health` on port 8001: expect `data.status` to be `ok`.
2. Open `/health/ready` on port 8001: expect `data.status` to be `ready`. This checks PostgreSQL and required schema fields.
3. Open `/docs` on port 8001 and the website on port 8000.
4. Log in with your newly created administrator; the admin workspace should open.
5. Register a worker, complete their profile, services, coverage, rate and availability, then approve them as admin.
6. Register a customer. Create a request matching that worker's category and location, then book a future appointment.
7. As the worker, accept, start and report completion. As the customer, confirm completion and leave a review.

Without sample records or approved workers, an empty directory is expected. It does not mean installation failed.

## Start the application

Ensure your PostgreSQL server is running. Open two PowerShell terminals **at the repository root**.

**Terminal 1 - backend:**

```powershell
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

**Terminal 2 - frontend:**

```powershell
cd frontend
php artisan serve --host=127.0.0.1 --port=8000
```

Keep both terminals and PostgreSQL running. Press Ctrl+C in each terminal to stop its server. These are local development commands.

| Address | Purpose |
| --- | --- |
| http://127.0.0.1:8000 | Website |
| http://127.0.0.1:8000/login | Login for all roles |
| http://127.0.0.1:8001/docs | Interactive API documentation |
| http://127.0.0.1:8001/health | Backend process health |
| http://127.0.0.1:8001/health/ready | PostgreSQL connectivity and required schema readiness |

Routine startup does not require database initialization, sample seeding or an asset rebuild.

## Updating an existing installation

After pulling changes, run the following from the repository root when dependencies or migrations have changed:

```powershell
cd backend
uv sync --frozen
.venv\Scripts\alembic.exe upgrade head
cd ..\frontend
composer install
npm.cmd ci
php artisan migrate --force
php artisan filament:assets
npm.cmd run build
php artisan optimize:clear
```

Preserve existing `.env` files, the Laravel application key and database files. Do not initialize, reset or seed databases on every startup. For CSS/JavaScript-only changes, run `npm.cmd run build` from `frontend/` and refresh with Ctrl+F5.

Restart the backend after Python changes if the running process has not reloaded them. Restart the frontend server after changing its environment configuration. Rebuilding frontend assets does not reload Python code.

## Common setup problems

| Problem | What to check |
| --- | --- |
| Command is not recognized | Install the tool, add it to PATH and reopen PowerShell. If necessary, use the full path to your own PHP executable. |
| Missing PHP extension or startup warning | Use `php --ini` to locate the CLI configuration and `php -m` to check extensions. Resolve the warning before running Composer. |
| Windows Application Control blocks a PHP DLL | This is an operating-system policy issue, not just a disabled PHP extension. Use a trusted PHP installation permitted by the device policy; on managed devices contact the administrator. |
| PostgreSQL connection fails | Check the service, host, port, username and password in `backend/.env`, then rerun `check-db`. |
| Database creation denied | Follow the pre-created database procedure in step 3. |
| SQLite file or sessions table missing | Create the SQLite file only if absent, check `DB_CONNECTION=sqlite`, then run `php artisan migrate --force` from `frontend/`. |
| Application key missing | On a fresh installation run `php artisan key:generate`. Preserve the key on an existing installation. |
| Vite manifest missing or styles outdated | From `frontend/`, install dependencies with `npm.cmd ci` if needed, then run `npm.cmd run build` and refresh the browser. |
| Website reports API unavailable | Start the backend, check `/health/ready` and verify `FASTAPI_BASE_URL`. Clear frontend configuration with `php artisan optimize:clear` after changes. |
| Port 8000 or 8001 occupied | Stop the old local server you started or select another port. Update `APP_URL` for a changed frontend port and `FASTAPI_BASE_URL` for a changed backend port. |
| Swagger requires a bearer token | Log in/register through the API and paste `data.accessToken` into Authorize. Website login manages tokens automatically. |
| Worker does not appear in results | Check profile completeness, administrator approval, category, coverage and availability filters. |
| Photo still has an old crop or white padding | Select the original photo again, adjust the crop preview and save. Previously generated images are not automatically regenerated. Check that the backend has restarted after image-processing changes. |
| Dashboard shows loading cards briefly | Customer/worker statistics load in a separate request. The skeleton is replaced when that request completes; it does not reduce API response time. If it persists, check the backend and the failed request in browser developer tools. |

## Accounts and roles

Customers and workers can register through the website. New workers complete their profiles and require administrator approval before public discovery and booking eligibility. Material profile changes can trigger another review.

Administrators use the same login page. Public registration cannot create an administrator. To create one explicitly, run from `backend/`:

```powershell
.venv\Scripts\python.exe -m app.cli create-admin
```

The command prompts for name, email, town and password. It does not change an existing user's role. There is no built-in shared admin password or role-switch login shortcut.

## Implemented features

| Area | Current functionality |
| --- | --- |
| Public website | Home, About, service catalog, searchable worker directory, category/town/availability filters, pagination, profiles, rates and reviews |
| Customer | Profile editing, service requests, request edits before booking, professional matching and comparison, bookings, completion confirmation/dispute, reviews and complaints |
| Worker | Profile, photo upload/crop/replacement/removal, skills, coverage towns, rates, availability, service radius/location, approval feedback, job responses, work updates and performance/history |
| Administrator | Dashboard, record search, worker approval/change requests, profile comparisons, category description edits, complaint decisions and audit records |
| Location | Leaflet map selection, explicit address search, optional worker geolocation, manual coordinates and service-radius checks; town matching when usable coordinates are absent |
| Matching | Approved eligible professionals filtered by service, coverage, availability and optional rate; alphabetical ordering, up to 50 candidates |
| Notifications | Unread count, All/Unread filters, mark read, links to related records and event-specific icons |

Location distances are straight-line estimates, not road routes or travel times. Map tiles and address search need internet access; town matching and manual coordinate entry remain available without those services.

### Booking and review flow

1. The customer creates a request and selects a service category.
2. The customer compares matching professionals and chooses an appointment start, expected end and optional separate completion deadline.
3. The booking starts as `pending`; the worker accepts or rejects it.
4. An accepted job moves to `in_progress` when the worker starts.
5. The worker reports completion, moving it to `awaiting_confirmation`.
6. The customer confirms `completed`, or gives a reason to return it to `in_progress`.
7. The customer can submit one review for the completed booking. The public review displays the customer's first name; the booking review API also returns `customerName`.

Permitted cancellation and correction actions require a reason. Rejected/cancelled bookings reopen the request. Completed bookings close it. Changes create timeline entries and notify the other party.

Booking creation checks time overlaps, including pending reservations. Accepting, starting and returning work to `in_progress` also recheck overlaps under a worker row lock. The current booking is excluded from its own conflict check. Conflict errors stay visible inside the action dialog without claiming success.

Times are stored in UTC and displayed in Asia/Colombo. Rates are quoted in LKR and represent a rate basis, not a guaranteed final job price.

### Current frontend improvements

- Consistent public typography, service icons, worker card hierarchy and short biography previews.
- Notification icons for booking events, reviews, profile approval/change requests and complaints; unknown events retain a bell icon.
- The notification bell requests unread pagination metadata with `perPage=1`, instead of downloading every notification.
- Delayed loading skeletons for worker-directory search/filter/pagination, booking/job status filters, recommendation filters, notification filters and admin record search/type/approval filters.
- Customer and worker dashboards show three statistic-card skeletons while their shared lazy-loaded statistics widget fetches data. The cards are replaced with the real counts when loading completes.
- Skeletons support responsive layouts and reduced motion. They do not replace Save/Accept/Cancel feedback or flash during background notification polling.
- Skeletons cover the asynchronous updates above and the dashboard statistics' initial load. Static pages have no artificial loading delays, and skeletons do not make API requests faster.
- Loading/error/empty states, modal-local API errors and disabled submit feedback.

Placeholder markup lives in `frontend/resources/views/components/loading-region.blade.php`, the directory's `frontend/resources/views/livewire/public/worker-directory.blade.php`, and `frontend/resources/views/filament/shared/workspace-stats-placeholder.blade.php`. `frontend/app/Filament/Shared/WorkspaceStats.php` selects the dashboard placeholder. Shared styles are in `frontend/resources/css/skillsync.css`.

## Worker profile photos

Workers can open **My profile > Profile photo** to select a photo, adjust its square crop using zoom and horizontal/vertical position sliders, then save it. Reset crop and Cancel selection leave the saved photo unchanged; removal requires confirmation. The browser exports the selected area at 512 x 512 pixels before upload. Photo changes are saved separately from the profile form. Existing profiles continue to show initials until a photo is uploaded; failed image loads also fall back to initials.

- Still JPG, PNG and WebP images only; maximum 2 MB, 16 megapixels and 8192 pixels per side; minimum 64 x 64 pixels.
- The backend decodes and validates image content, corrects EXIF orientation, resizes proportionally to a maximum of 512 pixels without adding padding, strips metadata and saves a JPEG thumbnail.
- Photos appear in the homepage featured profile and worker cards, worker directory cards, public profiles, recommendations, booking details and the worker's own profile. Photos and initials use the same rounded-square frame.
- Photos are public to anyone with their image link. Only the authenticated worker can upload or remove their own photo; this does not change verification/approval status.
- PostgreSQL stores the current photo key. Files live in `backend/storage/worker-photos/` (excluded from Git); `PHOTO_STORAGE_PATH` can override this directory. Replaced/deleted photo files are removed.
- The frontend serves photos through a same-origin proxy; backend tokens are not exposed in image URLs.

To use the editor:

1. Sign in as a worker and open **My profile > Choose a photo**.
2. Use **Zoom**, **Horizontal position** and **Vertical position** to place your face inside the square preview.
3. Use **Reset crop** to restore the starting position or **Cancel selection** to discard the selection.
4. Select **Save photo**. The selected square is uploaded and becomes the public photo only after a successful save.
5. To delete the saved image, select **Remove photo** and confirm.

The editor lives in `frontend/resources/js/photo-cropper.js`. A clear original at least 512 x 512 is recommended; resizing a small or blurry image cannot restore lost detail. The browser sends the cropped square to the backend, so the original upload is not retained as an editable master. Select the original file again to choose a different crop later. Direct API uploads are resized proportionally and do not open the browser crop editor.

After pulling this feature, run `uv sync --frozen` and `.venv\Scripts\alembic.exe upgrade head` from `backend/`, then `npm.cmd run build` from `frontend/`. The migration adds an optional `workers.photo_key` column and preserves existing records.

| API | Purpose |
| --- | --- |
| `PUT /api/v1/worker/profile/photo` | Authenticated worker uploads raw image bytes with `Content-Type: image/jpeg`, `image/png` or `image/webp` (not multipart/JSON) |
| `DELETE /api/v1/worker/profile/photo` | Authenticated worker removes their current photo |
| `GET /api/v1/worker-photos/{key}.jpg` | Public thumbnail; unknown or obsolete keys return 404 |

Worker responses include nullable `photoUrl`. New installations do not inherit uploaded photos from Git; retain both the storage directory and database when moving an existing installation.

## Sample data

**Cloning this repository does not copy the original developer's PostgreSQL records.** Each local installation connects to the database configured in its own `backend/.env`. The website loads business records through the backend API, not from files bundled with the frontend.

To populate a new computer for testing, first complete the dependency installation and `.env` configuration above and start PostgreSQL. Then run from the repository root:

```powershell
cd backend
.venv\Scripts\python.exe -m app.cli init-db
.venv\Scripts\python.exe -m app.cli check-db
.venv\Scripts\python.exe -m app.cli seed-samples
```

- `init-db` creates the configured project database if needed, applies migrations and inserts service categories.
- `check-db` verifies the PostgreSQL connection.
- `seed-samples` adds demonstration records to your own local `skillsync_backend` database and prints credentials for newly created sample accounts. It requires `APP_ENV=local` and `DB_NAME=skillsync_backend`.

These commands create sample data; they do not restore the original developer's database or later edits. After starting both application servers, the sample records are available through the normal website and API. If you prefer an empty marketplace, omit `seed-samples` and register accounts through the website.

The frontend has no standalone demo dataset or fallback that invents successful API responses. Sample accounts, workers, requests, bookings and reviews can be stored in PostgreSQL for application testing; they use the same APIs and UI as other records.

Optional command, run only when sample records are wanted, from `backend/`:

```powershell
.venv\Scripts\python.exe -m app.cli seed-samples
```

This command is restricted to the local `skillsync_backend` database. It prints credentials for newly created sample accounts. Rerunning it preserves existing sample accounts, passwords and edits. Sample data is never inserted automatically on startup.

## Current limitations

- Trained AI classification, learned ranking, category skill scores and reliability predictions are unavailable. Select categories manually; missing scores are shown as unavailable.
- Worker photos are stored on the backend filesystem. Back up the photo directory alongside PostgreSQL; a database backup alone does not include images.
- Removable selected-filter chips are not enabled; the directory uses its standard filter controls and Clear filters.
- A consistent real/demo/test provenance field across business records and the API is not implemented.
- Bookings/jobs, admin records, notifications and customer requests use server-side pagination. Filters are applied before counts and paging. Dashboards fetch bounded previews; completed history links to the paginated jobs list. The notification bell uses filtered metadata.

The large handoff document is a reference specification/snapshot, not proof that every feature described there exists in this checkout. Use this README and the current source to determine implementation status.

## Verification

From `backend/`, with PostgreSQL available:

```powershell
.venv\Scripts\python.exe -m app.cli check-db
.venv\Scripts\python.exe -m pytest -q
```

Backend tests use disposable PostgreSQL schemas and remove those test schemas afterward; they do not reset application tables. The test database user needs permission to create schemas. Browser integration is opt-in.

From `frontend/`:

```powershell
php vendor/bin/phpunit tests/Feature/ApiIntegrationTest.php
php vendor/bin/phpunit tests/Feature/WorkerPhotoTest.php
npm.cmd run build
```

Frontend API integration tests use HTTP fakes and test database settings. They do not insert business records into the running application.

For the isolated browser workflow, run from `backend/`:

```powershell
$env:RUN_FRONTEND_BROWSER='1'
$env:PHP_BINARY=(Get-Command php).Source
.venv\Scripts\python.exe -m pytest tests/test_frontend_browser.py -q -s
```

The browser runner starts temporary servers against a disposable PostgreSQL schema and temporary frontend SQLite database. It uses Microsoft Edge on Windows by default. Photo coverage includes crop controls, reset/cancel, saving, homepage/directory display, replacement and removal. See the frontend README for Chrome selection and focused browser runs.

## Further documentation

- [Frontend setup, authentication and checks](frontend/README.md)
- [Backend setup, API inventory and workflow rules](backend/README.md)
- [Frontend API contract](frontend/docs/api-contract.md)
