from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import text

from app.api.sessions import router as sessions_router
from app.api.projects import router as projects_router
from app.api.messages import router as messages_router
from app.api.documents import router as documents_router
from app.api.search import router as search_router
from app.api.research import router as research_router
from app.api.developer import router as developer_router
from app.api.orchestrator import router as orchestrator_router
from app.api.memory import router as memory_router
from app.auth.router import router as auth_router
from app.database.connection import engine, dispose_engine
from app.core.redis import init_redis_pool, close_redis_pool, get_redis_health
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Application startup: initialize Redis pool (graceful fallback)
    await init_redis_pool()
    yield
    # Application shutdown: cleanly close Redis and dispose of DB connection pool
    await close_redis_pool()
    dispose_engine()


app = FastAPI(
    title="Orchestra",
    description="Multi-Agent AI Engineering Platform API",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(documents_router)
app.include_router(search_router)
app.include_router(research_router)
app.include_router(developer_router)
app.include_router(orchestrator_router)
app.include_router(memory_router)
app.include_router(sessions_router)
app.include_router(messages_router)


@app.get("/")
def root():
    return {
        "project": "Orchestra",
        "component": "Platform Core",
        "status": "running",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/health/database")
def database_health():
    if engine is None:
        return {
            "database": "unconfigured",
            "status": "unhealthy",
            "error": "DATABASE_URL is not configured",
        }

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "database": "connected",
            "status": "healthy",
        }

    except Exception as e:
        return {
            "database": "disconnected",
            "status": "unhealthy",
            "error": str(e),
        }


@app.get("/health/redis")
async def redis_health():
    return await get_redis_health()


@app.get("/health/qdrant")
async def qdrant_health():
    if not settings.qdrant_url:
        return {
            "qdrant": "unconfigured",
            "status": "unhealthy",
        }

    try:
        from qdrant_client import AsyncQdrantClient

        client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=3.0,
        )
        await client.get_collections()
        await client.close()
        return {
            "qdrant": "connected",
            "status": "healthy",
        }
    except Exception as e:
        return {
            "qdrant": "disconnected",
            "status": "unhealthy",
            "error": str(e),
        }