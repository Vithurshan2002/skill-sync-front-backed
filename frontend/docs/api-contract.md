# SkillSync API integration

The browser uses Laravel Blade, Livewire, and Filament. Laravel sends server-to-server
HTTP requests to FASTAPI_BASE_URL; FastAPI owns business records in PostgreSQL.
SkillSyncGateway is implemented only by FastApiSkillSyncGateway. There is no mock
adapter, demo login, fixture initialization, or reset API.

## Authentication

AuthController posts JSON to /api/v1/auth/login or /api/v1/auth/register. Responses
contain data.accessToken, tokenType, expiresAt, and user. Tokens are opaque bearer
credentials, encrypted in the Laravel server-side session. BackendIdentity maps the
backend UUID to users.backend_id for Laravel/Filament sessions and panel permissions.
Frontend passwords are random local placeholders; login always uses FastAPI.

BackendSession validates GET /api/v1/me on authenticated requests and persists on
Livewire updates. Tokens belong to individual sessions and are never shared across
users. A 401 clears the session and requires login. Logout calls POST /api/v1/auth/logout
before clearing the local session; a backend outage does not prevent local logout.
Normal Laravel session security, CSRF, and login/register throttling remain enabled.
All browser calls stay on the Laravel origin; no browser-to-FastAPI CORS is required.

## Service mapping

All paths below begin with /api/v1.

| Frontend operation | Backend endpoint |
| --- | --- |
| Categories | GET /categories |
| Directory / profile | GET /workers, GET /workers/{id} |
| Identity / customer profile | GET /me, PATCH /me |
| Worker profile | GET /me plus GET /worker/profile; PATCH /worker/profile |
| Requests | GET/POST /requests, GET/PATCH /requests/{id} |
| Matching | POST /requests/{id}/recommendations |
| Bookings | GET/POST /bookings, GET /bookings/{id} |
| Booking progress | PATCH /bookings/{id}/status |
| Review | POST /bookings/{id}/review |
| Notifications | GET /notifications, PATCH /notifications/{id} |
| Dashboard totals | GET /dashboard |
| Worker history | GET /worker/performance plus GET /bookings |
| Administrator totals | GET /admin/dashboard |
| Administrator records | GET /admin/{entity} |
| Category editing | PATCH /admin/categories/{id} |
| Worker verification | PATCH /admin/workers/{id}/verification |

A new request can omit category; Find suitable workers then opens manual category
selection. The frontend does not call the unavailable classifier in this flow.
Recommendations return source=rule_based, nested worker profiles, reasons, and null
AI scores. The current list order is alphabetical. Verification writes include a
user-entered note. Admin roles can be created only through the backend CLI.

## Data and errors

Success envelopes use data, with meta.page/perPage/total/lastPage on lists. IDs are
opaque strings. The directory uses API pagination. Existing workspace tables follow
every API page before applying local filters, avoiding a first-page-only display.
Dashboard counts use dedicated backend totals. Worker profiles merge /me contact
fields with worker fields; performance merges recorded metrics and completed bookings.

The adapter sends only allowed payload fields, converts optional empty values to
null, normalizes integer form values, and sends timestamps with explicit offsets.
The application and form display timezone is Asia/Colombo; responses may be UTC.
LKR rates specify hour or visit and are not final invoice totals.

BackendClient handles 401, 403, 404, 409, 422 and unavailable services. Validation
errors map to form fields; conflicts are shown as operation errors. Network failures
produce a service-unavailable state and never load local fixture records. Mutations
are not automatically retried: after an interrupted booking or review, inspect the
current records before resubmitting.

## Booking rules

Assigned workers accept/reject pending bookings, start accepted bookings, and complete
in-progress bookings. Customers cancel their own pending/accepted bookings. Terminal
states cannot change. There is at most one active booking per request. Cancellation
or rejection reopens the request; completion closes it. Reviews require completion
and the owning customer, and are unique per booking. FastAPI enforces these rules
transactionally; UI visibility is not an authorization mechanism.
