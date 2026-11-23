# Orchestra Production Deployment & Operations Runbook

This guide is the authoritative operational runbook for deploying, configuring, monitoring, maintaining, and disaster-recovering the Orchestra Multi-Agent AI Platform in production environments using containerized topologies.

---

## 1. System Requirements & Architecture Overview

Orchestra is designed for single-node containerized deployment via Docker Compose, running all core platform services in an isolated, defense-in-depth network topology behind an unprivileged reverse proxy.

### Minimum Hardware Requirements
- **CPU:** 4 vCPUs (x86_64 / amd64 architecture)
- **RAM:** 8 GB memory (16 GB recommended for high document ingestion loads)
- **Disk:** 30 GB SSD storage (plus capacity for persistent document and vector storage)
- **OS:** Linux (Ubuntu 22.04 LTS / Debian 12 / RHEL 9 recommended) or Windows Server 2022 with Docker Desktop and WSL 2

### Software Prerequisites
- **Docker Engine:** $\ge 24.0.0$
- **Docker Compose:** v2.20.0 or later (`docker compose version`)
- **Host Firewall:** Only port `8080` (or external TLS proxy `443`) should be exposed to public or ingress networks. Internal stateful ports (`5432`, `6379`, `6333`) are strictly isolated within the internal `orchestra_data` network.

### Architectural Service Topology
```
                          [ Public Ingress / Host Traffic ]
                                         │
                                         ▼ (Port 8080 / Edge Network)
                         ┌───────────────────────────────┐
                         │    orchestra-reverse-proxy    │
                         │ (Nginx unprivileged 1.27-alp) │
                         └───────┬───────────────┬───────┘
                                 │               │
            Static & HTML Routes │               │ API Routes (/auth, /projects, /health)
                                 ▼               ▼
                     ┌──────────────────┐ ┌──────────────────┐
                     │orchestra-frontend│ │orchestra-backend │
                     │(Node 22 / NextJS)│ │(Python 3.13 / UV)│
                     └──────────────────┘ └────────┬─────────┘
                                                   │
                      Internal Network Isolation   ▼
            ┌──────────────────────────────────────┴──────────────────────────────────────┐
            │                     orchestra_data (Internal Bridge)                        │
            ├──────────────────────────┬──────────────────────────┬───────────────────────┤
            │                          │                          │                       │
            ▼                          ▼                          ▼                       ▼
┌───────────────────────┐  ┌───────────────────────┐  ┌───────────────────────┐  ┌────────────────┐
│  orchestra-postgres   │  │    orchestra-redis    │  │   orchestra-qdrant    │  │ orchestra-migr │
│     (PostgreSQL 16)   │  │    (Redis 7 Alpine)   │  │    (Qdrant 1.12)      │  │  (One-shot DDL)│
└───────────────────────┘  └───────────────────────┘  └───────────────────────┘  └────────────────┘
```

---

## 2. Environment Configuration

All deployment settings are managed via environment variables passed to Docker Compose.

### Step 1: Initialize Configuration from Template
```bash
cp .env.example .env
chmod 600 .env
```

### Step 2: Configure Mandatory Production Secrets
Generate cryptographically strong random secrets for production before starting the platform:

```bash
# Generate 64-character hex keys for secrets:
python -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_hex(24))"
python -c "import secrets; print('REDIS_PASSWORD=' + secrets.token_hex(24))"
python -c "import secrets; print('JWT_SECRET=' + secrets.token_hex(32))"
```

### Environment Variable Reference

