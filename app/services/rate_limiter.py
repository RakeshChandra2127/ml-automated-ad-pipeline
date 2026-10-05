import time
from redis.asyncio import Redis

class SlidingWindowRateLimiter:
    """
    Implements a Sliding Window Log rate limiter using Redis sorted sets.

    How it works:
    1. Each request is logged as a member in a sorted set, with the current timestamp as the score.
    2. On each request, we remove all entries older than the window.
    3. We count remaining entries. If count >= max_requests, the IP is rate-limited.
    4. If not limited, we add the current timestamp.
    5. We set a TTL on the key equal to the window size for automatic cleanup.

    Trade-off: This is more memory-intensive than a simple counter but provides
    precise per-second accuracy without the boundary problems of fixed windows.
    """
    def __init__(self, redis_client: Redis, max_requests: int = 100, window_seconds: int = 60):
        self.redis_client = redis_client
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def is_rate_limited(self, ip_address: str) -> bool:
        key = f'ratelimit:{ip_address}'
        now = int(time.time() * 1000)
        window_start = now - (self.window_seconds * 1000)

        async with self.redis_client.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.zadd(key, {str(now): now})
            pipe.expire(key, self.window_seconds)
            results = await pipe.execute()

        count = results[1]
        return count >= self.max_requests

    async def get_request_count(self, ip_address: str) -> int:
        key = f'ratelimit:{ip_address}'
        now = int(time.time() * 1000)
        window_start = now - (self.window_seconds * 1000)

        async with self.redis_client.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            results = await pipe.execute()
            
        return results[1]
