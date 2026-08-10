# SECURITY & REAL MONEY SAFETY SPECIFICATION

## 1. Credentials Isolation
- API keys, OAuth access tokens, and secrets are strictly managed in `.env` and loaded via `backend/app/config.py`.
- **Zero Credentials in Frontend**: Broker API secrets and private tokens never reach React or browser code.

## 2. Real Money Guardrails
- `REAL_TRADING_ENABLED=false` is enforced by default.
- Automated real-money execution by LLMs is strictly forbidden.
- Real broker order execution requires explicit human confirmation, passed backtest validation, and kill switch readiness.

## 3. API Security
- Strict CORS middleware headers.
- Input validation via Pydantic schemas.
- Backend error handling ensuring stack traces are not leaked to external clients.
