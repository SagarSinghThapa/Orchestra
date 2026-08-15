from fastapi import FastAPI
from sqlalchemy import text

from app.database.connection import engine


app = FastAPI(
    title="Multi-Agent AI Research System",
    description="Platform Core API - Member 2",
    version="1.0.0",
)


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