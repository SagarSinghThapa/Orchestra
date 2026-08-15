from fastapi import FastAPI

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