"""Deterministic synthetic Ohio-like research geometry; not actual farm records."""

import math
import os
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from . import models as m
from .db import Session, documents
from .services import detect, indexes


def polygon(x, y, width, height):
    return f"SRID=4326;POLYGON(({x} {y},{x + width} {y},{x + width} {y + height},{x} {y + height},{x} {y}))"


def seed():
    if os.getenv("SEED_DATA", "true").lower() != "true":
        return
    indexes()
    rng = random.Random(42)
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    with Session() as db:
        if db.scalar(select(m.Farm).limit(1)):
            return
        team = m.Team(id="team-demo", name="Field Systems Research Â· simulated lab")
        db.add(team)
        db.flush()
        db.add(
            m.User(
                id="user-demo",
                name="Demo researcher",
                email="researcher@example.invalid",
                team_id=team.id,
            )
        )
        db.flush()
        db.add(
            m.Researcher(
                name="Demo researcher",
                user_id="user-demo",
                affiliation="Simulated agricultural research lab",
            )
        )
        db.add(
            m.Season(
                id="season-demo",
                name=f"{now.year} growing season",
                start_date=now.date() - timedelta(days=90),
                end_date=now.date() + timedelta(days=30),
            )
        )
        types = [
            ("soil_moisture", "% VWC", 28, 5),
            ("soil_temperature", "Â°C", 21, 5),
            ("air_temperature", "Â°C", 24, 8),
            ("humidity", "%", 65, 15),
            ("rainfall", "mm", 1, 2),
            ("canopy_temperature", "Â°C", 26, 7),
            ("par", "Âµmol/mÂ²/s", 500, 350),
            ("leaf_wetness", "%", 35, 20),
        ]
        for measure, unit, _, _ in types:
            db.add(
                m.SensorType(
                    id=measure,
                    name=measure.replace("_", " ").title(),
                    measurement=measure,
                    unit=unit,
                )
            )
        for crop in ["corn", "soybean", "wheat"]:
            db.add(m.Crop(id=crop, name=crop.title()))
        db.flush()
        all_docs = []
        for fi in range(3):
            farm = m.Farm(
                id=f"farm-{fi}",
                name=["Prairie Creek", "Cedar Run", "North Ridge"][fi],
                team_id=team.id,
            )
            db.add(farm)
            db.flush()
            for field_index in range(2):
                k = fi * 2 + field_index
                x, y = -83.08 + fi * 0.025, 40.04 + field_index * 0.015
                field = m.Field(
                    id=f"field-{k}",
                    name=f"{farm.name} Â· {'East' if field_index else 'West'}",
                    farm_id=farm.id,
                    boundary=polygon(x, y, 0.009, 0.009),
                )
                crop = ["corn", "soybean", "wheat"][fi]
                exp = m.Experiment(
                    id=f"exp-{k}",
                    name=f"{crop.title()} water response {k + 1}",
                    description="Simulated randomized treatment blocks comparing rainfed and supplemental irrigation.",
                    crop_id=crop,
                    season_id="season-demo",
                    start_date=now.date() - timedelta(days=60),
                    end_date=now.date() + timedelta(days=30),
                )
                db.add_all([field, exp])
                db.flush()
                for ti in range(2):
                    db.add(
                        m.Treatment(
                            id=f"treatment-{k}-{ti}",
                            name=["Rainfed control", "Supplemental irrigation"][ti],
                            experiment_id=exp.id,
                        )
                    )
                db.flush()
                for pi in range(4):
                    px, py = x + 0.0005 + (pi % 2) * 0.004, y + 0.0005 + (pi // 2) * 0.004
                    plot = m.Plot(
                        id=f"plot-{k}-{pi}",
                        name=f"Block {k + 1} / Plot {pi + 1}",
                        field_id=field.id,
                        crop_id=crop,
                        experiment_id=exp.id,
                        treatment_id=f"treatment-{k}-{pi % 2}",
                        boundary=polygon(px, py, 0.0035, 0.0035),
                    )
                    db.add(plot)
                    db.flush()
                    for si, (measure, unit, center, amplitude) in enumerate(types):
                        sid = f"sensor-{k}-{pi}-{si}"
                        db.add(
                            m.Sensor(
                                id=sid,
                                name=f"{measure.replace('_', ' ').title()} Â· {k + 1}.{pi + 1}",
                                plot_id=plot.id,
                                type_id=measure,
                                location=f"SRID=4326;POINT({px + 0.0004 + si * 0.00035} {py + 0.0017})",
                            )
                        )
                        db.flush()
                        db.add(
                            m.Deployment(
                                name="Initial deployment",
                                sensor_id=sid,
                                plot_id=plot.id,
                                started_at=now - timedelta(days=60),
                            )
                        )
                        documents.devices.update_one(
                            {"sensor_id": sid},
                            {
                                "$set": {
                                    "sensor_id": sid,
                                    "manufacturer": "Simulated Instruments",
                                    "firmware": "2.1",
                                    "probe": {"depth_cm": 20} if si < 2 else {"shield": True},
                                }
                            },
                            upsert=True,
                        )
                        for hour in range(60 * 24):
                            if (
                                rng.random() < 0.035
                                or (si == 0 and 400 < hour < 480)
                                or (pi == 3 and si == 7 and hour > 1400)
                            ):
                                continue
                            timestamp = now - timedelta(
                                hours=60 * 24 - hour, minutes=rng.randint(0, 12)
                            )
                            value = max(
                                0,
                                center
                                + amplitude * math.sin(hour * math.pi / 12)
                                + rng.gauss(0, amplitude * 0.18)
                                + (hour / 1440 * 4 if si == 0 else 0),
                            )
                            if rng.random() < 0.007:
                                value += amplitude * 8
                            missing = rng.random() < 0.008
                            all_docs.append(
                                {
                                    "_id": f"{sid}-{hour}",
                                    "sensor_id": sid,
                                    "timestamp": timestamp,
                                    "received_at": timestamp,
                                    "value": None if missing else round(value, 3),
                                    "measurement": measure,
                                    "quality": ["missing"] if missing else [],
                                    "anomaly": False,
                                    "raw": {"v": value, "battery": round(rng.uniform(2.8, 3.6), 2)}
                                    if si % 2
                                    else {"samples": [{"reading": value, "unit": unit}]},
                                }
                            )
                db.add(
                    m.Note(
                        name="Simulation provenance",
                        experiment_id=exp.id,
                        body="All coordinates and measurements are synthetic. Missing intervals, spikes, drift and offline periods were injected.",
                    )
                )
            for day in range(60):
                db.add(
                    m.Weather(
                        name="Simulated weather",
                        farm_id=farm.id,
                        timestamp=now - timedelta(days=day),
                        temperature=22 + rng.gauss(0, 4),
                        rainfall=max(0, rng.gauss(1, 3)),
                    )
                )
        db.commit()
        for offset in range(0, len(all_docs), 5000):
            documents.readings.insert_many(all_docs[offset : offset + 5000])
        for sid in db.scalars(select(m.Sensor.id).where(m.Sensor.type_id == "soil_moisture")):
            detect(sid)
        print(f"Seeded {len(all_docs)} simulated readings across 192 sensors")


if __name__ == "__main__":
    seed()
