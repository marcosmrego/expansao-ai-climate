import pytest
from fastapi import HTTPException

from app.routes import collect


def test_auth_allows_any_key_when_secret_is_unset(monkeypatch):
    monkeypatch.setattr(collect, "_COLLECTOR_SECRET", "")

    collect._auth("")


def test_auth_accepts_matching_key(monkeypatch):
    monkeypatch.setattr(collect, "_COLLECTOR_SECRET", "segredo-é")

    collect._auth("segredo-é")


@pytest.mark.parametrize("key", ["", "errado", "segredo-é "])
def test_auth_rejects_wrong_key(monkeypatch, key):
    monkeypatch.setattr(collect, "_COLLECTOR_SECRET", "segredo-é")

    with pytest.raises(HTTPException) as exc:
        collect._auth(key)

    assert exc.value.status_code == 401
