from redis.asyncio import Redis
from redis.exceptions import ResponseError

class BloomFilterService:
    """
    Redis-backed Bloom Filter for click deduplication.

    Uses the RedisBloom module commands (BF.RESERVE, BF.ADD, BF.EXISTS) via
    redis-py's execute_command() method.

    Why Bloom Filter?
    - We need to deduplicate billions of click events in real-time.
    - A hash set would consume too much memory at this scale.
    - A Bloom Filter uses ~1.2 bytes per element at 1% false positive rate.
    - For 1M clicks: ~1.2MB vs ~64MB for a hash set.
    - Trade-off: Small false positive rate (legitimate clicks rarely dropped)
      is acceptable vs the memory savings and speed gains.
    - No false negatives: every duplicate IS caught.
    """
    def __init__(self, redis_client: Redis, filter_name: str = 'click_dedup', capacity: int = 1000000, error_rate: float = 0.01):
        self.redis_client = redis_client
        self.filter_name = filter_name
        self.capacity = capacity
        self.error_rate = error_rate

    async def initialize(self):
        try:
            await self.redis_client.execute_command('BF.RESERVE', self.filter_name, self.error_rate, self.capacity)
        except ResponseError:
            pass

    async def is_duplicate(self, click_id: str) -> bool:
        exists = await self.redis_client.execute_command('BF.EXISTS', self.filter_name, click_id)
        if exists:
            return True
        await self.redis_client.execute_command('BF.ADD', self.filter_name, click_id)
        return False

    async def reset(self):
        await self.redis_client.delete(self.filter_name)
        await self.initialize()
