from datetime import datetime
from sqlalchemy import (
    Column, Integer, BigInteger, String, Float, Boolean,
    Text, DateTime, ForeignKey
)
from sqlalchemy.orm import relationship
from app.database import Base


class Coach(Base):
    __tablename__ = "coach"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(100), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Athlete(Base):
    __tablename__ = "athletes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    garmin_email = Column(String(255), unique=True, nullable=False)
    garmin_password_encrypted = Column(Text, nullable=False)
    garmin_session = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    last_synced_at = Column(DateTime, nullable=True)
    total_activities = Column(Integer, default=0)
    total_distance_km = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    activities = relationship("Activity", back_populates="athlete", cascade="all, delete-orphan")
    sync_logs = relationship("SyncLog", back_populates="athlete", cascade="all, delete-orphan")


class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True)
    athlete_id = Column(Integer, ForeignKey("athletes.id"), nullable=False)
    garmin_activity_id = Column(BigInteger, unique=True, nullable=False, index=True)
    name = Column(String(255), default="")
    activity_type = Column(String(50), default="running")
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    distance_m = Column(Float, default=0.0)
    duration_s = Column(Float, default=0.0)
    elapsed_duration_s = Column(Float, default=0.0)
    avg_pace_s_per_km = Column(Float, nullable=True)
    avg_heart_rate = Column(Integer, nullable=True)
    max_heart_rate = Column(Integer, nullable=True)
    avg_cadence = Column(Float, nullable=True)
    avg_stride_length_cm = Column(Float, nullable=True)
    elevation_gain_m = Column(Float, nullable=True)
    elevation_loss_m = Column(Float, nullable=True)
    calories = Column(Integer, nullable=True)
    avg_temperature_c = Column(Float, nullable=True)
    training_effect_aerobic = Column(Float, nullable=True)
    training_effect_anaerobic = Column(Float, nullable=True)
    vo2max = Column(Float, nullable=True)
    garmin_raw_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    athlete = relationship("Athlete", back_populates="activities")
    laps = relationship("Lap", back_populates="activity", cascade="all, delete-orphan", order_by="Lap.lap_number")


class Lap(Base):
    __tablename__ = "laps"

    id = Column(Integer, primary_key=True, index=True)
    activity_id = Column(Integer, ForeignKey("activities.id"), nullable=False)
    lap_number = Column(Integer, nullable=False)
    distance_m = Column(Float, default=0.0)
    duration_s = Column(Float, default=0.0)
    avg_pace_s_per_km = Column(Float, nullable=True)
    avg_heart_rate = Column(Integer, nullable=True)
    max_heart_rate = Column(Integer, nullable=True)
    avg_cadence = Column(Float, nullable=True)
    elevation_gain_m = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    activity = relationship("Activity", back_populates="laps")


class TrainingPlan(Base):
    __tablename__ = "training_plans"

    id = Column(Integer, primary_key=True, index=True)
    athlete_id = Column(Integer, ForeignKey("athletes.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CoachMessage(Base):
    __tablename__ = "coach_messages"

    id = Column(Integer, primary_key=True, index=True)
    athlete_id = Column(Integer, ForeignKey("athletes.id"), nullable=False)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class SyncLog(Base):
    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    athlete_id = Column(Integer, ForeignKey("athletes.id"), nullable=True)
    sync_type = Column(String(50), nullable=False, default="manual")
    status = Column(String(20), nullable=False, default="success")
    activities_fetched = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    athlete = relationship("Athlete", back_populates="sync_logs")
