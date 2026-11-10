"""Ghers AI proof-of-concept API.

Uses *existing* pretrained land-cover predictions by Impact Observatory / Esri,
plus Open-Meteo modeled weather. It does NOT estimate germination probability.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

APP_VERSION = "1.0.0"
ESRI_YEAR = 2025
ESRI_URL = (
    "https://ic.imagery1.arcgis.com/arcgis/rest/services/"
    "Sentinel2_10m_LandCover/ImageServer/getSamples"
)
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
RIYADH_TZ = ZoneInfo("Asia/Riyadh")

# From Impact Observatory / Esri's official 9-class value legend.
LAND_COVER_CLASSES: dict[int, str] = {
    1: "Water",
    2: "Trees",
    4: "Flooded Vegetation",
    5: "Crops",
    7: "Built Area",
    8: "Bare Ground",
    9: "Snow/Ice",
    10: "Clouds",
    11: "Rangeland",
}

app = FastAPI(
    title="Ghers AI Environmental Analysis",
    description=(
        "Prototype API: pretrained 2025 land-cover classification and modeled "
        "weather. This is NOT a planting-suitability or germination prediction."
    ),
    version=APP_VERSION,
)


class Location(BaseModel):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "Ghers AI", "version": APP_VERSION, "status": "running"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": APP_VERSION}


async def fetch_land_cover(client: httpx.AsyncClient, lat: float, lon: float) -> dict[str, Any]:
    geometry = {
        "x": lon,
        "y": lat,
        "spatialReference": {"wkid": 4326},
    }
    mosaic = {
        "mosaicMethod": "esriMosaicAttribute",
        "where": f"Year = {ESRI_YEAR}",
        "sortField": "Year",
        "sortValue": str(ESRI_YEAR),
    }
    response = await client.get(
        ESRI_URL,
        params={
            "f": "json",
            "geometry": json.dumps(geometry, separators=(",", ":")),
            "geometryType": "esriGeometryPoint",
            "mosaicRule": json.dumps(mosaic, separators=(",", ":")),
            "outFields": "Year",
            "returnFirstValueOnly": "true",
            "interpolation": "RSP_NearestNeighbor",
        },
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise ValueError(f"Esri service error: {payload['error'].get('message', 'unknown')}")
    samples = payload.get("samples") or []
    if not samples:
        raise ValueError("No land-cover pixel was returned for the requested location")

    sample = samples[0]
    raw = str(sample.get("value", "")).strip().split(",")[0]
    code = int(float(raw))
    if code == 0 or code not in LAND_COVER_CLASSES:
        raise ValueError(f"Unknown/empty land-cover class: {code}")

    # If a sample provides a year attribute, prevent accidental use of an old layer.
    actual_year = (sample.get("attributes") or {}).get("Year")
    if actual_year is not None and int(actual_year) != ESRI_YEAR:
        raise ValueError(f"Land-cover returned unexpected year: {actual_year}")

    return {"land_cover": LAND_COVER_CLASSES[code], "land_cover_code": code}


async def fetch_climate(client: httpx.AsyncClient, lat: float, lon: float) -> dict[str, Any]:
    response = await client.get(
        WEATHER_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m",
            "daily": "precipitation_sum",
            "past_days": 7,
            "forecast_days": 1,
            "timezone": "Asia/Riyadh",
        },
    )
    response.raise_for_status()
    data = response.json()
    if data.get("error"):
        raise ValueError(data.get("reason", "Open-Meteo API error"))
    current = data.get("current") or {}
    daily = data.get("daily") or {}
    current_temp = current.get("temperature_2m")
    current_rh = current.get("relative_humidity_2m")
    if current_temp is None and current_rh is None:
        raise ValueError("Current weather variables missing")

    today = datetime.now(RIYADH_TZ).date()
    amounts_by_date = dict(zip(daily.get("time", []), daily.get("precipitation_sum", [])))
    complete_days = [
        amounts_by_date.get((today - timedelta(days=offset)).isoformat())
        for offset in range(1, 8)
    ]
    # Require each of the exact previous seven dates, not merely seven entries.
    rainfall_7d = (
        round(sum(float(amount) for amount in complete_days), 2)
        if all(amount is not None for amount in complete_days)
        else None
    )

    return {
        "temperature_c": round(float(current_temp), 1) if current_temp is not None else None,
        "humidity_pct": round(float(current_rh), 1) if current_rh is not None else None,
        "precipitation_mm": rainfall_7d,
        "precipitation_period": "previous_7_complete_days",
        "weather_time": current.get("time"),
        "weather_source_type": "modeled_estimates",
    }


def format_summary(land_cover: str, climate: dict[str, Any]) -> str:
    parts = []
    if land_cover != "Unavailable":
        parts.append(f"Land cover: {land_cover} (2025 satellite-derived classification).")
    if climate.get("temperature_c") is not None:
        parts.append(f"Current modeled air temperature: {climate['temperature_c']} C.")
    if climate.get("humidity_pct") is not None:
        parts.append(f"Current modeled relative humidity: {climate['humidity_pct']}%.")
    if climate.get("precipitation_mm") is not None:
        parts.append(f"Modeled precipitation over the previous 7 complete days: {climate['precipitation_mm']} mm.")
    if not parts:
        return "Environmental data unavailable. Please retry with an internet connection."
    parts.append("This describes the location; it does not predict planting or germination success.")
    return " ".join(parts)


@app.post("/analyze")
async def analyze(
    location: Location,
    x_api_key: str | None = Header(default=None),
) -> dict[str, Any]:
    # Optional header-based check; omit GHERS_API_KEY env var for a public demonstration.
    expected_key = os.getenv("GHERS_API_KEY", "")
    if expected_key and x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")

    async with httpx.AsyncClient(timeout=12.0, follow_redirects=False) as client:
        land_result, climate_result = await asyncio.gather(
            fetch_land_cover(client, location.latitude, location.longitude),
            fetch_climate(client, location.latitude, location.longitude),
            return_exceptions=True,
        )

    land_ok = not isinstance(land_result, Exception)
    climate_ok = not isinstance(climate_result, Exception)

    land = land_result if land_ok else {"land_cover": "Unavailable", "land_cover_code": None}
    climate = climate_result if climate_ok else {
        "temperature_c": None,
        "humidity_pct": None,
        "precipitation_mm": None,
        "precipitation_period": "previous_7_complete_days",
        "weather_time": None,
        "weather_source_type": "modeled_estimates",
    }

    status = "ok" if land_ok and climate_ok else "partial" if land_ok or climate_ok else "unavailable"
    source_errors = {}
    for source, outcome in (("land_cover", land_result), ("weather", climate_result)):
        if isinstance(outcome, Exception):
            error = {"type": type(outcome).__name__}
            if isinstance(outcome, httpx.HTTPStatusError):
                error["http_status"] = outcome.response.status_code
            source_errors[source] = error
    result = {
        "status": status,
        "latitude": location.latitude,
        "longitude": location.longitude,
        "land_cover": land["land_cover"],
        "climate": climate,
        "summary": format_summary(land["land_cover"], climate),
        "details": {
            "source_errors": source_errors,
            "land_cover_code": land["land_cover_code"],
            "land_cover_year": ESRI_YEAR,
            "land_cover_source": "Impact Observatory / Microsoft / Esri 10m annual land cover",
            "weather_source": "Open-Meteo",
            "analysis_type": "environmental_context_not_planting_suitability",
            "model_training": "third_party_pretrained_land_cover_model",
            "version": APP_VERSION,
        },
    }
    # App Inventor can display a partial response instead of invented values.
    if status == "unavailable":
        raise HTTPException(status_code=503, detail=result)
    return result
