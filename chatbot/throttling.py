import time
import redis
from collections import defaultdict
from fastapi import HTTPException, status
from typing import Dict, List
import json
import logging

logger = logging.getLogger(__name__)

# Rate limiting configuration
RATE_LIMITS = {
    "global_unauthenticated_user": {"limit": 20, "window": 60},  # 20 requests per minute
    "authenticated_user": {"limit": 100, "window": 60},  # 100 requests per minute
    "premium_user": {"limit": 500, "window": 60},  # 500 requests per minute
}

# In-memory fallback
user_requests = defaultdict(list)

# Redis connection (optional)
try:
    redis_client = redis.Redis(host='redis', port=6379, db=1, decode_responses=True)
    redis_client.ping()
    logger.info("Redis connection for rate limiting established")
except Exception as e:
    logger.warning(f"Redis connection failed: {e}. Using in-memory rate limiting.")
    redis_client = None

class RateLimiter:
    def __init__(self):
        self.redis_client = redis_client
        self.memory_store = user_requests
    
    def _get_rate_limit_config(self, user_type: str) -> Dict:
        """Get rate limit configuration for user type."""
        return RATE_LIMITS.get(user_type, RATE_LIMITS["global_unauthenticated_user"])
    
    def _get_requests_from_redis(self, key: str, window: int) -> List[float]:
        """Get recent requests from Redis."""
        try:
            current_time = time.time()
            # Remove old requests
            self.redis_client.zremrangebyscore(key, 0, current_time - window)
            # Get remaining requests
            requests = self.redis_client.zrangebyscore(key, current_time - window, current_time)
            return [float(req) for req in requests]
        except Exception as e:
            logger.error(f"Error getting requests from Redis: {e}")
            return []
    
    def _add_request_to_redis(self, key: str, timestamp: float, window: int):
        """Add request to Redis with expiration."""
        try:
            self.redis_client.zadd(key, {str(timestamp): timestamp})
            self.redis_client.expire(key, window)
        except Exception as e:
            logger.error(f"Error adding request to Redis: {e}")
    
    def _get_requests_from_memory(self, key: str, window: int) -> List[float]:
        """Get recent requests from memory."""
        current_time = time.time()
        self.memory_store[key] = [
            t for t in self.memory_store[key] 
            if t > current_time - window
        ]
        return self.memory_store[key]
    
    def _add_request_to_memory(self, key: str, timestamp: float):
        """Add request to memory store."""
        self.memory_store[key].append(timestamp)
    
    def check_rate_limit(self, user_id: str, user_type: str = "global_unauthenticated_user") -> Dict:
        """Check if user has exceeded rate limit."""
        config = self._get_rate_limit_config(user_type)
        limit = config["limit"]
        window = config["window"]
        
        current_time = time.time()
        key = f"rate_limit:{user_id}"
        
        # Get recent requests
        if self.redis_client:
            recent_requests = self._get_requests_from_redis(key, window)
        else:
            recent_requests = self._get_requests_from_memory(key, window)
        
        # Check if limit exceeded
        if len(recent_requests) >= limit:
            reset_time = min(recent_requests) + window
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Rate limit exceeded",
                    "limit": limit,
                    "window": window,
                    "current_usage": len(recent_requests),
                    "reset_time": reset_time,
                    "retry_after": int(reset_time - current_time)
                }
            )
        
        # Add current request
        if self.redis_client:
            self._add_request_to_redis(key, current_time, window)
        else:
            self._add_request_to_memory(key, current_time)
        
        # Return current status
        return {
            "allowed": True,
            "limit": limit,
            "remaining": limit - len(recent_requests) - 1,
            "reset_time": current_time + window
        }

# Global rate limiter instance
rate_limiter = RateLimiter()

def apply_rate_limit(user_id: str, user_type: str = "global_unauthenticated_user") -> Dict:
    """Apply rate limiting to a user."""
    return rate_limiter.check_rate_limit(user_id, user_type)

def get_rate_limit_info(user_id: str, user_type: str = "global_unauthenticated_user") -> Dict:
    """Get current rate limit information without consuming a request."""
    config = rate_limiter._get_rate_limit_config(user_type)
    key = f"rate_limit:{user_id}"
    
    if rate_limiter.redis_client:
        recent_requests = rate_limiter._get_requests_from_redis(key, config["window"])
    else:
        recent_requests = rate_limiter._get_requests_from_memory(key, config["window"])
    
    return {
        "limit": config["limit"],
        "remaining": config["limit"] - len(recent_requests),
        "reset_time": time.time() + config["window"],
        "window": config["window"]
    }