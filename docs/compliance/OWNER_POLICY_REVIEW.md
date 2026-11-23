# Formal Policy & Architecture Review Checklist

**Target:** Privacy Policy (`/privacy`) and Cookie Policy (`/cookies`)  
**Platform:** Orchestra Multi-Agent AI Research & Development Platform  
**Owner:** Solo Developer / Platform Administrator  
**Governance Status:** Mandatory Pre-Publication Verification Matrix

---

## 1. Multi-Gate Publication Governance Model

To prevent accidental, automated, or unverified publication of legal and compliance disclosures:

1. **Automatic publication via environment variables alone is strictly PROHIBITED.** Setting `NEXT_PUBLIC_POLICY_PUBLISHED=true` or any similar flag without fulfilling all three gates has zero effect.
2. **Mandatory Conditions for Official Publication:**
   - **Gate 1 — Formal Owner Sign-Off:** The platform owner must review this checklist, perform manual verification, and record their signature in this document.
   - **Gate 2 — Codebase Architectural Verification:** Every factual disclosure in `/privacy` and `/cookies` must match the empirical reality of the codebase (verified below).
   - **Gate 3 — Hardcoded Approved Effective Date:** The effective date must be approved by the owner and hardcoded in the governance configuration file (`frontend/src/features/privacy/governance.ts`).
3. In all other circumstances (development, CI, unreviewed production), policies strictly display the `[DRAFT — PENDING OWNER REVIEW]` alert banner.

---

## 2. Empirical Verification Matrix

### Section 1: Platform Overview & Tenancy Isolation
| Disclosure Clause | Empirical Codebase Source | Verification Status | Notes |
| :--- | :--- | :---: | :--- |
| Project-scoped tenancy isolation | `backend/app/api/documents.py` (`get_user_project`)<br/>`backend/app/api/search.py`<br/>`backend/app/api/sessions.py` | VERIFIED | All resource lookups validate `owner_id == current_user.id` or 404 (IDOR defense). |
| Zero third-party ad networks or tracking | `frontend/src/app/layout.tsx`<br/>`frontend/package.json` | VERIFIED | No Google Analytics, Meta Pixel, Hotjar, or ad scripts present. |
| Zero selling of user data | Repository architecture | VERIFIED | No data export pipelines or third-party marketing webhooks. |

### Section 2: Data Categories & Storage Infrastructure
| Disclosure Clause | Empirical Codebase Source | Verification Status | Notes |
| :--- | :--- | :---: | :--- |
| Passlib bcrypt password hashing | `backend/app/auth/security.py` (`pwd_context = CryptContext(schemes=["bcrypt"])`) | VERIFIED | Passwords never stored in plaintext. |
| PostgreSQL 16 relational storage | `docker-compose.yml`<br/>`backend/app/models/` | VERIFIED | Users, projects, documents metadata, sessions, messages, and evaluations in PostgreSQL. |
| Redis 7 token revocation & rate limiting | `backend/app/auth/jwt.py`<br/>`backend/app/core/rate_limit.py` | VERIFIED | Distributed token blacklist on logout; sliding window rate limiting. |
| Qdrant 1.12 vector embedding storage | `backend/app/research/vectorstore/qdrant.py` | VERIFIED | Chunks indexed in collection `orchestra_knowledge` with strict payload filters (`project_id`). |

### Section 3: Third-Party AI Sub-Processors
| Disclosure Clause | Empirical Codebase Source | Verification Status | Notes |
| :--- | :--- | :---: | :--- |
| NVIDIA NIM Inference (`https://integrate.api.nvidia.com/v1`) | `backend/app/research/embeddings/nvidia.py` | VERIFIED | Nemotron 3.5 Embed 1B embeddings; bounded retry with Retry-After handling. |
| OpenAI-compatible API providers | `backend/app/research/llm/openai.py`<br/>`backend/app/research/embeddings/openai.py` | VERIFIED | Configurable external LLM endpoint; API keys scrubbed from exception logs. |
| Operator-configured LangSmith tracing | `backend/app/core/config.py` (`langsmith_tracing`) | VERIFIED | Optional server-side tracing; never triggered by client cookies. |

### Section 4: Data Retention, Vector Purging & Cascade Deletion
| Disclosure Clause | Empirical Codebase Source | Verification Status | Notes |
| :--- | :--- | :---: | :--- |
| Immediate logout token revocation | `backend/app/api/auth.py` (`/auth/logout`) | VERIFIED | Access and refresh tokens blacklisted in Redis with TTL matching remaining lifetime. |
| Document vector purging upon deletion | `backend/app/api/documents.py` (`delete_document`) | VERIFIED | Removes Qdrant points by `document_id` filter and deletes storage disk payload. |
| Project cascade deletion | `backend/app/database/base.py`<br/>`backend/app/models/project.py` | VERIFIED | Deleting a project cascades to sessions, messages, documents, and vectors. |

### Section 5: Cookie & Storage Inventory
| Technology | Name | Lifetime | Security Attributes | Purpose | Codebase Reference |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Cookie | `access_token` | 15–30 min | `HttpOnly`, `SameSite=Lax`, `Secure` (prod) | Short-lived API authorization | `backend/app/api/auth.py` |
| Cookie | `refresh_token` | 7 days | `HttpOnly`, `SameSite=Lax`, `Secure` (prod) | Silent session extension | `backend/app/api/auth.py` |
| Cookie | `csrf_token` | Session | `SameSite=Lax`, `Secure` (prod) | CSRF double-submit defense | `backend/app/api/auth.py` |
| LocalStorage | `orchestra_selected_project_id` | Persistent | Client-side only | Active workspace UI continuity | `frontend/src/context/ProjectContext.tsx` |
| LocalStorage | `orchestra_cookie_consent` | 1 year | Client-side only | User cookie preference recording | `frontend/src/features/privacy/PrivacyContext.tsx` |

---

## 3. Owner Sign-Off & Status Declaration

```markdown
Reviewer: [Platform Owner / Solo Developer]
Review Date: Pending Formal Pre-Release Review
Verification Verdict: [DRAFT — PENDING OWNER REVIEW]
Approved Effective Date: None (Draft Status)
```

Until the declaration above is completed and the governance configuration updated, the platform enforces `[DRAFT — PENDING OWNER REVIEW]` banners across all privacy touchpoints.
