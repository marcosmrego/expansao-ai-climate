from datetime import date

from app.services import brasil_reservoir_service as svc

HOJE = date(2026, 10, 20)


def _linha(rid, nome, sistema, pct, prev=None, cap=None, uf="MG", data=date(2026, 10, 19), mun="X"):
    return (rid, nome, sistema, uf, mun, cap, data, pct, prev)


def _itens():
    linhas = [
        _linha(1, "ALFA ", "SIN", 90.0, 85.0),
        _linha(2, "BETA", "SIN", 15.0, 20.0),
        _linha(3, "GAMA", "SIN", 50.0, None),
        _linha(4, "VELHO", "SIN", 70.0, 70.0, data=date(2026, 9, 1)),
        _linha(5, "NE1", "NORDESTE", 10.0, 12.0, cap=100.0, uf="CE", data=date(2026, 10, 1)),
        _linha(6, "NE2", "NORDESTE", 30.0, 20.0, cap=300.0, uf="CE", data=date(2026, 10, 10)),
    ]
    return [svc._montar_item(l, HOJE) for l in linhas]


def test_montar_item_flags_and_variation():
    alfa = _itens()[0]

    assert alfa["nome"] == "ALFA"
    assert alfa["faixa"] == "alto"
    assert alfa["variacao_30d_pp"] == 5.0
    assert alfa["recente"] is True
    assert alfa["dias_desde_medicao"] == 1


def test_montar_item_stale_reading_is_not_recent():
    velho = _itens()[3]

    assert velho["recente"] is False
    assert velho["dias_desde_medicao"] == 49


def test_resumo_sistema_uses_only_recent_readings_and_variation_base():
    r = svc._resumo_sistema("SIN", _itens())

    assert r["total"] == 4
    assert r["com_medicao_recente"] == 3
    assert r["sem_medicao_recente"] == 1
    assert r["volume_pct_medio"] == round((90 + 15 + 50) / 3, 1)
    assert r["metodo_media"] == "simples"
    assert r["base_variacao"] == 2
    assert r["variacao_30d_pp"] == round(((90 + 15) / 2) - ((85 + 20) / 2), 1)
    assert r["faixas"]["critico"] == 1 and r["faixas"]["alto"] == 1 and r["faixas"]["medio"] == 1


def test_resumo_sistema_weighted_by_capacity():
    r = svc._resumo_sistema("NORDESTE", _itens())

    assert r["metodo_media"] == "ponderada"
    assert r["volume_pct_medio"] == round((10 * 100 + 30 * 300) / 400, 1)


def test_resumo_sistema_without_data_has_null_metrics():
    r = svc._resumo_sistema("DF", _itens())

    assert r["total"] == 0
    assert r["volume_pct_medio"] is None
    assert r["variacao_30d_pp"] is None
    assert r["data_mais_recente"] is None


def test_filtrar_by_system_uf_range_and_text():
    itens = _itens()

    assert [i["id"] for i in svc._filtrar(itens, "NORDESTE", None, None, None)] == [5, 6]
    assert [i["id"] for i in svc._filtrar(itens, None, "CE", "baixo", None)] == [6]
    assert [i["id"] for i in svc._filtrar(itens, None, None, None, "bet")] == [2]
    assert svc._filtrar(itens, "SIN", "CE", None, None) == []


def test_ordenar_puts_missing_values_last_and_supports_descending():
    itens = _itens()

    por_variacao = svc._ordenar(itens, "-variacao")
    assert por_variacao[0]["id"] == 6  # +10 pp
    assert por_variacao[-2]["variacao_30d_pp"] is None or por_variacao[-1]["variacao_30d_pp"] is None
    assert [i["id"] for i in svc._ordenar(itens, "volume")][:2] == [5, 2]
    assert svc._ordenar(itens, "nome")[0]["nome"] == "ALFA"


def test_ordenar_is_stable_and_accent_insensitive():
    linhas = [_linha(1, "ZULU", "SIN", 50.0), _linha(2, "Água Clara", "SIN", 50.0), _linha(3, "BETA", "SIN", 50.0)]
    itens = [svc._montar_item(l, HOJE) for l in linhas]

    assert [i["nome"] for i in svc._ordenar(itens, "nome")] == ["Água Clara", "BETA", "ZULU"]
    assert [i["id"] for i in svc._ordenar(itens, "volume")] == [2, 3, 1]  # empate: por nome, depois id
