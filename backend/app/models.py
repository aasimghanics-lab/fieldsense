import uuid
from datetime import date, datetime, timezone

from geoalchemy2 import Geometry
from sqlalchemy import JSON, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def uid():
    return str(uuid.uuid4())


class Identity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(160))


class Team(Identity, Base):
    __tablename__ = "teams"


class User(Identity, Base):
    __tablename__ = "users"
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    role: Mapped[str] = mapped_column(String(30), default="researcher")


class Researcher(Identity, Base):
    __tablename__ = "researchers"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    affiliation: Mapped[str] = mapped_column(String(200))


class Farm(Identity, Base):
    __tablename__ = "farms"
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"))


class Field(Identity, Base):
    __tablename__ = "fields"
    farm_id: Mapped[str] = mapped_column(ForeignKey("farms.id"), index=True)
    boundary = mapped_column(Geometry("POLYGON", srid=4326, spatial_index=True))


class Crop(Identity, Base):
    __tablename__ = "crops"


class Season(Identity, Base):
    __tablename__ = "seasons"
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)


class Experiment(Identity, Base):
    __tablename__ = "experiments"
    description: Mapped[str] = mapped_column(Text, default="")
    crop_id: Mapped[str] = mapped_column(ForeignKey("crops.id"), index=True)
    season_id: Mapped[str] = mapped_column(ForeignKey("seasons.id"))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)


class Treatment(Identity, Base):
    __tablename__ = "treatments"
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"), index=True)
    description: Mapped[str] = mapped_column(Text, default="")


class Plot(Identity, Base):
    __tablename__ = "plots"
    field_id: Mapped[str] = mapped_column(ForeignKey("fields.id"), index=True)
    crop_id: Mapped[str] = mapped_column(ForeignKey("crops.id"), index=True)
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"), index=True)
    treatment_id: Mapped[str] = mapped_column(ForeignKey("treatments.id"))
    boundary = mapped_column(Geometry("POLYGON", srid=4326, spatial_index=True))


class SensorType(Identity, Base):
    __tablename__ = "sensor_types"
    unit: Mapped[str] = mapped_column(String(30))
    measurement: Mapped[str] = mapped_column(String(50), unique=True)


class Sensor(Identity, Base):
    __tablename__ = "sensors"
    plot_id: Mapped[str] = mapped_column(ForeignKey("plots.id"), index=True)
    type_id: Mapped[str] = mapped_column(ForeignKey("sensor_types.id"))
    location = mapped_column(Geometry("POINT", srid=4326, spatial_index=True))


class Deployment(Identity, Base):
    __tablename__ = "deployments"
    sensor_id: Mapped[str] = mapped_column(ForeignKey("sensors.id"), index=True)
    plot_id: Mapped[str] = mapped_column(ForeignKey("plots.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Note(Identity, Base):
    __tablename__ = "notes"
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"), index=True)
    body: Mapped[str] = mapped_column(Text)


class Export(Identity, Base):
    __tablename__ = "exports"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    filters: Mapped[dict] = mapped_column(JSON)
    rows: Mapped[int]


class Weather(Identity, Base):
    __tablename__ = "weather"
    farm_id: Mapped[str] = mapped_column(ForeignKey("farms.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    temperature: Mapped[float]
    rainfall: Mapped[float]
