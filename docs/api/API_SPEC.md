# API_SPEC.md — AlphaEdge AI

This document defines the complete REST API surface for AlphaEdge AI, extending [`PROJECT_CONTEXT.md`](./PROJECT_CONTEXT.md) (§ 14, API Standards) and built against the schema in [`DATABASE.md`](./DATABASE.md). It is the contract every backend `api/` router and every frontend `lib/api-client` call must match. This is a specification, not code — implementation happens per-phase, always against this document.

If an endpoint isn't listed here, it doesn't exist yet — add it here first, then implement it.

---

## 1. API Philosophy

- **The API is the only door.** The Next.js frontend, and any future consumer (mobile app, public API product), talks to Postgres, Redis, brokers, and AI providers exclusively through this API — never directly. This is what keeps `PROJECT_CONTEXT.md`'s module boundaries real in practice, not just in a diagram.
- **Resources, not actions.** Endpoints represent nouns (`/stocks`, `/watchlists`) that support standard HTTP verbs — not RPC-style action endpoints (`/getStockData`), except where an operation is genuinely not resource-shaped (e.g. `/auth/webhook/clerk`), which is called out explicitly where it happens.
- **Predictable over clever.** Every list endpoint paginates, filters, and sorts the same way (Sections 10–12). Every error looks the same shape (Section 6). A developer who's used one endpoint should be able to guess how the next one behaves.
- **Read paths are cheap, write paths are careful.** Read endpoints are optimized for speed and caching. Write endpoints — especially anything touching money, orders, or broker credentials — favor explicitness and auditability over convenience.
- **The API never promises certainty it doesn't have.** Endpoints returning AI predictions, scores, or recommendations always include confidence/probability fields and never format responses in a way that implies guaranteed outcomes — consistent with `PROJECT_CONTEXT.md § 20`.

## 2. Versioning Strategy

- All endpoints are prefixed `/api/v1/...`. The prefix is written as `/v1/...` throughout this document for brevity.
- A breaking change (removed field, changed field type, changed status code semantics, removed endpoint) requires a new version (`/v2/...`) — it is never introduced silently into `/v1`.
- Additive, backward-compatible changes (new optional field, new endpoint, new optional query param) ship into the current version.
- `/v1` is supported for a minimum deprecation window (defined when `/v2` planning begins) after any successor version ships — no version is pulled without notice.
- The OpenAPI spec (Section 13) is versioned alongside the API and is the definitive record of what changed between versions.

## 3. Authentication Strategy

- **Clerk is the identity provider.** The frontend obtains a Clerk session and attaches a Clerk-issued JWT as a `Authorization: Bearer <token>` header on every request to protected endpoints.
- **The backend verifies, never trusts.** `core/security.py` verifies the JWT against Clerk's JWKS endpoint on every request — signature, expiry, and issuer are checked server-side; the frontend's claim of who's logged in is never taken at face value.
- **`clerk_user_id` → internal user.** On first verified request from a new Clerk identity, a corresponding row is created in `users.users` (also handled proactively via the Clerk webhook — Section on Authentication endpoints below) so every other table's `user_id` foreign key has something stable to point to, independent of Clerk-side identity changes.
- **Public endpoints are the explicit exception, not the default.** Any endpoint not requiring authentication is marked "Authentication Required: No" and is treated as reviewed-and-intentional (e.g. public stock lookup for marketing pages), not an oversight.
- **Service-to-service / webhook calls** (e.g. Clerk's webhook) authenticate via a shared signing secret verified against the request signature, not a user JWT.

## 4. Authorization Strategy

- **Role-based**, backed by `users.roles` (`free`, `pro`, `admin`, extensible). A request's permission level is resolved from the verified user's `role_id` on every request — never from a client-supplied field.
- **Permission levels used throughout this document:**
  - `Public` — no account needed.
  - `Authenticated` — any logged-in user, any role.
  - `Pro` — `pro` or `admin` role required (gates premium features: AI chat depth, backtesting, broker write access, etc. — exact gating finalized per-feature at implementation).
  - `Admin` — `admin` role only.
  - `Owner` — authenticated user acting only on their own resources (e.g. their own watchlist), enforced by scoping every query to the requester's `user_id`, regardless of role.
- **Resource ownership is enforced at the `application` layer**, not just checked in the router — a `Pro` user requesting another user's portfolio gets `403`, never another user's data, even if the resource ID is guessable.
- **Broker write access (order placement) is a second, narrower gate** on top of role: `broker.kite_integrations.write_access_enabled` must also be true, per `DATABASE.md`'s Kite integration table — an `admin` role does not implicitly grant broker write access to a user's own account.

## 5. Response Format

Every successful response follows one shape:

```
{
  "success": true,
  "data": { ... } | [ ... ],
  "meta": { ... }        // optional — pagination, timestamps, etc.
}
```

Every error response follows one shape (detailed in Section 6):

```
{
  "success": false,
  "error": {
    "code": "STRING_ERROR_CODE",
    "message": "Human-readable explanation",
    "details": { ... }    // optional — field-level validation info, etc.
  }
}
```

- All timestamps are ISO 8601, UTC (`2026-07-13T10:00:00Z`).
- All monetary/price values are returned as strings (not floats) to preserve precision from `NUMERIC` columns — the frontend parses with a decimal-safe library, never native float math.
- `null` is used for "explicitly no value," fields are never omitted to mean the same thing — every documented field is always present in the response.

## 6. Error Handling Standards

Standard error codes, reused across every endpoint. Endpoint-specific sections below list only errors *beyond* this standard set.

| HTTP Status | Code | Meaning |
|---|---|---|
| 400 | `BAD_REQUEST` | Malformed request (unparseable body, invalid query param format) |
| 401 | `AUTH_REQUIRED` | Missing or invalid authentication token |
| 403 | `FORBIDDEN` | Authenticated but not permitted (wrong role, not resource owner) |
| 404 | `NOT_FOUND` | Resource doesn't exist or isn't visible to this user |
| 409 | `CONFLICT` | Request conflicts with current state (e.g. duplicate watchlist name) |
| 422 | `VALIDATION_ERROR` | Body/params fail schema validation — `details` lists field-level errors |
| 429 | `RATE_LIMITED` | Rate limit exceeded — see Section 7 |
| 500 | `INTERNAL_ERROR` | Unexpected server error — never leaks stack traces or internal detail |
| 503 | `SERVICE_UNAVAILABLE` | A dependency (broker API, AI provider) is down; retry guidance included |

- Errors from external dependencies (Kite Connect, OpenAI, HuggingFace) are always translated into this shape — a raw upstream error body is never passed through to the client.
- Validation errors (`422`) always include `details.fields`, an array of `{ field, message }`, so the frontend can highlight the exact offending input.

## 7. Rate Limiting

- Enforced per authenticated user (by `user_id`) where authenticated, per IP where not.
- Default tiers (exact numbers finalized at implementation, structure fixed now):
  - `Public`/unauthenticated: lowest limit, read-only endpoints only.
  - `Authenticated` (`free` role): standard limit.
  - `Pro`: higher limit, particularly for AI Chat and AI Predictions endpoints (external API cost-bearing).
  - `Admin`: not rate-limited for internal operational endpoints, still limited for anything hitting external providers.
- Rate limit state is tracked in Redis (Section 7 of `DATABASE.md`), not Postgres — high-frequency counters don't belong in the transactional database.
- Every response includes `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` headers, so clients can self-throttle before hitting `429`.
- AI Chat and AI Predictions endpoints additionally enforce a cost-aware secondary limit (requests per hour), independent of the general per-minute limit, since these calls have real per-request external cost.

## 8. API Security

- All traffic over HTTPS only — no plaintext HTTP endpoint exists, including in preview environments.
- CORS restricted to known frontend origins (the deployed Vercel domain(s) and local dev origin) — not a wildcard.
- All input validated via Pydantic schemas at the `api` layer boundary before reaching `application`/`domain` (per `PROJECT_CONTEXT.md § 14`).
- No endpoint ever returns another user's PII, portfolio, holdings, orders, or broker tokens — enforced by ownership scoping (Section 4), tested explicitly (per `PROJECT_CONTEXT.md`'s Testing Checklist) for every user-scoped resource.
- Broker access tokens (`broker.kite_integrations`) are never returned in any API response, in any form, to any client — not even to the owning user's own frontend session. The frontend only ever sees connection *status* (`GET /v1/broker/kite/status`), never the token.
- Webhook endpoints (Clerk, and later any broker webhook) verify a cryptographic signature on every request; unsigned or invalid-signature requests are rejected before any processing.
- Admin endpoints require the `Admin` permission level and are additionally logged to `core.audit_logs` on every write.

