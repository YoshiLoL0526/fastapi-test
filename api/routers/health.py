import os
import time

from fastapi import APIRouter
from sqlalchemy import text

from api.core.database import AsyncSessionLocal, engine
from api.core.dependencies import AdminUser

router = APIRouter(prefix="/health", tags=["health"])

_start_time = time.time()


@router.get("/")
async def health_check():
    db_ok = False
    db_latency_ms = None
    try:
        t0 = time.perf_counter()
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        db_ok = True
    except Exception:
        pass

    return {
        "status": "ok" if db_ok else "degraded",
        "database": {"connected": db_ok, "latency_ms": db_latency_ms},
        "uptime_seconds": round(time.time() - _start_time, 1),
    }


@router.get("/metrics")
async def metrics(_admin: AdminUser):
    pool = engine.pool
    pool_status = {}
    try:
        pool_status = {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
        }
    except Exception:
        pass

    proc_memory_mb = None
    try:
        import resource
        usage = resource.getrusage(resource.RUSAGE_SELF)
        proc_memory_mb = round(usage.ru_maxrss / 1024, 2)
    except Exception:
        try:
            with open(f"/proc/{os.getpid()}/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        proc_memory_mb = round(int(line.split()[1]) / 1024, 2)
                        break
        except Exception:
            pass

    return {
        "uptime_seconds": round(time.time() - _start_time, 1),
        "pid": os.getpid(),
        "database_pool": pool_status,
        "process_memory_mb": proc_memory_mb,
    }
