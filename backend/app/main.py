from app.api.sessions import router as sessions_router
from app.api.projects import router as projects_router
from fastapi import FastAPI
from sqlalchemy import text
from app.auth.router import router as auth_router
from app.database.base import Base
from app.database.connection import engine
from app.models.user import User

app = FastAPI(
    title="Multi-Agent AI Research System",
    description="Platform Core API - Member 2",
    version="1.0.0",
)
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(sessions_router)
Base.metadata.create_all(bind=engine)

@app.get("/")
def root():
    return {
        "project": "Multi-Agent AI Research System",
        "component": "Platform Core",
        "member": "Member 2",
        "status": "running",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/health/database")
def database_health():
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