## 9. Naming Conventions

- URL paths: plural nouns, `kebab-case` for multi-word resources (`/geopolitical-events`, `/quarterly-results`).
- Path parameters: `{symbol}` for stock lookups (human-friendly, matches `market_data.stocks.symbol`), `{id}` (UUID) for everything else.
- Query parameters: `snake_case` (`sort_by`, `page_size`) — matches Pydantic model field convention on the backend.
- JSON body/response fields: `snake_case`, matching the database column names in `DATABASE.md` wherever the field is a direct pass-through, so there's no silent renaming between DB, API, and generated frontend types.
- Nested/sub-resources use path nesting only one level deep (`/watchlists/{id}/items`, not `/users/{id}/watchlists/{id}/items`) — deeper relationships are expressed via query params or separate top-level lookups instead.

## 10. Pagination Standards

Every list endpoint supports cursor-agnostic offset pagination via two query params:

| Param | Type | Default | Notes |
|---|---|---|---|
| `page` | integer | 1 | 1-indexed |
| `page_size` | integer | 25 | max 100 |

Response `meta` on paginated endpoints:

```
"meta": {
  "page": 1,
  "page_size": 25,
  "total_items": 342,
  "total_pages": 14
}
```

High-volume time-series endpoints (technical indicators, price history, API logs) additionally support cursor-based pagination via `after` (an opaque cursor token) for efficient deep pagination — noted explicitly on those endpoints, since offset pagination degrades on very large tables.

## 11. Filtering Standards

- Filters are passed as query params matching the field name being filtered, e.g. `?exchange=NSE&sector=energy`.
- Range filters use a `_min`/`_max` suffix: `?market_cap_min=1000000`.
- Date range filters use `_from`/`_to`: `?published_at_from=2026-01-01&published_at_to=2026-06-30`.
- Multi-value filters accept comma-separated values: `?exchange=NSE,BSE`.
- Every filterable field is explicitly documented per endpoint below — undocumented query params are ignored, not silently accepted, so typos fail visibly in testing rather than silently returning unfiltered results.

## 12. Sorting Standards

- `sort_by=<field>` selects the field; `sort_order=asc|desc` (default `desc` for time-based data, `asc` for alphabetical/name-based lists) controls direction.
- Only fields explicitly listed as sortable per endpoint are accepted — an invalid `sort_by` returns `422 VALIDATION_ERROR`, not a silent fallback to default sort.
- Multi-field sort is not supported in v1 (single `sort_by` only) — flagged as a candidate v2 enhancement if a real need emerges.

## 13. API Documentation Strategy

