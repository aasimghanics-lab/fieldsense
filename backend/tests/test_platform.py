import csv
import io
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import text

from app.db import Session, documents
from app.main import app
from app.services import Reading


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def headers():
    return {"Authorization": "Bearer " + os.environ["WRITE_TOKEN"]}


def payload(value=25):
    return {
        "id": "test-" + str(uuid.uuid4()),
        "sensor_id": "sensor-0-0-0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "value": value,
        "raw": {"nested": {"probe": "test"}},
    }


@pytest.mark.parametrize("value", [float("inf"), float("nan"), -float("inf")])
def test_finite(value):
    with pytest.raises(ValidationError):
        Reading(**payload(value))


def test_timezone():
    row = payload()
    row["timestamp"] = "2026-01-01T12:00:00"
    with pytest.raises(ValidationError):
        Reading(**row)


def test_future():
    row = payload()
    row["timestamp"] = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    with pytest.raises(ValidationError):
        Reading(**row)


def test_health(client):
    assert client.get("/api/health").json() == {
        "status": "ok",
        "postgres": "ok",
        "postgis": "ok",
        "mongo": "ok",
    }


@pytest.mark.parametrize(
    "path",
    [
        "farms",
        "fields",
        "plots",
        "crops",
        "experiments",
        "sensors",
        "treatments",
        "seasons",
        "weather",
        "notes",
    ],
)
def test_metadata(client, path):
    result = client.get("/api/" + path, params={"size": 2}).json()
    assert len(result["items"]) <= 2
    assert result["total"] >= 1


def test_ingest_idempotent_missing_and_unknown(client, headers):
    row = payload(None)
    try:
        assert client.post("/api/readings", json=[row]).status_code == 401
        assert client.post("/api/readings", json=[row], headers=headers).json()["inserted"] == 1
        assert client.post("/api/readings", json=[row], headers=headers).json()["duplicates"] == 1
        stored = documents.readings.find_one({"_id": row["id"]})
        assert stored["raw"] == row["raw"]
        assert stored["quality"] == ["missing"]
        row["sensor_id"] = "nonexistent"
        assert client.post("/api/readings", json=[row], headers=headers).status_code == 422
        assert client.post("/api/readings", json=[], headers=headers).status_code == 422
    finally:
        documents.readings.delete_one({"_id": row["id"]})


def test_pagination_filter_aggregation(client):
    result = client.get("/api/readings?farm=farm-0&sensor=sensor-0-0-0&size=7").json()
    assert len(result["items"]) == 7
    assert all(r["sensor_id"] == "sensor-0-0-0" for r in result["items"])
    next_page = client.get("/api/readings?sensor=sensor-0-0-0&size=7&page=2").json()
    assert result["items"][0]["timestamp"] != next_page["items"][0]["timestamp"]
    data = client.get("/api/series?sensor=sensor-0-0-0&hours=24").json()["items"]
    assert 50 <= len(data) <= 62
    assert any(r["anomalies"] > 0 for r in data)
    assert client.get("/api/readings?size=10001").status_code == 422
    assert (
        client.get("/api/readings?start=2026-02-01T00:00:00Z&end=2026-01-01T00:00:00Z").status_code
        == 422
    )


def test_geospatial(client):
    geo = client.get("/api/map?bbox=-83.081,40.039,-83.070,40.050").json()
    assert {f["properties"]["kind"] for f in geo["features"]} == {"field", "plot", "sensor"}
    assert len(client.get("/api/fields/field-0/sensors").json()) == 32
    assert client.get("/api/map?bbox=0,0,1,1").json()["features"] == []
    assert client.get("/api/map?bbox=1,2,0,0").status_code == 422
    with Session() as db:
        indexes = (
            db.execute(
                text(
                    "SELECT indexdef FROM pg_indexes WHERE tablename IN ('fields','plots','sensors')"
                )
            )
            .scalars()
            .all()
        )
        assert sum("gist" in i.lower() for i in indexes) == 3


def test_anomaly_model(client, headers):
    result = client.post("/api/sensors/sensor-0-0-0/detect", headers=headers).json()
    assert result["fitted"] >= 30
    assert 0 < result["anomalies"] < result["fitted"] * 0.1
    anomalies = client.get("/api/anomalies?sensor=sensor-0-0-0").json()
    assert anomalies["total"] == result["anomalies"]
    assert all(r["anomaly_score"] < 0 for r in anomalies["items"])


def test_export_matches_actual_readings(client):
    result = client.get("/api/exports/csv?sensor=sensor-0-0-0")
    assert result.status_code == 200
    rows = list(csv.DictReader(io.StringIO(result.text)))
    assert len(rows) == documents.readings.count_documents({"sensor_id": "sensor-0-0-0"})
    assert rows[0]["experiment_id"] == "exp-0"
    assert rows[0]["treatment_id"] == "treatment-0-0"


def test_experiment_validation(client, headers):
    body = {
        "name": "New trial",
        "description": "Testing",
        "crop_id": "corn",
        "season_id": "season-demo",
        "start_date": "2026-06-01",
        "end_date": "2026-05-01",
        "treatments": ["Control"],
    }
    assert client.post("/api/experiments", json=body, headers=headers).status_code == 422
    body["end_date"] = "2026-09-01"
    response = client.post("/api/experiments", json=body, headers=headers)
    assert response.status_code == 201
    eid = response.json()["id"]
    try:
        assert (
            client.post(
                "/api/notes",
                json={"experiment_id": eid, "body": "A test annotation"},
                headers=headers,
            ).status_code
            == 201
        )
    finally:
        with Session() as db:
            for table in ["notes", "treatments", "experiments"]:
                db.execute(
                    text(
                        f"DELETE FROM {table} WHERE {'id' if table == 'experiments' else 'experiment_id'}=:id"
                    ),
                    {"id": eid},
                )
            db.commit()


def test_sensor_detail_and_dashboard(client):
    detail = client.get("/api/sensors/sensor-0-0-0").json()
    assert detail["location"]["type"] == "Point"
    assert detail["device"]["probe"]["depth_cm"] == 20
    assert len(detail["deployments"]) == 1
    dashboard = client.get("/api/dashboard").json()
    assert dashboard["active_sensors"] + dashboard["offline_sensors"] == 192
    assert dashboard["readings"] > 200000
    assert client.get("/api/sensors/does-not-exist").status_code == 404
