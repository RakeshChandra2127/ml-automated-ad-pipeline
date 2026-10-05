import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as redis

from app.api.routes import router
from app.config import get_settings
from app.database import init_db
from app.services.rate_limiter import SlidingWindowRateLimiter
from app.services.bloom_filter import BloomFilterService
from app.services.event_producer import EventProducer

@asynccontextmanager
async def lifespan(app: FastAPI):
    # On Startup
    settings = get_settings()
    
    # Init DB
    await init_db()
    
    # Connect Redis
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    app.state.redis = redis_client
    
    # Initialize Services
    app.state.rate_limiter = SlidingWindowRateLimiter(
        redis_client, 
        max_requests=settings.RATE_LIMIT_MAX_REQUESTS, 
        window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS
    )
    app.state.bloom_filter = BloomFilterService(
        redis_client, 
        filter_name="ad_clicks_bf", 
        capacity=1000000, 
        error_rate=0.01
    )
    app.state.event_producer = EventProducer(
        redis_client, 
        stream_name=settings.EVENT_STREAM_NAME
    )
    
    yield
    
    # On Shutdown
    await redis_client.close()

app = FastAPI(
    title="AdEventTracker - Distributed Ad Event Tracker & AI Fraud Detection",
    description="High-throughput ad event ingestion and LLM-powered fraud detection system.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

app.include_router(router)

@app.get("/")
async def root():
    return {
        "message": "Welcome to AdEventTracker API",
        "docs": "/docs",
        "health": "/api/v1/health"
    }