- FastAPI's automatic OpenAPI schema generation is the source of interactive documentation (`/docs`, Swagger UI, and `/redoc`), always in sync with actual route definitions since it's generated from the same Pydantic models used to validate requests.
- The generated OpenAPI spec is exported into `docs/api/` (per `PROJECT_CONTEXT.md § 7`) on every release, versioned alongside the API version.
- `packages/shared-types` (frontend TypeScript types) is generated directly from this OpenAPI spec — this document (`API_SPEC.md`) and the DB schema are the human-authored source of truth; the OpenAPI spec and generated types are downstream of implementing this document accurately, not a separate design surface.
- Every endpoint in this document maps 1:1 to a route that must carry a docstring/description surfaced in the OpenAPI UI — undocumented routes fail review.

---

## 14. API Groups & Endpoints

Unless otherwise noted, all endpoints are prefixed `/v1`. "Standard errors" refers to the applicable subset of Section 6 (typically `AUTH_REQUIRED`, `VALIDATION_ERROR`, `RATE_LIMITED`, `INTERNAL_ERROR`) and is not repeated in full per endpoint.

### A. Authentication

#### `POST /auth/webhook/clerk`
- **Purpose:** Receives Clerk lifecycle events (user created/updated/deleted) and syncs `users.users` accordingly.
- **Path Params:** none
- **Query Params:** none
- **Request Body:** Clerk's webhook event payload (`type`, `data`)
- **Response Schema:** `{ received: true }`
- **Authentication Required:** No (verified instead via Clerk webhook signing secret in `Svix-Signature` header)
- **Permission Level:** N/A — service-to-service
- **Possible Errors:** `400 BAD_REQUEST` (invalid signature), `422 VALIDATION_ERROR` (unrecognized event shape)

#### `GET /auth/me`
- **Purpose:** Returns the authenticated user's resolved identity and role — the first call the frontend makes after login to bootstrap app state.
- **Path Params:** none · **Query Params:** none · **Request Body:** none
- **Response Schema:** `{ id, clerk_user_id, email, role: { name, permissions }, status, created_at }`
- **Authentication Required:** Yes
- **Permission Level:** Authenticated
- **Possible Errors:** Standard errors only

#### `POST /auth/logout`
- **Purpose:** Marks the current app-level session (`users.user_sessions`) as ended for audit purposes. Clerk's own session termination is handled client-side by the Clerk SDK; this call just closes AlphaEdge AI's session record.
- **Path Params:** none · **Query Params:** none · **Request Body:** none
- **Response Schema:** `{ ended_at }`
- **Authentication Required:** Yes
- **Permission Level:** Authenticated
- **Possible Errors:** Standard errors only

---

### B. Users

#### `GET /users/me/profile`
- **Purpose:** Returns the authenticated user's extended profile.
- **Response Schema:** `{ display_name, avatar_url, risk_profile, preferred_theme, timezone }`
- **Authentication Required:** Yes · **Permission Level:** Owner
- **Possible Errors:** `404 NOT_FOUND` (profile not yet created — frontend should treat as "needs onboarding," not an error state)

#### `PATCH /users/me/profile`
- **Purpose:** Updates the authenticated user's profile.
- **Request Body:** any subset of `{ display_name, avatar_url, risk_profile, preferred_theme, timezone }`
- **Response Schema:** updated profile object (same shape as `GET`)
- **Authentication Required:** Yes · **Permission Level:** Owner
- **Possible Errors:** `422 VALIDATION_ERROR` (e.g. invalid `risk_profile` enum value)

#### `DELETE /users/me`
- **Purpose:** Soft-deletes the authenticated user's account (`users.users.status = 'deleted'`) — does not hard-delete historical/audit data.
- **Response Schema:** `{ status: "deleted" }`
- **Authentication Required:** Yes · **Permission Level:** Owner
- **Possible Errors:** Standard errors only

#### `GET /users/me/sessions`
- **Purpose:** Lists recent app-level session activity for the authenticated user (security review use case).
- **Query Params:** `page`, `page_size`
- **Response Schema:** paginated array of `{ id, ip_address, user_agent, started_at, ended_at }`
- **Authentication Required:** Yes · **Permission Level:** Owner
- **Possible Errors:** Standard errors only

---

### C. Stocks

#### `GET /stocks`
- **Purpose:** Lists tradeable instruments.
- **Query Params:** `exchange` (`NSE,BSE`), `sector`, `industry`, `is_active` (bool), `sort_by` (`symbol`, `market_cap` — future field), `sort_order`, `page`, `page_size`
- **Response Schema:** paginated array of `{ id, symbol, exchange, company: { legal_name, sector, industry }, is_active }`
- **Authentication Required:** No · **Permission Level:** Public
- **Possible Errors:** Standard errors only

#### `GET /stocks/{symbol}`
- **Purpose:** Full detail for a single stock.
- **Path Params:** `symbol`
- **Query Params:** `exchange` (disambiguates if a symbol exists on both NSE/BSE)
- **Response Schema:** `{ id, symbol, exchange, isin, instrument_type, is_active, listed_at, company: {...} }`
- **Authentication Required:** No · **Permission Level:** Public
- **Possible Errors:** `404 NOT_FOUND`

#### `GET /stocks/{symbol}/price-history`
- **Purpose:** OHLCV candle data for charting (backed by the future `market_data.price_bars` table flagged in `DATABASE.md`).
- **Path Params:** `symbol`
- **Query Params:** `interval` (`1m`,`5m`,`15m`,`1h`,`1d` — required), `from`, `to` (ISO date, required), `after` (cursor, optional)
- **Response Schema:** `{ interval, bars: [{ timestamp, open, high, low, close, volume }], next_cursor }`
- **Authentication Required:** No · **Permission Level:** Public
- **Possible Errors:** `404 NOT_FOUND` (unknown symbol), `422 VALIDATION_ERROR` (invalid interval or date range)

