import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes import collect
from app.services import brasil_deforestation_service as dsvc
from app.services import brasil_fire_service as fsvc
from collector import deter_collector
from database import db


class _Conn:
    def __init__(self, eventos):
        self.eventos = eventos

    def close(self):
        self.eventos.append("close")


@pytest.fixture
def api(monkeypatch):
    eventos = []
    resposta = {"valor": {"registros": 3, "erros": []}}

    def coletar(conn):
        eventos.append("coletar")
        if isinstance(resposta["valor"], Exception):
            raise resposta["valor"]
        return resposta["valor"]

    monkeypatch.setattr(db, "conectar", lambda: _Conn(eventos))
    monkeypatch.setattr(deter_collector, "coletar", coletar)
    monkeypatch.setattr(dsvc, "invalidar_cache", lambda: eventos.append("cache_desmatamento"))
    monkeypatch.setattr(fsvc, "invalidar_cache", lambda: eventos.append("cache_status"))
    monkeypatch.setattr(collect, "_COLLECTOR_SECRET", "")
    app = FastAPI()
    app.include_router(collect.router)
    cliente = TestClient(app)
    cliente.eventos, cliente.resposta = eventos, resposta
    return cliente


def test_collect_deter_ok_invalidates_caches_after_closing(api):
    r = api.post("/api/collect/deter_desmatamento")

    assert r.status_code == 200
    assert r.json() == {"status": "ok", "registros": 3, "erros": []}
    assert api.eventos == ["coletar", "close", "cache_desmatamento", "cache_status"]


def test_collect_deter_partial_failure_is_reported_not_hidden(api):
    api.resposta["valor"] = {"registros": 3, "erros": ["deter-cerrado: HTTPError"]}

    r = api.post("/api/collect/deter_desmatamento")

    assert r.status_code == 200
    assert r.json()["status"] == "partial"


def test_collect_deter_all_projects_failing_is_502(api):
    api.resposta["valor"] = {"registros": 0, "erros": ["deter-amz: HTTPError", "deter-cerrado: HTTPError"]}

    assert api.post("/api/collect/deter_desmatamento").status_code == 502


def test_collect_deter_skipped_when_another_run_holds_the_lock(api):
    api.resposta["valor"] = {"registros": 0, "erros": [], "ignorado": "coleta já em andamento"}

    assert api.post("/api/collect/deter_desmatamento").json()["status"] == "skipped"


def test_collect_deter_invalidates_caches_even_when_collection_crashes(api):
    api.resposta["valor"] = RuntimeError("senha=segredo")

    r = api.post("/api/collect/deter_desmatamento")

    assert r.status_code == 500
    assert "segredo" not in r.text
    assert "cache_desmatamento" in api.eventos and "close" in api.eventos


def test_collect_deter_requires_key_when_secret_is_configured(api, monkeypatch):
    monkeypatch.setattr(collect, "_COLLECTOR_SECRET", "abc")

    assert api.post("/api/collect/deter_desmatamento").status_code == 401
    assert api.post("/api/collect/deter_desmatamento", headers={"x-api-key": "abc"}).status_code == 200
