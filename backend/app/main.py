import csv
import io
import json
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, model_validator
from pydantic import Field as ValueField
from pymongo.errors import PyMongoError
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from . import models as m
from .db import documents, mongo, session
from .services import (
    FilterQuery,
    Reading,
    detect,
    indexes,
    ingest,
    reading_query,
    sensor_metadata,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fieldsense")


@asynccontextmanager
async def lifespan(app):
    indexes()
    yield


app = FastAPI(title="FieldSense Research API", version="1.0.0", lifespan=lifespan)


def writer(authorization: str = Header(default="")):
    expected = os.getenv("WRITE_TOKEN", "")
    if not expected or not secrets.compare_digest(authorization, "Bearer " + expected):
        raise HTTPException(401, "A valid lab write token is required")


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    logger.info(
        json.dumps(
            {
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - start) * 1000, 2),
            }
        )
    )
    return response


async def storage_error(request, exc):
    logger.error(json.dumps({"event": "storage_unavailable", "type": type(exc).__name__}))
    return JSONResponse(
        status_code=503,
        content={"detail": "Research storage is temporarily unavailable. Please retry."},
    )


app.add_exception_handler(SQLAlchemyError, storage_error)
app.add_exception_handler(PyMongoError, storage_error)


def serialize(db, entity):
    result = {}
    for column in entity.__table__.columns:
        value = getattr(entity, column.name)
        if column.name in ("boundary", "location"):
            value = (
                json.loads(db.scalar(select(func.ST_AsGeoJSON(value))))
                if value is not None
                else None
            )
        result[column.name] = value
    return result


@app.get("/api/health")
def health(db=Depends(session)):
    db.execute(text("SELECT PostGIS_Version()"))
    mongo.admin.command("ping")
    return {"status": "ok", "postgres": "ok", "postgis": "ok", "mongo": "ok"}


def collection_route(model):
    def endpoint(
        page: int = Query(1, ge=1), size: int = Query(100, ge=1, le=500), db=Depends(session)
    ):
        total = db.scalar(select(func.count()).select_from(model))
        rows = db.scalars(
            select(model).order_by(model.name, model.id).offset((page - 1) * size).limit(size)
        )
        return {
            "items": [serialize(db, r) for r in rows],
            "total": total,
            "page": page,
            "size": size,
        }

    return endpoint


for name, model in {
    "farms": m.Farm,
    "fields": m.Field,
    "plots": m.Plot,
    "crops": m.Crop,
    "experiments": m.Experiment,
    "sensors": m.Sensor,
    "treatments": m.Treatment,
    "seasons": m.Season,
    "sensor-types": m.SensorType,
    "notes": m.Note,
    "exports": m.Export,
    "weather": m.Weather,
}.items():
    app.add_api_route("/api/" + name, collection_route(model), methods=["GET"], name="list_" + name)


@app.get("/api/map")
def map_data(bbox: str | None = None, db=Depends(session)):
    envelope = None
    if bbox:
        try:
            west, south, east, north = map(float, bbox.split(","))
            if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
                raise ValueError()
            envelope = func.ST_MakeEnvelope(west, south, east, north, 4326)
        except ValueError:
            raise HTTPException(422, "bbox must be west,south,east,north in WGS84")
    features = []
    for model, kind, geometry in [
        (m.Field, "field", m.Field.boundary),
        (m.Plot, "plot", m.Plot.boundary),
        (m.Sensor, "sensor", m.Sensor.location),
    ]:
        query = select(model)
        if envelope is not None:
            query = query.where(func.ST_Intersects(geometry, envelope))
        for row in db.scalars(query.limit(2000)):
            props = serialize(db, row)
            shape = props.pop("boundary", props.pop("location", None))
            features.append(
                {"type": "Feature", "geometry": shape, "properties": {**props, "kind": kind}}
            )
    return {"type": "FeatureCollection", "features": features}


