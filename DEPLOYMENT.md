# DEPLOYMENT & ENVIRONMENT SETUP SPECIFICATION

## 1. Local Environment Requirements
- Python 3.11 or greater
- Node.js 18 or greater (with npm)
- Optional: PostgreSQL 14+ with TimescaleDB extension, Redis 6+

## 2. Installation & Launch Steps

1. **Clone repository & prepare configuration**:
   ```bash
   cp .env.example .env
   ```

2. **Backend Setup**:
   ```bash
   pip install -r backend/requirements.txt
   uvicorn backend.app.main:app --reload --port 8000
   ```

3. **Frontend Setup**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

4. **Production Build**:
   ```bash
   cd frontend
   npm run build
   ```

## 3. Health Endpoints
- Backend API: `http://localhost:8000/health`
- Live Data Feed: `http://localhost:8000/health/data-feed`
- Database: `http://localhost:8000/health/database`
