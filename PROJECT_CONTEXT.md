# PROJECT_CONTEXT.md — AlphaEdge AI

**This file is the permanent memory of the AlphaEdge AI project.**
Every future phase, every future prompt, every future AI-generated file must be consistent with what's written here. If a future request conflicts with this file, this file wins unless the project owner explicitly amends it — and any amendment should be made *in this file*, not worked around silently.

This document does not contain application code. It contains the standards, structure, and rules that all future code must follow.

---

## 1. Project Vision

AlphaEdge AI is a production-grade, AI-assisted stock analysis platform for Indian markets (NSE/BSE), built to give retail investors and traders institutional-grade research tooling: live and historical charting, quantitative signal generation, machine-learning-based forecasting, direct broker integration, and a natural-language AI research assistant — all in one coherent product, not a bundle of disconnected tools.

## 2. Long-Term Goal

Grow AlphaEdge AI from a single-developer architecture-first build into a scalable, multi-module platform that can:
- Serve real users with real brokerage accounts (via Zerodha Kite Connect).
- Combine classical quant methods (technical indicators, statistical models) with modern ML (XGBoost/LightGBM) and LLM-based reasoning (OpenAI/HuggingFace) in a single research experience.
- Evolve module-by-module, phase-by-phase, without ever requiring a rewrite — every module is designed from day one to be extractable into its own service if scale demands it.
- Eventually support a sustainable business model (subscription tiers) and, only once mature and compliant, optional automated order execution.

## 3. Problems the Platform Solves

- Retail investors in India lack a single tool that combines live charting, quant screening, ML forecasting, and plain-English AI explanation — they currently stitch together broker apps, TradingView, spreadsheets, and news manually.
- Technical/statistical analysis tools are usually either too basic (simple indicator overlays) or too complex/expensive (institutional terminals) — there's a gap for a serious-but-accessible middle tier.
- Understanding *why* a model or indicator is signaling something is hard for non-quant users — the AI research assistant exists specifically to translate model output into understandable reasoning.
- Portfolio visibility is fragmented from research — AlphaEdge AI connects a user's actual Zerodha holdings to the same research tools they use to evaluate new ideas.

## 4. Target Users

- Retail equity/commodity traders and investors in India who already use a Zerodha account or similar.
- Users comfortable with technical analysis concepts who want ML-augmented signals rather than raw indicators alone.
- Users who want AI-assisted research (natural-language Q&A about a stock, a sector, or a signal) instead of manually reading filings and news.
- Not targeted in v1: institutional users, algo-trading firms needing colocated execution, or fully automated "black box" traders.

## 5. Complete Tech Stack

**Frontend:** Next.js, React, TypeScript, TailwindCSS, shadcn/ui
**Backend:** FastAPI, Python
**Database:** PostgreSQL (+ `pgvector` extension for embeddings, Redis for cache/queue)
**Authentication:** Clerk
**Charts:** TradingView (Lightweight Charts or Advanced Charting Library — decision pending, see Section 18/Open Decisions in the architecture doc)
**Broker:** Zerodha Kite Connect API
**AI/ML:** OpenAI, HuggingFace, Scikit-learn, XGBoost, LightGBM
**Deployment:** Docker, GitHub (+ GitHub Actions for CI), Vercel (frontend), Railway (backend, worker, Postgres, Redis)

No new top-level technology is introduced into this stack without an explicit decision recorded in `docs/architecture/` (an ADR). Future AI responses must not silently substitute a different library, framework, or service.

## 6. Architecture Summary

Clean Architecture inside a modular monolith, monorepo-hosted, microservices-ready.

- Frontend (Next.js) talks only to the FastAPI backend over REST (+ WebSocket for live data) — never directly to Postgres, TradingView data feeds, brokers, or AI providers.
- Backend is organized into independent domain modules (`market_data`, `quant_engine`, `ai_assistant`, `broker`, `users`, `alerts`, `billing`), each following the same four-layer shape: `domain → application → infrastructure/api`.
- Dependency rule: `api` depends on `application` depends on `domain`; `infrastructure` implements ports defined by `application`. `domain` never depends on anything else.
- One PostgreSQL database, schema-per-module, so modules are logically isolated now and physically separable later.
- All external integrations (OpenAI, HuggingFace, Kite Connect, Clerk) are wrapped in a single infrastructure adapter per module — no module calls an external SDK directly outside its own `infrastructure/` layer.

