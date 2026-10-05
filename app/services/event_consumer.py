import asyncio
import logging
from redis.asyncio import Redis
from redis.exceptions import ResponseError
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.models.event import AdEvent
from datetime import datetime

logger = logging.getLogger(__name__)

class EventConsumer:
    """
    Consumes ad events from the Redis Stream and persists them to PostgreSQL.

    Uses Redis Consumer Groups for reliable, distributed processing:
    1. XGROUP CREATE to create the consumer group (if not exists)
    2. XREADGROUP to read new messages
    3. Batch-insert events into PostgreSQL
    4. XACK to acknowledge processed messages

    If the consumer crashes before XACK, messages remain in the Pending
    Entries List (PEL) and are redelivered on restart — achieving
    at-least-once delivery semantics.
    """
    def __init__(self, redis_client: Redis, db_session_factory: async_sessionmaker, stream_name: str = 'ad_events_stream', group_name: str = 'event_processors', consumer_name: str = 'consumer_1'):
        self.redis_client = redis_client
        self.db_session_factory = db_session_factory
        self.stream_name = stream_name
        self.group_name = group_name
        self.consumer_name = consumer_name

    async def initialize_group(self):
        try:
            await self.redis_client.xgroup_create(self.stream_name, self.group_name, id='0', mkstream=True)
        except ResponseError as e:
            if "BUSYGROUP Consumer Group name already exists" not in str(e):
                logger.error(f"Error creating group: {e}")

    async def consume_batch(self, batch_size: int = 100) -> int:
        streams = {self.stream_name: '>'}
        messages = await self.redis_client.xreadgroup(
            self.group_name,
            self.consumer_name,
            streams,
            count=batch_size,
            block=2000
        )

        if not messages:
            return 0

        stream_name, records = messages[0]
        if not records:
            return 0

        processed_ids = []
        events = []

        for message_id, data in records:
            try:
                decoded_data = {k.decode('utf-8') if isinstance(k, bytes) else k: v.decode('utf-8') if isinstance(v, bytes) else v for k, v in data.items()}
                if 'timestamp' in decoded_data:
                    decoded_data['timestamp'] = datetime.fromisoformat(decoded_data['timestamp'])
                events.append(AdEvent(**decoded_data))
                processed_ids.append(message_id)
            except Exception as e:
                logger.error(f"Error parsing message {message_id}: {e}")

        if events:
            try:
                async with self.db_session_factory() as session:
                    session.add_all(events)
                    await session.commit()
                await self.redis_client.xack(self.stream_name, self.group_name, *processed_ids)
            except Exception as e:
                logger.error(f"Error inserting to DB: {e}")
                return 0

        return len(processed_ids)

    async def claim_pending(self, min_idle_ms: int = 60000) -> int:
        result = await self.redis_client.xautoclaim(
            self.stream_name,
            self.group_name,
            self.consumer_name,
            min_idle_time=min_idle_ms,
            start_id='0'
        )
        return len(result[1])

    async def start_consuming(self):
        await self.initialize_group()
        while True:
            try:
                count = await self.consume_batch()
                if count == 0:
                    await asyncio.sleep(0.1)
                else:
                    logger.info(f"Processed {count} events.")
            except Exception as e:
                logger.error(f"Error in consume loop: {e}")
                await asyncio.sleep(1)
