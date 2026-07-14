# DATABASE.md — AlphaEdge AI

This document is the complete database architecture for AlphaEdge AI. It extends [`PROJECT_CONTEXT.md`](./PROJECT_CONTEXT.md) (see § 10, Database Strategy) with full table-level detail and is authoritative for all schema work across every phase. No SQL is included here by design — this is the design specification that migrations (Alembic, per `PROJECT_CONTEXT.md § 10`) will be written against in later phases.

If a future table, column, or strategy isn't in this document, it doesn't exist yet — add it here first, then implement it.

---

## 1. Database Philosophy

AlphaEdge AI's data layer follows five principles, in priority order:

1. **One database, many boundaries.** A single PostgreSQL instance is used, but every backend module (`users`, `market_data`, `quant_engine`, `ai_assistant`, `broker`, `alerts`) owns its own schema. Modules never read or write another module's tables directly — access goes through that module's `application` layer. This gives the operational simplicity of a monolith today with the option to physically split any schema into its own database later without redesigning anything.
2. **Correctness before cleverness.** Financial data must be trustworthy. Normalize by default; only denormalize (e.g. for a hot read path) when a specific, measured performance need justifies it, and document the tradeoff when it happens.
3. **Append where truth is historical.** Prices, indicators, signals, predictions, and logs describe what was true *at a point in time* — these tables are insert-heavy and effectively immutable. Mutable "current state" (a user's profile, a portfolio's current holdings) is modeled separately from the historical record that produced it.
4. **Every table is auditable.** `created_at` (and `updated_at` where the row is mutable) exists on every table without exception. Nothing is silently overwritten without a trace.
5. **Design for the whole project now, build incrementally.** This document specifies tables for every planned phase (Phase 1 through Phase 7) so later phases never require restructuring earlier tables — only adding to them. Tables belonging to later phases are still created early if another table depends on them via foreign key; they simply stay unused until their phase arrives.

## 2. Why PostgreSQL Was Selected

