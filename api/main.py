from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.core.config import settings
from api.core.database import close_db
from api.middleware.request_id import RequestIDMiddleware
from api.middleware.timing import TimingMiddleware
from api.routers import auth, cart, categories, health, inventory, orders, payments, products, reviews, uploads, users, websockets


@asynccontextmanager
async def lifespan(app: FastAPI):
    import pathlib
    pathlib.Path(settings.upload_dir).mkdir(exist_ok=True)
    yield
    await close_db()


import pathlib
pathlib.Path(settings.upload_dir).mkdir(exist_ok=True)

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

# Static file serving for uploaded images
app.mount(f"/{settings.upload_dir}", StaticFiles(directory=settings.upload_dir, html=False), name="uploads")

# Routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(products.router)
app.include_router(categories.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(payments.router)
app.include_router(inventory.router)
app.include_router(reviews.router)
app.include_router(uploads.router)
app.include_router(websockets.router)
app.include_router(health.router)


def start() -> None:
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
    )
