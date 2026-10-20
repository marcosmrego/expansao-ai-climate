from datetime import date

import pytest

from app.services import brasil_fire_calc as calc


@pytest.mark.parametrize("texto,dias", [("24h", 1), ("48h", 2), ("7d", 7), ("365d", 365), (" 30D ", 30)])
def test_parse_periodo_valid(texto, dias):
    assert calc.parse_periodo(texto) == dias


@pytest.mark.parametrize("texto", ["", "abc", "0d", "-1d", "99999d", "7", "7w", None])
def test_parse_periodo_invalid(texto):
    with pytest.raises(ValueError):
        calc.parse_periodo(texto)


def test_janelas_base_same_dates_prior_years():
    jan = calc.janelas_base(date(2026, 10, 18), 30, ano_inicial=2024)

    assert jan == [
        (date(2024, 9, 19), date(2024, 10, 18), 2024),
        (date(2025, 9, 19), date(2025, 10, 18), 2025),
    ]


def test_janelas_base_short_period_widened_to_seven_days_centered():
    (ini, fim, ano), = calc.janelas_base(date(2026, 10, 18), 1, ano_inicial=2025)

    assert (fim - ini).days + 1 == calc.comprimento_base(1) == 7
    assert ini <= date(2025, 10, 18) <= fim
    assert ano == 2025


def test_janelas_base_leap_day_does_not_crash():
    jan = calc.janelas_base(date(2024, 2, 29), 1, ano_inicial=2023)

    assert jan[0][2] == 2023
    assert jan[0][0].year == 2023


def test_anomalia_above_normal():
    r = calc.anomalia(20.0, [10.0, 12.0, 8.0, 10.0])

    assert r["media_historica"] == 10.0
    assert r["variacao_pct"] == 100.0
    assert r["situacao"] == "acima"
    assert r["z"] > 1


def test_anomalia_below_and_normal():
    base = [10.0, 12.0, 8.0, 10.0]

    assert calc.anomalia(5.0, base)["situacao"] == "abaixo"
    assert calc.anomalia(10.5, base)["situacao"] == "normal"


def test_anomalia_not_enough_history_returns_none_fields():
    r = calc.anomalia(5.0, [4.0, 6.0])

    assert r["media_historica"] is None
    assert r["situacao"] is None


def test_anomalia_zero_baseline_has_no_percentage():
    r = calc.anomalia(3.0, [0.0, 0.0, 0.0, 0.0])

    assert r["variacao_pct"] is None
    assert r["z"] is None


def test_desvio_de_somas_matches_direct_computation():
    valores = [0, 0, 4, 6, 0]
    soma, soma_q = sum(valores), sum(v * v for v in valores)
    media = soma / len(valores)
    esperado = (sum((v - media) ** 2 for v in valores) / (len(valores) - 1)) ** 0.5

    assert calc.desvio_de_somas(soma, soma_q, len(valores)) == pytest.approx(esperado)
    assert calc.desvio_de_somas(1, 1, 1) == 0.0


def test_codigo_valido_and_nome():
    assert calc.codigo_valido("uf", "PI")
    assert not calc.codigo_valido("uf", "XX")
    assert calc.codigo_valido("bioma", "mata-atlantica")
    assert calc.codigo_valido("brasil", "BR")
    assert calc.nome_codigo("bioma", "mata-atlantica") == "Mata Atlântica"
    assert calc.nome_codigo("uf", "PI") == "Piauí"


def test_celula_mapa_zoom():
    assert calc.celula_mapa(3) == 2.0
    assert calc.celula_mapa(5) == 0.5
    assert calc.celula_mapa(7) is None


def test_janelas_base_period_crossing_new_year_is_not_inverted():
    jan = calc.janelas_base(date(2026, 10, 19), 365, ano_inicial=2003)

    assert jan[0][2] == 2004  # 2003 não tem o ano anterior inteiro
    for ini, fim, ano in jan:
        assert ini < fim
        assert (fim - ini).days + 1 == 365 or (fim - ini).days + 1 == 366
        assert fim.year == ano


def test_janelas_base_january_period():
    jan = calc.janelas_base(date(2026, 1, 15), 30, ano_inicial=2024)

    # 2024 ficaria com início em dez/2023, antes da série; só 2025 é completo
    assert jan == [(date(2024, 12, 17), date(2025, 1, 15), 2025)]
