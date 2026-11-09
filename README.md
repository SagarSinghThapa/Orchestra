# Orchestra — Multi-Agent AI Research & Developer Intelligence Platform

Orchestra is an enterprise multi-agent AI engineering platform unifying deep research intelligence, codebase analysis, and autonomous developer workflows in an isolated, observable, and resilient architecture.

---

## 1. Quickstart — Containerized Deployment

Orchestra deploys as a cohesive multi-container stack via Docker Compose, including PostgreSQL 16, Redis 7, Qdrant 1.12, FastAPI backend, Next.js frontend, and an unprivileged Nginx reverse proxy.

### Prerequisites
- Docker Engine $\ge 24.0.0$
- Docker Compose v2.20.0 or later
- Git

### One-Command Boot
```bash
# 1. Clone repository
git clone https://github.com/SagarSinghThapa/Multi-Agent-AI-Research-system.git
cd Multi-Agent-AI-Research-system

# 2. Configure environment
cp .env.example .env
# Edit .env and supply mandatory secrets (POSTGRES_PASSWORD, REDIS_PASSWORD, JWT_SECRET)

# 3. Build and launch services
docker compose --env-file .env up -d --build

# 4. Verify stack readiness
curl -f http://127.0.0.1:8080/health/ready
```

Once running:
- **Frontend UI & API Gateway:** [http://127.0.0.1:8080](http://127.0.0.1:8080)
- **API Health Check:** `GET http://127.0.0.1:8080/health`
- **Readiness Probe:** `GET http://127.0.0.1:8080/health/ready`

For complete operational runbooks, backup procedures, TLS termination, and troubleshooting, see [DEPLOYMENT.md](DEPLOYMENT.md).

---

## 2. Platform Architecture

```
Client / Ingress (Port 8080)
       │
       ▼
Nginx Reverse Proxy (Unprivileged 1.27)
       │
       ├───► Next.js 16 Frontend (Node 22 Standalone)
       └───► FastAPI Backend (Python 3.13)
                 │
                 ├───► PostgreSQL 16 (Relational state & checkpoints)
                 ├───► Redis 7 (Distributed Lua rate limiting & caching)
                 └───► Qdrant 1.12 (Dense vector storage & search)
```

---

## 3. Local Development & Testing

### Backend Suites
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"

# Run unit and resilience tests
pytest tests/ -v -m "not load and not integration"

# Run integration tests (with Docker Compose dependencies up)
pytest tests/integration/ -v
```

### Frontend Suites
```bash
cd frontend
npm ci

# Linting & Typecheck
npm run lint
npx tsc --noEmit

# Vitest Component Suite
npm run test

# Production Build
npm run build
```

### End-to-End Playwright Suite
```bash
cd frontend
npm run test:e2e
```

### Automated Deployment Smoke Verification
```bash
python scripts/test_deployment_smoke.py
```

---

## 4. Documentation References

- **Production Runbook:** [DEPLOYMENT.md](DEPLOYMENT.md)
- **Member 3 Final Report:** [docs/member3/FINAL_REPORT.md](docs/member3/FINAL_REPORT.md)
- **Canonical GSD Planning:** `.gsd/`
