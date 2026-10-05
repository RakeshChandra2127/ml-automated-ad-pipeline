from datetime import datetime
from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel, Field, IPvAnyAddress, ConfigDict


class AdEventCreate(BaseModel):
    """Schema for creating a new advertising event."""
    event_type: Literal['impression', 'click', 'conversion']
    campaign_id: str = Field(..., min_length=1, max_length=50)
    publisher_id: str = Field(..., min_length=1, max_length=50)
    ip_address: IPvAnyAddress
    user_agent: str = Field(..., max_length=500)
    click_id: Optional[str] = None
    referrer_url: Optional[str] = None
    timestamp: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class EventResponse(BaseModel):
    """Schema for responding to an event creation request."""
    status: str
    event_id: str
    message: str


class FraudReportResponse(BaseModel):
    """Schema for responding with a fraud analysis report."""
    report_id: str
    risk_level: str
    total_events_analyzed: int
    suspicious_ips_count: int
    analyzed_window: str
    llm_analysis: Optional[str] = None
    recommended_actions: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    """Schema for the API healthcheck endpoint."""
    status: str
    version: str
    redis_connected: bool
    db_connected: bool
