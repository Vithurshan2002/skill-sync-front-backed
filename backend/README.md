# SkillSync backend

**FastAPI + PostgreSQL** service under `backend/`. The Laravel frontend now uses this service for authentication and business data. Laravel's SQLite database holds only its local session identities and framework data; PostgreSQL owns the application records. See [frontend setup](../frontend/README.md).

The API implements registration/login/logout, customer and worker profiles, the category catalog, worker search, private requests, rule-based matching, booking transitions, reviews, notifications, dashboard counts, and administrator records/category/verification controls. Swagger UI is available at `/docs`, ReDoc at `/redoc`, and the OpenAPI contract at `/openapi.json`.

## Start this prepared Windows workspace

Your existing PostgreSQL server must be running. Its connection details are in the ignored `backend/.env`; do not share or commit that file.

```powershell
cd C:\Users\User\Desktop\project\backend
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

Open **http://127.0.0.1:8001/docs**. The frontend uses port 8000; the backend uses 8001. No frontend server is needed to test these APIs.

Keep the terminal open. Press Ctrl+C to stop the API. Routine startup does not require rebuilding the database.

## Fresh setup

Requirements: Python 3.12+, uv, and PostgreSQL. This workspace was implemented with PostgreSQL 18. The exact Python dependencies are pinned in `uv.lock`.

```powershell
cd backend
uv sync --frozen
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Edit `.env` using your PostgreSQL details:

```dotenv
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=skillsync_backend
DB_USER=postgres
DB_PASSWORD=your-existing-postgresql-password
```

Quote dotenv values containing spaces or special characters. Separate connection fields avoid URL-encoding passwords. `DATABASE_URL`, if supplied, overrides those fields and must use the `postgresql+psycopg` driver.

Then initialize the dedicated project database:

```powershell
.venv\Scripts\python.exe -m app.cli init-db
.venv\Scripts\python.exe -m app.cli check-db
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8001
```

`init-db` creates the named database if absent, applies Alembic migrations, and inserts missing categories. It does not reset records or replace edited category descriptions. The database creator deliberately accepts only names beginning with `skillsync`. It requires permission to create a database. If a database administrator already created the database for a less privileged application user, use:

```powershell
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\python.exe -m app.cli seed-categories
```

Never copy `.env.example` over an existing configured `.env` during routine startup. For macOS/Linux, use `cp .env.example .env`, `uv sync --frozen`, and `uv run python -m app.cli init-db`; start with `uv run uvicorn app.main:app --reload --port 8001`.

## Test the complete flow in Swagger UI

1. Open `/docs`. Expand **POST /api/v1/auth/register**, select **Try it out**, and register a customer:

   ```json
   {
     "name": "Anu Example",
     "email": "anu@example.com",
     "password": "Choose-your-own-strong-password",
     "role": "customer",
     "town": "Colombo"
   }
   ```

2. Copy the returned `data.accessToken`. Click **Authorize** and paste only the token. The same account can sign in to the connected Laravel frontend.
3. **POST /api/v1/requests** creates the customer's job. Use a future ISO 8601 timestamp with an offset, for example a future day at `10:00:00+05:30`. Supply:

   ```json
   {
     "title": "Repair a leaking kitchen tap",
     "description": "My kitchen tap keeps leaking even when it is closed.",
     "town": "Colombo",
     "address": "Example address",
     "preferredAt": "2099-01-15T10:00:00+05:30",
     "budgetLkr": 3500,
     "category": "Plumbing"
   }
   ```

   Replace the illustrative 2099 timestamp with your intended future appointment. Save the request ID and customer token locally while testing.
