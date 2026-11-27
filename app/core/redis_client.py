import json
import redis.asyncio as redis
from fastapi import HTTPException
from app.core.config import settings

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

async def check_rate_limit(user_id: int, limit: int = 15, window_seconds: int = 60):
    """Allows max 15 messages per minute per user using Redis atomic counters."""
    key = f"rate_limit:user:{user_id}"
    current_count = await redis_client.incr(key)
    if current_count == 1:
        await redis_client.expire(key, window_seconds)
    if current_count > limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again in a minute.")
    
async def get_cached_history(user_id: int) -> list[dict]:
    """Fetches recent conversation turns directly from Redis RAM."""
    key = f"chat_history:user:{user_id}"
    raw_items = await redis_client.lrange(key, -6, -1)
    return [json.loads(item) for item in raw_items]

async def append_cached_history(user_id: int, role: str, message: str):
    """Saves latest turn in Redis with a 24-hour TTL."""
    key = f"chat_history:user:{user_id}"
    await redis_client.rpush(key, json.dumps({"role": role, "message": message}))
    await redis_client.ltrim(key, -10, -1)
    await redis_client.expire(key, 86400)