| Variable | Type | Default | Required in Production | Description |
| :--- | :--- | :--- | :---: | :--- |
| `ENVIRONMENT` | string | `production` | Yes | Enforces production runtime security assertions |
| `ORCHESTRA_PORT` | integer | `8080` | No | Public host port mapped to the reverse proxy |
| `POSTGRES_DB` | string | `orchestra` | Yes | Production database name |
| `POSTGRES_USER` | string | `postgres` | Yes | Database administrative user |
| `POSTGRES_PASSWORD` | string | — | **YES** | Strong database password (no default permitted) |
| `REDIS_PASSWORD` | string | — | **YES** | Strong Redis authentication password |
| `JWT_SECRET` | string | — | **YES** | Cryptographic secret for signing tokens ($\ge 32$ chars) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | integer | `30` | No | Access token expiration lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | integer | `7` | No | Refresh token rotation lifetime |
| `COOKIE_SECURE` | boolean | `true` | Yes (for TLS) | Enforces `Secure` flag on HttpOnly session cookies |
| `LLM_PROVIDER` | string | `openai_compatible` | Yes | Active LLM provider family |
| `LLM_API_KEY` | string | — | **YES** | API key for LLM inference |
| `LLM_BASE_URL` | string | `https://api.openai.com/v1` | Yes | Base URL for LLM chat completions endpoint |
| `LLM_MODEL` | string | `gpt-4o-mini` | No | Target model identifier |
| `EMBEDDING_PROVIDER` | string | `openai_compatible` | Yes | Active embedding vector provider |
| `EMBEDDING_API_KEY` | string | — | **YES** | API key for generating document embeddings |
| `EMBEDDING_BASE_URL` | string | `https://api.openai.com/v1` | Yes | Base URL for embeddings endpoint |
| `EMBEDDING_MODEL` | string | `text-embedding-3-small`| No | Target embedding model name |
| `EMBEDDING_DIMENSION` | integer | `1536` | No | Vector size (must match Qdrant collection) |
| `RATE_LIMIT_ENABLED` | boolean | `true` | Yes | Enforces request rate limits |
| `RATE_LIMIT_BACKEND` | string | `redis` | Yes | Enforces distributed Redis sliding window limiter |

> [!WARNING]
> **Vector Embedding Transition Warning:**
> Test vectors (`EMBEDDING_PROVIDER=test`) must never be mixed with real semantic embeddings (`EMBEDDING_PROVIDER=openai_compatible`). Both providers generate 1536-dimensional vectors to satisfy Qdrant's schema contract, but cosine similarity between synthetic test vectors and real embeddings is semantically invalid. When transitioning from local offline testing to production real-AI RAG, operators must purge or reindex the target Qdrant collection (`orchestra_knowledge`).

---

## 3. One-Command Boot & Initialization

To build the images and launch the complete stack:

```bash
docker compose --env-file .env up -d --build
```

### What Happens on Boot:
1. Docker Compose provisions the `orchestra_data` (internal) and `orchestra_edge` (public) networks.
2. `orchestra-postgres`, `orchestra-redis`, and `orchestra-qdrant` spin up and pass internal health checks.
3. The `orchestra-migration` service executes Alembic DDL migrations (`alembic upgrade head`) and exits with code 0.
4. Once migrations succeed, `orchestra-backend` starts and performs startup lifespan validation (enforcing production security requirements).
5. `orchestra-frontend` and `orchestra-reverse-proxy` start and begin serving incoming requests.

---

## 4. Health Probes & Operational Monitoring

All health monitoring is accessible through the reverse proxy:

### Liveness Probe
Lightweight probe that verifies the reverse proxy and backend process are alive:
```bash
curl -f http://127.0.0.1:8080/health
# Expected: {"status":"healthy"}
```

### Multi-Dependency Readiness Probe
Deep probe verifying that PostgreSQL, Redis, and Qdrant are all reachable and healthy:
```bash
curl -f http://127.0.0.1:8080/health/ready
# Expected: {"status":"ready","dependencies":{"database":"healthy","redis":"healthy","qdrant":"healthy"}}
```

If any stateful dependency fails, `/health/ready` returns `HTTP 503 Service Unavailable` with details on which subsystem is degraded:
```json
{"status":"not_ready","dependencies":{"database":"healthy","redis":"unhealthy","qdrant":"healthy"}}
```

### Metrics Privacy Assurance
The internal `/metrics` endpoint is protected by Nginx and returns `HTTP 404 Not Found` to public clients. Internal scrapers (Prometheus) can scrape backend container port 8000 directly from within the `orchestra_data` network.

---

## 5. Automated Deployment Smoke Verification

Run the automated 9-stage verification suite against a running stack:

```bash
# Executable directly on host:
python scripts/test_deployment_smoke.py

# Or executed container-native:
docker compose --env-file .env run --rm backend python scripts/test_deployment_smoke.py
```

Expected output:
```
RESULT: ALL 9 DEPLOYMENT SMOKE STAGES PASSED (0 FAILURES)
```

---

## 6. Data Persistence, Backup & Disaster Recovery

Orchestra persists state across three dedicated named volumes:
1. `orchestra_pg_data`: Relational data (users, projects, documents metadata, sessions, checkpoints, evaluation runs).
2. `orchestra_qdrant_data`: Dense vector storage and HNSW indexing structures.
3. `orchestra_storage_data`: Raw uploaded document files (`.pdf`, `.md`, `.txt`).

### Backup Procedures

