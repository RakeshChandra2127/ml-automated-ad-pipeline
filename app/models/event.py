from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import String, Integer, Float, Boolean, DateTime, JSON, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AdEvent(Base):
    """SQLAlchemy model for storing advertising events."""
    __tablename__ = "ad_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    campaign_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    publisher_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False, index=True)
    user_agent: Mapped[str] = mapped_column(String(500), nullable=False)
    click_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    referrer_url: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed: Mapped[bool] = mapped_column(Boolean, default=False)


class TrafficAggregate(Base):
    """SQLAlchemy model for storing sliding window traffic statistics."""
    __tablename__ = "traffic_aggregates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False, index=True)
    campaign_id: Mapped[str] = mapped_column(String(50), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    impression_count: Mapped[int] = mapped_column(Integer, default=0)
    click_count: Mapped[int] = mapped_column(Integer, default=0)
    conversion_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_click_to_conversion_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ctr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class FraudReport(Base):
    """SQLAlchemy model for storing AI-generated fraud analysis reports."""
    __tablename__ = "fraud_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    analyzed_window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    analyzed_window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_events_analyzed: Mapped[int] = mapped_column(Integer, nullable=False)
    suspicious_ips_count: Mapped[int] = mapped_column(Integer, default=0)
    suspicious_ips: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(20), default="low")
    llm_analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommended_actions: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
