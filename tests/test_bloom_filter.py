import pytest
from unittest.mock import AsyncMock
from app.services.bloom_filter import BloomFilterService

@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    return redis

@pytest.mark.asyncio
async def test_new_click_not_duplicate(mock_redis):
    # Mocking BF.EXISTS to return 0 (not found)
    mock_redis.execute_command = AsyncMock(return_value=0)
    
    bf = BloomFilterService(mock_redis, "test_bf", 1000, 0.01)
    result = await bf.might_contain("click_123")
    
    assert result is False
    mock_redis.execute_command.assert_called_with("BF.EXISTS", "test_bf", "click_123")

@pytest.mark.asyncio
async def test_same_click_is_duplicate(mock_redis):
    # Mocking BF.EXISTS to return 1 (found)
    mock_redis.execute_command = AsyncMock(return_value=1)
    
    bf = BloomFilterService(mock_redis, "test_bf", 1000, 0.01)
    result = await bf.might_contain("click_123")
    
    assert result is True

@pytest.mark.asyncio
async def test_different_clicks_not_duplicate(mock_redis):
    # Call 1: click_A -> not found
    # Call 2: click_B -> not found
    mock_redis.execute_command = AsyncMock(side_effect=[0, 0])
    
    bf = BloomFilterService(mock_redis, "test_bf", 1000, 0.01)
    assert await bf.might_contain("click_A") is False
    assert await bf.might_contain("click_B") is False
