import os

from pymongo import MongoClient
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


engine = create_engine(os.getenv('DATABASE_URL', 'postgresql+psycopg://fieldsense:local-research-only@localhost:5432/fieldsense'), pool_pre_ping=True, pool_size=10, max_overflow=10)
Session = sessionmaker(engine)
mongo = MongoClient(os.getenv('MONGO_URL', 'mongodb://localhost:27017'), serverSelectionTimeoutMS=3000, tz_aware=True)
documents = mongo.fieldsense


def session():
    with Session() as db:
        yield db
