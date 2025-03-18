import os

from cachelib import FileSystemCache

SESSION_TYPE = "cachelib"
SESSION_CACHELIB = FileSystemCache(
    cache_dir=os.environ.get("SESSION_CACHE_DIR", "/tmp/flask_session"),
    threshold=int(os.environ.get("SESSION_CACHE_THRESHOLD", 500)),
)
