"""Urban Flood Nowcasting System — FastAPI Application.

SIH26085: High-Resolution Urban Flood Nowcasting & Drainage Coupling.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.api.routers import cities, rainfall, simulations, alerts, geodata, validation, ai, nowcast
from services.api.routers import replay, scheduler, decision, tide, drainage, impact, ml, field_ops, auth, weather, subareas, provenance
from services.api.metrics import metrics_router, PrometheusMetricsMiddleware
from services.api.middleware.rate_limit import RateLimitMiddleware
from services.database.connection import engine, Base, verify_db_connectivity
from services.data.store import get_data_store

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: load real data, verify DB if available, cleanup on shutdown."""
    logger.info("Starting Urban Flood Nowcasting System API")

    # Load the local candidate data package for development/audit. The store
    # does not validate the source claims embedded in those files.
    store = get_data_store()
    logger.info(
        "Real data store ready",
        wards=len(store.wards().get("features", [])),
        flood_hotspots=len(store.flood_hotspots().get("features", [])),
        rain_gauge_records=len(store.rainfall_gauges()),
        historical_events=len(store.historical_events()),
    )

    # Connect to PostgreSQL / PostGIS if available (dev/prod), otherwise operate standalone
    db_available = await verify_db_connectivity()
    if db_available:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables verified (PostgreSQL/PostGIS connected)")
        except Exception as e:
            logger.warning("Failed to initialize database tables", error=str(e))
    # Pre-warm live nowcasting baseline in background so dashboard has instant raster & data
    try:
        import asyncio
        from services.nowcast.pipeline import run_nowcast_pipeline
        asyncio.create_task(run_nowcast_pipeline(catchment="hindmata_dadar", duration_hours=3.0, grid_size=60))
        logger.info("Launched initial nowcast pipeline run in background")
    except Exception as e:
        logger.warning("Could not launch initial nowcast run", error=str(e))

    yield

    logger.info("Shutting down API")
    try:
        await engine.dispose()
    except Exception:
        pass


app = FastAPI(
    title="Mumbai Urban Flood Nowcasting System (MUFNS)",
    description=(
        "SIH26085 research prototype. The current simulation endpoint is an "
        "explicitly synthetic, non-georeferenced scenario experiment. Local "
        "Mumbai dataset provenance and model validation are incomplete; outputs "
        "are not operational flood forecasts or municipal decision advice."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow both frontend apps
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # citizen-web
        "http://localhost:3001",  # city-dashboard
        "http://localhost:5173",  # vite dev
        "*",  # Allow all origins for development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(PrometheusMetricsMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=300)

# ── Routers ──
app.include_router(auth.router, prefix="/api/v1", tags=["Authentication"])
app.include_router(metrics_router)
app.include_router(geodata.router, prefix="/api/v1", tags=["Geodata"])
app.include_router(cities.router, prefix="/api/v1", tags=["Cities"])
app.include_router(rainfall.router, prefix="/api/v1", tags=["Rainfall"])
app.include_router(simulations.router, prefix="/api/v1", tags=["Simulations"])
app.include_router(alerts.router, prefix="/api/v1", tags=["Alerts"])
app.include_router(validation.router, prefix="/api/v1", tags=["Validation"])
app.include_router(ai.router, prefix="/api/v1", tags=["AI Assistant"])
app.include_router(nowcast.router, prefix="/api/v1", tags=["Nowcasting"])
app.include_router(replay.router, tags=["Historical Replay"])
app.include_router(scheduler.router, prefix="/api/v1", tags=["Scheduler"])
app.include_router(decision.router, prefix="/api/v1", tags=["Decision Support"])
app.include_router(tide.router, prefix="/api/v1", tags=["Tide & Coastal"])
app.include_router(drainage.router, prefix="/api/v1", tags=["Drainage & SWMM"])
app.include_router(impact.router, prefix="/api/v1", tags=["Impact & Exposure"])
app.include_router(ml.router, prefix="/api/v1", tags=["ML Surrogate"])
app.include_router(field_ops.router, prefix="/api/v1", tags=["Field Operations"])
app.include_router(weather.router, prefix="/api/v1", tags=["Weather Intelligence"])
app.include_router(subareas.router, prefix="/api/v1")
app.include_router(provenance.router, prefix="/api/v1")




# ── Health Check ──
@app.get("/health", tags=["System"])
async def health_check():
    """System health check. Verifies API is running and database status."""
    from services.database.connection import _db_online

    db_ok = False
    postgis_version = None

    if _db_online is True:
        try:
            from sqlalchemy import text

            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT PostGIS_Version()"))
                postgis_version = result.scalar()
                db_ok = True
        except Exception:
            db_ok = False

    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "postgis-cluster" if db_ok else "standalone (local-storage)",
        "database": "connected (PostGIS)" if db_ok else "standalone (data/cities)",
        "postgis_version": postgis_version,
        "scheduler": _get_scheduler_status(),
        "version": "0.2.0",
    }


def _get_scheduler_status() -> dict:
    """Get scheduler status summary for health check."""
    try:
        from services.nowcast.scheduler import get_scheduler_state
        state = get_scheduler_state()
        return {
            "running": state.is_running,
            "paused": state.paused,
            "total_runs": state.total_runs,
            "success_rate_pct": round(100 * state.successful_runs / max(1, state.total_runs), 1),
        }
    except Exception:
        return {"running": False}

