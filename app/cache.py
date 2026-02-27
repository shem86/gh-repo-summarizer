import json
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class BaseCache(ABC):
    @abstractmethod
    def get(self, key: str) -> Optional[dict]:
        ...

    @abstractmethod
    def set(self, key: str, value: dict, ttl: int) -> None:
        ...


class LocalFileCache(BaseCache):
    def __init__(self, cache_dir: str) -> None:
        self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self._dir / f"{key}.json"

    def get(self, key: str) -> Optional[dict]:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            if data["expires_at"] < time.time():
                return None
            return data["data"]
        except (json.JSONDecodeError, KeyError, OSError):
            return None

    def set(self, key: str, value: dict, ttl: int) -> None:
        path = self._path(key)
        tmp = path.with_suffix(".tmp")
        payload = {"expires_at": time.time() + ttl, "data": value}
        tmp.write_text(json.dumps(payload))
        tmp.rename(path)
