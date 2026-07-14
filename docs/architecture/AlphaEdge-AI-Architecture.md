# AlphaEdge AI — System Architecture (Phase 0)

**Status:** Architecture-only. No application code has been written yet.
**Purpose of this document:** the single source of truth for how AlphaEdge AI is structured. Every future phase must extend this document rather than contradict it. When new modules are added later, this file should be updated, not replaced.

---

## 1. Product Definition

**What AlphaEdge AI is:** an AI-assisted stock analysis and research platform for Indian markets (NSE/BSE, via Zerodha Kite Connect), giving retail users institutional-grade tooling: live/historical charting, quantitative signal generation, ML-based forecasting, portfolio and broker integration, and natural-language research powered by LLMs.

**What it is not (v1):** not a broker itself, not a fully automated trading bot placing unsupervised orders, not a SEBI-registered advisory engine. Early phases produce *analysis and signals*, not autonomous execution — automated order placement is a deliberately gated, opt-in capability introduced only after the core platform is stable.

### Core Pillars
1. **Market Data & Charting** — real-time and historical price data, TradingView-powered charts.
2. **Quant Research Engine** — classical technical indicators + statistical/ML models (Scikit-learn, XGBoost, LightGBM) for signal generation and forecasting.
3. **AI Research Assistant** — LLM (OpenAI + HuggingFace models) layer for natural-language Q&A, summarization of filings/news, and explaining model outputs in plain English.
4. **Broker Integration** — Zerodha Kite Connect for account linking, holdings/positions sync, and (later) order placement.
5. **Platform Layer** — auth (Clerk), user accounts, watchlists, alerts, subscription/billing (future phase).

---

## 2. High-Level Architecture Style

**Pattern:** Clean Architecture + Modular Monolith → Microservices-ready.

Rationale: a single team, early-stage product should not start as microservices (too much operational overhead too early). But every module is built with clear boundaries (its own domain layer, its own service layer, its own DB schema/namespace) so any module can later be extracted into its own deployable service with minimal rewrite.

```
┌──────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                              │
│   Next.js (React + TypeScript) — Web App, deployed on Vercel     │
└───────────────────────────┬────────────────────────────────────--┘
                             │ HTTPS / REST (+ WebSocket for live data)
┌───────────────────────────▼───────────────────────────────────--─┐
│                        API GATEWAY LAYER                          │
│         FastAPI (Python) — single entrypoint, versioned /v1       │
│   - Auth middleware (Clerk JWT verification)                      │
│   - Rate limiting, request validation, logging, correlation IDs   │
└───────────────────────────┬────────────────────────────────────--┘
                             │
        ┌────────────────────┼──────────────────────┬─────────────────┐
        ▼                    ▼                      ▼                 ▼
┌───────────────┐   ┌─────────────────┐   ┌──────────────────┐  ┌──────────────┐
│ Market Data    │   │ Quant/ML Engine │   │ AI Research      │  │ Broker        │
│ Module         │   │ Module          │   │ Assistant Module │  │ Integration   │
│ (Clean Arch)   │   │ (Clean Arch)    │   │ (Clean Arch)     │  │ Module        │
└───────┬────────┘   └────────┬────────┘   └────────┬─────────┘  └──────┬───────┘
        │                     │                      │                  │
        └─────────────────────┴──────────┬───────────┴──────────────────┘
                                          ▼
                             ┌──────────────────────────┐
                             │   PostgreSQL (primary DB) │
                             │   + Redis (cache/queue)   │
                             └──────────────────────────┘
```

Every module in the middle row follows the same internal Clean Architecture shape (see Section 5), so adding a new module later (e.g. "Options Analytics", "News Sentiment", "Portfolio Optimizer") means copying the same pattern — never inventing a new one.

---

## 3. Repository & Monorepo Structure

A monorepo is used so frontend, backend, and shared contracts evolve together without version drift. This structure is **final for the life of the project** — new modules are added inside it, the top level does not change.

