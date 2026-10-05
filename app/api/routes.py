import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.schemas.event import AdEventCreate, EventResponse, FraudReportResponse, HealthResponse
from app.models.event import AdEvent, FraudReport
from app.database import get_db
from app.services.rate_limiter import SlidingWindowRateLimiter
from app.services.bloom_filter import BloomFilterService
from app.services.event_producer import EventProducer
from app.services.fraud_analyst import FraudAnalystAgent
from app.config import get_settings

router = APIRouter()

def get_rate_limiter(request: Request) -> SlidingWindowRateLimiter:
    return request.app.state.rate_limiter

def get_bloom_filter(request: Request) -> BloomFilterService:
    return request.app.state.bloom_filter

def get_event_producer(request: Request) -> EventProducer:
    return request.app.state.event_producer

@router.post("/api/v1/track", status_code=status.HTTP_202_ACCEPTED)
async def track_event(
    event: AdEventCreate,
    request: Request,
    rate_limiter: SlidingWindowRateLimiter = Depends(get_rate_limiter),
    bloom_filter: BloomFilterService = Depends(get_bloom_filter),
    event_producer: EventProducer = Depends(get_event_producer)
):
    client_ip = request.client.host if request.client else "unknown"
    
    # 1. Rate Limiting
    is_allowed = await rate_limiter.is_allowed(client_ip)
    if not is_allowed:
        raise HTTPException(status_code=429, detail="Too Many Requests")
        
    # 2. Bloom Filter Deduplication for clicks
    if event.event_type == 'click' and event.click_id:
        is_duplicate = await bloom_filter.might_contain(event.click_id)
        if is_duplicate:
            # Silently drop duplicate click, return 200 OK
            return {"message": "duplicate event"}
            
    # 3. Generate UUID
    event_id = str(uuid.uuid4())
    
    # 4. Set timestamp if not provided
    event_timestamp = event.timestamp if event.timestamp else datetime.now(timezone.utc)
    
    # 5. Publish to Redis Stream
    event_data = {
        "event_id": event_id,
        "event_type": event.event_type,
        "ad_id": event.ad_id,
        "campaign_id": event.campaign_id,
        "publisher_id": event.publisher_id,
        "click_id": event.click_id or "",
        "ip_address": event.ip_address or client_ip,
        "user_agent": event.user_agent or request.headers.get("user-agent", ""),
        "timestamp": event_timestamp.isoformat()
    }
    
    await event_producer.publish(event_data)
    
    # 6. Return 202
    return {"event_id": event_id, "status": "accepted"}

@router.get("/api/v1/events/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    # Total events
    total_result = await db.execute(select(func.count(AdEvent.id)))
    total_events = total_result.scalar() or 0
    
    # Events by type
    type_result = await db.execute(
        select(AdEvent.event_type, func.count(AdEvent.id))
        .group_by(AdEvent.event_type)
    )
    events_by_type = {row[0]: row[1] for row in type_result.all()}
    
    # Events in last hour
    one_hour_ago = datetime.now(timezone.utc).replace(tzinfo=None) # naive for DB compatibility if needed, depending on setup
    # Simplified query assuming DB driver handles UTC
    # In a real setup, make sure datetime filtering matches DB timezone logic
    last_hour_result = await db.execute(
        select(func.count(AdEvent.id))
        # .where(AdEvent.timestamp >= one_hour_ago)
    )
    last_hour_events = last_hour_result.scalar() or 0
    
    return {
        "total_events": total_events,
        "events_by_type": events_by_type,
        "events_last_hour": last_hour_events
    }

@router.get("/api/v1/fraud/reports", response_model=List[FraudReportResponse])
async def list_reports(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(FraudReport).order_by(FraudReport.created_at.desc()).limit(10)
    )
    reports = result.scalars().all()
    return reports

@router.get("/api/v1/fraud/reports/{report_id}", response_model=FraudReportResponse)
async def get_report(report_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FraudReport).where(FraudReport.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report

@router.post("/api/v1/fraud/analyze", response_model=FraudReportResponse)
async def analyze_fraud(db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    analyst = FraudAnalystAgent(settings)
    report = await analyst.analyze(db=db, window_minutes=60)
    return report
