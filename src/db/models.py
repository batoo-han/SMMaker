"""
SQLAlchemy models and helpers for user data.
"""

import os
from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    Boolean,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# SQLite database location within project directory
DB_DIR = os.path.join(os.getcwd(), "data")
DB_PATH = os.path.join(DB_DIR, "users.db")

Base = declarative_base()

class User(Base):
    """User account."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user", nullable=False)

    settings = relationship("UserSetting", back_populates="user", cascade="all, delete-orphan")

class UserSetting(Base):
    """Arbitrary key-value user settings."""

    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    key = Column(String, nullable=False)
    value = Column(String, nullable=False)

    user = relationship("User", back_populates="settings")


class Topic(Base):
    """Topic for future publication."""

    __tablename__ = "topics"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    topic = Column(String, nullable=False)
    status = Column(String, default="ожидание", nullable=False)
    scheduled = Column(DateTime)
    network = Column(String)
    url = Column(String)
    ai_text = Column(String)
    model_text = Column(String)
    tokens_text = Column(String)
    ai_image = Column(String)
    model_image = Column(String)
    tokens_image = Column(String)

    user = relationship("User")


class Schedule(Base):
    """User-defined schedule."""

    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    network = Column(String, nullable=False)
    text_generator = Column(String, nullable=False)
    image_generator = Column(String)
    cron = Column(String, nullable=False)
    timezone = Column(String, default="Europe/Moscow")
    enabled = Column(Boolean, default=True)

    user = relationship("User")


def get_engine(db_path: str = DB_PATH):
    """Return SQLAlchemy engine, creating directories if needed."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return create_engine(f"sqlite:///{db_path}")


def init_db(db_path: str = DB_PATH):
    """Create tables in the SQLite database."""
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    return engine


SessionLocal = sessionmaker(autoflush=False, bind=get_engine())