```
alphaedge-ai/
├── apps/
│   ├── web/                     # Next.js frontend (App Router)
│   └── api/                     # FastAPI backend
├── packages/
│   ├── shared-types/            # TypeScript types shared by web (generated from OpenAPI)
│   └── ui/                      # shadcn/ui-based shared component library (future phase)
├── infra/
│   ├── docker/                  # Dockerfiles, docker-compose
│   ├── github/                  # CI/CD workflows
│   └── railway/                 # Railway service configs
├── docs/
│   ├── architecture/            # This file + future ADRs (Architecture Decision Records)
│   └── api/                     # OpenAPI spec exports
└── .env.example
```

Rules that apply to this structure going forward:
- New backend domain modules live inside `apps/api/app/modules/<module_name>/`.
- New frontend feature areas live inside `apps/web/app/<feature>/`.
- Nothing is ever created at the monorepo root except config files (`.gitignore`, `README.md`, `docker-compose.yml`, etc).

---

## 4. Frontend Architecture (Next.js)

**Rendering strategy:** App Router, mixing Server Components (for data-heavy, SEO-relevant pages like public stock pages) and Client Components (for interactive charts, dashboards, real-time widgets).

```
apps/web/
├── app/
│   ├── (public)/                # Marketing/landing, SEO'd, server-rendered
│   ├── (auth)/                  # Clerk sign-in/sign-up routes
│   ├── (dashboard)/             # Authenticated app shell
│   │   ├── dashboard/
│   │   ├── stocks/[symbol]/     # Stock detail + TradingView chart
│   │   ├── screener/            # Quant screener UI (future phase)
│   │   ├── portfolio/           # Broker-linked holdings (future phase)
│   │   ├── ai-assistant/        # Chat-style research assistant
│   │   └── settings/
│   └── api/                     # Next.js route handlers ONLY for things that must run at the edge (e.g. Clerk webhooks) — all real business logic lives in FastAPI, never here
├── components/
│   ├── ui/                      # shadcn/ui primitives
│   ├── charts/                  # TradingView wrapper components
│   └── domain/                  # Feature-specific composed components
├── lib/
│   ├── api-client/              # Typed fetch wrapper hitting FastAPI, using shared-types
│   ├── auth/                    # Clerk helpers
│   └── utils/
├── hooks/
└── styles/
```

**Key decisions:**
- **State management:** server state via React Query (TanStack Query) against the FastAPI backend; local/UI state via React state/hooks. No Redux — not needed for this shape of app.
- **Styling:** TailwindCSS + shadcn/ui as the only component system. No competing UI libraries introduced later without an ADR.
- **Charts:** TradingView's Lightweight Charts (or Advanced Charting Library if licensed) wrapped in a single `components/charts/` module so the rest of the app never talks to TradingView's API directly — this keeps a future chart-vendor swap contained.
- **Type safety across the stack:** FastAPI generates an OpenAPI spec → a codegen step produces `packages/shared-types` → frontend never hand-writes API response types.

---

## 5. Backend Architecture (FastAPI, Clean Architecture)

Every domain module follows the **same four-layer shape**. This is the most important rule for long-term scalability — a future engineer (or future you) should be able to open any module and immediately know where things live.

```
apps/api/app/
├── modules/
│   └── <module_name>/
│       ├── domain/              # Entities, value objects, domain exceptions — pure Python, zero framework deps
│       ├── application/         # Use cases / services — orchestrate domain logic, define ports (interfaces)
│       ├── infrastructure/      # Adapters: DB repositories, external API clients, ML model loaders
│       └── api/                 # FastAPI routers, request/response schemas (Pydantic) — the only layer that knows about HTTP
├── core/
│   ├── config.py                # Settings (env-driven, pydantic-settings)
│   ├── security.py              # Clerk JWT verification, dependency-injected auth
│   ├── db.py                    # SQLAlchemy engine/session management
│   └── logging.py
├── shared/
│   ├── events/                  # Internal event bus contracts (for future async module-to-module comms)
│   └── exceptions/
└── main.py                      # App factory, router registration, middleware
```