Full detail lives in `docs/architecture/AlphaEdge-AI-Architecture.md`. This file summarizes it; that file is authoritative for diagrams and data flow.

## 7. Folder Structure

```
alphaedge-ai/
├── apps/
│   ├── web/                     # Next.js frontend (App Router)
│   │   ├── app/(public|auth|dashboard)/...
│   │   ├── components/{ui,charts,domain}/
│   │   ├── lib/{api-client,auth,utils}/
│   │   ├── hooks/
│   │   └── styles/
│   └── api/                     # FastAPI backend
│       ├── app/modules/<module_name>/{domain,application,infrastructure,api}/
│       ├── app/core/             # config, security, db, logging
│       ├── app/shared/           # events, exceptions
│       └── app/main.py
├── packages/
│   ├── shared-types/             # generated from OpenAPI, consumed by web
│   └── ui/                       # shared component library (future)
├── infra/
│   ├── docker/
│   ├── github/                   # CI workflows
│   └── railway/
├── docs/
│   ├── architecture/             # architecture doc + ADRs
│   └── api/                      # OpenAPI exports
└── .env.example
```

This structure is final at the top level. New features live inside existing folders — new modules under `apps/api/app/modules/`, new frontend feature areas under `apps/web/app/`. Nothing new is added at repo root except project-wide config.

## 8. Backend Module List

| Module | Responsibility | Phase Introduced |
|---|---|---|
| `market_data` | Live/historical OHLCV ingestion and serving, symbol metadata | Phase 1 |
| `users` | App-specific user data, preferences, watchlists (Clerk owns identity) | Phase 1 |
| `quant_engine` | Technical indicators, statistical/ML models, screener scoring | Phase 2 |
| `ai_assistant` | LLM orchestration, RAG over news/filings, plain-English explanations | Phase 3 |
| `broker` | Zerodha Kite Connect OAuth, holdings/positions sync, gated order placement | Phase 4 (read), Phase 6 (write) |
| `alerts` | Price/signal alert rules, notification dispatch | Phase 5 |
| `billing` | Subscription tiers, payment integration | Phase 7 |

New modules follow the same four-layer internal structure as existing ones — no exceptions.

## 9. Frontend Module List

| Area | Route group | Responsibility | Phase |
|---|---|---|---|
| Marketing/landing | `(public)` | SEO'd public pages | Phase 1 |
| Auth | `(auth)` | Clerk sign-in/sign-up | Phase 1 |
| Dashboard shell | `(dashboard)/dashboard` | Authenticated home | Phase 1 |
| Stock detail | `(dashboard)/stocks/[symbol]` | TradingView chart + data | Phase 1 |
| Screener | `(dashboard)/screener` | Quant screener UI | Phase 2 |
| AI Assistant | `(dashboard)/ai-assistant` | Chat-style research UI | Phase 3 |
| Portfolio | `(dashboard)/portfolio` | Broker-linked holdings | Phase 4 |
| Settings | `(dashboard)/settings` | Profile, preferences, broker link | Phase 1 (basic), expanded later |

## 10. Database Strategy

- Single PostgreSQL instance, one schema per backend module (e.g. `market_data.*`, `quant_engine.*`, `broker.*`).
- `pgvector` extension used for embeddings (news/filings RAG) — no separate vector database at current scale.
- Redis used for hot-path caching (live price reads) and as a lightweight task queue for async jobs (ML inference, LLM calls, broker sync).
- Migrations managed with a single migration tool (Alembic, standard for FastAPI/SQLAlchemy) — one migration history for the whole database, tagged by module in migration messages.
- No module reads or writes another module's schema directly — cross-module data access goes through that module's `application` layer / public interface, never a raw cross-schema query.
- Historical market data is append-only where possible; mutable state (user data, holdings) is designed with standard audit columns (`created_at`, `updated_at`) from day one.

