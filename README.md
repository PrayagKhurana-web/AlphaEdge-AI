<div align="center">

# AlphaEdge AI

**AI-assisted stock analysis for Indian markets — quant signals, ML forecasting, and natural-language research, in one platform.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](#license)
[![Status](https://img.shields.io/badge/status-architecture%20phase-orange)](#project-status)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](#contributing)

[Project Vision](#vision) · [Features](#features-planned) · [Architecture](#architecture-overview) · [Tech Stack](#tech-stack) · [Contributing](#contributing) · [Disclaimer](#disclaimer)

</div>

---

## Project Overview

**AlphaEdge AI** is an open, production-grade platform that gives retail investors and traders in Indian markets (NSE/BSE) the kind of research tooling usually locked behind institutional terminals — live and historical charting, quantitative signal generation, machine-learning-based forecasting, direct broker integration via Zerodha, and a natural-language AI research assistant that explains *why* a signal fired, not just that it did.

It's built module by module, phase by phase, on a Clean Architecture foundation designed to scale from a single-developer project to a platform that can serve real users with real brokerage accounts — without ever requiring a rewrite along the way.

This repository's permanent source of truth for architecture, standards, and rules is [`PROJECT_CONTEXT.md`](./PROJECT_CONTEXT.md). If anything in this README and that file ever conflict, `PROJECT_CONTEXT.md` wins.

## Project Status

> 🏗️ **Architecture phase.** No application code has shipped yet. The system design, folder structure, and engineering standards are finalized; implementation begins at Phase 1 (see [Future Roadmap](#future-roadmap)).

## Vision

Most retail traders in India stitch together a broker app, a charting tool, a spreadsheet, and scattered news to make a single decision. AlphaEdge AI's vision is to unify that workflow into one coherent product — combining classical technical analysis, modern ML-based forecasting (XGBoost/LightGBM), and LLM-powered research (OpenAI/HuggingFace) so that a serious retail investor can research, understand, and act, all in one place, without needing an institutional budget to do it.

Long-term, AlphaEdge AI aims to:
- Connect real portfolios (via Zerodha Kite Connect) to the same research tools used to evaluate new ideas.
- Make model output *understandable* — a signal is only useful if a user knows why it exists.
- Grow as a modular platform where every capability — screening, forecasting, alerts, broker sync — is independently scalable.
- Eventually support optional, heavily-gated automated execution, only once the platform and its compliance posture are mature.

## Features Planned

| Feature | Description | Status |
|---|---|---|
| 📈 Live & historical charting | TradingView-powered charts for NSE/BSE symbols | Planned — Phase 1 |
| 🔐 Authentication | Secure sign-up/sign-in via Clerk | Planned — Phase 1 |
| 🧮 Quant screener | Technical indicators + ML-based ranking (XGBoost/LightGBM) | Planned — Phase 2 |
| 🤖 AI research assistant | Natural-language Q&A over stocks, sectors, filings, and news | Planned — Phase 3 |
| 🏦 Broker integration | Zerodha Kite Connect — holdings/positions sync (read-only first) | Planned — Phase 4 |
| 🔔 Alerts | Price and signal-based alerting | Planned — Phase 5 |
| ⚙️ Gated order placement | Opt-in, audited, automated execution | Planned — Phase 6 |
| 💳 Subscription tiers | Billing for premium research/features | Planned — Phase 7 |

See [`PROJECT_CONTEXT.md § 18`](./PROJECT_CONTEXT.md#18-future-phases) for the full phase breakdown.

## Architecture Overview

AlphaEdge AI is a **Clean Architecture, modular monolith**, built inside a single monorepo, designed so that any backend module can be extracted into its own service later without a rewrite.

```
┌─────────────────────────────┐
│   Next.js frontend (Vercel) │
└──────────────┬──────────────┘
               │ REST + WebSocket
┌──────────────▼──────────────┐
│   FastAPI backend (Railway) │
│  ┌────────┬────────┬──────┐ │
│  │ market │ quant  │ ai   │ │   ...and more domain modules,
│  │ _data  │ engine │asst. │ │   each following the same
│  └────────┴────────┴──────┘ │   domain → application →
└──────────────┬──────────────┘   infrastructure/api layering
               │
┌──────────────▼──────────────┐
│  PostgreSQL (+pgvector)     │
│  + Redis (cache/queue)      │
└──────────────────────────────┘
```

Every backend module follows the same four layers — `domain` (pure business logic), `application` (use cases, ports), `infrastructure` (DB/external API adapters), `api` (FastAPI routers) — so the codebase stays predictable as it grows. Full detail lives in [`docs/architecture/AlphaEdge-AI-Architecture.md`](./docs/architecture/AlphaEdge-AI-Architecture.md).

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js · React · TypeScript · TailwindCSS · shadcn/ui |
| **Backend** | FastAPI · Python |
| **Database** | PostgreSQL (+ `pgvector`) · Redis |
| **Auth** | Clerk |
| **Charts** | TradingView |
| **Broker** | Zerodha Kite Connect API |
| **AI / ML** | OpenAI · HuggingFace · Scikit-learn · XGBoost · LightGBM |
| **Deployment** | Docker · GitHub Actions · Vercel · Railway |

The stack is intentionally fixed — see [`PROJECT_CONTEXT.md § 5`](./PROJECT_CONTEXT.md#5-complete-tech-stack) for the policy on introducing new technologies.

## Folder Structure

```
alphaedge-ai/
├── apps/
│   ├── web/              # Next.js frontend (App Router)
│   └── api/               # FastAPI backend, organized by Clean Architecture modules
├── packages/
│   ├── shared-types/       # Types generated from the OpenAPI spec, shared by the frontend
│   └── ui/                 # Shared component library (future)
├── infra/
│   ├── docker/              # Dockerfiles, docker-compose
│   ├── github/               # CI/CD workflows
│   └── railway/               # Railway service configs
├── docs/
│   ├── architecture/           # Architecture doc + ADRs
│   └── api/                     # OpenAPI spec exports
├── PROJECT_CONTEXT.md            # Permanent source of truth for this project
└── README.md                      # You are here
```

Full detail, including the internal structure of each backend module, is in [`PROJECT_CONTEXT.md § 7`](./PROJECT_CONTEXT.md#7-folder-structure).

## Installation Roadmap

> ⚠️ Placeholder — real setup instructions land once Phase 1 implementation begins. This section documents the *intended* shape of local setup so contributors know what's coming.

```bash
# (planned — not yet functional)
git clone https://github.com/<org>/alphaedge-ai.git
cd alphaedge-ai

# Backend
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in Clerk, OpenAI, Kite Connect keys, etc.
uvicorn app.main:app --reload

# Frontend
cd apps/web
npm install
cp .env.example .env.local
npm run dev

# Full stack, containerized
docker compose up
```

Once Phase 1 lands, this section will be replaced with verified, tested setup steps, including database migrations and seed data.

## Development Workflow

1. **Read [`PROJECT_CONTEXT.md`](./PROJECT_CONTEXT.md) before starting any work** — it's the standing reference for architecture, conventions, and rules.
2. Pick up work scoped to the current phase (see [Future Roadmap](#future-roadmap)) — features aren't pulled forward out of order without a documented reason.
3. Branch from `main` using the naming convention in `PROJECT_CONTEXT.md § 17` (e.g. `feature/market-data/ohlcv-ingest`).
4. Build inside the existing module structure — new backend logic lives in `apps/api/app/modules/<module>/`, following the `domain → application → infrastructure/api` layering; new frontend features live in `apps/web/app/`.
5. Write tests alongside the feature (see the [Testing Checklist](#testing-checklist) in `PROJECT_CONTEXT.md`).
6. Open a PR against `main`, referencing the phase and module. CI (lint, type-check, test, build) must pass.
7. At least one review before merge. No direct commits to `main`.

## Coding Standards

- **Python:** PEP 8, full type hints, Pydantic for all data contracts, `black` + `ruff` enforced in CI.
- **TypeScript:** strict mode, no unjustified `any`, named exports only, `eslint` + `prettier` enforced in CI.
- Business logic lives in `domain`/`application` (backend) or `lib`/`hooks` (frontend) — never in route handlers or page components.
- Small, single-responsibility functions; no god files; comments explain *why*, not *what*.
- UI: shadcn/ui + Tailwind only, dark-mode-first, data-forward — not a generic SaaS template look.

The complete, authoritative standards — including naming conventions, API standards, and security standards — are in [`PROJECT_CONTEXT.md §§ 12–16`](./PROJECT_CONTEXT.md#12-coding-standards).

## Future Roadmap

| Phase | Scope |
|---|---|
| **0** | Architecture, repo scaffolding, standards (current) |
| **1** | Auth + `market_data` module + stock detail page with TradingView chart |
| **2** | `quant_engine`: technical indicators + first ML model |
| **3** | `ai_assistant`: LLM research chat, RAG over news/filings |
| **4** | `broker` module: Zerodha read-only integration |
| **5** | Alerts, watchlists, personalization |
| **6** | Broker write access — gated order placement |
| **7** | Billing/subscription tiers, public launch hardening |

Beyond Phase 7: module extraction into independent services as needed, additional broker/data-source support, a mobile app, and a public API product. See [`PROJECT_CONTEXT.md § 27`](./PROJECT_CONTEXT.md#27-future-expansion-plan) for detail.

## Contributing

AlphaEdge AI is intended to grow into a community-driven open-source project. Contributions are welcome once implementation begins, with a few standing rules:

- **Read `PROJECT_CONTEXT.md` first** — every contribution must be consistent with the architecture and standards defined there.
- **Extend, don't rewrite.** No PR should restructure or "clean up" an existing module without a clearly stated reason and scope.
- **Stay in scope.** Features are built in the phase they're planned for (see the roadmap above) unless there's a specific reason to pull work forward.
- **Follow the module pattern.** New backend modules follow the same `domain → application → infrastructure/api` layering as existing ones; no exceptions.
- **Tests are not optional.** PRs without tests for new logic won't be merged.
- **One clear PR, one clear purpose.** Reference the phase and module in your PR description.

A full `CONTRIBUTING.md` with issue templates, PR templates, and a code of conduct will be added once the repository opens for external contributions.

## License

This project is licensed under the **MIT License** — see the `LICENSE` file for details (to be added at Phase 1). Use of this software does not constitute a financial relationship with its contributors, and third-party services it integrates with (Zerodha, OpenAI, Clerk, etc.) are governed by their own respective terms.

## Disclaimer

**AlphaEdge AI provides research, quantitative signals, and probability-based insights — not guaranteed investment advice.**

Nothing produced by this platform (technical indicators, ML model outputs, screener rankings, or AI-generated explanations) should be interpreted as a certainty, a recommendation to buy or sell any security, or a substitute for independent judgment or advice from a SEBI-registered investment advisor. All models are probabilistic and can be wrong; past performance and backtested results do not guarantee future outcomes. Trading and investing in equity and commodity markets carries risk, including the risk of loss of capital. Users are solely responsible for their own investment decisions.

---

<div align="center">

Built with a Clean Architecture, phase-by-phase approach — see [`PROJECT_CONTEXT.md`](./PROJECT_CONTEXT.md) for the full engineering source of truth.

</div>
