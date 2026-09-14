"""Run with python -m app.simulator; retries reuse IDs for idempotency."""

import os
import random
import time
import uuid
from datetime import datetime, timezone

import httpx


def main():
    base = os.getenv("API_URL", "http://frontend")
    headers = {"Authorization": "Bearer " + os.environ["WRITE_TOKEN"]}
    with httpx.Client(base_url=base, timeout=20) as client:
        sensors = (
            client.get("/api/sensors", params={"size": 500}).raise_for_status().json()["items"]
        )
        while True:
            batch = [
                {
                    "id": str(uuid.uuid4()),
                    "sensor_id": s["id"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "value": random.uniform(20, 35),
                    "raw": {"source": "continuous simulator"},
                }
                for s in sensors
                if s["type_id"] == "soil_moisture"
            ]
            for attempt in range(5):
                try:
                    response = client.post("/api/readings", json=batch, headers=headers)
                    response.raise_for_status()
                    print(response.json(), flush=True)
                    break
                except httpx.HTTPError:
                    if attempt == 4:
                        raise
                    time.sleep(2**attempt)
            time.sleep(15)


if __name__ == "__main__":
    main()
