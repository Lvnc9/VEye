# Authentication, RBAC, personnel (Phase 1) — ✅ done

Code: `backend/apps/accounts/` (`models.py`, `views.py`, `authentication.py`, `serializers.py`, `tests.py`)
and `backend/apps/core/permissions.py`. Frontend: `lib/current-user.tsx`, `app/(auth)/login`, `proxy.ts`.

## Auth mechanics
- Login `POST /api/v1/auth/login/` with `{national_code, password}` — **checked as a pair**
  (V_1.0 checked them independently: any valid user + any valid password got in).
- JWT (SimpleJWT) stored in **httpOnly cookies**: `access_token` (15 min), `refresh_token` (7 days),
  plus a readable `csrftoken` (double-submit CSRF). `CookieJWTAuthentication` enforces CSRF on
  POST/PUT/PATCH/DELETE (missing header → 403).
- Refresh `POST /auth/refresh/` rotates the refresh token and blacklists the old one.
- Logout `POST /auth/logout/` blacklists both tokens in Redis (`blacklist:<jti>`, TTL = remaining
  life); old tokens then return 401.
- Login rate limit 10/min/IP (`django-ratelimit`); wrong password → 401 Persian message.
- `GET /auth/me/` returns the user incl. `title` and `capabilities[]`.
- Frontend `api-client.ts`: on 401 tries one refresh then redirects to `/login` — **except** for the
  session endpoints themselves (`/auth/login|refresh|logout`), otherwise a wrong password reloaded the page.
- `proxy.ts` guards routes; public: `/login`, `/verify/*` (the verify page itself is Phase 5).

## User model
`User` (`national_code` = USERNAME_FIELD), `full_name`, `mobile_phone`, `access_roll`, `access_level`.
- Rolls: **کارفرمایی** (employer) · **ستادی** (headquarters) · **صفی** (guild/line). Levels 1–3.
- `User.title` resolves the 3×3 سمت matrix (`TITLE_MATRIX`), ported from `V_1.0 register.py:739-769`:

| | L1 | L2 | L3 |
|---|---|---|---|
| کارفرمایی | مدیر عامل | رئیس هیئت مدیره | عضو هیئت مدیره |
| ستادی | نماینده مدیریت | معاون/مشاور | مدیر/رئیس |
| صفی | سرپرست | کارشناس | کارمند/اپراتور |

## Capabilities (confirmed by the product owner)
Computed from the roll (**not** Django Groups — a group-sync signal and seed migration were removed).

| Capability | Granted to |
|---|---|
| `create_document` (تدوین) | صفی, ستادی |
| `confirm_document` (تایید) | ستادی |
| `approve_document` (تصویب) | کارفرمایی |
| `manage_personnel` | کارفرمایی |
| `print_document` (ساخت و نمایش PDF) | **every roll** — added in Phase 4; gates `POST …/pdf/{kind}/` only (reads/downloads need just a login) |

Separation of duties is deliberate and tested: no roll holds the whole create→confirm→approve chain;
کارفرمایی cannot author. Superusers hold everything.
DRF permission `HasCapability` (`apps/core/permissions.py`) reads `required_capability` (all methods)
and/or `write_capability` (unsafe methods) from the view. For a view holding actions with *different* capabilities use
`capability_required(cap)` (same file) as an action's `permission_classes` — the document viewset's submit/confirm/approve do (Phase 5).
On top of capabilities the workflow enforces **no one signs two steps of one document** (409 `same_person`) — see [09-workflow.md](09-workflow.md).

## Personnel API — `/api/v1/personnel/`
Any authenticated user can **read** (the register needs names/سمت). Writes need `manage_personnel`.
`GET /personnel/{id}/title/` returns the computed title. `is_staff` cannot be set through the API.
**DELETE** returns **409 `user_has_documents`** (Persian message) if the person authored any document
(`Document.created_by` is `PROTECT`); retire people by `PATCH {is_active:false}` — history stays attributable.
V_1.0 never persisted registered personnel at all (the screen only set a label).

## Known auth caveats
See [07-known-gaps.md](07-known-gaps.md): Enter-key login submit unverified; `change-me` dev secret triggers a
PyJWT key-length warning and passes the prod guard. Deactivating a user takes effect immediately on every
request (SimpleJWT's `get_user` rejects inactive users), and refresh also refuses inactive users.