#### 1. PostgreSQL Database Dump
Create a clean transactional snapshot of the relational database:
```bash
docker exec -t orchestra-postgres pg_dump -U postgres orchestra | gzip > backup_orchestra_$(date +%Y%m%d_%H%M%S).sql.gz
```

#### 2. Raw Document Storage Backup
Archive raw uploaded files:
```bash
docker run --rm \
  -v multi-agent-ai-research-system_orchestra_storage_data:/data:ro \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/storage_backup_$(date +%Y%m%d_%H%M%S).tar.gz -C /data .
```

#### 3. Qdrant Vector Snapshot
Trigger an internal Qdrant collection snapshot:
```bash
docker exec orchestra-qdrant curl -s -X POST http://localhost:6333/collections/orchestra_knowledge/snapshots
```

---

## 7. Zero-Downtime Updates & Migration Protocol

When deploying new versions of Orchestra:

1. **Pull or Checkout Latest Code:**
   ```bash
   git pull origin main
   ```
2. **Build Updated Containers:**
   ```bash
   docker compose --env-file .env build
   ```
3. **Execute Database Migrations:**
   ```bash
   docker compose --env-file .env run --rm migration
   ```
4. **Perform Graceful Service Refresh:**
   ```bash
   docker compose --env-file .env up -d --no-deps backend frontend reverse-proxy
   ```
5. **Verify Stack Health:**
   ```bash
   python scripts/test_deployment_smoke.py
   ```

---

## 8. Production Docker Compose Topology (`docker-compose.prod.yml`)

For hardened production deployments, Orchestra provides `docker-compose.prod.yml`. This configuration enforces strict resource bounds, fail-closed TLS verification, and isolated networking:

```bash
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```

### Production Hardening Highlights:
- **Standard Ports:** Binds `80:80` (HTTP) and `443:443` (HTTPS).
- **Resource Constraints:**
  - `backend`: 2.0 CPUs, 2048 MB RAM limit
  - `frontend`: 2.0 CPUs, 2048 MB RAM limit
  - `postgres`, `redis`, `qdrant`: 1024 MB RAM limit each
  - `reverse-proxy`: 1.0 CPU, 512 MB RAM limit
- **Volume Isolation:** Mounts `./nginx/certs/live` as a read-only volume (`:ro`) and `/var/www/certbot` for ACME challenges.
- **Fail-Closed Container Startup:** The reverse proxy entrypoint verifies that trusted certificates exist and are non-empty before starting Nginx. If certificates are absent, the container terminates immediately with code 1.

---

## 9. Real-Domain HTTPS, Fail-Closed TLS & Let's Encrypt Flow

Orchestra enforces strict HTTPS on production domains with automated ACME HTTP-01 pass-through.

### Automated Let's Encrypt / Certbot Setup:
1. Ensure your DNS records (`A` / `CNAME`) point to the host server IP.
2. Initialize Certbot challenge directory:
   ```bash
   mkdir -p ./nginx/certs/live ./certbot_webroot
   ```
3. Issue initial certificate via Certbot webroot:
   ```bash
   certbot certonly --webroot -w ./certbot_webroot \
     -d yourdomain.com \
     --email admin@yourdomain.com --agree-tos --non-interactive
   ```
4. Link or copy the issued certificates to `./nginx/certs/live/`:
   ```bash
   cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ./nginx/certs/live/
   cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ./nginx/certs/live/
   chmod 600 ./nginx/certs/live/privkey.pem
   ```
5. Launch the production stack:
   ```bash
   docker compose -f docker-compose.prod.yml --env-file .env up -d
   ```

### Fail-Closed TLS Rules:
- If trusted certificates are missing in production (`ENVIRONMENT=production`), Nginx will **FAIL TO START**.
- **Self-signed development certificates are strictly quarantined to local development and will NEVER be loaded in production under any circumstances.**
- Automated HTTP-to-HTTPS 301 redirection is enforced on Port 80 for all production traffic, exempting only `/.well-known/acme-challenge/`.
- HSTS (`max-age=31536000; includeSubDomains`) is strictly applied to real HTTPS domains, excluding localhost and IP addresses.

---

## 10. Operational Monitoring & Observability Runbook

### Health Probes
- **Liveness:** `GET /health` returns `{"status":"healthy"}` (200 OK).
- **Readiness:** `GET /health/ready` validates PostgreSQL connection pool, Redis ping, and Qdrant cluster availability. Returns 200 OK when all dependencies are green, or 503 Service Unavailable if any service degrades.

