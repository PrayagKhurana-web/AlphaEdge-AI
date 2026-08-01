# AlphaEdge Intelligence — Phase 3

## Goal

Transform AlphaEdge from a normal stock-analysis dashboard into a
probability-based stock intelligence platform.

## Major Features

1. AlphaEdge Pulse
   - Predict next-session direction
   - Predict 5-session direction
   - Predict 20-session direction
   - Bullish and bearish probabilities
   - Expected price range
   - Confidence score
   - Invalidation level
   - Walk-forward backtesting

2. Multibagger Radar
   - Rank stocks for 3–5 year growth potential
   - Growth, profitability, valuation and risk features
   - Explainable potential score
   - Probability of high-growth regime
   - Risk flags and confidence

3. Portfolio Copilot
   - Zerodha Kite account connection
   - Holdings and positions import
   - Entry-price-aware analysis
   - Portfolio risk and exposure
   - Signal tracking
   - No automatic order placement in the first version

4. Mobile Experience
   - Fully responsive interface
   - Installable PWA
   - Mobile alerts and portfolio view

## Prediction Engine Milestones

1. Historical dataset builder
2. Feature engineering pipeline
3. Outcome labels
4. Baseline logistic-regression model
5. Random Forest and XGBoost comparison
6. Walk-forward validation
7. Model metrics and calibration
8. Prediction API
9. Prediction UI
10. Signal outcome tracking

## Initial Prediction Horizons

- Next trading session
- 5 trading sessions
- 20 trading sessions

## Initial Labels

A prediction is based on future percentage return:

- Bullish: future return above positive threshold
- Neutral: future return within neutral range
- Bearish: future return below negative threshold

Thresholds will be volatility-aware and tested through backtesting.

## Safety Rules

- Never describe predictions as guaranteed.
- Always show model probability and confidence.
- Always show model version and evaluation metrics.
- Avoid look-ahead bias and data leakage.
- Use chronological walk-forward validation.
- Include transaction costs in strategy testing.
