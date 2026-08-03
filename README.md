# AlphaEdge AI

Explainable Indian stock-market intelligence for research, portfolio tracking, technical analysis, probabilistic forecasting, and long-term screening.

## Project status

AlphaEdge AI v1.0 is feature-complete for the defined personal-use scope.

Validated release baseline:

- 71 backend tests passing
- frontend ESLint passing
- Next.js production build passing
- installable PWA manifest and icons
- offline fallback page
- JWT authentication
- user-isolated watchlist and portfolio data
- no tracked `.env` secrets

## Features

### Market research
- NSE and BSE stock search
- market-index and stock quotes
- historical price data
- company fundamentals
- annual and quarterly financial statements
- financial-data freshness indicators

### Technical and financial intelligence
- SMA, EMA, RSI, MACD, Bollinger Bands, ATR, and volume analysis
- support and resistance levels
- deterministic technical signals
- financial-health scoring and observations
- explainable combined stock outlook
- ranked AlphaEdge Top Picks

### AlphaEdge Pulse
- bearish, neutral, and bullish probabilities
- 1-session, 5-session, and 20-session horizons
- chronological holdout evaluation
- walk-forward evaluation
- confidence score and model metadata

Pulse is a research baseline, not a guaranteed forecasting system.

### Multibagger Radar
- single-stock Multibagger Potential analysis
- ranked configured stock universe
- growth, financial strength, valuation, momentum, risk, and data-completeness scores
- positive, neutral, and negative observations
- cached and concurrency-limited screening

The Multibagger score is a deterministic screening framework, not a promise of future returns.

### Personal account features
- email/password registration and login
- JWT session restoration
- personal watchlist
- personal portfolio
- invested value, current value, profit/loss, returns, and allocation metrics
- user-level data isolation

### Progressive Web App
- installable manifest
- mobile and desktop icons
- standalone display mode
- offline fallback
- service worker for static assets
- responsive layout

Live market, authentication, portfolio, and prediction API responses are not cached by the service worker.

## Technology stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4, Recharts |
| Backend | FastAPI, Python 3.12, Pydantic |
| Database | MySQL with asynchronous SQLAlchemy access |
| Authentication | JWT bearer authentication |
| Market data | Yahoo Finance-compatible providers |
| Machine learning | Scikit-learn baseline classification |
| Testing | Pytest, pytest-asyncio, HTTPX |
| Quality | ESLint, TypeScript production build, GitHub Actions |
| Application format | Progressive Web App |

## Architecture

AlphaEdge AI is a modular monolith using Clean Architecture principles.

Backend modules separate:

```text
domain
application
infrastructure
api
```

Repository structure:

```text
AlphaEdge-AI/
â”œâ”€â”€ backend/
â”‚   â”œâ”€â”€ app/
â”‚   â”‚   â”œâ”€â”€ core/
â”‚   â”‚   â”œâ”€â”€ db/
â”‚   â”‚   â”œâ”€â”€ modules/
â”‚   â”‚   â””â”€â”€ main.py
â”‚   â””â”€â”€ tests/
â”œâ”€â”€ frontend/
â”‚   â”œâ”€â”€ public/
â”‚   â””â”€â”€ src/
â”‚       â”œâ”€â”€ app/
â”‚       â”œâ”€â”€ auth/
â”‚       â”œâ”€â”€ components/
â”‚       â””â”€â”€ services/
â”œâ”€â”€ docs/
â”œâ”€â”€ PROJECT_CONTEXT.md
â””â”€â”€ README.md
```

## Local setup

### Requirements
- Python 3.12
- Node.js and npm
- MySQL Server
- Git

### Clone
```powershell
git clone https://github.com/PrayagKhurana-web/AlphaEdge-AI.git
cd AlphaEdge-AI
```

### Backend
```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Backend URL: `http://127.0.0.1:8000`

API docs: `http://127.0.0.1:8000/docs`

### Frontend
```powershell
cd frontend
npm install
Copy-Item .env.example .env.local
npm run dev
```

Frontend URL: `http://localhost:3000`

## Testing

Backend:
```powershell
cd backend
.venv\Scripts\python.exe -m pytest -q
```

Expected v1 baseline: `71 passed`

Frontend:
```powershell
cd frontend
npm run lint
npm run build
```

## Security notes
- Never commit `.env` or `.env.local`.
- Use a random JWT secret of at least 32 characters.
- Configure only trusted frontend origins.
- Use HTTPS in production.
- Portfolio and watchlist operations require authentication.
- Brokerage credentials and automatic trading are not part of v1.

## Known limitations
- Third-party market data may be delayed, incomplete, or unavailable.
- Prediction output uses a baseline historical-price model.
- Rankings screen a configured universe, not every Indian security.
- No brokerage integration or order execution.
- No notifications or billing.
- Offline mode provides a fallback, not offline live-market data.

## Roadmap after v1
- improved prediction models
- larger configurable stock universe
- alerts and notifications
- richer portfolio analytics
- production deployment and monitoring
- additional market-data providers
- optional premium features

## License

This project is licensed under the MIT License.

## Disclaimer

AlphaEdge AI is an informational and educational research platform.

Nothing produced by the platformâ€”including technical signals, financial-health scores, probability outputs, Top Picks, Multibagger rankings, or explanatory observationsâ€”constitutes investment advice, a buy or sell recommendation, or a guarantee of future performance.

Market data can be delayed or inaccurate. Models and rules can be wrong. Investing and trading involve the risk of partial or complete capital loss. Users are solely responsible for their decisions and should consult a SEBI-registered investment adviser when appropriate.
