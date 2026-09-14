"""Measured local HTTP workloads; run inside the backend container."""

import json
import os
import platform
import statistics
import time
import uuid
from datetime import datetime, timezone

import httpx

from app.db import documents


def main():
    results = {}
    with httpx.Client(base_url=os.getenv("API_URL", "http://frontend"), timeout=120) as c:
        workload = {
            "recent readings": "/api/readings?sensor=sensor-0-0-0&size=100",
            "time aggregation": "/api/series?measurement=soil_moisture&hours=24",
            "dashboard": "/api/dashboard",
            "spatial lookup": "/api/map?bbox=-83.081,40.039,-83.070,40.050",
        }
        for name, path in workload.items():
            c.get(path).raise_for_status()
            samples = []
            for _ in range(20):
                start = time.perf_counter()
                c.get(path).raise_for_status()
                samples.append((time.perf_counter() - start) * 1000)
            results[name] = {
                "requests": 20,
                "median_ms": round(statistics.median(samples), 2),
                "p95_ms": round(sorted(samples)[18], 2),
            }
        ids = ["benchmark-" + str(uuid.uuid4()) for _ in range(1000)]
        batch = [
            {
                "id": id,
                "sensor_id": "sensor-0-0-0",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "value": 25.0,
            }
            for id in ids
        ]
        try:
            start = time.perf_counter()
            c.post(
                "/api/readings",
                json=batch,
                headers={"Authorization": "Bearer " + os.environ["WRITE_TOKEN"]},
            ).raise_for_status()
            elapsed = time.perf_counter() - start
            results["bulk ingestion"] = {
                "rows": 1000,
                "elapsed_ms": round(elapsed * 1000, 2),
                "rows_per_second": round(1000 / elapsed, 2),
            }
        finally:
            documents.readings.delete_many({"_id": {"$in": ids}})
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "cpu_model": next(
                (
                    line.split(":", 1)[1].strip()
                    for line in open("/proc/cpuinfo")
                    if line.startswith("model name")
                ),
                "unknown",
            ),
            "memory": next(
                (line.strip() for line in open("/proc/meminfo") if line.startswith("MemTotal")),
                "unknown",
            ),
            "readings": documents.readings.estimated_document_count(),
            "results": results,
        }
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
