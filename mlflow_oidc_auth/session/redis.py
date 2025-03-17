import os

import redis

SESSION_TYPE = "redis"
SESSION_REDIS = redis.Redis(
    host=os.environ.get("REDIS_HOST", "localhost"),
    port=int(os.environ.get("REDIS_PORT", 6379)),
    db=int(os.environ.get("REDIS_DB", 0)),
    password=os.environ.get("REDIS_PASSWORD", None),
    ssl=os.environ.get("REDIS_SSL", str(False)).lower() in ("true", "1", "t"),
    username=os.environ.get("REDIS_USERNAME", None),
)