### Internal Prometheus Scraping
The Prometheus metrics endpoint (`/metrics`) is blocked from public access at the reverse proxy (returns `HTTP 404`). Internal Prometheus collectors must scrape the backend container directly within the private network:
```bash
# Internal network scrape target:
http://orchestra-backend:8000/metrics
```

### Alert Thresholds & Operational SLOs
| Metric | Threshold | Severity | Immediate Action |
| :--- | :--- | :---: | :--- |
| HTTP 5xx Error Rate | > 1.0% over 5 min | Critical | Inspect backend logs: `docker compose logs -f backend` |
| P95 Request Latency | > 2.0s over 10 min | Warning | Inspect slow SQL queries and external LLM provider timeouts |
| Redis Memory Usage | > 80% maxmemory | Warning | Check token blacklist TTL and rate limit eviction |
| Host Disk Capacity | > 85% full | Critical | Check Qdrant snapshot storage and raw document storage |
| NVIDIA NIM Availability | Repeated 503s | Warning | Fallback to independent BM25 engages automatically; check NVIDIA API status |

---

## 11. Human-Gated Destructive Operations Protocol

> [!CAUTION]
> **Strict Destructive Safety Mandate:**
> All database downgrades, rollbacks, and restorations are **strictly human-gated**.
> Automated, unattended, or pipeline-triggered downgrades (`alembic downgrade`, `psql < backup.sql`) are strictly PROHIBITED in deployment pipelines.

If an operational recovery requiring schema or data modification is necessary, the operator must execute the following protocol in sequence:

### Step 1: Pre-Flight Verified Checksummed Backup (Mandatory)
Before executing any rollback or restore operation, create a timestamped backup and verify both file size and SHA-256 checksum:
```bash
# 1. Create transactional backup
docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U postgres -d orchestra > pre_recovery_backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Verify backup is non-empty and generate SHA-256 checksum
test -s pre_recovery_backup_*.sql && sha256sum pre_recovery_backup_*.sql
```
*If the backup file is empty (0 bytes) or fails checksum validation, STOP IMMEDIATELY. Do not proceed.*

### Step 2: Migration Compatibility & Impact Analysis
Review the specific downgrade or recovery operation:
- Document all tables, columns, or foreign keys that will be altered or dropped.
- Identify affected active user sessions or orphaned vector embeddings.
- Ensure that document files in `orchestra_storage_data` remain synchronized with relational records.

### Step 3: Explicit Human Operator Execution
Only after Steps 1 and 2 are satisfied and documented, execute the targeted operation manually:

```bash
# Manual migration downgrade to specific revision:
docker compose -f docker-compose.prod.yml exec backend alembic downgrade <target_revision>

# OR manual point-in-time restore from verified backup:
docker compose -f docker-compose.prod.yml exec -T postgres psql -U postgres -d orchestra < pre_recovery_backup_verified.sql
```

### Step 4: Post-Recovery Health & Integrity Verification
```bash
# Verify deep readiness probe
curl -f https://yourdomain.com/health/ready

# Run smoke test suite inside the container
docker compose -f docker-compose.prod.yml run --rm backend python scripts/test_deployment_smoke.py
```

---

## 12. Operational Troubleshooting Guide

### Issue: Backend reports `not_ready` with `database: unhealthy`
- Inspect PostgreSQL logs: `docker compose logs --tail=50 postgres`
- Test direct connection from backend: `docker exec -it orchestra-backend-prod python -c "import psycopg; psycopg.connect('postgresql://postgres:PASSWORD@postgres:5432/orchestra')"`
- Ensure `orchestra-postgres-prod` health status is `healthy`.

### Issue: Reverse proxy exits immediately on boot in production
- Check logs: `docker compose -f docker-compose.prod.yml logs reverse-proxy`
- If error is `FATAL: Production mode requires valid trusted TLS certificates`: verify that `./nginx/certs/live/fullchain.pem` and `./nginx/certs/live/privkey.pem` exist, have permissions readable by user 101, and are non-empty.

### Issue: Document upload fails with `413 Request Entity Too Large`
- The Nginx reverse proxy enforces a 12MB limit (`client_max_body_size 12M`) to accommodate 10MB file payloads plus boundary metadata.
- Files exceeding 10MB are rejected by design to prevent out-of-memory errors on PDF parsers.

### Issue: Requests fail with HTTP 503 during Redis restart
- Orchestra enforces a differentiated rate-limiting fail-closed policy. When Redis is unavailable, expensive routes (Auth, AI research, and code mutation) return 503 to protect system integrity, while cheap reads fail open.
- Once Redis recovers, all routes automatically resume within 5 seconds.
