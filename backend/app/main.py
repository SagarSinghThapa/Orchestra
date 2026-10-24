from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import text

from app.api.sessions import router as sessions_router
from app.api.projects import router as projects_router
from app.api.messages import router as messages_router
from app.auth.router import router as auth_router
from app.database.connection import engine
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Application startup: verify configuration without side-effect table creation
    # Database schema lifecycle is managed authoritatively via Alembic migrations
    yield
    # Application shutdown


app = FastAPI(
    title="Orchestra",
    description="Multi-Agent AI Engineering Platform API",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(projects_router)
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