4. Register another account with `role: "worker"` and a different email. Authorize with the worker's token. Worker registration starts unavailable, with no service categories or rate.
5. **PATCH /api/v1/worker/profile** completes the worker profile:

   ```json
   {
     "bio": "Careful repairs for household taps and pipes.",
     "categories": ["Plumbing"],
     "serviceTowns": ["Colombo"],
     "yearsExperience": 5,
     "rateLkr": 2500,
     "rateUnit": "visit",
     "available": true
   }
   ```

   Save the worker ID. A profile needs a biography, at least one category, at least one service town, and a positive rate. An administrator must approve it using **PATCH /api/v1/admin/workers/{worker_id}/verification** with `{"verified": true, "note": "Profile and service details checked."}` before it appears in matching. Material profile changes require review again. Optional worker location requires `latitude`, `longitude`, and `serviceRadiusKm` together; request location requires both coordinates. Matching uses the worker radius when both locations exist, otherwise service towns.
6. Authorize with the customer token again. Call **POST /api/v1/requests/{request_id}/recommendations** with `{}`. The eligible worker should appear. The public worker directory supports `category`, `town`, `search`, `available`, `maxRate`, `page`, and `perPage` filters.
7. **POST /api/v1/bookings** with `requestId`, `workerId`, a future `scheduledAt`, and a later `scheduledEndAt` creates a pending booking. Optional `deadlineAt` defaults to the end time and cannot precede it. Use ISO 8601 timestamps with offsets. Overlapping active bookings for the worker return 409. Its rate is a snapshot of the worker's current rate, not a final job invoice.
8. Authorize with the assigned worker token. Call **PATCH /api/v1/bookings/{booking_id}/status** three times, in order:

   ```json
   {"status": "accepted"}
   ```
   ```json
   {"status": "in_progress"}
   ```
   ```json
   {"status": "awaiting_confirmation", "note": "Tap repaired and checked."}
   ```

9. Authorize with the customer token. Confirm with **PATCH /api/v1/bookings/{booking_id}/status** and `{"status": "completed"}`. Only this confirmation closes the request and updates completed-job metrics. To dispute completion instead, send `{"status": "in_progress", "note": "The tap still leaks and needs another check."}`. After confirmation, **POST /api/v1/bookings/{booking_id}/review**:

   ```json
   {"rating": 5, "comment": "Careful work and clear communication."}
   ```

10. Check booking details, `/api/v1/dashboard`, notifications, the worker's public reviews, and `/api/v1/worker/performance` using the appropriate role. The booking and review survive API restarts because they are stored in PostgreSQL.
11. **POST /api/v1/auth/logout** revokes only the current token. Using that token again returns 401. Log in again to receive a new one. Tokens expire after eight hours by default; there is no refresh-token endpoint in this version.

## Administrator account

For optional local demonstration data, run `.venv\Scripts\python.exe -m app.cli seed-samples`.
This explicit command is restricted to `APP_ENV=local` and the `skillsync_backend` database.
It adds 24 fictional workers covering all ten categories, four customers, one sample administrator,
64 requests, 60 bookings across all lifecycle states, 40 reviews, and three complaints.
Worker names and biographies use natural display copy. Reserved sample emails and the seed audit record identify the fictional accounts; they are not training data.
Phone numbers are intentionally absent; sample accounts use reserved `example.com` email addresses.
The command prints a randomly generated password once for the new sample accounts:
`sample.admin@example.com`, `sample.customer01@example.com` through `sample.customer04@example.com`,
and `sample.worker01@example.com` through `sample.worker24@example.com`.
Workers 01–20 have completed-job histories; 21–22 await approval, 23 needs corrections,
and 24 is approved but unavailable. Worker 08 is a Colombo plumber; customer 01 is in Colombo.
Run the command only when sample data is wanted. It is never called at startup or by migrations.
Re-running it preserves existing records, account passwords, and subsequent edits without duplicating the batch.

Public registration accepts only customer or worker roles. There is no default administrator or shared password. Create one explicitly from the backend terminal:

```powershell
.venv\Scripts\python.exe -m app.cli create-admin
```