## 11. AI/ML Strategy

Two separate subsystems, intentionally not merged:

**Quant/ML Engine** — deterministic-leaning, statistical: Scikit-learn for baselines, XGBoost/LightGBM for gradient-boosted forecasting and screener ranking. Runs as scheduled batch jobs plus on-demand inference. Model artifacts are versioned (metadata tracked in Postgres from the start, even before a full model registry exists).

**AI Research Assistant** — generative, LLM-based: OpenAI for general reasoning/synthesis, HuggingFace models for cheaper/specialized tasks (sentiment classification, embeddings). RAG over news/filings using `pgvector`. Every call to an external AI provider goes through one internal gateway (`ai_assistant.infrastructure`) — never called directly from another module — so provider swaps, cost controls, and guardrails happen in exactly one place.

The `ai_assistant` module is designed to consume `quant_engine` signals as context, so the assistant can explain *why* a signal fired in plain English — this connection is planned now so it doesn't require restructuring later.

## 12. Coding Standards

- **Python (backend):** PEP 8, type hints everywhere, `pydantic` for all request/response and settings models, no bare `except:`, no mutable default arguments, docstrings on all public functions/classes in `application` and `domain` layers.
- **TypeScript (frontend):** strict mode on, no `any` without an explicit justifying comment, prefer explicit return types on exported functions, no default exports for components (named exports only, for consistent refactoring/searchability).
- **General:** small, single-responsibility functions; no god files; no logic in FastAPI route handlers or React page components beyond orchestration — real logic lives in `application`/`domain` (backend) or `lib`/`hooks` (frontend).
- **Formatting/linting enforced, not optional:** `black` + `ruff` (Python), `eslint` + `prettier` (TypeScript) — CI fails the build if these fail.
- **Comments explain "why," not "what"** — code should be readable enough that "what" is self-evident.

## 13. UI Design Standards

- shadcn/ui + TailwindCSS only — no competing component libraries introduced without an ADR.
- Design must feel like a serious financial tool: dense, data-forward, low-noise. Not a generic SaaS landing-page aesthetic — no default purple-gradient-hero look.
- Dark mode is a first-class citizen, not an afterthought (financial/charting tools are predominantly used in dark mode).
- Consistent spacing/typography scale via Tailwind config — no ad hoc pixel values in components.
- Charts and data tables are the visual centerpiece; chrome (nav, sidebars) stays minimal so data has room to breathe.
- Every interactive financial number (price, %, signal) has a consistent, reused formatting component — never inline `toFixed()` scattered across files.
- Accessibility: semantic HTML, proper contrast ratios even in dark mode, keyboard-navigable interactive elements.

## 14. API Standards

- REST, versioned from day one: `/api/v1/...` — a v2 can be introduced later without breaking v1 clients.
- Resource-oriented URLs (`/v1/stocks/{symbol}`, `/v1/portfolio/holdings`) — no RPC-style endpoint names.
- All request/response bodies defined as Pydantic schemas — no raw dicts crossing the `api` layer boundary.
- Consistent error response shape across the entire API (status code + machine-readable error code + human-readable message) — defined once in `shared/exceptions`, used everywhere.
- Pagination, filtering, and sorting follow one consistent query-param convention across all list endpoints.
- OpenAPI spec is the contract — frontend types are generated from it, never hand-duplicated.
- WebSocket endpoints reserved for genuinely real-time data (live prices) only — not used as a REST substitute.

## 15. Security Standards

- All authentication via Clerk-issued JWTs, verified server-side against Clerk's JWKS on every request — frontend is never trusted for identity.
- Secrets only in environment variables (Vercel/Railway dashboards in deployed environments), never committed — `.env.example` holds keys only, no values.
- Zerodha access tokens stored encrypted at rest, scoped strictly per-user, never logged.
- All external input validated at the `api` layer boundary (Pydantic) before it reaches `application`/`domain`.
- Principle of least privilege: broker write-access (order placement) is a separate, explicitly gated capability from read-access — never bundled by default.
- No secrets, tokens, or PII in logs — `core/logging.py` is the single place log redaction rules are enforced.
- Dependencies kept current; CI includes a dependency vulnerability check before merge (tooling choice finalized when CI is built in a later phase).

