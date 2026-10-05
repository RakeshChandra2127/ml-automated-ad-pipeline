import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from app.models.event import AdEvent

class TrafficAggregator:
    """
    Aggregates raw ad events into sliding window statistics.
    Used by the Fraud Analyst to detect anomalies.
    """
    async def aggregate_window(self, db: AsyncSession, window_minutes: int = 60) -> list[dict]:
        now = datetime.datetime.utcnow()
        window_start = now - datetime.timedelta(minutes=window_minutes)

        stmt = select(
            AdEvent.ip_address,
            AdEvent.campaign_id,
            func.count(1).filter(AdEvent.event_type == 'impression').label('impression_count'),
            func.count(1).filter(AdEvent.event_type == 'click').label('click_count'),
            func.count(1).filter(AdEvent.event_type == 'conversion').label('conversion_count')
        ).where(
            AdEvent.timestamp >= window_start
        ).group_by(
            AdEvent.ip_address,
            AdEvent.campaign_id
        )

        result = await db.execute(stmt)
        stats = []
        for row in result.all():
            imp = row.impression_count or 0
            clk = row.click_count or 0
            conv = row.conversion_count or 0
            ctr = (clk / imp) if imp > 0 else 0.0
            stats.append({
                "ip_address": row.ip_address,
                "campaign_id": row.campaign_id,
                "impression_count": imp,
                "click_count": clk,
                "conversion_count": conv,
                "ctr": ctr
            })
        return stats

    async def get_top_ips(self, db: AsyncSession, window_minutes: int = 60, limit: int = 20) -> list[dict]:
        now = datetime.datetime.utcnow()
        window_start = now - datetime.timedelta(minutes=window_minutes)

        stmt = select(
            AdEvent.ip_address,
            func.count(1).label('total_events')
        ).where(
            AdEvent.timestamp >= window_start
        ).group_by(
            AdEvent.ip_address
        ).order_by(
            desc('total_events')
        ).limit(limit)

        result = await db.execute(stmt)
        return [{"ip_address": row.ip_address, "total_events": row.total_events} for row in result.all()]

    async def get_anomaly_candidates(self, db: AsyncSession, window_minutes: int = 60) -> list[dict]:
        stats = await self.aggregate_window(db, window_minutes)
        candidates = []

        for stat in stats:
            ip = stat['ip_address']
            cid = stat['campaign_id']
            clk = stat['click_count']
            ctr = stat['ctr']
            conv = stat['conversion_count']

            is_anomaly = False

            if ctr > 0.8 and clk > 10:
                is_anomaly = True
            elif clk > 50:
                is_anomaly = True
            elif conv > 0:
                # Check for fast conversions
                stmt = select(AdEvent).where(
                    and_(
                        AdEvent.ip_address == ip,
                        AdEvent.campaign_id == cid,
                        AdEvent.event_type.in_(['click', 'conversion'])
                    )
                ).order_by(AdEvent.timestamp)
                result = await db.execute(stmt)
                events = result.scalars().all()
                
                click_times = [e.timestamp for e in events if e.event_type == 'click']
                conv_times = [e.timestamp for e in events if e.event_type == 'conversion']
                
                fast_conv = False
                for c_time in conv_times:
                    for clk_time in click_times:
                        if 0 <= (c_time - clk_time).total_seconds() < 1:
                            fast_conv = True
                            break
                    if fast_conv:
                        break
                
                if fast_conv:
                    is_anomaly = True

            if is_anomaly:
                candidates.append(stat)

        return candidates