The command prompts for name, email, town, and a hidden password. Existing accounts are never silently promoted. Log in through `/api/v1/auth/login` and use that token for admin APIs.

`GET /api/v1/admin/{entity}` supports `workers`, `customers`, `categories`, `requests`, `bookings`, `reviews`, and `complaints`; `/api/v1/admin/{entity}/{record_id}` returns a detail record. Admins can update category descriptions/examples and review worker applications and profile changes with a required note. Those writes produce audit records. Approval controls directory and booking eligibility; it is an administrator decision, not an automated identity or credential check. Admins cannot bypass booking transitions, register other admins through the public API, or delete/block accounts in this scope.

## Endpoint inventory

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Process liveness |
| GET | `/health/ready` | PostgreSQL/schema readiness |
| POST | `/api/v1/auth/register` | Customer/worker registration and access token |
| POST | `/api/v1/auth/login` | Sign in and issue access token |
| POST | `/api/v1/auth/logout` | Revoke current token |
| GET / PATCH | `/api/v1/me` | Own identity / customer contact profile |
| GET | `/api/v1/categories` | Exact ten category labels |
| GET | `/api/v1/workers` | Filtered, paginated directory |
| GET | `/api/v1/workers/{worker_id}` | Public worker profile and latest 20 written reviews |
| GET / PATCH | `/api/v1/worker/profile` | Own worker profile |
| GET | `/api/v1/worker/performance` | Actual completed-job counts and ratings; nullable model scores |
| GET / POST | `/api/v1/requests` | Authorized list / create request |
| GET / PATCH | `/api/v1/requests/{request_id}` | Authorized details / edit unbooked request |
| POST | `/api/v1/requests/{request_id}/classify` | Explicit 503 until a trained model is installed |
| POST | `/api/v1/requests/{request_id}/recommendations` | Rule-based eligible workers |
| GET / POST | `/api/v1/bookings` | Authorized list / create pending booking |
| GET | `/api/v1/bookings/{booking_id}` | Details, history, worker, request, review |
| PATCH | `/api/v1/bookings/{booking_id}/status` | Legal lifecycle transition |
| POST | `/api/v1/bookings/{booking_id}/review` | One review after completion |
| POST | `/api/v1/bookings/{booking_id}/complaint` | Customer complaint with a reason; one per eligible booking |
| GET | `/api/v1/notifications` | Own notifications, optionally unread only |
| PATCH | `/api/v1/notifications/{notification_id}` | Mark own notification read |
| GET | `/api/v1/dashboard` | Counts scoped to current role |
| GET | `/api/v1/admin/dashboard` | Global counts and model availability |
| GET | `/api/v1/admin/{entity}` | Paginated admin records |
| GET | `/api/v1/admin/{entity}/{record_id}` | Admin record details |
| PATCH | `/api/v1/admin/categories/{category_id}` | Description/example; taxonomy remains immutable |
| PATCH | `/api/v1/admin/workers/{worker_id}/verification` | Manual verification with audit note |
| PATCH | `/api/v1/admin/complaints/{complaint_id}/resolution` | Final upheld/dismissed decision with evidence and audit record |

Admin record lists also include `complaints`. Customers can cancel pending, accepted, or in-progress bookings; workers can cancel accepted or in-progress bookings. Cancellation requires a reason. Complaint resolution records an administrative decision and notifies both parties; it does not automatically change booking status or ratings.

For existing installations, back up PostgreSQL and run `.venv\Scripts\alembic.exe upgrade head`. The workflow migration preserves records and existing verified approvals. Legacy end times, deadlines, and customer confirmations remain null rather than being invented.

## Database and application structure

```text
app/
  api/           # HTTP routers, photo endpoints and pagination dependencies
  core/          # Settings, database sessions, authentication and errors
  services/      # Feature operations, shared queries and workflow rules
  models/        # SQLAlchemy entities and constraints
  schemas/       # Pydantic contracts and response serializers
  main.py        # FastAPI application factory and health endpoints
  cli.py         # Database setup, seed and administrator commands
  catalog.py     # Stable service categories
  sample_data.py # Optional demo-data generation
```

