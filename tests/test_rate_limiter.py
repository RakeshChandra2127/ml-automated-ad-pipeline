import pytest
import time
from unittest.mock import AsyncMock, MagicMock
from app.services.rate_limiter import SlidingWindowRateLimiter

@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    pipeline = AsyncMock()
    redis.pipeline.return_value = pipeline
    return redis

@pytest.mark.asyncio
async def test_allows_requests_under_limit(mock_redis):
    pipeline = mock_redis.pipeline.return_value
    pipeline.execute = AsyncMock(return_value=[1, 1, 1, 3]) # zremrangebyscore, zadd, expire, zcard
    
    limiter = SlidingWindowRateLimiter(mock_redis, max_requests=5, window_seconds=60)
    is_allowed = await limiter.is_allowed("192.168.1.1")
    
    assert is_allowed is True
    pipeline.execute.assert_called_once()

@pytest.mark.asyncio
async def test_blocks_requests_over_limit(mock_redis):
    pipeline = mock_redis.pipeline.return_value
    pipeline.execute = AsyncMock(return_value=[1, 1, 1, 6]) # zcard returns 6
    
    limiter = SlidingWindowRateLimiter(mock_redis, max_requests=5, window_seconds=60)
    is_allowed = await limiter.is_allowed("192.168.1.1")
    
    assert is_allowed is False

@pytest.mark.asyncio
async def test_window_expires_and_resets(mock_redis):
    pipeline = mock_redis.pipeline.return_value
    # Initial request under limit
    pipeline.execute = AsyncMock(return_value=[1, 1, 1, 1])
    limiter = SlidingWindowRateLimiter(mock_redis, max_requests=1, window_seconds=1)
    
    assert await limiter.is_allowed("127.0.0.1") is True
    
    # Simulate over limit
    pipeline.execute = AsyncMock(return_value=[1, 1, 1, 2])
    assert await limiter.is_allowed("127.0.0.1") is False
    
    # Simulate time pass and reset
    pipeline.execute = AsyncMock(return_value=[1, 1, 1, 1])
    assert await limiter.is_allowed("127.0.0.1") is True