#### `GET /stocks/{symbol}/company`
- **Purpose:** Company-level detail for the stock's issuing company.
- **Path Params:** `symbol`
- **Response Schema:** `{ id, legal_name, cin, founded_year, description, website_url, logo_url, sector, industry }`
- **Authentication Required:** No · **Permission Level:** Public
- **Possible Errors:** `404 NOT_FOUND`

#### `GET /sectors`
- **Purpose:** Lists all sectors, for taxonomy browsing/filtering UI.
- **Response Schema:** array of `{ id, name, description }`
- **Authentication Required:** No · **Permission Level:** Public

#### `GET /industries`
- **Purpose:** Lists industries, optionally scoped to a sector.
- **Query Params:** `sector_id`
- **Response Schema:** array of `{ id, name, sector_id }`
- **Authentication Required:** No · **Permission Level:** Public

---

### D. Search

#### `GET /search`
- **Purpose:** Unified fuzzy search across stocks and companies (uses `pg_trgm`, per `DATABASE.md § 3`) — powers the global search bar.
- **Query Params:** `q` (required, min 2 chars), `type` (`stock`,`company`,`all` — default `all`), `page`, `page_size`
- **Response Schema:** paginated array of `{ type, id, symbol?, name, exchange?, match_score }`
- **Authentication Required:** No · **Permission Level:** Public
- **Possible Errors:** `422 VALIDATION_ERROR` (`q` too short)

#### `GET /search/stocks`
- **Purpose:** Search scoped specifically to stocks by symbol or company name.
- **Query Params:** `q` (required), `exchange`, `page`, `page_size`
- **Response Schema:** paginated array of `{ id, symbol, exchange, company_name }`
- **Authentication Required:** No · **Permission Level:** Public

---

### E. Technical Analysis

#### `GET /stocks/{symbol}/indicators`
- **Purpose:** Latest (or historical) computed indicator values for a stock.
- **Path Params:** `symbol`
- **Query Params:** `indicator_type` (`RSI`,`MACD`,`SMA_50`,... comma-separated), `interval` (`1d`,`1h`,...), `from`, `to`, `after` (cursor)
- **Response Schema:** `{ indicators: [{ indicator_type, interval, value, computed_at }], next_cursor }`
- **Authentication Required:** No · **Permission Level:** Public
- **Possible Errors:** `404 NOT_FOUND`, `422 VALIDATION_ERROR`

#### `GET /stocks/{symbol}/signals`
- **Purpose:** Technical signals (buy/sell/hold/watch) generated for a stock.
- **Path Params:** `symbol`
- **Query Params:** `signal_type`, `from`, `to`, `page`, `page_size`
- **Response Schema:** paginated array of `{ id, signal_type, confidence, reason_code, triggered_at, expires_at, strategy_id }`
- **Authentication Required:** No · **Permission Level:** Public

#### `GET /screener/technical`
- **Purpose:** Screens the full stock universe by technical signal/indicator criteria — the core "find me stocks matching X" endpoint.
- **Query Params:** `signal_type`, `indicator_type`, `indicator_value_min`, `indicator_value_max`, `sector`, `exchange`, `sort_by` (`confidence`,`triggered_at`), `sort_order`, `page`, `page_size`
- **Response Schema:** paginated array of `{ stock: { symbol, exchange, company_name }, matching_signal: {...} }`
- **Authentication Required:** No (basic) · **Permission Level:** Public for limited result count; `Pro` for full unrestricted screener results (exact free-tier limit finalized at implementation)
- **Possible Errors:** `422 VALIDATION_ERROR`, `403 FORBIDDEN` (free tier exceeding allowed screener depth)

---

### F. Fundamental Analysis

#### `GET /stocks/{symbol}/financials`
- **Purpose:** Financial statement summaries for a company.
- **Path Params:** `symbol`
- **Query Params:** `statement_type` (`balance_sheet`,`profit_loss`,`cash_flow`), `fiscal_year`
- **Response Schema:** array of `{ id, statement_type, period_end, fiscal_year, source }` (raw_data omitted from list view, available via detail if needed in a later phase)
- **Authentication Required:** No · **Permission Level:** Public

#### `GET /stocks/{symbol}/quarterly-results`
- **Purpose:** Structured quarterly metrics (revenue, net profit, EPS, margin).
- **Path Params:** `symbol`
- **Query Params:** `fiscal_year`, `page`, `page_size`
- **Response Schema:** paginated array of `{ quarter, fiscal_year, revenue, net_profit, eps, operating_margin_pct }`
- **Authentication Required:** No · **Permission Level:** Public

#### `GET /stocks/{symbol}/annual-reports`
- **Purpose:** Annual report metadata and summaries.
- **Path Params:** `symbol`
- **Query Params:** `fiscal_year`
- **Response Schema:** array of `{ id, fiscal_year, document_url, summary, published_at }`
- **Authentication Required:** No · **Permission Level:** Public

---

### G. AI Recommendations

#### `GET /stocks/{symbol}/recommendations`
- **Purpose:** Current AI-synthesized recommendation for a stock.
- **Path Params:** `symbol`
- **Query Params:** `include_expired` (bool, default false)
- **Response Schema:** array of `{ recommendation_type, confidence, rationale_summary, valid_from, valid_until }`
- **Authentication Required:** No · **Permission Level:** Public
- **Note:** response always includes `confidence`; UI copy consuming this must not imply certainty (`PROJECT_CONTEXT.md § 20`).

#### `GET /recommendations`
- **Purpose:** Top current recommendations across the universe, for a "today's ideas" style view.
- **Query Params:** `recommendation_type`, `sector`, `min_confidence`, `sort_by` (`confidence`,`valid_from`), `page`, `page_size`
- **Response Schema:** paginated array of `{ stock: {...}, recommendation_type, confidence, rationale_summary }`
- **Authentication Required:** Yes · **Permission Level:** Authenticated (full list); `Pro` for `min_confidence`/advanced filtering
- **Possible Errors:** `403 FORBIDDEN` (advanced filters on free tier)