Configuration resolves `backend/.env` and photo storage from the backend root. Startup remains `uvicorn app.main:app`; CLI commands remain `python -m app.cli`. Alembic uses the same model metadata and existing migrations. No database changes are required.

- `app/main.py`: application factory, health checks, common error responses.
- `app/api/routes.py`, `app/api/admin.py`: public/authenticated and administrator endpoints.
- `app/core/auth.py`: Argon2 password hashing and expiring, revocable opaque bearer credentials. Only SHA-256 token digests are stored.
- `app/schemas/__init__.py`: validated camelCase payloads and response schemas. Unknown input keys are rejected.
- `app/services/`: ownership, matching rules, transactions, booking lifecycle, notifications.
- `app/models/__init__.py`: PostgreSQL entities and constraints.
- `app/catalog.py`: stable category catalog only, not a worker/model training dataset.
- `migrations/`: versioned Alembic migrations, including the unique partial index preventing two active bookings for one request.
- `tests/`: PostgreSQL API integration and concurrent-submission tests.

Tables: `users`, `access_tokens`, `categories`, `workers`, `worker_categories`, `worker_towns`, `worker_metrics`, `service_requests`, `bookings`, `booking_events`, `reviews`, `notifications`, `complaints`, and `audit_events`. Alembic maintains its own version table. Worker metrics contain actual completed-job counts, not learned predictions.

Booking writes lock the request, then booking, then worker as needed. One active booking per request and one review per booking are also database-enforced. Status history, notifications, request state, completed counts, and review totals are updated in the same transaction.

Customers may cancel pending, accepted, or in-progress bookings. Assigned workers may accept/reject pending bookings, start accepted bookings, and report completion for customer confirmation. Only the customer can confirm completion; a dispute returns the job to in-progress. Terminal states cannot be changed. Rejection/cancellation reopens the request; completion closes it. Request category, town, and other details cannot change while booked or closed.

Timestamps are timezone-aware and returned in UTC; clients can display `Asia/Colombo`. Money is stored as fixed-precision decimal in LKR and returned as JSON numbers. `hour` and `visit` are different rate bases; `maxRate` is a simple numeric filter, not a final-cost comparison.

## Model boundary and frontend connection

No training dataset or model artifact has been supplied. This backend does not read the frontend's demo fixtures, manufacture scores, or claim a trained model exists.

- Classification returns `503` with `error.code: "model_unavailable"`; requests can select or correct their category manually.
- Recommendations filter approved complete profiles by category, radius/town, availability, and optional rate, then return at most 50 eligible workers in stable alphabetical order. `source` is `rule_based`, `rank` is presentation order, and `matchScore`, `categorySkillScore`, and `reliabilityProbability` stay null.
- Performance exposes actual booking/review history; future trained outputs will need defined targets, versioning, evaluation, and calibration.
- Authentication uses JSON login and HTTP Bearer tokens, not the OAuth password form or JWT. Laravel encrypts each token in the server-side session and handles expiry/revocation.
- Lists return `data` plus pagination `meta`. Private single records return `data`; errors return `error.code`, `error.message`, and optional `error.fields`. Cross-owner records return 404, role denials 403, validation 422, state/uniqueness conflicts 409, unavailable services 503.
- The frontend accepts nullable match scores and `source: "rule_based"`, and uses manual category selection while classification is unavailable.
- Writes have no automatic retry/replay mechanism. Duplicate active bookings/reviews return 409; callers should retrieve current state after an uncertain submission rather than blindly retrying writes.

Email verification/recovery, payment processing, email/SMS delivery, account suspension, model training, and production deployment are outside this version. Before public deployment, configure HTTPS, authentication rate limits, a dedicated least-privilege database role, and backup/monitoring. The API uses bearer headers, exposes no cross-origin browser permissions, and binds to loopback in the documented startup command.