## 16. Naming Conventions

- **Backend modules/packages:** `snake_case` (`market_data`, `ai_assistant`).
- **Python classes:** `PascalCase`; functions/variables: `snake_case`; constants: `UPPER_SNAKE_CASE`.
- **TypeScript/React components:** `PascalCase` filenames and export names (`StockChart.tsx`); hooks: `useCamelCase` (`useStockData.ts`); utility functions: `camelCase`.
- **API routes:** plural nouns, kebab-case where multi-word (`/v1/watchlist-items`), not verbs.
- **Database tables:** `snake_case`, plural (`holdings`, `signals`), schema-prefixed by module (`quant_engine.signals`).
- **Environment variables:** `UPPER_SNAKE_CASE`, prefixed by concern where helpful (`CLERK_SECRET_KEY`, `KITE_API_KEY`).
- **Git branches:** see Section 17.

## 17. Git Branch Strategy

- `main` — always deployable; protected; merges only via reviewed PRs.
- `develop` — integration branch for the current phase's work (optional once the team is a single developer, but the convention is defined now for when it isn't).
- Feature branches: `feature/<module-name>/<short-description>` (e.g. `feature/market-data/ohlcv-ingest`).
- Fix branches: `fix/<module-name>/<short-description>`.
- Architecture/docs-only changes: `docs/<short-description>`.
- Every PR references the phase and module it belongs to in its description.
- No direct commits to `main`.

## 18. Future Phases

| Phase | Scope |
|---|---|
| 0 | Architecture, repo scaffolding, environment setup (current phase — this doc) |
| 1 | Auth (Clerk) + `market_data` module + stock detail page with TradingView chart |
| 2 | `quant_engine`: technical indicators + first ML model (screener/ranking) |
| 3 | `ai_assistant`: LLM research chat, RAG over news/filings |
| 4 | `broker` module: Zerodha read-only integration |
| 5 | Alerts, watchlists, user personalization |
| 6 | Broker write access (gated order placement) |
| 7 | Billing/subscription tiers, public launch hardening |

## 19. Rules Every Future AI Response Must Follow

1. Read this file (and the architecture doc) before generating anything for this project.
2. Never rebuild or restructure the project from scratch — always extend what exists.
3. Keep every new file compatible with existing files and this document's conventions.
4. Before generating code, explain what is being built and where the file belongs in the folder structure.
5. Follow Clean Architecture layering strictly — no shortcuts that skip `domain`/`application`.
6. Keep every module scalable and designed to connect with modules planned in Section 18.
7. Use the exact tech stack in Section 5 — no silent substitutions.
8. Follow the naming conventions in Section 16 without exception.
9. Any deviation from this document must be called out explicitly and, ideally, result in this document being updated.
10. When ambiguity exists, prefer the option most consistent with what's already been built, not the most "interesting" option.

## 20. Things the AI Must NEVER Do

- Never generate a full rewrite of an existing module "for cleanliness" — extend or refactor incrementally with a stated reason.
- Never introduce a new frontend UI library, state manager, or backend framework outside Section 5's stack without flagging it as a decision to confirm first.
- Never bypass the `api → application → domain` dependency rule (e.g. no direct DB calls from a route handler).
- Never place secrets, API keys, or tokens directly in code or commit them to the repo.
- Never enable broker order-placement (write access) casually — it is a gated, explicitly-opt-in capability (Phase 6) requiring confirmation UX and audit logging.
- Never fabricate financial data, model performance numbers, or backtest results — if data isn't available, say so.
- Never present AI/model output as guaranteed financial advice — the platform produces research and signals, not guarantees, and UI copy must never imply certainty the model doesn't have.
- Never skip explaining where a generated file belongs in the folder structure.
- Never silently drop or ignore one of the rules in Section 19.

