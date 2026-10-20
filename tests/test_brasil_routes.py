import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes import brasil
from app.services import brasil_fire_service as svc


@pytest.fixture
def client(monkeypatch):
    chamadas = {}

    def fake(nome):
        def _f(*args, **kwargs):
            chamadas[nome] = args
            return {"ok": nome}
        return _f

    monkeypatch.setattr(svc, "resumo", fake("resumo"))
    monkeypatch.setattr(svc, "serie", fake("serie"))
    monkeypatch.setattr(svc, "mapa", fake("mapa"))
    monkeypatch.setattr(svc, "status", fake("status"))
    app = FastAPI()
    app.include_router(brasil.router)
    c = TestClient(app)
    c.chamadas = chamadas
    return c


def test_resumo_defaults_and_passthrough(client):
    r = client.get("/api/brasil/focos/resumo")

    assert r.status_code == 200
    assert client.chamadas["resumo"] == ("uf", "30d")


@pytest.mark.parametrize("qs", ["periodo=xyz", "periodo=0d", "nivel=cidade"])
def test_resumo_rejects_bad_input(client, qs):
    assert client.get(f"/api/brasil/focos/resumo?{qs}").status_code == 422


def test_serie_validates_code_for_level(client):
    assert client.get("/api/brasil/focos/serie?nivel=uf&codigo=XX").status_code == 422
    assert client.get("/api/brasil/focos/serie?nivel=uf&codigo=PA").status_code == 200
    assert client.get("/api/brasil/focos/serie?nivel=bioma&codigo=cerrado").status_code == 200
    assert client.get("/api/brasil/focos/serie").status_code == 200


@pytest.mark.parametrize("bbox", ["1,2", "a,b,c,d", "10,0,5,5", "-200,0,0,0", "0,-95,1,1"])
def test_mapa_rejects_bad_bbox(client, bbox):
    assert client.get(f"/api/brasil/focos/mapa?bbox={bbox}").status_code == 422


def test_mapa_parses_bbox_and_limits(client):
    r = client.get("/api/brasil/focos/mapa?bbox=-50,-20,-40,-10&zoom=8&limite=50")

    assert r.status_code == 200
    periodo, bbox, zoom, limite, somente_ref = client.chamadas["mapa"]
    assert bbox == (-50.0, -20.0, -40.0, -10.0)
    assert (zoom, limite, somente_ref) == (8, 50, False)
    assert client.get("/api/brasil/focos/mapa?limite=999999").status_code == 422
    assert client.get("/api/brasil/focos/mapa?zoom=99").status_code == 422


def test_service_failure_returns_generic_500(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("segredo interno do banco")

    monkeypatch.setattr(svc, "status", boom)

    r = client.get("/api/brasil/status")

    assert r.status_code == 500
    assert "segredo" not in r.text
