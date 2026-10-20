from datetime import date

import pytest

from app.services import brasil_reservoir_calc as rc
from app.services import brasil_fire_calc as fc


@pytest.mark.parametrize("pct,faixa", [
    (0, "critico"), (19.9, "critico"), (20, "baixo"), (39.99, "baixo"), (40, "medio"),
    (60, "bom"), (79.9, "bom"), (80, "alto"), (101, "alto"),
])
def test_faixa_boundaries(pct, faixa):
    assert rc.faixa_de(pct) == faixa


def test_faixa_unknown_is_none():
    assert rc.faixa_de(None) is None


def test_recente_depends_on_system():
    hoje = date(2026, 10, 20)

    assert rc.recente("SIN", date(2026, 10, 15), hoje)
    assert not rc.recente("SIN", date(2026, 10, 10), hoje)
    assert rc.recente("NORDESTE", date(2026, 10, 1), hoje)
    assert not rc.recente("NORDESTE", date(2026, 9, 1), hoje)
    assert not rc.recente("SIN", None, hoje)


def test_media_weighted_when_all_have_capacity():
    valor, metodo = rc.media_pct([(50.0, 100.0), (100.0, 300.0)])

    assert metodo == "ponderada"
    assert valor == pytest.approx(87.5)


def test_media_simple_when_capacity_missing():
    valor, metodo = rc.media_pct([(50.0, None), (100.0, 300.0)])

    assert metodo == "simples"
    assert valor == pytest.approx(75.0)


def test_media_empty_is_none():
    assert rc.media_pct([]) == (None, None)


def test_variacao_pp():
    assert rc.variacao_pp(60.0, 50.5) == pytest.approx(9.5)
    assert rc.variacao_pp(None, 50.0) is None
    assert rc.variacao_pp(50.0, None) is None


def test_sistema_names_cover_all_systems():
    assert set(rc.SISTEMA_NOMES) == {"SIN", "NORDESTE", "CANTAREIRA", "DF", "RMBH"}


def test_parse_periodo_accepts_years():
    assert fc.parse_periodo("5y") == 1825
    assert fc.parse_periodo("10y") == 3650
    with pytest.raises(ValueError):
        fc.parse_periodo("11y")
