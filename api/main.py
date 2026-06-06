from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.core.config import settings
from api.core.database import close_db
from api.middleware.request_id import RequestIDMiddleware
from api.middleware.timing import TimingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_db()


app = FastAPI(
    title="FastAPI E-commerce Benchmark",
    description="Async e-commerce API for LAN load testing",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Middleware — order matters: outermost runs first on request, last on response
app.add_middleware(TimingMiddleware)
app.add_middleware(RequestIDMiddleware)


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok", "environment": settings.environment}


def start() -> None:
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
    )