---

### H. AI Predictions

#### `GET /stocks/{symbol}/predictions`
- **Purpose:** Raw model forecasts for a stock.
- **Path Params:** `symbol`
- **Query Params:** `prediction_type`, `horizon_days`, `model_id`, `page`, `page_size`
- **Response Schema:** paginated array of `{ prediction_type, horizon_days, predicted_value, probability, predicted_at, target_date, model: { name, version } }`
- **Authentication Required:** Yes · **Permission Level:** Authenticated

#### `GET /stocks/{symbol}/scores`
- **Purpose:** Composite AI scores for a stock.
- **Path Params:** `symbol`
- **Query Params:** `score_type`
- **Response Schema:** array of `{ score_type, score_value, components, computed_at }`
- **Authentication Required:** No · **Permission Level:** Public

#### `GET /stocks/{symbol}/ai-explanation`
- **Purpose:** Latest LLM-generated plain-English explanation of a prediction or signal.
- **Path Params:** `symbol`
- **Query Params:** `ai_prediction_id`, `technical_signal_id` (at least one recommended; omitted returns the most recent explanation of any kind)
- **Response Schema:** `{ explanation_text, llm_model_used, generated_at }`
- **Authentication Required:** Yes · **Permission Level:** Authenticated
- **Possible Errors:** `404 NOT_FOUND` (no explanation generated yet for the given reference)

---

### I. News

#### `GET /news`
- **Purpose:** Lists ingested news articles.
- **Query Params:** `company_id`, `sector`, `sentiment_label`, `published_at_from`, `published_at_to`, `sort_by` (`published_at`), `page`, `page_size`
- **Response Schema:** paginated array of `{ id, headline, source, source_url, published_at, content_summary, sentiment: { label, score } }`
- **Authentication Required:** No · **Permission Level:** Public

#### `GET /news/{id}`
- **Purpose:** Single news item detail.
- **Path Params:** `id`
- **Response Schema:** `{ id, headline, source, source_url, published_at, content_summary, company, sentiment }`
- **Authentication Required:** No · **Permission Level:** Public
- **Possible Errors:** `404 NOT_FOUND`

#### `GET /stocks/{symbol}/news`
- **Purpose:** News scoped to a specific stock's company.
- **Path Params:** `symbol`
- **Query Params:** `page`, `page_size`
- **Response Schema:** same shape as `GET /news`
- **Authentication Required:** No · **Permission Level:** Public
- **Possible Errors:** `404 NOT_FOUND` (unknown symbol)

---

### J. Geopolitics

#### `GET /geopolitical-events`
- **Purpose:** Lists macro/geopolitical events.
- **Query Params:** `category`, `severity`, `event_date_from`, `event_date_to`, `company_id`, `page`, `page_size`
- **Response Schema:** paginated array of `{ id, title, description, category, severity, event_date, source_url }`
- **Authentication Required:** No · **Permission Level:** Public

#### `GET /geopolitical-events/{id}`
- **Purpose:** Single event detail.
- **Path Params:** `id`
- **Response Schema:** `{ id, title, description, category, severity, event_date, source_url, company }`
- **Authentication Required:** No · **Permission Level:** Public
- **Possible Errors:** `404 NOT_FOUND`

---

### K. Watchlists

#### `GET /watchlists`
- **Purpose:** Lists the authenticated user's watchlists.
- **Response Schema:** array of `{ id, name, is_default, item_count, created_at }`
- **Authentication Required:** Yes · **Permission Level:** Owner

#### `POST /watchlists`
- **Purpose:** Creates a watchlist.
- **Request Body:** `{ name, is_default? }`
- **Response Schema:** created watchlist object
- **Authentication Required:** Yes · **Permission Level:** Owner
- **Possible Errors:** `409 CONFLICT` (duplicate name for this user), `422 VALIDATION_ERROR`

#### `GET /watchlists/{id}`
- **Purpose:** Watchlist detail including items.
- **Path Params:** `id`
- **Response Schema:** `{ id, name, is_default, items: [{ id, stock: {...}, notes, added_at }] }`
- **Authentication Required:** Yes · **Permission Level:** Owner
- **Possible Errors:** `404 NOT_FOUND` (not found or not owned by requester)

#### `PATCH /watchlists/{id}`
- **Purpose:** Renames/updates a watchlist.
- **Path Params:** `id` · **Request Body:** `{ name?, is_default? }`
- **Response Schema:** updated watchlist object
- **Authentication Required:** Yes · **Permission Level:** Owner
- **Possible Errors:** `404 NOT_FOUND`, `409 CONFLICT`

#### `DELETE /watchlists/{id}`
- **Purpose:** Deletes a watchlist (cascades to its items).
- **Path Params:** `id`
- **Response Schema:** `{ deleted: true }`
- **Authentication Required:** Yes · **Permission Level:** Owner
- **Possible Errors:** `404 NOT_FOUND`

#### `POST /watchlists/{id}/items`
- **Purpose:** Adds a stock to a watchlist.
- **Path Params:** `id` · **Request Body:** `{ stock_id, notes? }`
- **Response Schema:** created watchlist item
- **Authentication Required:** Yes · **Permission Level:** Owner
- **Possible Errors:** `404 NOT_FOUND` (watchlist or stock), `409 CONFLICT` (already on the list)

#### `DELETE /watchlists/{id}/items/{item_id}`
- **Purpose:** Removes a stock from a watchlist.
- **Path Params:** `id`, `item_id`
- **Response Schema:** `{ deleted: true }`
- **Authentication Required:** Yes · **Permission Level:** Owner
- **Possible Errors:** `404 NOT_FOUND`

---

### L. Portfolio

