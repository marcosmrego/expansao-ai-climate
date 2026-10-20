from datetime import date

import pytest

from collector import prodes_collector as pc


def _f(uf, ano, area, classe="DESMATAMENTO"):
    return {"properties": {"state": uf, "year": ano, "area_km": area, "main_class": classe}}


def test_agregar_soma_por_ano_e_uf_so_desmatamento():
    feicoes = [_f("PA", 2023, 1.5), _f("PA", 2023, 2.5), _f("MT", 2023, 3.0),
               _f("PA", 2023, 9.0, "RESIDUO"), _f("pa", 2022, 1.0, "desmatamento")]

    r = pc.agregar(feicoes)

    assert r == {(2023, "PA"): 4.0, (2023, "MT"): 3.0, (2022, "PA"): 1.0}


@pytest.mark.parametrize("feicao", [
    None, {}, {"properties": None}, _f("PA", 2023, -1), _f("PA", 2023, "x"), _f("PA", "2023", 1.0),
    _f("PA", 1900, 1.0), _f("PAR", 2023, 1.0), _f(None, 2023, 1.0), _f("PA", 2023, float("nan")),
])
def test_agregar_ignora_feicoes_invalidas(feicao):
    assert pc.agregar([feicao]) == {}


def test_linhas_inclui_total_por_ano():
    linhas = pc.linhas("prodes-amazonia", {(2023, "PA"): 4.0, (2023, "MT"): 3.0, (2022, "PA"): 1.0})

    assert ("prodes-amazonia", 2023, "TOTAL", 7.0) in linhas
    assert ("prodes-amazonia", 2023, "PA", 4.0) in linhas
    assert ("prodes-amazonia", 2022, "TOTAL", 1.0) in linhas
    assert len(linhas) == 5


def test_anos_incrementais_cobre_os_ultimos_anos_e_historico_completo_com_desde():
    assert pc.anos_a_coletar(date(2026, 10, 20), None, "prodes-amazonia") == [2024, 2025, 2026]
    assert pc.anos_a_coletar(date(2026, 10, 20), 2022, "prodes-amazonia") == [2022, 2023, 2024, 2025, 2026]
    assert pc.anos_a_coletar(date(2026, 10, 20), 1990, "prodes-amazonia")[0] == pc.ANO_INICIAL["prodes-amazonia"]


def test_filtro_cql():
    assert pc.filtro_cql(2023) == "year=2023"


class _Resp:
    def __init__(self, dados):
        self._dados = dados

    def json(self):
        return self._dados


def _paginas(monkeypatch, paginas):
    fila = iter(paginas)
    monkeypatch.setattr(pc, "_consultar", lambda params: _Resp(next(fila)))
    monkeypatch.setattr(pc.time, "sleep", lambda s: None)


def test_baixar_ano_soma_paginas_e_confere_numero_de_feicoes(monkeypatch):
    monkeypatch.setattr(pc, "PAGE_SIZE", 2)
    _paginas(monkeypatch, [
        {"features": [_f("PA", 2023, 1.0), _f("PA", 2023, 2.0)], "numberMatched": 3},
        {"features": [_f("MT", 2023, 4.0)], "numberMatched": 3},
    ])

    recebidas, soma = pc._baixar_ano("prodes-amazonia", 2023)

    assert recebidas == 3 and soma == {(2023, "PA"): 3.0, (2023, "MT"): 4.0}


def test_baixar_ano_falha_se_o_servidor_truncar_a_resposta(monkeypatch):
    _paginas(monkeypatch, [{"features": [_f("PA", 2023, 1.0)], "numberMatched": 52376}])

    with pytest.raises(RuntimeError, match="52376"):
        pc._baixar_ano("prodes-amazonia", 2023)


def test_baixar_ano_falha_se_muitas_feicoes_de_desmatamento_forem_descartadas(monkeypatch):
    ruins = [_f(None, 2023, 1.0) for _ in range(5)]
    _paginas(monkeypatch, [{"features": ruins + [_f("PA", 2023, 1.0)], "numberMatched": 6}])

    with pytest.raises(RuntimeError, match="descartadas"):
        pc._baixar_ano("prodes-amazonia", 2023)
