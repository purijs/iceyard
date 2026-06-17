import threading
import time
from collections import defaultdict, deque


class FixedWindowRateLimiter:
    """In-memory sliding-window limiter (per-process).

    Suitable for single-node deployments and for protecting auth endpoints from
    brute force. A multi-replica deployment should back this with a shared store.
    """

    def __init__(self, max_attempts: int, window_seconds: float):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        moment = now if now is not None else time.monotonic()
        with self._lock:
            hits = self._hits[key]
            cutoff = moment - self.window_seconds
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.max_attempts:
                return False
            hits.append(moment)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
