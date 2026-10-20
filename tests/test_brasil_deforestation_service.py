from datetime import date

import pytest

from app.services import brasil_deforestation_service as svc

HOJE = date(2026, 10, 20)


def _resumo(**sobrescritas):
    base = dict(
        projeto="deter-amz", periodo="30d", hoje=HOJE, ultima_data=date(2026, 10, 15),
        primeira_data=date(2016, 8, 1),
        por_grupo=[("desmatamento", 120.456, 40), ("degradacao", 30.0, 10), ("queimada", 5.0, 3)],
        por_uf=[("PA", 80.0, 25), ("MT", 30.0, 10), (None, 10.456, 5)],
        acumulado_atual=300.0, acumulado_anterior=250.0,
    )
    return svc.montar_resumo(**{**base, **sobrescritas})


def test_resumo_window_and_freshness():
    r = _resumo()

    assert r["inicio"] == "2026-09-21"  # 30 dias contando hoje
    assert r["fim"] == "2026-10-20"
    assert r["dados_ate"] == "2026-10-15"
    assert r["dias_defasagem"] == 5
    assert r["projeto_nome"] == "DETER Amazônia"


def test_resumo_deforestation_total_excludes_other_classes():
    r = _resumo()

    assert r["desmatamento_km2"] == 120.46
    assert [g["grupo"] for g in r["por_grupo"]] == ["desmatamento", "degradacao", "queimada"]
    assert r["por_grupo"][1]["nome"] == "Degradação"


def test_resumo_counts_mining_as_deforestation():
    r = _resumo(por_grupo=[("desmatamento", 100.0, 40), ("mineracao", 5.5, 4), ("degradacao", 30.0, 10)])

    assert r["desmatamento_km2"] == 105.5
    assert r["desmatamento_alertas"] == 44


def test_resumo_labels_missing_uf():
    r = _resumo()

    assert [u["uf"] for u in r["por_uf"]] == ["PA", "MT", "N/D"]
    assert r["por_uf"][0]["alertas"] == 25


def test_resumo_prodes_year_compares_with_previous_year():
    prodes = _resumo()["ano_prodes"]

    assert prodes["ano"] == 2027
    assert prodes["inicio"] == "2026-08-01"
    assert prodes["acumulado_km2"] == 300.0
    assert prodes["anterior"] == {"ano": 2026, "acumulado_km2": 250.0, "ate": "2025-10-20"}
    assert prodes["variacao_pct"] == 20.0


def test_resumo_hides_comparison_when_history_is_incomplete():
    prodes = _resumo(primeira_data=date(2026, 7, 22))["ano_prodes"]

    assert prodes["anterior"] is None
    assert prodes["variacao_pct"] is None
    assert prodes["acumulado_km2"] == 300.0


def test_resumo_variation_is_none_when_previous_is_zero():
    prodes = _resumo(acumulado_anterior=0.0)["ano_prodes"]

    assert prodes["variacao_pct"] is None


def test_resumo_without_any_data():
    r = _resumo(ultima_data=None, primeira_data=None, por_grupo=[], por_uf=[],
                acumulado_atual=0.0, acumulado_anterior=0.0)

    assert r["dados_ate"] is None
    assert r["dias_defasagem"] is None
    assert r["desmatamento_km2"] == 0.0
    assert r["por_grupo"] == []
    assert r["ano_prodes"]["anterior"] is None


def test_resumo_experimental_warning(monkeypatch):
    monkeypatch.setattr(svc.dc, "PROJETOS_EXPERIMENTAIS", frozenset({"deter-amz"}))

    r = _resumo()

    assert r["experimental"] is True
    assert "experimental" in r["aviso_experimental"].lower()
    assert _resumo(projeto="deter-cerrado")["experimental"] is False


@pytest.mark.parametrize("periodo", ["7d", "1y", "abc"])
def test_resumo_rejects_unknown_period(periodo):
    with pytest.raises(ValueError):
        _resumo(periodo=periodo)


def test_serie_mensal_fills_missing_months_with_zero():
    linhas = [(date(2026, 8, 1), 10.0, 4), (date(2026, 10, 1), 30.126, 9)]

    pontos = svc.montar_serie(linhas, hoje=HOJE, meses=3)

    assert pontos == [
        {"mes": "2026-08", "area_km2": 10.0, "alertas": 4},
        {"mes": "2026-09", "area_km2": 0.0, "alertas": 0},
        {"mes": "2026-10", "area_km2": 30.13, "alertas": 9},
    ]


class _FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.conn.consultas.append((sql, params))

    def fetchall(self):
        return self.conn.linhas


