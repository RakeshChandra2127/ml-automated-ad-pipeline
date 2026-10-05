import asyncio
import httpx
import uuid
import random
from datetime import datetime, timezone

API_URL = "http://localhost:8000/api/v1/track"

async def generate_events():
    async with httpx.AsyncClient() as client:
        print("Seeding Normal Events...")
        for _ in range(500):
            event = {
                "event_type": random.choice(["impression", "click"]),
                "ad_id": f"ad_{random.randint(1, 100)}",
                "campaign_id": f"camp_{random.randint(1, 5)}",
                "publisher_id": f"pub_{random.randint(1, 10)}",
                "ip_address": f"192.168.1.{random.randint(1, 50)}",
                "click_id": str(uuid.uuid4()) if random.random() > 0.5 else None,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await client.post(API_URL, json=event)
        
        print("Seeding Suspicious Events (High Volume Same IP)...")
        bad_ip = "10.0.0.99"
        for _ in range(100):
            event = {
                "event_type": "click",
                "ad_id": "ad_101",
                "campaign_id": "camp_suspicious",
                "publisher_id": "pub_1",
                "ip_address": bad_ip,
                "click_id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await client.post(API_URL, json=event)

        print("Seeding Suspicious Events (Fast Click-to-Conversion)...")
        for _ in range(20):
            conv_ip = f"172.16.0.{random.randint(1, 20)}"
            click_id = str(uuid.uuid4())
            click_event = {
                "event_type": "click",
                "ad_id": "ad_202",
                "campaign_id": "camp_fast",
                "publisher_id": "pub_2",
                "ip_address": conv_ip,
                "click_id": click_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await client.post(API_URL, json=click_event)
            # Conversion happens instantly
            conv_event = {
                "event_type": "conversion",
                "ad_id": "ad_202",
                "campaign_id": "camp_fast",
                "publisher_id": "pub_2",
                "ip_address": conv_ip,
                "click_id": click_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await client.post(API_URL, json=conv_event)
            
        print("Data Seeding Complete.")
        print("Summary: 500 normal, 100 high-volume clicks from one IP, 20 fast conversions.")

if __name__ == "__main__":
    asyncio.run(generate_events())
