import json

from fastapi.testclient import TestClient
import main


client = TestClient(main.app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_reject_invalid_coordinates():
    response = client.post("/analyze", json={"latitude": 110, "longitude": 43.98})
    assert response.status_code == 422


def test_full_response(monkeypatch):
    async def fake_land(*args):
        return {"land_cover": "Bare Ground", "land_cover_code": 8}

    async def fake_weather(*args):
        return {
            "temperature_c": 25.4,
            "humidity_pct": 40.0,
            "precipitation_mm": 1.5,
            "precipitation_period": "previous_7_complete_days",
            "weather_time": "2026-11-09T20:30",
            "weather_source_type": "modeled_estimates",
        }

    monkeypatch.setattr(main, "fetch_land_cover", fake_land)
    monkeypatch.setattr(main, "fetch_climate", fake_weather)
    response = client.post("/analyze", json={"latitude": 26.3592, "longitude": 43.9818})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["land_cover"] == "Bare Ground"
    assert body["climate"]["precipitation_mm"] == 1.5
    assert "not predict" in body["summary"]


def test_partial_response(monkeypatch):
    async def failing_land(*args):
        raise RuntimeError("Esri down")

    async def fake_weather(*args):
        return {
            "temperature_c": 22.0,
            "humidity_pct": 50.0,
            "precipitation_mm": None,
            "precipitation_period": "previous_7_complete_days",
            "weather_time": "2026-11-09T20:30",
            "weather_source_type": "modeled_estimates",
        }

    monkeypatch.setattr(main, "fetch_land_cover", failing_land)
    monkeypatch.setattr(main, "fetch_climate", fake_weather)
    response = client.post("/analyze", json={"latitude": 26.3592, "longitude": 43.9818})
    assert response.status_code == 200
    assert response.json()["status"] == "partial"
    assert response.json()["land_cover"] == "Unavailable"


def test_all_unavailable(monkeypatch):
    async def fail(*args):
        raise RuntimeError("unavailable")

    monkeypatch.setattr(main, "fetch_land_cover", fail)
    monkeypatch.setattr(main, "fetch_climate", fail)
    response = client.post("/analyze", json={"latitude": 26.3592, "longitude": 43.9818})
    assert response.status_code == 503
    assert response.json()["detail"]["status"] == "unavailable"


def test_esri_sample_parsing():
    class FakeResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {"samples": [{"value": "8", "attributes": {"Year": 2025}}]}

    class FakeClient:
        async def get(self, url, params):
            assert params["geometryType"] == "esriGeometryPoint"
            assert json.loads(params["mosaicRule"])["where"] == "Year = 2025"
            return FakeResponse()

    import asyncio
    result = asyncio.run(main.fetch_land_cover(FakeClient(), 26.3592, 43.9818))
    assert result == {"land_cover": "Bare Ground", "land_cover_code": 8}


def test_open_meteo_weather_parsing():
    from datetime import datetime, timedelta
    dates = [(datetime.now(main.RIYADH_TZ).date() - timedelta(days=d)).isoformat() for d in range(7, 0, -1)]
    dates.append(datetime.now(main.RIYADH_TZ).date().isoformat())

    class FakeResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {
                "current": {"temperature_2m": 29.2, "relative_humidity_2m": 32, "time": "2026-11-09T20:30"},
                "daily": {"time": dates, "precipitation_sum": [1, 2, 0, 0, 0, 0, 3, 99]},
            }

    class FakeClient:
        async def get(self, url, params):
            assert params["past_days"] == 7
            return FakeResponse()

    import asyncio
    result = asyncio.run(main.fetch_climate(FakeClient(), 26.3592, 43.9818))
    assert result["precipitation_mm"] == 6
    assert result["temperature_c"] == 29.2


def test_rainfall_requires_exact_seven_dates():
    import asyncio
    from datetime import datetime, timedelta

    today = datetime.now(main.RIYADH_TZ).date()
    # Seven records, but yesterday is absent and an older day is present.
    dates = [(today - timedelta(days=d)).isoformat() for d in range(8, 1, -1)]

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "current": {"temperature_2m": 25, "relative_humidity_2m": 40},
                "daily": {"time": dates, "precipitation_sum": [1] * 7},
            }

    class FakeClient:
        async def get(self, url, params):
            return FakeResponse()

    result = asyncio.run(main.fetch_climate(FakeClient(), 24.7136, 46.6753))
    assert result["precipitation_mm"] is None
