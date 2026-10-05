import asyncio
import signal
import logging
import redis.asyncio as redis
from app.config import get_settings
from app.database import init_db, AsyncSessionLocal
from app.services.event_consumer import EventConsumer
from app.services.fraud_analyst import FraudAnalystAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

shutdown_event = asyncio.Event()

def handle_sigint(*args):
    logger.info("Received shutdown signal. Stopping worker...")
    shutdown_event.set()

async def fraud_analysis_loop(redis_client, settings):
    logger.info("Starting scheduled fraud analysis loop...")
    analyst = FraudAnalystAgent(settings)
    interval = getattr(settings, 'FRAUD_ANALYSIS_INTERVAL_MINUTES', 60) * 60
    
    while not shutdown_event.is_set():
        try:
            logger.info("Running scheduled fraud analysis...")
            async with AsyncSessionLocal() as db:
                report = await analyst.analyze(db, window_minutes=60)
                logger.info(f"Fraud analysis complete. Report ID: {report.id}")
        except Exception as e:
            logger.error(f"Error during fraud analysis: {e}")
        
        # Wait for the interval or until shutdown is requested
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue

async def main():
    logger.info("Starting worker process...")
    settings = get_settings()
    
    await init_db()
    
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    
    consumer = EventConsumer(
        redis=redis_client,
        db_session_factory=AsyncSessionLocal,
        stream_name=settings.EVENT_STREAM_NAME,
        group_name="event_consumers_group",
        consumer_name="worker_1"
    )

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, handle_sigint)
    loop.add_signal_handler(signal.SIGTERM, handle_sigint)

    consumer_task = asyncio.create_task(consumer.start_consuming())
    fraud_task = asyncio.create_task(fraud_analysis_loop(redis_client, settings))
    
    # Wait until shutdown
    await shutdown_event.wait()
    
    # Graceful shutdown
    logger.info("Cancelling tasks...")
    consumer_task.cancel()
    fraud_task.cancel()
    
    await asyncio.gather(consumer_task, fraud_task, return_exceptions=True)
    await redis_client.close()
    logger.info("Worker process terminated gracefully.")

if __name__ == "__main__":
    asyncio.run(main())