@app.get("/api/fields/{field_id}/sensors")
def contained(field_id: str, db=Depends(session)):
    field = db.get(m.Field, field_id)
    if not field:
        raise HTTPException(404, "Field not found")
    return [
        serialize(db, s)
        for s in db.scalars(
            select(m.Sensor).where(func.ST_Covers(field.boundary, m.Sensor.location))
        )
    ]


@app.get("/api/sensors/{sensor_id}")
def sensor_detail(sensor_id: str, db=Depends(session)):
    sensor = db.get(m.Sensor, sensor_id)
    if not sensor:
        raise HTTPException(404, "Sensor not found")
    latest = documents.readings.find_one(
        {"sensor_id": sensor_id}, {"_id": 0}, sort=[("timestamp", -1)]
    )
    return {
        **serialize(db, sensor),
        "latest": latest,
        "device": documents.devices.find_one({"sensor_id": sensor_id}, {"_id": 0}),
        "deployments": [
            serialize(db, d)
            for d in db.scalars(select(m.Deployment).where(m.Deployment.sensor_id == sensor_id))
        ],
    }


@app.get("/api/readings")
def readings(
    filters: FilterQuery,
    page: int = Query(1, ge=1, le=10000),
    size: int = Query(100, ge=1, le=1000),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    db=Depends(session),
):
    query = reading_query(db, filters)
    rows = list(
        documents.readings.find(query, {"_id": 0, "raw": 0})
        .sort([("timestamp", 1 if order == "asc" else -1), ("sensor_id", 1)])
        .skip((page - 1) * size)
        .limit(size)
    )
    return {
        "items": rows,
        "total": documents.readings.count_documents(query),
        "page": page,
        "size": size,
    }


@app.get("/api/series")
def series(filters: FilterQuery, hours: int = Query(24, ge=1, le=168), db=Depends(session)):
    query = reading_query(db, filters)
    if not filters.start:
        query.setdefault("timestamp", {})["$gte"] = datetime.now(timezone.utc) - timedelta(days=90)
    pipeline = [
        {"$match": query},
        {
            "$group": {
                "_id": {
                    "sensor": "$sensor_id",
                    "time": {
                        "$dateTrunc": {"date": "$timestamp", "unit": "hour", "binSize": hours}
                    },
                },
                "value": {"$avg": "$value"},
                "min": {"$min": "$value"},
                "max": {"$max": "$value"},
                "count": {"$sum": 1},
                "missing": {"$sum": {"$cond": [{"$eq": ["$value", None]}, 1, 0]}},
                "anomalies": {"$sum": {"$cond": ["$anomaly", 1, 0]}},
            }
        },
        {"$sort": {"_id.time": 1}},
        {"$limit": 6001},
    ]
    rows = list(documents.readings.aggregate(pipeline))
    if len(rows) > 6000:
        raise HTTPException(
            422, "Select fewer sensors, a shorter date range, or larger aggregation interval"
        )
    return {
        "items": [
            {"sensor_id": r.pop("_id")["sensor"], **r, "timestamp": original["_id"]["time"]}
            for original in rows
            for r in [dict(original)]
        ]
    }


@app.post("/api/readings", dependencies=[Depends(writer)], status_code=201)
def bulk_readings(batch: list[Reading] = Body(min_length=1, max_length=5000), db=Depends(session)):
    return ingest(db, batch)


@app.get("/api/anomalies")
def anomalies(
    filters: FilterQuery,
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=1000),
    db=Depends(session),
):
    query = {**reading_query(db, filters), "anomaly": True}
    return {
        "items": list(
            documents.readings.find(query, {"_id": 0, "raw": 0})
            .sort("timestamp", -1)
            .skip((page - 1) * size)
            .limit(size)
        ),
        "total": documents.readings.count_documents(query),
    }


@app.post("/api/sensors/{sensor_id}/detect", dependencies=[Depends(writer)])
def anomaly_detection(sensor_id: str, db=Depends(session)):
    if not db.get(m.Sensor, sensor_id):
        raise HTTPException(404, "Sensor not found")
    return detect(sensor_id)