- **Relational integrity where it matters most.** Financial relationships (a stock belongs to a company, a company belongs to a sector, an order belongs to a user's portfolio) are inherently relational. Foreign keys and transactional integrity prevent the kind of silent data corruption that a NoSQL store would allow.
- **`pgvector` gives us embeddings without a second database.** The AI research assistant (Phase 3) needs vector similarity search over news/filings. Postgres with `pgvector` avoids operating a separate vector database at AlphaEdge AI's current scale.
- **JSONB for the genuinely variable parts.** Some data (raw broker API payloads, AI model metadata, flexible system settings) doesn't benefit from rigid columns. Postgres's `JSONB` gives schema flexibility exactly where it's needed, without abandoning relational structure everywhere else.
- **Mature partitioning and indexing.** Time-series-heavy tables (technical indicators, API logs, news) benefit from native table partitioning and a rich index ecosystem (B-tree, GIN, BRIN) — all available in Postgres without extra infrastructure.
- **One engine, one operational surface.** A single, extremely well-understood database technology reduces operational risk for a project that will scale in scope faster than it scales its team.
- **Ecosystem fit.** First-class support in both FastAPI (via SQLAlchemy/Alembic) and every deployment target under consideration (Railway, and any future managed Postgres provider).

## 3. Database Architecture

- **One PostgreSQL instance**, one database (`alphaedge`), **schema-per-module**:
  - `users` — identity-adjacent app data, watchlists, sessions
  - `market_data` — instruments, companies, financials, news, sector/industry taxonomy
  - `quant_engine` — indicators, signals, models, predictions, backtests, recommendations
  - `ai_assistant` — AI-generated explanations and RAG-supporting structures
  - `broker` — portfolios, holdings, orders, Kite Connect integration state
  - `alerts` — alert rules and notification history
  - `core` — cross-cutting platform concerns not owned by a single domain module: API logs, audit logs, system settings
- **Redis** sits alongside Postgres (not shown in the ER diagram — it's cache/queue, not source-of-truth storage) for hot-path reads (live prices) and async job queuing.
- **Extensions used:** `pgvector` (embeddings), `pg_trgm` (fuzzy text search on company/stock names, future phase), `uuid-ossp` or `pgcrypto` (UUID generation).
- **Primary key strategy:** UUID (v4) for all user-facing and cross-module-referenced entities, to avoid leaking sequential IDs and to make IDs safely generatable client-side or across services if a module is later split out. Purely internal, high-volume, module-local tables (e.g. `api_logs`) may use `BIGSERIAL` where UUID overhead isn't justified — called out per table below.
- **Timestamps:** `TIMESTAMPTZ` everywhere, stored in UTC, converted at the presentation layer.
- **Money/price precision:** `NUMERIC(18,4)` for prices and monetary values — never floating point — to avoid rounding errors in financial calculations.

## 4. ER Diagram (Text Format)

```
[roles] 1───* [users] 1───1 [user_profiles]
                 │
                 ├──1───* [user_sessions]
                 ├──1───* [watchlists] 1───* [watchlist_items] *───1 [stocks]
                 ├──1───* [portfolios] 1───* [holdings] *───1 [stocks]
                 ├──1───* [orders] *───1 [stocks]
                 ├──1───1 [kite_integrations]
                 ├──1───* [alerts] *───1 [stocks]
                 ├──1───* [notification_history] *───1 [alerts]
                 └──1───* [audit_logs]

[sectors] 1───* [industries] 1───* [companies] 1───* [stocks]

[companies] 1───* [financial_statements] 1───* [quarterly_results]
[companies] 1───* [annual_reports]
[companies] 1───* [news] *───1 [news_sentiment]
[companies] 1───* [geopolitical_events]   (nullable company_id — events can be non-company-specific)

[stocks] 1───* [technical_indicators]
[stocks] 1───* [technical_signals] *───1 [strategies]
[stocks] 1───* [ai_predictions] *───1 [models]
[stocks] 1───* [ai_scores]
[stocks] 1───* [ai_explanations] *───1 [ai_predictions] (nullable — can explain a signal instead)
[stocks] 1───* [recommendations] *───1 [ai_predictions] (nullable)

[strategies] 1───* [backtesting]
[models] 1───* [model_performance]

[users] 1───* [api_logs]   (nullable user_id — system-originated calls have none)
[system_settings]   (standalone key-value config, no relations)
```

Notes on reading this diagram: `1───*` denotes one-to-many, `1───1` one-to-one. All foreign keys are enforced at the database level even across schemas (Postgres supports cross-schema FKs within one database) — the "modules don't read each other's tables directly" rule in Section 1 is an *application-layer* discipline, not a database limitation; the FK still protects referential integrity at the storage layer.

---

## 5. Table Specifications

Each table below is listed as `schema.table_name`.

### `users.roles`

- **Purpose:** Defines the set of permission levels in the platform (e.g. `free`, `pro`, `admin`). Referenced by `users` rather than hardcoding role strings, so new tiers can be added without a code change.
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** none
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | name | VARCHAR(50) | e.g. `free`, `pro`, `admin` |
  | description | TEXT | nullable |
  | permissions | JSONB | flexible permission flags, e.g. broker write access, AI assistant access |
  | created_at | TIMESTAMPTZ | |
- **Indexes:** unique index on `name`.
- **Constraints:** `name` NOT NULL, UNIQUE.

### `users.users`

- **Purpose:** App-specific record for each authenticated user. Clerk is the identity provider and owns credentials/session mechanics; this table is the internal anchor every other module's `user_id` foreign key points to.
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** `role_id` → `users.roles.id`
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | clerk_user_id | VARCHAR(255) | external identity reference from Clerk |
  | email | VARCHAR(255) | mirrored from Clerk for query convenience |
  | role_id | UUID | FK → roles.id |
  | status | VARCHAR(20) | `active`, `suspended`, `deleted` |
  | created_at | TIMESTAMPTZ | |
  | updated_at | TIMESTAMPTZ | |
- **Indexes:** unique index on `clerk_user_id`; index on `email`.
- **Constraints:** `clerk_user_id` NOT NULL, UNIQUE. `status` CHECK IN (`active`,`suspended`,`deleted`).

### `users.user_profiles`

- **Purpose:** Extended, mutable profile information separate from the core identity row — kept apart so profile edits don't touch the security-sensitive `users` table.
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** `user_id` → `users.users.id` (one-to-one)
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | user_id | UUID | FK, UNIQUE (enforces 1:1) |
  | display_name | VARCHAR(100) | nullable |
  | avatar_url | TEXT | nullable |
  | risk_profile | VARCHAR(20) | `conservative`, `moderate`, `aggressive` — self-declared, used to tune AI assistant tone/recommendations |
  | preferred_theme | VARCHAR(10) | `light`, `dark` |
  | timezone | VARCHAR(50) | default `Asia/Kolkata` |
  | created_at | TIMESTAMPTZ | |
  | updated_at | TIMESTAMPTZ | |
- **Indexes:** unique index on `user_id`.
- **Constraints:** `user_id` UNIQUE, NOT NULL, ON DELETE CASCADE.

### `users.watchlists`

- **Purpose:** Named collections of stocks a user tracks.
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** `user_id` → `users.users.id`
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | user_id | UUID | FK |
  | name | VARCHAR(100) | e.g. "Core Holdings", "Defence Sector" |
  | is_default | BOOLEAN | default false |
  | created_at | TIMESTAMPTZ | |
  | updated_at | TIMESTAMPTZ | |
- **Indexes:** index on `user_id`.
- **Constraints:** `name` NOT NULL. Unique composite (`user_id`, `name`) — no duplicate watchlist names per user.

### `users.watchlist_items`

- **Purpose:** Individual stocks within a watchlist.
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** `watchlist_id` → `users.watchlists.id`; `stock_id` → `market_data.stocks.id`
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | watchlist_id | UUID | FK |
  | stock_id | UUID | FK |
  | added_at | TIMESTAMPTZ | |
  | notes | TEXT | nullable, user's own note on why it's on the list |
- **Indexes:** composite index on (`watchlist_id`, `stock_id`); index on `stock_id`.
- **Constraints:** Unique composite (`watchlist_id`, `stock_id`) — a stock appears once per watchlist. ON DELETE CASCADE from `watchlist_id`.

### `users.user_sessions`

- **Purpose:** Lightweight record of app-level session activity (device/IP/login metadata) for security review and audit — distinct from Clerk's own session store, which remains authoritative for auth itself.
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** `user_id` → `users.users.id`
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | user_id | UUID | FK |
  | clerk_session_id | VARCHAR(255) | reference to Clerk's session |
  | ip_address | INET | |
  | user_agent | TEXT | |
  | started_at | TIMESTAMPTZ | |
  | ended_at | TIMESTAMPTZ | nullable |
- **Indexes:** index on `user_id`; index on `started_at` (for recent-activity queries).
- **Constraints:** none beyond FK.

### `market_data.sectors`

- **Purpose:** Top-level market taxonomy (e.g. Energy, IT, Defence).
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** none
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | name | VARCHAR(100) | |
  | description | TEXT | nullable |
  | created_at | TIMESTAMPTZ | |
- **Indexes:** unique index on `name`.
- **Constraints:** `name` NOT NULL, UNIQUE.

### `market_data.industries`

- **Purpose:** Sub-classification within a sector (e.g. "Renewable Energy" under "Energy").
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** `sector_id` → `market_data.sectors.id`
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | sector_id | UUID | FK |
  | name | VARCHAR(100) | |
  | created_at | TIMESTAMPTZ | |
- **Indexes:** index on `sector_id`; unique composite (`sector_id`, `name`).
- **Constraints:** `name` NOT NULL.

### `market_data.companies`

- **Purpose:** A listed company (one company can, rarely, issue multiple instruments — kept separate from `stocks` for that reason).
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** `industry_id` → `market_data.industries.id`
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | industry_id | UUID | FK, nullable until classified |
  | legal_name | VARCHAR(255) | |
  | cin | VARCHAR(30) | Corporate Identification Number, nullable |
  | founded_year | SMALLINT | nullable |
  | description | TEXT | nullable |
  | website_url | TEXT | nullable |
  | logo_url | TEXT | nullable |
  | created_at | TIMESTAMPTZ | |
  | updated_at | TIMESTAMPTZ | |
- **Indexes:** index on `industry_id`; trigram index (`pg_trgm`) on `legal_name` for fuzzy search (future phase).
- **Constraints:** `legal_name` NOT NULL. `cin` UNIQUE where not null.

### `market_data.stocks`

- **Purpose:** A tradeable instrument (symbol) — the core entity nearly every other module references.
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** `company_id` → `market_data.companies.id`
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | company_id | UUID | FK |
  | symbol | VARCHAR(20) | e.g. `RELIANCE` |
  | exchange | VARCHAR(10) | `NSE`, `BSE` |
  | isin | VARCHAR(12) | nullable |
  | instrument_type | VARCHAR(20) | `equity`, `etf`, `index` (future-proofing) |
  | is_active | BOOLEAN | default true — false if delisted |
  | listed_at | DATE | nullable |
  | created_at | TIMESTAMPTZ | |
  | updated_at | TIMESTAMPTZ | |
- **Indexes:** unique composite (`symbol`, `exchange`); index on `company_id`; index on `is_active` (partial index for active stocks — heavily queried subset).
- **Constraints:** `symbol` + `exchange` UNIQUE. `exchange` CHECK IN (`NSE`,`BSE`).

> **Note on OHLCV price data:** raw historical/live candle data (open/high/low/close/volume per interval) is intentionally **not** listed as one of the 35 requested tables and is treated as a high-volume, append-only time-series concern. It will live in a dedicated `market_data.price_bars` table (partitioned by month, per Section 8) designed in detail during Phase 1 implementation — flagged here so its absence from this table list isn't mistaken for an oversight.

### `market_data.financial_statements`

- **Purpose:** Parent record for a company's periodic financial statement (balance sheet / P&L / cash flow), one row per filing period, with line items normalized into related tables (`quarterly_results` for the P&L view used most in-app; full balance-sheet/cash-flow line items follow the same pattern in a later phase).
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** `company_id` → `market_data.companies.id`
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | company_id | UUID | FK |
  | statement_type | VARCHAR(20) | `balance_sheet`, `profit_loss`, `cash_flow` |
  | period_end | DATE | |
  | fiscal_year | SMALLINT | |
  | source | VARCHAR(50) | e.g. `NSE filing`, `manual entry` |
  | raw_data | JSONB | full parsed statement, structured fields extracted into typed tables as needed |
  | created_at | TIMESTAMPTZ | |
- **Indexes:** composite index (`company_id`, `period_end`); index on `statement_type`.
- **Constraints:** unique composite (`company_id`, `statement_type`, `period_end`).

### `market_data.quarterly_results`

- **Purpose:** Structured, queryable quarterly financial metrics (revenue, net profit, EPS, etc.) — the fast-access counterpart to the raw JSONB in `financial_statements`.
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** `company_id` → `market_data.companies.id`; `financial_statement_id` → `market_data.financial_statements.id` (nullable)
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | company_id | UUID | FK |
  | financial_statement_id | UUID | FK, nullable |
  | quarter | SMALLINT | 1–4 |
  | fiscal_year | SMALLINT | |
  | revenue | NUMERIC(18,2) | nullable |
  | net_profit | NUMERIC(18,2) | nullable |
  | eps | NUMERIC(10,4) | nullable |
  | operating_margin_pct | NUMERIC(6,3) | nullable |
  | created_at | TIMESTAMPTZ | |
- **Indexes:** composite index (`company_id`, `fiscal_year`, `quarter`).
- **Constraints:** unique composite (`company_id`, `fiscal_year`, `quarter`). `quarter` CHECK BETWEEN 1 AND 4.

### `market_data.annual_reports`

- **Purpose:** Metadata and (optionally) parsed summary of a company's annual report, used as source material for AI research (RAG).
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** `company_id` → `market_data.companies.id`
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | company_id | UUID | FK |
  | fiscal_year | SMALLINT | |
  | document_url | TEXT | link to source PDF |
  | summary | TEXT | nullable, AI- or human-generated |
  | published_at | DATE | nullable |
  | created_at | TIMESTAMPTZ | |
- **Indexes:** composite index (`company_id`, `fiscal_year`).
- **Constraints:** unique composite (`company_id`, `fiscal_year`).

### `market_data.news`

- **Purpose:** Ingested news articles relevant to companies/sectors, used both for display and as RAG source material.
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** `company_id` → `market_data.companies.id` (nullable — a market-wide story may not target one company)
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | company_id | UUID | FK, nullable |
  | headline | VARCHAR(500) | |
  | source | VARCHAR(100) | publisher name |
  | source_url | TEXT | |
  | published_at | TIMESTAMPTZ | |
  | content_summary | TEXT | nullable — paraphrased, not full-text reproduction, for copyright safety |
  | embedding | VECTOR(1536) | `pgvector`, for RAG similarity search |
  | created_at | TIMESTAMPTZ | ingestion time |
- **Indexes:** index on `company_id`; index on `published_at`; IVFFlat/HNSW index on `embedding` (`pgvector`).
- **Constraints:** `headline` NOT NULL. Unique on (`source_url`) where not null, to prevent duplicate ingestion.

### `market_data.news_sentiment`

- **Purpose:** AI-derived sentiment score for a news item (produced by the `ai_assistant` module's HuggingFace sentiment pipeline, stored here since it's a derived attribute of the news record).
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** `news_id` → `market_data.news.id`
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | news_id | UUID | FK, UNIQUE (1:1) |
  | sentiment_label | VARCHAR(10) | `positive`, `negative`, `neutral` |
  | sentiment_score | NUMERIC(5,4) | -1.0 to 1.0 |
  | model_used | VARCHAR(100) | which HuggingFace model produced this |
  | scored_at | TIMESTAMPTZ | |
- **Indexes:** unique index on `news_id`; index on `sentiment_label`.
- **Constraints:** `sentiment_score` CHECK BETWEEN -1 AND 1.

### `market_data.geopolitical_events`

- **Purpose:** Macro/geopolitical events (e.g. rate decisions, conflicts, trade policy changes) that the AI assistant and quant engine can factor into context — not company-specific by default.
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** `company_id` → `market_data.companies.id` (nullable — most events are market-wide, but a sanction/tariff event might target one company)
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | company_id | UUID | FK, nullable |
  | title | VARCHAR(300) | |
  | description | TEXT | paraphrased summary |
  | category | VARCHAR(50) | `monetary_policy`, `conflict`, `trade`, `regulatory`, etc. |
  | severity | VARCHAR(10) | `low`, `medium`, `high` |
  | event_date | DATE | |
  | source_url | TEXT | nullable |
  | embedding | VECTOR(1536) | for RAG |
  | created_at | TIMESTAMPTZ | |
- **Indexes:** index on `event_date`; index on `category`; vector index on `embedding`.
- **Constraints:** `title` NOT NULL.

### `quant_engine.technical_indicators`

- **Purpose:** Computed technical indicator values (RSI, MACD, moving averages, etc.) per stock per interval — a high-volume time-series table.
- **Primary Key:** `id` (BIGSERIAL — internal, high-volume table, UUID overhead not justified)
- **Foreign Keys:** `stock_id` → `market_data.stocks.id`
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | BIGSERIAL | PK |
  | stock_id | UUID | FK |
  | indicator_type | VARCHAR(30) | `RSI`, `MACD`, `SMA_50`, etc. |
  | interval | VARCHAR(10) | `1d`, `1h`, `15m` |
  | value | NUMERIC(18,6) | |
  | computed_at | TIMESTAMPTZ | |
- **Indexes:** composite index (`stock_id`, `indicator_type`, `computed_at` DESC) — primary query pattern is "latest N indicator values for a stock." Table partitioned by month (Section 8).
- **Constraints:** none beyond FK; not unique, since indicators are recomputed on a schedule and history is kept.

### `quant_engine.technical_signals`

- **Purpose:** Discrete buy/sell/hold-type signals generated from indicators or strategies — what the screener and alerts actually consume.
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** `stock_id` → `market_data.stocks.id`; `strategy_id` → `quant_engine.strategies.id` (nullable — some signals are rule-based, not tied to a formal strategy)
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | stock_id | UUID | FK |
  | strategy_id | UUID | FK, nullable |
  | signal_type | VARCHAR(20) | `buy`, `sell`, `hold`, `watch` |
  | confidence | NUMERIC(5,4) | 0–1 |
  | reason_code | VARCHAR(50) | e.g. `RSI_OVERSOLD`, `MACD_CROSSOVER` |
  | triggered_at | TIMESTAMPTZ | |
  | expires_at | TIMESTAMPTZ | nullable |
- **Indexes:** composite index (`stock_id`, `triggered_at` DESC); index on `signal_type`.
- **Constraints:** `confidence` CHECK BETWEEN 0 AND 1.

### `quant_engine.strategies`

- **Purpose:** Named, versioned definitions of a quant strategy (a combination of indicator rules) that can generate signals and be backtested.
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** none (author is a system concept for now; `created_by_user_id` reserved for a future phase allowing user-defined strategies)
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | name | VARCHAR(100) | |
  | description | TEXT | nullable |
  | rules | JSONB | structured rule definition |
  | version | SMALLINT | default 1 |
  | is_active | BOOLEAN | default true |
  | created_at | TIMESTAMPTZ | |
  | updated_at | TIMESTAMPTZ | |
- **Indexes:** unique composite (`name`, `version`).
- **Constraints:** `name` NOT NULL.

### `quant_engine.backtesting`

- **Purpose:** Records of a strategy's backtest run against historical data — inputs, parameters, and summary results.
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** `strategy_id` → `quant_engine.strategies.id`
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | strategy_id | UUID | FK |
  | start_date | DATE | |
  | end_date | DATE | |
  | universe | JSONB | which stocks/sector were tested |
  | total_return_pct | NUMERIC(8,3) | nullable |
  | win_rate_pct | NUMERIC(6,3) | nullable |
  | max_drawdown_pct | NUMERIC(6,3) | nullable |
  | sharpe_ratio | NUMERIC(6,3) | nullable |
  | full_results | JSONB | detailed trade-by-trade output |
  | run_at | TIMESTAMPTZ | |
- **Indexes:** index on `strategy_id`; index on `run_at`.
- **Constraints:** `end_date` CHECK > `start_date`.

### `quant_engine.models`

- **Purpose:** Registry of trained ML models (XGBoost/LightGBM/Scikit-learn), versioned, so predictions can always be traced to the exact model that produced them.
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** none
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | name | VARCHAR(100) | e.g. `screener-ranker` |
  | model_type | VARCHAR(30) | `xgboost`, `lightgbm`, `sklearn` |
  | version | VARCHAR(20) | semantic or incremental |
  | artifact_url | TEXT | storage location of the serialized model |
  | training_dataset_ref | TEXT | description/pointer to training data snapshot |
  | hyperparameters | JSONB | |
  | is_active | BOOLEAN | default false — only one active version serves predictions per model name |
  | trained_at | TIMESTAMPTZ | |
  | created_at | TIMESTAMPTZ | |
- **Indexes:** unique composite (`name`, `version`); partial index on `is_active` where true.
- **Constraints:** `name` NOT NULL.

### `quant_engine.model_performance`

- **Purpose:** Tracked accuracy/performance metrics for a model over time, both at training time and via ongoing live evaluation against realized outcomes.
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** `model_id` → `quant_engine.models.id`
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | model_id | UUID | FK |
  | evaluation_type | VARCHAR(20) | `training`, `validation`, `live` |
  | metric_name | VARCHAR(50) | `accuracy`, `precision`, `recall`, `rmse`, etc. |
  | metric_value | NUMERIC(10,6) | |
  | evaluated_at | TIMESTAMPTZ | |
- **Indexes:** composite index (`model_id`, `evaluated_at` DESC).
- **Constraints:** none beyond FK.

### `quant_engine.ai_predictions`

- **Purpose:** A specific model's forecast for a stock (e.g. predicted direction/price range over a horizon) — the raw ML output.
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** `stock_id` → `market_data.stocks.id`; `model_id` → `quant_engine.models.id`
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | stock_id | UUID | FK |
  | model_id | UUID | FK |
  | prediction_type | VARCHAR(30) | `price_target`, `direction`, `volatility` |
  | horizon_days | SMALLINT | e.g. 5, 30 |
  | predicted_value | NUMERIC(18,6) | interpretation depends on `prediction_type` |
  | probability | NUMERIC(5,4) | nullable, model confidence |
  | predicted_at | TIMESTAMPTZ | |
  | target_date | DATE | when the prediction is meant to resolve |
- **Indexes:** composite index (`stock_id`, `predicted_at` DESC); index on `model_id`.
- **Constraints:** `probability` CHECK BETWEEN 0 AND 1 where not null.

### `quant_engine.ai_scores`

- **Purpose:** Aggregate, human-readable composite scores per stock (e.g. an overall "AlphaEdge Score" blending technicals, fundamentals, sentiment, and ML predictions) — what the screener sorts by.
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** `stock_id` → `market_data.stocks.id`
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | stock_id | UUID | FK |
  | score_type | VARCHAR(30) | `overall`, `momentum`, `value`, `sentiment` |
  | score_value | NUMERIC(6,3) | normalized, e.g. 0–100 |
  | components | JSONB | breakdown of what fed into the score |
  | computed_at | TIMESTAMPTZ | |
- **Indexes:** composite index (`stock_id`, `score_type`, `computed_at` DESC).
- **Constraints:** none beyond FK.

### `ai_assistant.ai_explanations`

- **Purpose:** LLM-generated, plain-English explanations of a prediction, signal, or score — the bridge between quant output and user understanding.
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** `stock_id` → `market_data.stocks.id`; `ai_prediction_id` → `quant_engine.ai_predictions.id` (nullable); `technical_signal_id` → `quant_engine.technical_signals.id` (nullable)
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | stock_id | UUID | FK |
  | ai_prediction_id | UUID | FK, nullable |
  | technical_signal_id | UUID | FK, nullable |
  | explanation_text | TEXT | |
  | llm_model_used | VARCHAR(50) | e.g. `gpt-4.1` |
  | prompt_version | VARCHAR(20) | tracks which prompt template generated this |
  | generated_at | TIMESTAMPTZ | |
- **Indexes:** index on `stock_id`; index on `ai_prediction_id`.
- **Constraints:** at least one of `ai_prediction_id` / `technical_signal_id` should be set — enforced at the application layer (a CHECK across nullable FKs is avoidable complexity at the DB level).

### `quant_engine.recommendations`

- **Purpose:** The final, user-facing recommendation surface — synthesizes signals, scores, and predictions into a single actionable (but non-guaranteed) suggestion.
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** `stock_id` → `market_data.stocks.id`; `ai_prediction_id` → `quant_engine.ai_predictions.id` (nullable)
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | stock_id | UUID | FK |
  | ai_prediction_id | UUID | FK, nullable |
  | recommendation_type | VARCHAR(20) | `buy`, `sell`, `hold`, `avoid` |
  | confidence | NUMERIC(5,4) | |
  | rationale_summary | TEXT | short human-readable summary |
  | valid_from | TIMESTAMPTZ | |
  | valid_until | TIMESTAMPTZ | nullable |
- **Indexes:** composite index (`stock_id`, `valid_from` DESC).
- **Constraints:** `confidence` CHECK BETWEEN 0 AND 1.

### `broker.portfolios`

- **Purpose:** A user's portfolio container — separate from `holdings` so portfolio-level metadata (name, linked broker account) doesn't repeat per holding.
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** `user_id` → `users.users.id`; `kite_integration_id` → `broker.kite_integrations.id` (nullable)
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | user_id | UUID | FK |
  | kite_integration_id | UUID | FK, nullable — null until broker is linked |
  | name | VARCHAR(100) | default "My Portfolio" |
  | is_synced_from_broker | BOOLEAN | default false |
  | last_synced_at | TIMESTAMPTZ | nullable |
  | created_at | TIMESTAMPTZ | |
- **Indexes:** index on `user_id`.
- **Constraints:** none beyond FK.

### `broker.holdings`

- **Purpose:** Individual stock positions within a portfolio, either broker-synced or manually tracked.
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** `portfolio_id` → `broker.portfolios.id`; `stock_id` → `market_data.stocks.id`
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | portfolio_id | UUID | FK |
  | stock_id | UUID | FK |
  | quantity | NUMERIC(18,4) | |
  | average_buy_price | NUMERIC(18,4) | |
  | source | VARCHAR(10) | `broker`, `manual` |
  | last_synced_at | TIMESTAMPTZ | nullable |
  | created_at | TIMESTAMPTZ | |
  | updated_at | TIMESTAMPTZ | |
- **Indexes:** composite index (`portfolio_id`, `stock_id`).
- **Constraints:** unique composite (`portfolio_id`, `stock_id`) — one row per stock per portfolio, quantity updated in place. `quantity` CHECK >= 0.

### `broker.orders`

- **Purpose:** Record of order intents and their lifecycle — covers both the read-only "orders placed on Zerodha, synced in" case (early phases) and future in-app order placement (Phase 6, gated).
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** `user_id` → `users.users.id`; `stock_id` → `market_data.stocks.id`; `portfolio_id` → `broker.portfolios.id`
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | user_id | UUID | FK |
  | portfolio_id | UUID | FK |
  | stock_id | UUID | FK |
  | order_type | VARCHAR(10) | `buy`, `sell` |
  | order_mode | VARCHAR(10) | `market`, `limit` |
  | quantity | NUMERIC(18,4) | |
  | price | NUMERIC(18,4) | nullable for market orders |
  | status | VARCHAR(20) | `pending`, `placed`, `executed`, `cancelled`, `rejected` |
  | broker_order_id | VARCHAR(50) | nullable, Kite's own order ID once placed |
  | placed_via | VARCHAR(10) | `sync` (read-only import) or `app` (Phase 6 in-app placement) |
  | created_at | TIMESTAMPTZ | |
  | updated_at | TIMESTAMPTZ | |
- **Indexes:** index on `user_id`; index on `broker_order_id`; index on `status`.
- **Constraints:** `quantity` CHECK > 0. `status` CHECK IN listed values.

### `broker.kite_integrations`

- **Purpose:** Per-user Zerodha Kite Connect connection state — access tokens, scopes, sync status. Isolated as its own table (not columns on `users`) because it's sensitive, broker-specific, and optional.
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** `user_id` → `users.users.id` (one-to-one)
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | user_id | UUID | FK, UNIQUE |
  | kite_user_id | VARCHAR(50) | Zerodha's own user identifier |
  | access_token_encrypted | TEXT | encrypted at rest, never logged |
  | refresh_token_encrypted | TEXT | nullable, encrypted at rest |
  | scopes | JSONB | e.g. `["read"]` vs `["read","write"]` |
  | write_access_enabled | BOOLEAN | default false — the Phase 6 gate |
  | token_expires_at | TIMESTAMPTZ | |
  | connected_at | TIMESTAMPTZ | |
  | last_synced_at | TIMESTAMPTZ | nullable |
- **Indexes:** unique index on `user_id`; unique index on `kite_user_id`.
- **Constraints:** `user_id` UNIQUE. `write_access_enabled` requires an explicit application-layer confirmation flow before ever being set true (enforced in `application`, not just the DB).

### `alerts.alerts`

- **Purpose:** User-defined alert rules (price threshold, signal-triggered, etc.).
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** `user_id` → `users.users.id`; `stock_id` → `market_data.stocks.id`
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | user_id | UUID | FK |
  | stock_id | UUID | FK |
  | alert_type | VARCHAR(20) | `price_above`, `price_below`, `signal_triggered` |
  | threshold_value | NUMERIC(18,4) | nullable, used for price alerts |
  | signal_type_filter | VARCHAR(20) | nullable, used for signal alerts |
  | is_active | BOOLEAN | default true |
  | created_at | TIMESTAMPTZ | |
  | triggered_at | TIMESTAMPTZ | nullable, last time it fired |
- **Indexes:** composite index (`stock_id`, `is_active`) — the evaluation job's primary query; index on `user_id`.
- **Constraints:** `alert_type` CHECK IN listed values.

### `alerts.notification_history`

- **Purpose:** Log of every notification actually sent to a user, for delivery auditing and to prevent duplicate sends.
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** `alert_id` → `alerts.alerts.id` (nullable — some notifications are system messages, not alert-triggered); `user_id` → `users.users.id`
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | alert_id | UUID | FK, nullable |
  | user_id | UUID | FK |
  | channel | VARCHAR(20) | `email`, `push`, `in_app` |
  | message | TEXT | |
  | status | VARCHAR(20) | `sent`, `failed`, `pending` |
  | sent_at | TIMESTAMPTZ | nullable |
  | created_at | TIMESTAMPTZ | |
- **Indexes:** index on `user_id`; index on `alert_id`.
- **Constraints:** `status` CHECK IN listed values.

### `core.api_logs`

- **Purpose:** Structured log of API requests for observability, debugging, and rate-limit/abuse analysis. Extremely high volume — designed for cheap writes and time-bounded reads.
- **Primary Key:** `id` (BIGSERIAL)
- **Foreign Keys:** `user_id` → `users.users.id` (nullable — unauthenticated or system calls have none)
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | BIGSERIAL | PK |
  | user_id | UUID | FK, nullable |
  | method | VARCHAR(10) | `GET`, `POST`, etc. |
  | path | VARCHAR(255) | |
  | status_code | SMALLINT | |
  | response_time_ms | INTEGER | |
  | correlation_id | UUID | ties a request across services/logs |
  | requested_at | TIMESTAMPTZ | |
- **Indexes:** index on `requested_at` (partition key, see Section 8); index on `correlation_id`; index on `user_id`.
- **Constraints:** none beyond FK. This table is a strong candidate to move to a dedicated logging store (outside Postgres) if volume outgrows it — flagged in Section 15.

### `core.audit_logs`

- **Purpose:** Immutable record of security- and integrity-sensitive actions (login, broker link/unlink, order placement, role changes, settings changes) — distinct from `api_logs`, which is general traffic; this table is specifically for actions that need a permanent, tamper-evident trail.
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** `user_id` → `users.users.id` (nullable — some actions are system-initiated)
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | user_id | UUID | FK, nullable |
  | action | VARCHAR(100) | e.g. `broker.write_access_enabled`, `role.changed` |
  | entity_type | VARCHAR(50) | e.g. `order`, `kite_integration` |
  | entity_id | UUID | nullable |
  | metadata | JSONB | before/after state or relevant detail |
  | ip_address | INET | nullable |
  | occurred_at | TIMESTAMPTZ | |
- **Indexes:** index on `user_id`; index on `occurred_at`; index on `action`.
- **Constraints:** rows are insert-only at the application layer — no update/delete path is exposed, enforced by convention and, in a later phase, by a restrictive DB role/trigger.

### `core.system_settings`

- **Purpose:** Global, admin-configurable platform settings (feature flags, maintenance mode, default rate limits) that shouldn't require a deploy to change.
- **Primary Key:** `id` (UUID)
- **Foreign Keys:** none
- **Columns:**
  | Column | Type | Notes |
  |---|---|---|
  | id | UUID | PK |
  | key | VARCHAR(100) | e.g. `maintenance_mode`, `max_watchlists_per_user` |
  | value | JSONB | flexible value type |
  | description | TEXT | nullable |
  | updated_by_user_id | UUID | nullable, FK → users.users.id |
  | updated_at | TIMESTAMPTZ | |
- **Indexes:** unique index on `key`.
- **Constraints:** `key` NOT NULL, UNIQUE.

---

## 6. Database Normalization Strategy

- Baseline target is **Third Normal Form (3NF)** across all transactional tables — no repeating groups, every non-key column depends only on the key.
- Deliberate, documented exceptions:
  - `market_data.financial_statements.raw_data` and other `JSONB` columns hold source-of-truth flexible data (e.g. full statement payloads, model hyperparameters) where the *shape* varies by source/model and forcing full normalization would mean constant schema churn. Structured, frequently-queried fields are still extracted into typed columns (e.g. `quarterly_results`) alongside the raw JSONB — this is a deliberate, narrow denormalization, not a general pattern.
  - Derived/aggregate tables (`ai_scores`, `model_performance`) are intentionally denormalized *summaries* of underlying data — they exist specifically so the app doesn't recompute aggregates on every read. They are regenerated from source tables, never hand-edited, so they don't introduce a second source of truth.
- No table stores computed values that could silently drift from their source without an explicit recomputation job responsible for keeping them current.

## 7. Caching Strategy

- **Redis is the cache layer**, not a table replacement. Cached data always has a Postgres source of truth.
- **Hot-path caching:** latest price per stock, latest `ai_scores`, and active `technical_signals` are cached with short TTLs (seconds to low minutes) since they're read far more often than they change.
- **Cache invalidation:** write-through on ingestion — when a new price/indicator/signal is written to Postgres, the corresponding cache key is updated or invalidated in the same operation, never left to expire silently on data that must be fresh.
- **Query result caching** for expensive, slow-changing aggregates (e.g. sector-level rollups) with medium TTLs (minutes), explicitly not used for anything user-financial-decision-critical without a freshness indicator shown in the UI.
- **Session/rate-limit counters** also live in Redis, separate key namespace from data caching.

## 8. Partitioning Strategy

Time-series, high-volume tables are partitioned by range on their time column, by month:
- `quant_engine.technical_indicators` (partitioned on `computed_at`)
- `core.api_logs` (partitioned on `requested_at`)
- the future `market_data.price_bars` table (partitioned on candle timestamp)

Partitioning keeps indexes small and queries fast as these tables grow into hundreds of millions of rows, and allows old partitions to be dropped or archived cheaply (see Section 9) instead of running expensive `DELETE` queries.

Tables that are large but not naturally time-partitioned (`market_data.news`, `quant_engine.ai_predictions`) are monitored and are candidates for partitioning by `created_at`/`predicted_at` if/when their size warrants it — not partitioned from day one to avoid premature complexity.

## 9. Backup Strategy

- **Automated daily full backups** of the Postgres instance, retained on a rolling 30-day window at minimum.
- **Point-in-time recovery (PITR)** enabled via continuous WAL archiving, so the database can be restored to any point within the retention window, not just to a daily snapshot boundary.
- **Pre-migration snapshots:** a backup is taken immediately before every schema migration is applied to production, independent of the daily schedule.
- **Partition archival:** old partitions (Section 8) that age out of the active retention window (e.g. `api_logs` older than 12 months) are exported to cold storage before being dropped, rather than deleted outright.
- **Restore drills:** backups are periodically test-restored to a non-production environment to verify they're actually usable — a backup that's never been restored is unverified.

## 10. Migration Strategy

- **Alembic** manages all schema changes, with one linear migration history for the whole database (per `PROJECT_CONTEXT.md § 10`), migration messages tagged by schema/module (e.g. `[market_data] add companies table`).
- Every migration is **additive and backward-compatible by default**: add columns as nullable or with defaults, add tables outright, avoid destructive changes (dropping/renaming columns) in the same release that stops using them — deprecate first, remove later, so a rollback of application code never leaves the database in an incompatible state.
- Migrations are reviewed the same way code is (Section "Development Workflow" in `README.md`) and run automatically as a gated CI/CD step before the application deploy that depends on them.
- Each module's tables are migrated independently where possible, so a `market_data` migration doesn't require touching `broker` tables in the same migration file.

## 11. Scaling Strategy

- **Vertical scaling first:** a single well-indexed Postgres instance on a reasonably sized managed instance comfortably handles AlphaEdge AI's expected load through at least Phase 4–5 (Section 13).
- **Read replicas** are the first horizontal step once read load (screener queries, chart data, AI context lookups) starts contending with write load (price ingestion, log writes) — read-heavy modules (`market_data`, `quant_engine` reads) are routed to a replica while writes stay on the primary.
- **Schema-per-module physical separation:** because modules never cross-query each other's tables directly (Section 1), any schema — most likely `core.api_logs` first, given its volume — can be moved to its own database instance or replaced with a purpose-built store (e.g. a log aggregation service) without touching other modules' code.
- **Connection pooling** (e.g. PgBouncer) sits in front of Postgres once concurrent connections from the API layer and worker processes grow beyond what direct connections comfortably support.
- **Redis scaling:** starts single-instance, moves to Redis Cluster or a managed clustered offering if cache/queue throughput becomes a bottleneck — independent of Postgres scaling decisions.

## 12. Security Strategy

- **Encryption in transit:** all connections to Postgres and Redis use TLS, no exceptions, in every environment including local development against remote services.
- **Encryption at rest:** enabled at the managed database provider level; additionally, specific sensitive columns (`kite_integrations.access_token_encrypted`, `refresh_token_encrypted`) are application-level encrypted before storage, so they're never plaintext even to someone with raw database access.
- **Least-privilege DB roles:** the application's runtime DB user has only the privileges it needs (no `DROP`/`ALTER` in production); migrations run under a separate, more privileged role used only by CI/CD.
- **No PII/secrets in logs:** enforced by `core/logging.py` redaction rules (per `PROJECT_CONTEXT.md § 15`) — `api_logs` and `audit_logs` never store token values, passwords, or full request bodies containing sensitive fields.
- **Row-level access control** is enforced at the application layer (every query scoped by `user_id` from the verified Clerk JWT) — the database does not currently rely on Postgres Row-Level Security, but schemas are designed so RLS could be added later as a defense-in-depth layer without restructuring tables.
- **Audit trail:** every sensitive state change is captured in `core.audit_logs` (Section 5), which is insert-only by convention.

## 13. Expected Database Size

Rough, planning-level estimates — not commitments — based on a moderate-scale retail platform covering the NSE/BSE universe (~5,000 listed instruments):

| Category | Phase 1–2 estimate | Phase 5–7 estimate (mature) |
|---|---|---|
| Reference data (companies, stocks, sectors, industries) | < 50 MB | < 200 MB |
| Financial statements / quarterly results / annual reports | ~200 MB | ~2 GB |
| Technical indicators (time-series, partitioned) | ~5–10 GB/year | 50+ GB/year |
| News + embeddings | ~1–5 GB | 20+ GB |
| AI predictions / scores / explanations | ~1–3 GB/year | 20+ GB/year |
| User data (users, portfolios, holdings, watchlists) | < 500 MB at 10K users | ~5 GB at 100K+ users |
| API logs (partitioned, rolling retention) | ~10 GB/month | ~50+ GB/month, older partitions archived |

Total: expect **low tens of GB** through early phases, growing into the **hundreds of GB range** (dominated by time-series indicator/log data) at meaningful scale — well within single-instance Postgres capability given the partitioning and archival strategy above.

## 14. Performance Optimization Strategy

- Every foreign key column is indexed by default; every table's primary "how will this be queried" access pattern is indexed explicitly (documented per table in Section 5) rather than added reactively after a slow query is found.
- Composite indexes are ordered to match actual query patterns (most selective / most-filtered-on column first).
- `EXPLAIN ANALYZE` review is a required step (Section 22 checklist in `PROJECT_CONTEXT.md`) before any new query pattern ships in a module that touches a high-volume table.
- Hot aggregates (`ai_scores`, latest indicator values) are precomputed on write rather than calculated on every read.
- Redis absorbs the highest-frequency reads (Section 7) so Postgres is largely insulated from live-price read load.
- Partition pruning (Section 8) keeps time-series queries scoped to relevant partitions instead of scanning full history by default.
- Connection pooling (Section 11) prevents connection exhaustion from becoming a bottleneck before query performance is.

## 15. Future Expansion Strategy

- `core.api_logs` is the most likely first candidate to move out of Postgres entirely into a dedicated log/observability platform, once volume makes it a poor fit for the primary transactional database — its schema is deliberately simple and self-contained to make that migration low-risk.
- A dedicated `market_data.price_bars` table (flagged in Section 5) will be formally specified at Phase 1 implementation, including its own partitioning and downsampling strategy for different chart intervals.
- If a broker beyond Zerodha is added (`PROJECT_CONTEXT.md § 27`), `broker.kite_integrations` generalizes into a `broker.broker_integrations` table with a `broker_type` discriminator, following the same adapter-pattern isolation already used for Kite Connect — existing Kite rows migrate forward, not replaced.
- If a model registry matures beyond `quant_engine.models`/`model_performance`, those tables become the relational index into a dedicated MLOps system rather than being replaced by one.
- Multi-exchange/international expansion would extend `market_data.stocks.exchange` and add exchange-specific reference tables, not restructure the core stock/company relationship.
- Any of these expansions follows the same rule as everything else in this project: extend this document and the schema, never redesign around it.

---

*This document must stay in sync with the actual schema. Any new table, column, or strategy change discovered during implementation gets reflected here before (or in the same PR as) the migration that introduces it.*
