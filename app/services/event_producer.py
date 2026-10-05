from redis.asyncio import Redis

class EventProducer:
    """
    Publish ad events to a Redis Stream for asynchronous processing.

    Redis Streams provide:
    - Persistent, append-only log (events survive restarts)
    - Consumer groups (multiple workers can process in parallel)
    - Acknowledgement (at-least-once delivery semantics)
    - Automatic ID generation (time-based ordering)

    Trade-off vs Kafka:
    - Redis Streams: simpler ops, lower latency, good for <100K events/sec
    - Kafka: better for >100K events/sec, stronger durability guarantees, 
      but heavier infrastructure
    """
    def __init__(self, redis_client: Redis, stream_name: str = 'ad_events_stream'):
        self.redis_client = redis_client
        self.stream_name = stream_name

    async def publish(self, event_data: dict) -> str:
        stringified_data = {k: str(v) for k, v in event_data.items()}
        message_id = await self.redis_client.xadd(
            name=self.stream_name,
            fields=stringified_data,
            maxlen=1000000,
            approximate=True
        )
        return message_id

    async def get_stream_info(self) -> dict:
        info = await self.redis_client.xinfo_stream(self.stream_name)
        return info