**Dependency rule (non-negotiable):** `api` → `application` → `domain`, and `infrastructure` → `application`'s ports. Domain never imports from infrastructure or api. This is what lets a module's ML engine, DB, or external API be swapped without touching business logic.

### Planned modules (built incrementally, each independently deployable later)
| Module | Responsibility |
|---|---|
| `market_data` | Ingests and serves live/historical OHLCV data, symbol metadata |
| `quant_engine` | Technical indicators, statistical models, XGBoost/LightGBM signal generation |
| `ai_assistant` | LLM orchestration (OpenAI + HuggingFace), prompt templates, RAG over filings/news |
| `broker` | Zerodha Kite Connect OAuth, holdings sync, order placement (gated) |
| `users` | Profile, preferences, watchlists — Clerk is identity provider, this module owns app-specific user data |
| `alerts` | Price/signal alert rules and notification dispatch (future phase) |
| `billing` | Subscription tiers (future phase) |

Each module gets its own Postgres schema (e.g. `quant_engine.signals`, `broker.holdings`) inside the single database — logically separated now, physically separable later if a module needs its own DB.

---

## 6. Data Architecture

**Primary store:** PostgreSQL — one instance, one database, schema-per-module.

**Caching/queueing:** Redis — used for (a) caching hot market-data reads, (b) as a lightweight task queue for async jobs (ML inference, LLM calls, broker sync) via a worker process, so the API layer never blocks on slow operations.

**Data flow for live prices (conceptual, not code):**
```
Zerodha Kite WebSocket → market_data.infrastructure (ingest worker)
   → normalize → write-through to Redis (hot cache) → periodic flush to Postgres (historical)
   → FastAPI WebSocket endpoint → Next.js client (live chart updates)
```

**Data flow for ML signals:**
```
Scheduled job (Railway cron / worker) → quant_engine.application use case
   → pulls features from market_data → runs XGBoost/LightGBM model
   → writes signal to quant_engine schema → exposed via api/ router
   → ai_assistant module can reference signals when answering user questions
```

This is the key cross-module connection point: `quant_engine` produces structured signals, `ai_assistant` consumes them as context — this is designed now so Phase 2+ doesn't require restructuring either module.

---

## 7. AI/ML Architecture

Two distinct AI subsystems, kept architecturally separate because they have different latency, cost, and correctness requirements:

**A. Quant/ML Engine (deterministic-ish, statistical)**
- Scikit-learn for classical models (regression, classification baselines).
- XGBoost / LightGBM for gradient-boosted forecasting and ranking (e.g. screener scoring).
- Runs as scheduled batch jobs + on-demand inference endpoints.
- Model artifacts versioned and stored (future phase: a model registry — even just a `models/` bucket with version metadata in Postgres to start).

**B. AI Research Assistant (LLM-based, generative)**
- OpenAI for general reasoning/chat and complex synthesis.
- HuggingFace models for specialized/cheaper tasks (e.g. sentiment classification on news, embeddings for RAG).
- Retrieval-Augmented Generation: embeddings stored via `pgvector` extension on the same Postgres instance (no separate vector DB needed at this scale) — indexed news, filings, and quant signals.
- Every LLM call goes through a single internal `ai_assistant.infrastructure` gateway — no other module calls OpenAI/HuggingFace directly. This means swapping providers or adding guardrails/cost controls happens in one place.

---

## 8. Authentication & Authorization

- **Clerk** is the identity provider (sign-up, sign-in, session, MFA, social login).
- Frontend uses Clerk's Next.js SDK for session state.
- Backend never trusts the frontend directly — every FastAPI request carries a Clerk-issued JWT, verified via `core/security.py` using Clerk's JWKS endpoint.
- Authorization (what a user is *allowed* to do — e.g. free vs paid tier, broker-linked vs not) is application-level logic inside the `users` module, layered on top of Clerk's authentication.

