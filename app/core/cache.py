import time


class TTLCache:
    """Cache em memória com expiração por entrada."""

    def __init__(self, ttl: int = 3600, max_entries: int = 512):
        self._store: dict = {}
        self._ttl = ttl
        self._max = max_entries

    def get(self, key: str):
        entry = self._store.get(key)
        if entry and time.monotonic() < entry[1]:
            return entry[0]
        self._store.pop(key, None)
        return None

    def set(self, key: str, value) -> None:
        now = time.monotonic()
        if len(self._store) >= self._max:
            self._store = {k: v for k, v in self._store.items() if v[1] > now}
        if len(self._store) >= self._max:
            self._store.pop(next(iter(self._store)))
        self._store[key] = (value, now + self._ttl)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()
