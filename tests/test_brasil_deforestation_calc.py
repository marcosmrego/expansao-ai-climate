from datetime import date, timedelta

import pytest

from app.services import brasil_deforestation_calc as dc


@pytest.mark.parametrize("dia,ano", [
    (date(2025, 7, 31), 2025), (date(2025, 8, 1), 2026), (date(2026, 1, 15), 2026),
    (date(2026, 7, 31), 2026), (date(2026, 8, 1), 2027), (date(2026, 10, 20), 2027),
])
def test_ano_prodes_runs_from_august_to_july(dia, ano):
    assert dc.ano_prodes(dia) == ano


def test_janela_prodes_covers_august_to_july():
    assert dc.janela_prodes(2026) == (date(2025, 8, 1), date(2026, 7, 31))


def test_janela_prodes_is_consistent_with_ano_prodes():
    inicio, fim = dc.janela_prodes(2027)

    assert dc.ano_prodes(inicio) == 2027
    assert dc.ano_prodes(fim) == 2027
    assert dc.ano_prodes(inicio - timedelta(days=1)) == 2026
    assert dc.ano_prodes(fim + timedelta(days=1)) == 2028


@pytest.mark.parametrize("classe,grupo", [
    ("DESMATAMENTO_CR", "desmatamento"), ("DESMATAMENTO_VEG", "desmatamento"),
    ("desmatamento_cr", "desmatamento"), ("DESMATAMENTO", "desmatamento"),
    ("CS_DESORDENADO", "corte_seletivo"), ("CS_GEOMETRICO", "corte_seletivo"),
    ("DEGRADACAO", "degradacao"), ("CICATRIZ_DE_QUEIMADA", "queimada"),
    ("MINERACAO", "mineracao"), ("ALGO_NOVO", "outras"), (None, "outras"), ("", "outras"),
])
def test_grupo_classe(classe, grupo):
    assert dc.grupo_classe(classe) == grupo


def test_only_clear_cut_groups_count_as_deforestation():
    assert dc.GRUPOS_DESMATAMENTO == {"desmatamento", "mineracao"}


@pytest.mark.parametrize("projeto,experimental", [
    ("deter-amz", False), ("deter-cerrado", False), ("deter-pantanal", True), ("prodes-amazonia", False),
])
def test_experimental_flag(projeto, experimental):
    assert dc.experimental(projeto) is experimental


def test_projetos_have_display_names():
    assert dc.PROJETO_NOMES["deter-amz"] == "DETER Amazônia"
    assert set(dc.PROJETOS_DETER) <= set(dc.PROJETO_NOMES)


@pytest.mark.parametrize("dia,esperado", [
    (date(2026, 10, 20), date(2025, 10, 20)),
    (date(2028, 2, 29), date(2027, 2, 28)),  # 29/02 não existe no ano anterior
    (date(2026, 3, 1), date(2025, 3, 1)),
])
def test_um_ano_antes(dia, esperado):
    assert dc.um_ano_antes(dia) == esperado


def test_periodos_dias_for_alert_windows():
    assert dc.PERIODOS_ALERTAS == {"30d": 30, "90d": 90, "365d": 365}