#### `GET /portfolios`
- **Purpose:** Lists the authenticated user's portfolios.
- **Response Schema:** array of `{ id, name, is_synced_from_broker, last_synced_at }`
- **Authentication Required:** Yes · **Permission Level:** Owner

#### `POST /portfolios`
- **Purpose:** Creates a manual (non-broker-synced) portfolio.
- **Request Body:** `{ name }`
- **Response Schema:** created portfolio object
- **Authentication Required:** Yes · **Permission Level:** Owner
- **Possible Errors:** `422 VALIDATION_ERROR`

#### `GET /portfolios/{id}`
- **Purpose:** Portfolio detail with summary metrics.
- **Path Params:** `id`
- **Response Schema:** `{ id, name, is_synced_from_broker, last_synced_at, holdings_count, total_value_estimate }`
- **Authentication Required:** Yes · **Permission Level:** Owner
- **Possible Errors:** `404 NOT_FOUND`

#### `GET /portfolios/{id}/holdings`
- **Purpose:** Lists holdings within a portfolio.
- **Path Params:** `id` · **Query Params:** `page`, `page_size`
- **Response Schema:** paginated array of `{ id, stock: {...}, quantity, average_buy_price, source, last_synced_at }`
- **Authentication Required:** Yes · **Permission Level:** Owner
- **Possible Errors:** `404 NOT_FOUND`

#### `POST /portfolios/{id}/holdings`
- **Purpose:** Manually adds a holding to a non-broker-synced portfolio.
- **Path Params:** `id` · **Request Body:** `{ stock_id, quantity, average_buy_price }`
- **Response Schema:** created holding object
- **Authentication Required:** Yes · **Permission Level:** Owner
- **Possible Errors:** `404 NOT_FOUND`, `409 CONFLICT` (holding for this stock already exists — use `PATCH` instead), `422 VALIDATION_ERROR`

#### `PATCH /portfolios/{id}/holdings/{holding_id}`
- **Purpose:** Updates a manually-tracked holding.
- **Path Params:** `id`, `holding_id` · **Request Body:** `{ quantity?, average_buy_price? }`
- **Response Schema:** updated holding object
- **Authentication Required:** Yes · **Permission Level:** Owner
- **Possible Errors:** `404 NOT_FOUND`, `403 FORBIDDEN` (attempting to edit a broker-synced holding directly)

#### `DELETE /portfolios/{id}/holdings/{holding_id}`
- **Purpose:** Removes a manually-tracked holding.
- **Path Params:** `id`, `holding_id`
- **Response Schema:** `{ deleted: true }`
- **Authentication Required:** Yes · **Permission Level:** Owner
- **Possible Errors:** `404 NOT_FOUND`, `403 FORBIDDEN` (broker-synced holdings are removed via broker sync, not directly)

#### `GET /portfolios/{id}/orders`
- **Purpose:** Order history for a portfolio (synced or in-app).
- **Path Params:** `id` · **Query Params:** `status`, `from`, `to`, `page`, `page_size`
- **Response Schema:** paginated array of `{ id, order_type, order_mode, quantity, price, status, broker_order_id, placed_via, created_at }`
- **Authentication Required:** Yes · **Permission Level:** Owner
- **Possible Errors:** `404 NOT_FOUND`

#### `POST /portfolios/{id}/orders`
- **Purpose:** Places an order via the linked broker. **Phase 6, gated feature** — disabled until `broker.kite_integrations.write_access_enabled` is true for the user, which itself requires a separate explicit confirmation flow.
- **Path Params:** `id` · **Request Body:** `{ stock_id, order_type, order_mode, quantity, price? }`
- **Response Schema:** created order object with `status: "pending"`
- **Authentication Required:** Yes · **Permission Level:** Pro + broker write access explicitly enabled
- **Possible Errors:** `403 FORBIDDEN` (write access not enabled), `422 VALIDATION_ERROR`, `503 SERVICE_UNAVAILABLE` (Kite API down)
- **Note:** every call to this endpoint is written to `core.audit_logs`, per `DATABASE.md § 12`, regardless of outcome.

---

### M. Kite Integration

#### `GET /broker/kite/connect`
- **Purpose:** Returns the Kite Connect OAuth authorization URL to redirect the user to.
- **Response Schema:** `{ authorization_url }`
- **Authentication Required:** Yes · **Permission Level:** Authenticated

