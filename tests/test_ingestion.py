import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from app.main import app

client = TestClient(app)

@pytest.fixture
def mock_deps():
    with patch("app.api.routes.get_rate_limiter") as mock_rl, \
         patch("app.api.routes.get_bloom_filter") as mock_bf, \
         patch("app.api.routes.get_event_producer") as mock_ep:
         
        rl_instance = AsyncMock()
        rl_instance.is_allowed.return_value = True
        mock_rl.return_value = rl_instance
        
        bf_instance = AsyncMock()
        bf_instance.might_contain.return_value = False
        mock_bf.return_value = bf_instance
        
        ep_instance = AsyncMock()
        mock_ep.return_value = ep_instance
        
        yield rl_instance, bf_instance, ep_instance

def test_track_impression_returns_202(mock_deps):
    payload = {
        "event_type": "impression",
        "ad_id": "ad_1",
        "campaign_id": "camp_1",
        "publisher_id": "pub_1"
    }
    response = client.post("/api/v1/track", json=payload)
    assert response.status_code == 202
    assert "event_id" in response.json()

def test_track_click_with_duplicate_returns_200(mock_deps):
    rl, bf, ep = mock_deps
    bf.might_contain.return_value = True # Simulate duplicate
    
    payload = {
        "event_type": "click",
        "ad_id": "ad_1",
        "campaign_id": "camp_1",
        "publisher_id": "pub_1",
        "click_id": "duplicate_click_id"
    }
    response = client.post("/api/v1/track", json=payload)
    assert response.status_code == 200
    assert response.json() == {"message": "duplicate event"}

def test_rate_limited_returns_429(mock_deps):
    rl, bf, ep = mock_deps
    rl.is_allowed.return_value = False # Simulate rate limit
    
    payload = {
        "event_type": "impression",
        "ad_id": "ad_1",
        "campaign_id": "camp_1",
        "publisher_id": "pub_1"
    }
    response = client.post("/api/v1/track", json=payload)
    assert response.status_code == 429

def test_invalid_event_type_returns_422():
    payload = {
        "event_type": "invalid_type",
        "ad_id": "ad_1",
        "campaign_id": "camp_1",
        "publisher_id": "pub_1"
    }
    response = client.post("/api/v1/track", json=payload)
    assert response.status_code == 422

def test_health_endpoint():
    # Assuming health endpoint is defined in routes or root
    response = client.get("/")
    assert response.status_code == 200