## Verification

### Service organization

Administrative writes and photo processing/storage live in `app/services/admin_service.py` and `app/services/photo_service.py`. HTTP routes retain transport validation and authentication dependencies.

Other application operations in `app/services/` are split into `account_service.py`, `profile_service.py`, `request_service.py`, `booking_service.py`, `matching_service.py`, and `notification_service.py`. Shared query/pagination helpers are in `service_queries.py`; profile-review and location rules remain in `workflows.py`. Routers import the feature modules directly; the services package initializer does not eagerly import them.

Service write operations commit their own transaction. Helpers such as `notify()` only stage changes so booking events, notifications and record updates commit together. The refactor preserves booking row-lock order, ownership checks, endpoint paths and response schemas. No database migration is required for this restructuring.

### List filters

- `GET /api/v1/bookings`: `page`, `perPage`, exact `status`, and `search` (request title or town). Dashboard previews can use `group=active|confirmed` and `order=scheduled_asc|scheduled_desc`.
- `GET /api/v1/admin/{entity}`: `page`, `perPage`, `search`, and `pendingOnly=true` for complete pending worker applications.
- `GET /api/v1/notifications`: `page`, `perPage`, and `unread=true`.
- `GET /api/v1/requests`: `page` and `perPage`.

Filters and ownership restrictions are applied before counting and paging. Search is case-insensitive with literal wildcard characters. Filter changes reset frontend page selection. Failed reads show retry states instead of empty results. Admin details use the single-record endpoint rather than downloading every record.

### Running checks

The test suite covers approval changes, coordinate validation, radius matching, concurrent overlapping bookings, customer confirmation/disputes, complaints, migration preservation, and photo validation/storage. Run the commands below for the result on your checkout. The runner may report an upstream Starlette/httpx deprecation warning.

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\ruff.exe check app tests migrations
.venv\Scripts\ruff.exe format --check app tests migrations
.venv\Scripts\alembic.exe check
.venv\Scripts\python.exe -m compileall -q app migrations
```

Tests use your configured PostgreSQL database and create an isolated schema named `skillsync_test_<random UUID>` for each test. They run the actual migration, create their own accounts and bookings, and remove only that test schema afterward. They never truncate or reset the application's public tables. The configured test role needs schema creation permission; do not run development tests using production credentials.

Official references used: [FastAPI security](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/), [SQLAlchemy PostgreSQL](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html), and [Alembic migrations](https://alembic.sqlalchemy.org/en/latest/tutorial.html).



## Worker profile photos

See the [worker photo setup and endpoint reference](../README.md#worker-profile-photos). Run `uv sync --frozen` and `.venv\Scripts\alembic.exe upgrade head` after pulling this feature. Pillow validates and normalizes the uploaded image; PostgreSQL stores an optional photo key and JPEGs are stored in `storage/worker-photos/` (or `PHOTO_STORAGE_PATH`). Back up the files as well as the database.

Upload accepts raw image bytes, not multipart form data: `PUT /api/v1/worker/profile/photo` with a worker bearer token and an image Content-Type. The 2 MB limit is enforced while reading the body. `DELETE` on the same path removes only that worker's photo. Public thumbnail URLs have no authentication token; files are public to anyone with the link.

The website crop editor sends its selected square as a 512 x 512 PNG. Pillow validates the submitted content, corrects EXIF orientation, resizes proportionally to a maximum side of 512 pixels, strips metadata and encodes JPEG. It adds no outer padding. Direct API clients may send non-square images; their proportions are preserved. The uploaded original is not retained separately. Restart the backend after image-processing changes if automatic reload has not applied them.

For focused photo regression coverage, run `.venv\Scripts\python.exe -m pytest tests/test_photos.py -q` from `backend/`.