@app.get("/api/dashboard")
def dashboard(db=Depends(session)):
    latest = list(
        documents.readings.aggregate(
            [
                {"$sort": {"sensor_id": 1, "timestamp": -1}},
                {"$group": {"_id": "$sensor_id", "timestamp": {"$first": "$timestamp"}}},
            ]
        )
    )
    cutoff = datetime.now(timezone.utc) - timedelta(hours=6)
    total_sensors = db.scalar(select(func.count()).select_from(m.Sensor))
    active = sum(r["timestamp"] > cutoff for r in latest)
    return {
        "active_sensors": active,
        "offline_sensors": total_sensors - active,
        "fields": db.scalar(select(func.count()).select_from(m.Field)),
        "plots": db.scalar(select(func.count()).select_from(m.Plot)),
        "experiments": db.scalar(select(func.count()).select_from(m.Experiment)),
        "readings": documents.readings.estimated_document_count(),
        "anomalies": documents.readings.count_documents({"anomaly": True}),
        "quality_warnings": documents.readings.count_documents({"quality.0": {"$exists": True}}),
        "recent": list(
            documents.readings.find({}, {"_id": 0, "raw": 0}).sort("received_at", -1).limit(5)
        ),
        "simulated": True,
    }


class ExperimentInput(BaseModel):
    name: str = ValueField(min_length=3, max_length=160)
    description: str = ValueField(max_length=10000)
    crop_id: str
    season_id: str
    start_date: date
    end_date: date
    treatments: list[str] = ValueField(min_length=1, max_length=20)

    @model_validator(mode="after")
    def dates(self):
        if self.start_date > self.end_date:
            raise ValueError("End date must follow start date")
        return self


@app.post("/api/experiments", dependencies=[Depends(writer)], status_code=201)
def create_experiment(payload: ExperimentInput, db=Depends(session)):
    if not db.get(m.Crop, payload.crop_id) or not db.get(m.Season, payload.season_id):
        raise HTTPException(422, "Choose an existing crop and growing season")
    experiment = m.Experiment(**payload.model_dump(exclude={"treatments"}))
    db.add(experiment)
    db.flush()
    for treatment in payload.treatments:
        db.add(m.Treatment(name=treatment, experiment_id=experiment.id))
    db.commit()
    return serialize(db, experiment)


class NoteInput(BaseModel):
    experiment_id: str
    body: str = ValueField(min_length=1, max_length=10000)


@app.post("/api/notes", dependencies=[Depends(writer)], status_code=201)
def create_note(payload: NoteInput, db=Depends(session)):
    if not db.get(m.Experiment, payload.experiment_id):
        raise HTTPException(404, "Experiment not found")
    note = m.Note(name="Research note", **payload.model_dump())
    db.add(note)
    db.commit()
    return serialize(db, note)


@app.get("/api/exports/csv")
def export_csv(filters: FilterQuery, db=Depends(session)):
    query = reading_query(db, filters)
    count = documents.readings.count_documents(query)
    if count > 500000:
        raise HTTPException(422, "Limit export to 500,000 rows using filters")
    metadata = sensor_metadata(db, filters)
    db.add(m.Export(name="Research CSV", filters=filters.model_dump(mode="json"), rows=count))
    db.commit()

    def generate():
        buffer = io.StringIO()
        columns = [
            "sensor_id",
            "sensor",
            "plot",
            "plot_id",
            "field",
            "field_id",
            "farm_id",
            "crop_id",
            "experiment_id",
            "treatment_id",
            "measurement",
            "unit",
            "timestamp",
            "value",
            "anomaly",
            "quality",
        ]
        writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        yield buffer.getvalue()
        for row in documents.readings.find(query).sort("timestamp", 1).batch_size(1000):
            buffer.seek(0)
            buffer.truncate(0)
            data = {
                **metadata[row["sensor_id"]],
                **row,
                "timestamp": row["timestamp"].isoformat(),
                "quality": "|".join(row["quality"]),
            }
            for key, value in data.items():
                if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
                    data[key] = "'" + value
            writer.writerow(data)
            yield buffer.getvalue()

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=fieldsense-readings.csv"},
    )
