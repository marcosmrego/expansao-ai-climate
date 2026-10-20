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


@pytest.fixture
def client_res(monkeypatch):
    from app.services import brasil_reservoir_service as rsvc
    chamadas = {}

    def fake(nome, retorno=None):
        def _f(*args, **kwargs):
            chamadas[nome] = args
            return {"ok": nome} if retorno is None else retorno
        return _f

    monkeypatch.setattr(rsvc, "resumo", fake("resumo"))
    monkeypatch.setattr(rsvc, "listar", fake("listar"))
    monkeypatch.setattr(rsvc, "serie", fake("serie"))
    app = FastAPI()
    app.include_router(brasil.router)
    c = TestClient(app)
    c.chamadas = chamadas
    c.rsvc = rsvc
    c.monkeypatch = monkeypatch
    return c


def test_reservatorios_lista_normalizes_uf_and_passes_filters(client_res):
    r = client_res.get("/api/brasil/reservatorios?sistema=SIN&uf=mg&faixa=baixo&q=cam&ordem=nome&offset=10&limite=20")

    assert r.status_code == 200
    assert client_res.chamadas["listar"] == ("SIN", "MG", "baixo", "cam", "nome", 10, 20)


@pytest.mark.parametrize("qs", ["sistema=XX", "uf=123", "uf=1a", "faixa=otimo", "ordem=x", "limite=0", "limite=9999", "offset=-1"])
def test_reservatorios_lista_rejects_bad_input(client_res, qs):
    assert client_res.get(f"/api/brasil/reservatorios?{qs}").status_code == 422


def test_reservatorio_serie_404_and_validation(client_res):
    client_res.monkeypatch.setattr(client_res.rsvc, "serie", lambda *a, **k: None)

    assert client_res.get("/api/brasil/reservatorios/19001/serie").status_code == 404
    assert client_res.get("/api/brasil/reservatorios/19001/serie?periodo=abc").status_code == 422
    assert client_res.get("/api/brasil/reservatorios/19001/serie?periodo=77d").status_code == 422
    assert client_res.get("/api/brasil/reservatorios/0/serie").status_code == 422
    assert client_res.get("/api/brasil/reservatorios/abc/serie").status_code == 422


def test_reservatorio_serie_default_period_is_five_years(client_res):
    assert client_res.get("/api/brasil/reservatorios/19001/serie").status_code == 200
    assert client_res.chamadas["serie"] == (19001, "5y")


@pytest.fixture
def client_des(monkeypatch):
    from app.services import brasil_deforestation_service as dsvc

    chamadas = {}

    def fake(nome):
        def _f(*args, **kwargs):
            chamadas[nome] = args
            return {"ok": nome}
        return _f

    monkeypatch.setattr(dsvc, "resumo", fake("resumo"))
    monkeypatch.setattr(dsvc, "serie", fake("serie"))
    monkeypatch.setattr(dsvc, "ultimos_alertas", fake("alertas"))
    app = FastAPI()
    app.include_router(brasil.router)
    c = TestClient(app)
    c.chamadas = chamadas
    return c


def test_desmatamento_resumo_passes_defaults(client_des):
    r = client_des.get("/api/brasil/desmatamento/resumo")

    assert r.status_code == 200
    assert client_des.chamadas["resumo"] == ("deter-amz", "90d")


def test_desmatamento_resumo_accepts_cerrado_and_period(client_des):
    assert client_des.get("/api/brasil/desmatamento/resumo?projeto=deter-cerrado&periodo=365d").status_code == 200
    assert client_des.chamadas["resumo"] == ("deter-cerrado", "365d")


@pytest.mark.parametrize("qs", ["projeto=prodes", "projeto=x", "periodo=7d", "periodo=abc"])
def test_desmatamento_resumo_rejects_bad_input(client_des, qs):
    assert client_des.get(f"/api/brasil/desmatamento/resumo?{qs}").status_code == 422


def test_desmatamento_serie_validates_months(client_des):
    assert client_des.get("/api/brasil/desmatamento/serie?meses=36").status_code == 200
    assert client_des.chamadas["serie"] == ("deter-amz", 36)
    assert client_des.get("/api/brasil/desmatamento/serie?meses=0").status_code == 422
    assert client_des.get("/api/brasil/desmatamento/serie?meses=999").status_code == 422


def test_desmatamento_alertas_normalizes_uf_and_filters(client_des):
    r = client_des.get("/api/brasil/desmatamento/alertas?uf=pa&grupo=desmatamento&limite=20")

    assert r.status_code == 200
    assert client_des.chamadas["alertas"] == ("deter-amz", "30d", "PA", "desmatamento", 20)


@pytest.mark.parametrize("qs", ["uf=1", "uf=PAR", "grupo=lixo", "limite=0", "limite=9999"])
def test_desmatamento_alertas_rejects_bad_input(client_des, qs):
    assert client_des.get(f"/api/brasil/desmatamento/alertas?{qs}").status_code == 422


def test_desmatamento_hides_internal_errors(client_des, monkeypatch):
    from app.services import brasil_deforestation_service as dsvc

    def boom(*a, **k):
        raise RuntimeError("senha=segredo host=db")

    monkeypatch.setattr(dsvc, "resumo", boom)

    r = client_des.get("/api/brasil/desmatamento/resumo")

    assert r.status_code == 500
    assert "segredo" not in r.text


def test_desmatamento_alertas_rejects_nonexistent_uf(client_des):
    assert client_des.get("/api/brasil/desmatamento/alertas?uf=ZZ").status_code == 422
    assert client_des.get("/api/brasil/desmatamento/alertas?uf=pa").status_code == 200
