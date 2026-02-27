import json

import pytest

from app.cache import BaseCache, LocalFileCache


class TestLocalFileCache:
    # Cycle 1 — cache miss returns None
    def test_get_returns_none_for_missing_key(self, tmp_path):
        cache = LocalFileCache(str(tmp_path))
        assert cache.get("nonexistent") is None

    # Cycle 2 — set/get roundtrip
    def test_set_get_roundtrip(self, tmp_path):
        cache = LocalFileCache(str(tmp_path))
        value = {"summary": "A project", "technologies": ["Python"], "structure": "flat"}
        cache.set("mykey", value, ttl=3600)
        assert cache.get("mykey") == value

    # Cycle 3 — TTL expiry
    def test_get_returns_none_for_expired_entry(self, tmp_path):
        cache = LocalFileCache(str(tmp_path))
        payload = {"expires_at": 1.0, "data": {"summary": "old"}}
        (tmp_path / "mykey.json").write_text(json.dumps(payload))
        assert cache.get("mykey") is None

    # Cycle 4 — corrupted file
    def test_get_returns_none_for_corrupted_file(self, tmp_path):
        cache = LocalFileCache(str(tmp_path))
        (tmp_path / "mykey.json").write_text("not valid json {{{")
        assert cache.get("mykey") is None

    def test_base_cache_is_abstract(self):
        with pytest.raises(TypeError):
            BaseCache()  # type: ignore[abstract]


# Cycle 5 — Config defaults
def test_settings_has_cache_defaults():
    from app.config import Settings
    s = Settings()
    assert s.cache_enabled is True
    assert s.cache_ttl == 604800
    assert s.cache_dir == ".cache"
