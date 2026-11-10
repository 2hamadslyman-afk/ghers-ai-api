"""Opt-in live checks. Sends public city coordinates to Esri and Open-Meteo."""
import json
from pathlib import Path

from fastapi.testclient import TestClient
from main import app

if __name__ == "__main__":
    results = []
    with TestClient(app) as client:
        for city, lat, lon in [
            ("Buraydah", 26.3592, 43.9818),
            ("Riyadh", 24.7136, 46.6753),
            ("Abha", 18.2164, 42.5053),
        ]:
            response = client.post("/analyze", json={"latitude": lat, "longitude": lon})
            results.append({"city": city, "http_status": response.status_code, "response": response.json()})
            print(city, response.status_code, response.json().get("status", "unavailable"), flush=True)
    Path("live_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
