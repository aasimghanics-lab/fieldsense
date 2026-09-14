import math
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from pymongo import UpdateOne
from sklearn.ensemble import IsolationForest
from sqlalchemy import select

from .db import documents
from .models import Field as ResearchField
from .models import Plot, Sensor, SensorType


class Reading(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    sensor_id: str
    timestamp: datetime
    value: float | None
    raw: dict = Field(default_factory=dict)

    @field_validator("value")
    @classmethod
    def finite(cls, value):
        if value is not None and not math.isfinite(value):
            raise ValueError("Value must be finite")
        return value

    @field_validator("timestamp")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None:
            raise ValueError("Timestamp must include a timezone")
        if value > datetime.now(timezone.utc):
            raise ValueError("Future readings are not accepted")
        return value


class Filters(BaseModel):
    farm: str | None = None
    field: str | None = None
    plot: str | None = None
    crop: str | None = None
    experiment: str | None = None
    sensor: str | None = None
    measurement: str | None = None
    start: datetime | None = None
    end: datetime | None = None


FilterQuery = Annotated[Filters, Depends()]


def sensor_metadata(db, filters):
    query = (
        select(Sensor, Plot, ResearchField, SensorType)
        .join(Plot, Sensor.plot_id == Plot.id)
        .join(ResearchField, Plot.field_id == ResearchField.id)
        .join(SensorType, Sensor.type_id == SensorType.id)
    )
    for key, column in {
        "farm": ResearchField.farm_id,
        "field": Plot.field_id,
        "plot": Plot.id,
        "crop": Plot.crop_id,
        "experiment": Plot.experiment_id,
        "sensor": Sensor.id,
        "measurement": SensorType.measurement,
    }.items():
        if getattr(filters, key):
            query = query.where(column == getattr(filters, key))
    return {
        s.id: dict(
            sensor_id=s.id,
            sensor=s.name,
            plot=p.name,
            plot_id=p.id,
            field=f.name,
            field_id=f.id,
            farm_id=f.farm_id,
            crop_id=p.crop_id,
            experiment_id=p.experiment_id,
            treatment_id=p.treatment_id,
            measurement=t.measurement,
            unit=t.unit,
        )
        for s, p, f, t in db.execute(query)
    }


def reading_query(db, filters):
    for value in (filters.start, filters.end):
        if value is not None and value.tzinfo is None:
            raise HTTPException(422, "Time filters must include a timezone")
    if filters.start and filters.end and filters.start > filters.end:
        raise HTTPException(422, "Start must precede end")
    query = {"sensor_id": {"$in": list(sensor_metadata(db, filters))}}
    if filters.start or filters.end:
        query["timestamp"] = {}
        if filters.start:
            query["timestamp"]["$gte"] = filters.start
        if filters.end:
            query["timestamp"]["$lte"] = filters.end
    return query


def indexes():
    documents.readings.create_index([("sensor_id", 1), ("timestamp", -1)])
    documents.readings.create_index([("timestamp", -1), ("_id", 1)])
    documents.readings.create_index([("anomaly", 1), ("timestamp", -1)])
    documents.devices.create_index("sensor_id", unique=True)


def ingest(db, readings):
    metadata = sensor_metadata(db, Filters())
    unknown = {r.sensor_id for r in readings} - metadata.keys()
    if unknown:
        raise HTTPException(422, "Unknown sensor identifier")
    operations = []
    for reading in readings:
        row = reading.model_dump()
        row["_id"] = row.pop("id")
        row["measurement"] = metadata[reading.sensor_id]["measurement"]
        row["quality"] = ["missing"] if reading.value is None else []
        limits = {
            "soil_moisture": (0, 100),
            "humidity": (0, 100),
            "leaf_wetness": (0, 100),
            "soil_temperature": (-50, 80),
            "air_temperature": (-60, 70),
            "canopy_temperature": (-60, 90),
            "rainfall": (0, 500),
            "par": (0, 3000),
        }
        low, high = limits[row["measurement"]]
        if reading.value is not None and not low <= reading.value <= high:
            row["quality"].append("out_of_range")
        row["received_at"] = datetime.now(timezone.utc)
        row["anomaly"] = False
        operations.append(UpdateOne({"_id": row["_id"]}, {"$setOnInsert": row}, upsert=True))
    result = documents.readings.bulk_write(operations, ordered=False)
    return {"inserted": result.upserted_count, "duplicates": len(readings) - result.upserted_count}


def detect(sensor_id):
    rows = list(
        documents.readings.find({"sensor_id": sensor_id, "value": {"$ne": None}}, {"value": 1})
        .sort("timestamp", -1)
        .limit(10000)
    )
    if len(rows) < 30:
        raise HTTPException(422, "At least 30 nonmissing readings are required")
    model = IsolationForest(n_estimators=100, contamination=0.025, random_state=42, n_jobs=1)
    values = [[r["value"]] for r in rows]
    labels = model.fit_predict(values)
    scores = model.decision_function(values)
    documents.readings.bulk_write(
        [
            UpdateOne(
                {"_id": r["_id"]},
                {
                    "$set": {
                        "anomaly": bool(label == -1),
                        "anomaly_score": float(score),
                        "model": "isolation-forest-v1",
                    }
                },
            )
            for r, label, score in zip(rows, labels, scores)
        ]
    )
    return {
        "fitted": len(rows),
        "anomalies": int(sum(labels == -1)),
        "model": "isolation-forest-v1",
    }