---

## 9. Broker Integration (Zerodha Kite Connect)

- Isolated entirely inside the `broker` module — no other module imports Kite Connect's SDK directly.
- OAuth-style login flow: user connects their Zerodha account → access token stored encrypted, scoped per-user.
- Two capability tiers, introduced in separate phases:
  1. **Read-only** (early phase): holdings, positions, historical trades — purely informational, low risk.
  2. **Write** (later, opt-in, heavily gated): order placement — requires explicit confirmation UX, audit logging, and rate/size safeguards before it's enabled.

---

## 10. Deployment Architecture

```
GitHub (source of truth, monorepo)
   │
   ├── GitHub Actions (CI): lint, type-check, test, build — on every PR
   │
   ├──► Vercel: deploys apps/web on merge to main (preview deploys on PRs)
   │
   └──► Railway: deploys apps/api (FastAPI) + worker process + PostgreSQL + Redis
              — Dockerized, one service per component, defined in infra/docker + infra/railway
```

- **Environments:** `local` (docker-compose, everything on one machine) → `preview` (per-PR, Vercel + Railway preview envs) → `production`.
- **Secrets:** never committed; managed via Vercel/Railway env dashboards, mirrored in `.env.example` (keys only, no values) for local dev.
- **Containerization:** every backend component (API, worker) has its own Dockerfile under `infra/docker/`, so any component can be deployed to any container platform later without lock-in to Railway specifically.

---

## 11. Cross-Cutting Concerns (apply to every module, every phase)

- **Logging:** structured JSON logs, correlation ID per request, propagated from frontend → API → worker jobs.
- **Error handling:** domain-specific exceptions in `domain/`, translated to proper HTTP error responses only in `api/` — never leak raw exceptions to the client.
- **Testing:** unit tests at the domain/application layer (no framework deps, fast), integration tests at the infrastructure/api layer. Test pyramid, not ice-cream-cone.
- **Config:** all environment-driven via `pydantic-settings` on the backend and `.env` on the frontend — no hardcoded secrets or URLs anywhere.
- **Versioning:** API is versioned from day one (`/api/v1/...`) so breaking changes in later phases don't break the existing frontend build.
- **Observability (future phase):** hook point reserved in `core/logging.py` for adding a provider (e.g. Sentry, Better Stack) without restructuring.

---

## 12. Phase Roadmap (high-level — detailed specs come per-phase)

| Phase | Scope |
|---|---|
| **0 (this doc)** | Architecture, repo scaffolding, environment setup — no features |
| **1** | Auth (Clerk) + `market_data` module + basic stock detail page with TradingView chart |
| **2** | `quant_engine`: technical indicators + first ML model (screener/ranking) |
| **3** | `ai_assistant`: LLM research chat, RAG over news/filings |
| **4** | `broker` module: Zerodha read-only integration (holdings/positions) |
| **5** | Alerts, watchlists, user personalization |
| **6** | Broker write access (order placement) — gated rollout |
| **7** | Billing/subscription tiers, public launch hardening |

Each phase produces working, deployed software that extends this same repo and architecture — never a rewrite.

---

## 13. Open Decisions (to be resolved before Phase 1 coding starts)

These are flagged now, not decided, so Phase 1 doesn't stall on them later:
1. Which TradingView product — free Lightweight Charts vs licensed Advanced Charting Library (cost/feature tradeoff).
2. Exact Postgres hosting: Railway-managed Postgres vs a dedicated provider (e.g. Supabase/Neon) — affects `pgvector` availability.
3. Whether the async worker (Section 6) is a separate Railway service from day one, or starts as background tasks inside FastAPI and gets extracted later.
4. Kite Connect API cost (it's a paid API with a monthly fee) — confirm budget before Phase 4.

---

*Next step, when you're ready: Phase 1 detailed design — data models for `market_data` and `users`, Clerk setup steps, and the first API contracts — still architecture/spec level before any code is generated, per your rules.*
