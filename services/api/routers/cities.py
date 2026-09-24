"""City CRUD API router.

Manages the multi-city configuration layer.
Nothing is hardcoded to Mumbai — any city can be registered
with its own CRS, DEM, drainage, and simulation parameters.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping, shape
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from packages.contracts.city import (
    BoundingBox,
    CityCreate,
    CityResponse,
    WardResponse,
)
from services.database import City, Ward, get_db

logger = structlog.get_logger()
router = APIRouter()

# In-memory city registry for standalone mode
_standalone_cities: dict[str, CityResponse] = {}


def _load_city_from_disk(city_id: str = "mumbai") -> Optional[CityResponse]:
    """Load city configuration from data/cities/{city_id}/config.json."""
    config_path = Path("data/cities") / city_id / "config.json"
    if not config_path.exists():
        return None
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        bbox = data.get("bbox")
        bbox_obj = (
            BoundingBox(
                min_lon=bbox["min_lon"],
                min_lat=bbox["min_lat"],
                max_lon=bbox["max_lon"],
                max_lat=bbox["max_lat"],
            )
            if bbox
            else None
        )
        return CityResponse(
            city_id=data["city_id"],
            name=data["name"],
            state=data.get("state", ""),
            country=data.get("country", "IN"),
            crs_epsg=data["crs_epsg"],
            cell_size_m=data.get("cell_size_m", 30.0),
            bbox=bbox_obj,
            timezone=data.get("timezone", "Asia/Kolkata"),
            config=data.get("config", {}),
            created_at=datetime.now(timezone.utc),
        )
    except Exception as e:
        logger.error("Failed to read city config file", path=str(config_path), error=str(e))
        return None


def _load_wards_from_disk(city_id: str = "mumbai") -> list[WardResponse]:
    """Load ward geometries from data/cities/{city_id}/wards.geojson."""
    geojson_path = Path("data/cities") / city_id / "wards.geojson"
    if not geojson_path.exists():
        return []
    try:
        from services.ingestion.wards import parse_ward_geojson
        parsed = parse_ward_geojson(geojson_path)
        return [
            WardResponse(
                ward_id=w["ward_id"],
                city_id=city_id,
                name=w["name"],
                area_sq_km=w.get("area_sq_km"),
                population=w.get("population"),
                geometry_geojson=w.get("geometry_geojson"),
                metadata=w.get("properties", {}),
            )
            for w in parsed
        ]
    except Exception as e:
        logger.error("Failed to parse local ward GeoJSON", path=str(geojson_path), error=str(e))
        return []


def _city_to_response(city: City) -> CityResponse:
    """Convert ORM City to response model."""
    bbox_dict = None
    if city.bbox is not None:
        try:
            geom = to_shape(city.bbox)
            bounds = geom.bounds  # (minx, miny, maxx, maxy)
            bbox_dict = BoundingBox(
                min_lon=bounds[0],
                min_lat=bounds[1],
                max_lon=bounds[2],
                max_lat=bounds[3],
            )
        except Exception:
            bbox_dict = None

    return CityResponse(
        city_id=city.city_id,
        name=city.name,
        state=city.state or "",
        country=city.country or "IN",
        crs_epsg=city.crs_epsg,
        cell_size_m=city.cell_size_m or 30.0,
        bbox=bbox_dict,
        timezone=city.timezone or "Asia/Kolkata",
        config=city.config or {},
        created_at=city.created_at,
    )


@router.post("/cities", response_model=CityResponse, status_code=status.HTTP_201_CREATED)
async def create_city(body: CityCreate, db: Optional[AsyncSession] = Depends(get_db)):
    """Register a new city in the system (supports PostGIS or Standalone)."""
    # Standalone mode fallback if DB is not available
    if db is None:
        if body.city_id in _standalone_cities or _load_city_from_disk(body.city_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"City '{body.city_id}' already exists",
            )
        resp = CityResponse(
            city_id=body.city_id,
            name=body.name,
            state=body.state,
            country=body.country,
            crs_epsg=body.crs_epsg,
            cell_size_m=body.cell_size_m,
            bbox=body.bbox,
            timezone=body.timezone,
            config=body.config,
            created_at=datetime.now(timezone.utc),
        )
        _standalone_cities[body.city_id] = resp
        logger.info("City registered (standalone mode)", city_id=body.city_id)
        return resp

    # Database mode
    try:
        existing = await db.execute(select(City).where(City.city_id == body.city_id))
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"City '{body.city_id}' already exists",
            )

        wkt = body.bbox.to_wkt_polygon()
        city = City(
            city_id=body.city_id,
            name=body.name,
            state=body.state,
            country=body.country,
            crs_epsg=body.crs_epsg,
            cell_size_m=body.cell_size_m,
            bbox=text(f"ST_GeomFromText('{wkt}', 4326)"),
            timezone=body.timezone,
            config=body.config,
        )
        db.add(city)
        await db.flush()

        result = await db.execute(select(City).where(City.city_id == body.city_id))
        created = result.scalar_one()
        return _city_to_response(created)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Database insert failed, registering standalone", error=str(e))
        resp = CityResponse(
            city_id=body.city_id,
            name=body.name,
            state=body.state,
            country=body.country,
            crs_epsg=body.crs_epsg,
            cell_size_m=body.cell_size_m,
            bbox=body.bbox,
            timezone=body.timezone,
            config=body.config,
            created_at=datetime.now(timezone.utc),
        )
        _standalone_cities[body.city_id] = resp
        return resp


@router.get("/cities", response_model=list[CityResponse])
async def list_cities(db: Optional[AsyncSession] = Depends(get_db)):
    """List all registered cities."""
    db_cities = []
    if db is not None:
        try:
            result = await db.execute(select(City).order_by(City.name))
            db_cities = [_city_to_response(c) for c in result.scalars().all()]
        except Exception as e:
            logger.debug("Database city query failed, using standalone fallback", error=str(e))

    if db_cities:
        return db_cities

    # Standalone mode: return from disk + memory
    cities_map = {}
    mumbai = _load_city_from_disk("mumbai")
    if mumbai:
        cities_map["mumbai"] = mumbai
    cities_map.update(_standalone_cities)
    return list(cities_map.values())


@router.get("/cities/{city_id}", response_model=CityResponse)
async def get_city(city_id: str, db: Optional[AsyncSession] = Depends(get_db)):
    """Get a specific city by ID."""
    if db is not None:
        try:
            result = await db.execute(select(City).where(City.city_id == city_id))
            city = result.scalar_one_or_none()
            if city is not None:
                return _city_to_response(city)
        except Exception as e:
            logger.debug("Database get_city failed, using standalone fallback", error=str(e))

    # Standalone fallback
    if city_id in _standalone_cities:
        return _standalone_cities[city_id]
    disk_city = _load_city_from_disk(city_id)
    if disk_city is not None:
        return disk_city

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"City '{city_id}' not found",
    )


@router.get("/cities/{city_id}/wards", response_model=list[WardResponse])
async def list_wards(city_id: str, db: Optional[AsyncSession] = Depends(get_db)):
    """List all wards for a city."""
    if db is not None:
        try:
            result = await db.execute(
                select(Ward).where(Ward.city_id == city_id).order_by(Ward.name)
            )
            wards = result.scalars().all()
            if wards:
                responses = []
                for w in wards:
                    geojson = None
                    if w.geometry is not None:
                        try:
                            geojson = mapping(to_shape(w.geometry))
                        except Exception:
                            pass
                    responses.append(
                        WardResponse(
                            ward_id=w.ward_id,
                            city_id=w.city_id,
                            name=w.name or "",
                            area_sq_km=w.area_sq_km,
                            population=w.population,
                            geometry_geojson=geojson,
                            metadata=w.metadata_ or {},
                        )
                    )
                return responses
        except Exception as e:
            logger.debug("Database list_wards failed, using standalone fallback", error=str(e))

    # Standalone fallback: load from disk GeoJSON
    disk_wards = _load_wards_from_disk(city_id)
    if disk_wards:
        return disk_wards

    # If city exists but no wards found
    if city_id == "mumbai" or city_id in _standalone_cities or _load_city_from_disk(city_id):
        return []

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"City '{city_id}' not found",
    )