## 21. Definition of Done for Every Feature

A feature is done only when:
- It follows the Clean Architecture layering for its module.
- It has typed request/response contracts (Pydantic backend, generated types frontend).
- It has unit tests for `domain`/`application` logic and at least one integration test for its `api` endpoint(s).
- It handles and surfaces errors using the shared error-response shape (Section 14).
- It has no hardcoded secrets/URLs and reads config via `core/config.py` (backend) or environment variables (frontend).
- UI states are complete: loading, empty, error, and populated — not just the "happy path."
- It's been explained (what it does, where its files live) before being considered complete — not just delivered as raw code.
- It doesn't break any previously working module or page.

## 22. Code Quality Checklist

- [ ] Passes `black` + `ruff` (Python) / `eslint` + `prettier` (TypeScript) with zero warnings
- [ ] No `any` types without justification; no bare `except:`
- [ ] No logic leaked into route handlers or page components
- [ ] Functions are small and single-purpose; no god files
- [ ] Naming follows Section 16 conventions
- [ ] No dead code or commented-out blocks left in
- [ ] Docstrings/comments explain "why," not "what"

## 23. Performance Checklist

- [ ] Hot-path reads (live prices) go through Redis cache, not direct Postgres hits every time
- [ ] Database queries use indexes appropriate to their schema; no unbounded `SELECT *` on large tables
- [ ] Frontend data fetching uses React Query caching/deduping, not redundant fetches
- [ ] Heavy ML/LLM calls run async via the worker/queue, never blocking the request-response cycle
- [ ] Pagination applied to all list endpoints that can grow unbounded
- [ ] Charting components avoid unnecessary re-renders (memoization where appropriate)

## 24. Security Checklist

- [ ] Every protected endpoint verifies the Clerk JWT server-side
- [ ] All external input validated via Pydantic at the API boundary
- [ ] No secrets or tokens in code, logs, or version control
- [ ] Broker tokens encrypted at rest and scoped per-user
- [ ] Order-placement (write) paths are behind an explicit, separately gated permission
- [ ] Dependency versions current; no known critical CVEs in use
- [ ] Error responses never leak stack traces or internal details to the client

## 25. Testing Checklist

- [ ] Unit tests cover `domain` and `application` layers for the feature
- [ ] Integration test covers at least the primary `api` endpoint happy path and one failure path
- [ ] Frontend: critical interactive components have at least basic rendering/interaction tests
- [ ] No test relies on live external services (OpenAI, Kite, etc.) — mocked/stubbed in tests
- [ ] CI passes fully before merge to `main`

## 26. Deployment Checklist

- [ ] Builds successfully in CI (lint, type-check, test, build) before merge
- [ ] Environment variables confirmed present in Vercel/Railway for the target environment
- [ ] Database migrations applied and reversible
- [ ] Preview deploy verified before merging to `main`
- [ ] No breaking change to `/api/v1` without a version bump or explicit migration plan
- [ ] Rollback plan exists (previous Docker image/tag or Vercel deployment can be restored)

## 27. Future Expansion Plan

Beyond Phase 7, the architecture is designed to support (not yet scoped in detail — to be designed when reached, following the same process as this document):
- Extraction of any backend module (e.g. `quant_engine`, `ai_assistant`) into an independently deployed service if load demands it — enabled by the existing clean module boundaries and schema separation.
- Additional data sources beyond Zerodha (other brokers, alternative data providers) — isolated behind the same adapter pattern used for Kite Connect.
- Mobile app (React Native or similar) reusing the same FastAPI backend and shared-types package.
- Public API product (third-party developers building on AlphaEdge AI's signals/research) — versioned API and auth model already support this.
- Model registry maturation (from metadata-in-Postgres to a dedicated registry/MLOps pipeline) as the number of models grows.
- Internationalization/multi-exchange support, if expanding beyond NSE/BSE.

---

*This file must be kept up to date. Any future architectural decision, new module, or standards change gets reflected here — this document is never allowed to drift out of sync with the actual project.*