#### `GET /broker/kite/callback`
- **Purpose:** OAuth callback endpoint Kite redirects to after user approval; exchanges the request token for an access token and creates/updates `broker.kite_integrations`.
- **Query Params:** `request_token`, `status` (from Kite's redirect)
- **Response Schema:** `{ connected: true, kite_user_id }`
- **Authentication Required:** Yes (session must still be valid at callback time) · **Permission Level:** Authenticated
- **Possible Errors:** `400 BAD_REQUEST` (invalid/expired request token), `503 SERVICE_UNAVAILABLE`

#### `GET /broker/kite/status`
- **Purpose:** Returns the authenticated user's broker connection status — never the token itself (Section 8).
- **Response Schema:** `{ connected, kite_user_id, scopes, write_access_enabled, token_expires_at, last_synced_at }`
- **Authentication Required:** Yes · **Permission Level:** Owner

#### `POST /broker/kite/sync`
- **Purpose:** Triggers an on-demand sync of holdings/positions/orders from Kite into the user's portfolio.
- **Response Schema:** `{ synced_at, holdings_updated, orders_updated }`
- **Authentication Required:** Yes · **Permission Level:** Owner
- **Possible Errors:** `404 NOT_FOUND` (no broker connection), `503 SERVICE_UNAVAILABLE`

#### `POST /broker/kite/write-access`
- **Purpose:** Enables order-placement (write) capability after explicit user confirmation — the Phase 6 gate described in `DATABASE.md`.
- **Request Body:** `{ confirmed: true, acknowledgement_text_version }` (exact confirmation UX/legal copy finalized at Phase 6 design)
- **Response Schema:** `{ write_access_enabled: true }`
- **Authentication Required:** Yes · **Permission Level:** Pro
- **Possible Errors:** `422 VALIDATION_ERROR` (`confirmed` not true), `403 FORBIDDEN` (role doesn't qualify)

#### `DELETE /broker/kite/disconnect`
- **Purpose:** Revokes and deletes the stored Kite integration for the user.
- **Response Schema:** `{ disconnected: true }`
- **Authentication Required:** Yes · **Permission Level:** Owner

---

### N. Alerts

#### `GET /alerts`
- **Purpose:** Lists the authenticated user's alert rules.
- **Query Params:** `is_active`, `stock_id`, `page`, `page_size`
- **Response Schema:** paginated array of `{ id, stock, alert_type, threshold_value, signal_type_filter, is_active, triggered_at }`
- **Authentication Required:** Yes · **Permission Level:** Owner

#### `POST /alerts`
- **Purpose:** Creates an alert rule.
- **Request Body:** `{ stock_id, alert_type, threshold_value?, signal_type_filter? }`
- **Response Schema:** created alert object
- **Authentication Required:** Yes · **Permission Level:** Owner
- **Possible Errors:** `422 VALIDATION_ERROR` (e.g. `threshold_value` missing for a price alert)

#### `GET /alerts/{id}`
- **Purpose:** Alert detail.
- **Path Params:** `id`
- **Response Schema:** full alert object
- **Authentication Required:** Yes · **Permission Level:** Owner
- **Possible Errors:** `404 NOT_FOUND`

#### `PATCH /alerts/{id}`
- **Purpose:** Updates an alert rule (e.g. toggling `is_active`).
- **Path Params:** `id` · **Request Body:** any subset of alert fields
- **Response Schema:** updated alert object
- **Authentication Required:** Yes · **Permission Level:** Owner
- **Possible Errors:** `404 NOT_FOUND`, `422 VALIDATION_ERROR`

#### `DELETE /alerts/{id}`
- **Purpose:** Deletes an alert rule.
- **Path Params:** `id`
- **Response Schema:** `{ deleted: true }`
- **Authentication Required:** Yes · **Permission Level:** Owner
- **Possible Errors:** `404 NOT_FOUND`

#### `GET /notifications`
- **Purpose:** Lists notification history for the authenticated user.
- **Query Params:** `channel`, `status`, `page`, `page_size`
- **Response Schema:** paginated array of `{ id, alert_id, channel, message, status, sent_at }`
- **Authentication Required:** Yes · **Permission Level:** Owner

---

### O. AI Chat

#### `POST /ai-assistant/chat`
- **Purpose:** Sends a natural-language message to the AI research assistant and returns its response, optionally scoped to a stock/context.
- **Request Body:** `{ message, stock_symbol?, conversation_id? }`
- **Response Schema:** `{ conversation_id, response_text, referenced_sources: [{ type, id, title }], llm_model_used, generated_at }`
- **Authentication Required:** Yes · **Permission Level:** Authenticated (basic query volume); `Pro` for extended context/higher-frequency use
- **Possible Errors:** `403 FORBIDDEN` (free-tier limit exceeded), `429 RATE_LIMITED` (cost-aware secondary limit, Section 7), `503 SERVICE_UNAVAILABLE` (OpenAI/HuggingFace down)
- **Note:** `conversation_id` and any persisted chat history table are a Phase 3 implementation detail not yet specified in `DATABASE.md` — flagged here to be formally added when Phase 3 database design happens, following `PROJECT_CONTEXT.md`'s "extend, never redesign around it" rule.

#### `GET /stocks/{symbol}/ai-explanation` — see Section H (AI Predictions); intentionally not duplicated here since it's explanation retrieval, not chat.

---

### P. Backtesting

#### `GET /strategies/{id}/backtests`
- **Purpose:** Lists backtest runs for a strategy.
- **Path Params:** `id` · **Query Params:** `page`, `page_size`
- **Response Schema:** paginated array of `{ id, start_date, end_date, total_return_pct, win_rate_pct, max_drawdown_pct, sharpe_ratio, run_at }`
- **Authentication Required:** Yes · **Permission Level:** Pro
- **Possible Errors:** `404 NOT_FOUND`

#### `POST /strategies/{id}/backtests`
- **Purpose:** Triggers a new backtest run for a strategy (queued async job — worker per `DATABASE.md § 6` data flow).
- **Path Params:** `id` · **Request Body:** `{ start_date, end_date, universe }`
- **Response Schema:** `{ id, status: "queued" }`
- **Authentication Required:** Yes · **Permission Level:** Pro
- **Possible Errors:** `404 NOT_FOUND`, `422 VALIDATION_ERROR` (`end_date` before `start_date`), `429 RATE_LIMITED` (compute-cost-aware limit)

#### `GET /backtests/{id}`
- **Purpose:** Full backtest result including detailed trade-by-trade output.
- **Path Params:** `id`
- **Response Schema:** `{ id, strategy_id, start_date, end_date, universe, total_return_pct, win_rate_pct, max_drawdown_pct, sharpe_ratio, full_results, run_at, status }`
- **Authentication Required:** Yes · **Permission Level:** Pro
- **Possible Errors:** `404 NOT_FOUND`

---

### Q. Strategies

#### `GET /strategies`
- **Purpose:** Lists available strategies.
- **Query Params:** `is_active`, `page`, `page_size`
- **Response Schema:** paginated array of `{ id, name, description, version, is_active }`
- **Authentication Required:** No · **Permission Level:** Public (view); creation/editing gated below

#### `POST /strategies`
- **Purpose:** Creates a new strategy definition. User-authored strategies are a future-phase capability (`created_by_user_id` reserved per `DATABASE.md`); until then this is an admin/system-curated endpoint.
- **Request Body:** `{ name, description?, rules }`
- **Response Schema:** created strategy object
- **Authentication Required:** Yes · **Permission Level:** Admin (Phase ≤7); reassessed to `Pro` if/when user-authored strategies ship
- **Possible Errors:** `409 CONFLICT` (name+version already exists), `422 VALIDATION_ERROR` (invalid `rules` shape)

#### `GET /strategies/{id}`
- **Purpose:** Strategy detail.
- **Path Params:** `id`
- **Response Schema:** full strategy object including `rules`
- **Authentication Required:** No · **Permission Level:** Public
- **Possible Errors:** `404 NOT_FOUND`

#### `PATCH /strategies/{id}`
- **Purpose:** Updates a strategy (typically creates a new version rather than mutating a live one — exact versioning behavior finalized at implementation).
- **Path Params:** `id` · **Request Body:** `{ description?, rules?, is_active? }`
- **Response Schema:** updated strategy object
- **Authentication Required:** Yes · **Permission Level:** Admin
- **Possible Errors:** `404 NOT_FOUND`, `422 VALIDATION_ERROR`

#### `DELETE /strategies/{id}`
- **Purpose:** Deactivates a strategy (soft delete — `is_active = false`; historical signals/backtests referencing it are preserved).
- **Path Params:** `id`
- **Response Schema:** `{ deactivated: true }`
- **Authentication Required:** Yes · **Permission Level:** Admin
- **Possible Errors:** `404 NOT_FOUND`

---

### R. Admin

All endpoints in this group require `Permission Level: Admin` and are logged to `core.audit_logs` on every call, not just writes.

#### `GET /admin/users`
- **Purpose:** Lists platform users for administration.
- **Query Params:** `role`, `status`, `q` (search by email), `page`, `page_size`
- **Response Schema:** paginated array of `{ id, email, role, status, created_at }`
- **Authentication Required:** Yes

#### `PATCH /admin/users/{id}/role`
- **Purpose:** Changes a user's role.
- **Path Params:** `id` · **Request Body:** `{ role_id }`
- **Response Schema:** updated user object
- **Authentication Required:** Yes
- **Possible Errors:** `404 NOT_FOUND`, `422 VALIDATION_ERROR` (unknown `role_id`)

#### `GET /admin/system-settings`
- **Purpose:** Lists all system settings.
- **Response Schema:** array of `{ id, key, value, description, updated_at }`
- **Authentication Required:** Yes

#### `PATCH /admin/system-settings/{key}`
- **Purpose:** Updates a system setting's value.
- **Path Params:** `key` · **Request Body:** `{ value }`
- **Response Schema:** updated setting object
- **Authentication Required:** Yes
- **Possible Errors:** `404 NOT_FOUND`, `422 VALIDATION_ERROR`

#### `GET /admin/audit-logs`
- **Purpose:** Queries the audit log.
- **Query Params:** `user_id`, `action`, `entity_type`, `occurred_at_from`, `occurred_at_to`, `page`, `page_size`
- **Response Schema:** paginated array of `{ id, user_id, action, entity_type, entity_id, metadata, ip_address, occurred_at }`
- **Authentication Required:** Yes

#### `GET /admin/api-logs`
- **Purpose:** Queries API request logs for observability/debugging.
- **Query Params:** `user_id`, `status_code`, `path`, `requested_at_from`, `requested_at_to`, `page`, `page_size`
- **Response Schema:** paginated array of `{ id, method, path, status_code, response_time_ms, correlation_id, requested_at }`
- **Authentication Required:** Yes

#### `GET /admin/models`
- **Purpose:** Lists registered ML models.
- **Query Params:** `is_active`, `model_type`
- **Response Schema:** array of `{ id, name, model_type, version, is_active, trained_at }`
- **Authentication Required:** Yes

#### `POST /admin/models`
- **Purpose:** Registers a newly trained model version.
- **Request Body:** `{ name, model_type, version, artifact_url, training_dataset_ref, hyperparameters }`
- **Response Schema:** created model object
- **Authentication Required:** Yes
- **Possible Errors:** `409 CONFLICT` (name+version exists), `422 VALIDATION_ERROR`

#### `PATCH /admin/models/{id}/activate`
- **Purpose:** Marks a model version as the active one serving predictions for its name (and implicitly deactivates the previously active version of the same model name).
- **Path Params:** `id`
- **Response Schema:** `{ id, is_active: true }`
- **Authentication Required:** Yes
- **Possible Errors:** `404 NOT_FOUND`

---

## 15. Summary Table

| Group | Endpoint Count | Primary Permission Levels |
|---|---|---|
| Authentication | 3 | Public/Authenticated |
| Users | 4 | Owner |
| Stocks | 6 | Public |
| Search | 2 | Public |
| Technical Analysis | 3 | Public/Pro |
| Fundamental Analysis | 3 | Public |
| AI Recommendations | 2 | Public/Authenticated/Pro |
| AI Predictions | 3 | Authenticated |
| News | 3 | Public |
| Geopolitics | 2 | Public |
| Watchlists | 7 | Owner |
| Portfolio | 8 | Owner/Pro |
| Kite Integration | 6 | Owner/Pro |
| Alerts | 6 | Owner |
| AI Chat | 1 | Authenticated/Pro |
| Backtesting | 3 | Pro |
| Strategies | 5 | Public/Admin |
| Admin | 8 | Admin |

---

*This document must stay in sync with the actual API. Any new endpoint, changed field, or changed permission level gets reflected here before (or in the same PR as) the code that introduces it — implementation follows spec, spec is never reverse-documented from whatever the code happened to do.*