class _FakeConn:
    def __init__(self, linhas):
        self.linhas, self.consultas = linhas, []

    def cursor(self):
        return _FakeCursor(self)

    def close(self):
        pass


@pytest.fixture
def banco(monkeypatch):
    svc.invalidar_cache()
    conn = _FakeConn([(date(2026, 10, 15), "DESMATAMENTO_CR", "desmatamento", 1.23456, "PA", "Altamira", False)])
    monkeypatch.setattr(svc, "conectar", lambda: conn)
    return conn


def _agora():
    from datetime import datetime
    return datetime(2026, 10, 20, 12, 0, tzinfo=svc._FUSO)


def test_ultimos_alertas_formats_rows_and_passes_filters_as_parameters(banco):
    r = svc.ultimos_alertas("deter-amz", "30d", "PA", "desmatamento", 20, agora=_agora())

    assert r["itens"] == [{"data": "2026-10-15", "classe": "DESMATAMENTO_CR", "grupo": "desmatamento",
                           "area_km2": 1.2346, "uf": "PA", "municipio": "Altamira", "experimental": False}]
    sql, params = banco.consultas[-1]
    assert "%s::text IS NULL" in sql and "'" not in sql.split("WHERE")[1]
    assert params == ("deter-amz", date(2026, 9, 21), date(2026, 10, 20), "PA", "PA", "desmatamento", "desmatamento", 20)


def test_ultimos_alertas_is_cached_per_day_and_filter(banco):
    svc.ultimos_alertas("deter-amz", "30d", None, None, 50, agora=_agora())
    svc.ultimos_alertas("deter-amz", "30d", None, None, 50, agora=_agora())
    svc.ultimos_alertas("deter-amz", "30d", "MT", None, 50, agora=_agora())

    selects = [c for c in banco.consultas if c[0].lstrip().startswith("SELECT")]
    assert len(selects) == 2  # a repetição veio do cache; outra UF consulta de novo


def test_ultimos_alertas_clamps_limit_and_rejects_bad_project(banco):
    assert svc.ultimos_alertas("deter-amz", "30d", None, None, 99999, agora=_agora())["limite"] == svc.LIMITE_ALERTAS_MAX
    with pytest.raises(ValueError):
        svc.ultimos_alertas("prodes", "30d", None, None, 10, agora=_agora())


def test_invalidar_cache_clears_alert_cache(banco):
    svc.ultimos_alertas("deter-amz", "30d", None, None, 50, agora=_agora())
    svc.invalidar_cache()
    svc.ultimos_alertas("deter-amz", "30d", None, None, 50, agora=_agora())

    assert len([c for c in banco.consultas if c[0].lstrip().startswith("SELECT")]) == 2


def test_inicio_periodo_counts_today_as_part_of_the_window():
    assert svc.inicio_periodo(HOJE, "30d") == date(2026, 9, 21)
    assert (HOJE - svc.inicio_periodo(HOJE, "365d")).days == 364


# ── Soma anual dos polígonos PRODES ───────────────────────────────────────────

_LINHAS_TAXA = [(2022, "TOTAL", 12689.0), (2023, "TOTAL", 8020.4), (2023, "PA", 4000.0),
                (2023, "MT", 2000.2), (2022, "PA", 6000.0)]


def test_montar_taxas_serie_anual_e_ranking_do_ultimo_ano():
    r = svc.montar_taxas("deter-amz", _LINHAS_TAXA)

    assert r["projeto"] == "deter-amz"
    assert r["fonte"] == "PRODES Amazônia Legal"
    assert r["anos"] == [{"ano": 2022, "area_km2": 12689.0}, {"ano": 2023, "area_km2": 8020.4}]
    assert r["ultimo_ano"] == 2023
    assert r["por_uf"] == [{"uf": "PA", "area_km2": 4000.0}, {"uf": "MT", "area_km2": 2000.2}]
    assert r["variacao_pct"] == pytest.approx(-36.8, abs=0.1)


def test_montar_taxas_sem_dados():
    r = svc.montar_taxas("deter-cerrado", [])

    assert r["anos"] == [] and r["ultimo_ano"] is None and r["por_uf"] == [] and r["variacao_pct"] is None


def test_taxas_consulta_o_projeto_prodes_correspondente(monkeypatch):
    svc.invalidar_cache()
    conn = _FakeConn(_LINHAS_TAXA)
    monkeypatch.setattr(svc, "conectar", lambda: conn)

    r = svc.taxas("deter-cerrado")

    assert conn.consultas[-1][1] == ("prodes-cerrado",)
    assert r["fonte"] == "PRODES Cerrado"
    svc.taxas("deter-cerrado")
    assert len(conn.consultas) == 2  # statement_timeout + 1 consulta; o 2º uso vem do cache
