from datetime import date, datetime, timezone

import pytest

from collector import inpe_fire_collector as c

HEADER = (
    "id,lat,lon,data_hora_gmt,satelite,municipio,estado,pais,municipio_id,"
    "estado_id,pais_id,numero_dias_sem_chuva,precipitacao,risco_fogo,bioma,frp"
)


def _csv(*rows: str) -> list[str]:
    return [HEADER, *rows]


ROW_REF = (
    "aaa,  -9.563100, -44.603000,2026-10-18 17:52:00,AQUA_M-T,REDENÇÃO DO GURGUÉIA,"
    "PIAUÍ,Brasil,2208700,22,33,2,0.66,0.06,Cerrado,71.9"
)
ROW_OTHER = (
    "bbb,  -4.180000, -45.760000,2026-10-18 00:15:00,MSG-03,SANTA LUZIA,"
    "MARANHÃO,Brasil,2110005,21,33,20,2.8,1.0,Amazônia,"
)


def test_parse_marks_reference_satellite_and_normalizes_fields():
    focos = list(c.parse_focos(_csv(ROW_REF)))

    assert len(focos) == 1
    f = focos[0]
    assert f.fonte_id == "aaa"
    assert f.is_ref is True
    assert f.uf == "PI"
    assert f.bioma == "cerrado"
    assert f.detectado_em == datetime(2026, 10, 18, 17, 52, tzinfo=timezone.utc)
    assert f.latitude == pytest.approx(-9.5631)
    assert f.frp == pytest.approx(71.9)
    assert f.municipio_id == 2208700


def test_parse_missing_frp_is_none_and_non_reference_satellite():
    f = list(c.parse_focos(_csv(ROW_OTHER)))[0]

    assert f.frp is None
    assert f.is_ref is False
    assert f.uf == "MA"
    assert f.bioma == "amazonia"


def test_parse_ignores_other_countries_and_bad_rows():
    outro_pais = ROW_REF.replace("Brasil", "Argentina")
    quebrada = "ccc,abc,def,data-ruim,AQUA_M-T,X,PIAUÍ,Brasil,1,22,33,1,0,0,Cerrado,1"

    focos = list(c.parse_focos(_csv(outro_pais, quebrada, ROW_REF)))

    assert [f.fonte_id for f in focos] == ["aaa"]


def test_parse_negative_sentinels_become_none():
    row = ROW_REF.replace(",2,0.66,0.06,", ",-999,-999,-999,")

    f = list(c.parse_focos(_csv(row)))[0]

    assert f.dias_sem_chuva is None
    assert f.precipitacao is None
    assert f.risco_fogo is None


@pytest.mark.parametrize("nome,sigla", [
    ("PIAUÍ", "PI"), ("piauí", "PI"), ("Pará", "PA"), ("RIO GRANDE DO SUL", "RS"),
    ("DISTRITO FEDERAL", "DF"), ("Mato Grosso do Sul", "MS"),
])
def test_normalizar_uf(nome, sigla):
    assert c.normalizar_uf(nome) == sigla


def test_normalizar_uf_unknown_returns_none():
    assert c.normalizar_uf("Narnia") is None
    assert c.normalizar_uf("") is None


def test_slug_bioma():
    assert c.slug_bioma("Mata Atlântica") == "mata-atlantica"
    assert c.slug_bioma("Amazônia") == "amazonia"
    assert c.slug_bioma("") is None


def test_agregar_focos_counts_by_day_and_level_reference_only():
    focos = list(c.parse_focos(_csv(ROW_REF, ROW_OTHER)))

    agg = c.agregar_focos(focos)

    d = date(2026, 10, 18)
    assert agg[(d, "brasil", "BR")].focos == 1
    assert agg[(d, "uf", "PI")].focos == 1
    assert agg[(d, "bioma", "cerrado")].focos == 1
    assert (d, "uf", "MA") not in agg
    assert agg[(d, "brasil", "BR")].frp_soma == pytest.approx(71.9)


def test_agregar_anual_ref_rows_have_no_satellite_column():
    linhas = [
        "id_bdq,foco_id,lat,lon,data_pas,pais,estado,municipio,bioma",
        "1,x1,-7.5,-37.7,2025-01-01 16:52:00,Brasil,PERNAMBUCO,SOLIDÃO,Caatinga",
        "2,x2,-7.6,-37.8,2025-01-01 17:10:00,Brasil,PERNAMBUCO,SOLIDÃO,Caatinga",
        "3,x3,-7.6,-37.8,2025-01-02 17:10:00,Argentina,SALTA,X,Chaco",
    ]

    agg = c.agregar_anual_ref(linhas)

    assert agg[(date(2025, 1, 1), "uf", "PE")].focos == 2
    assert agg[(date(2025, 1, 1), "bioma", "caatinga")].focos == 2
    assert (date(2025, 1, 2), "brasil", "BR") not in agg


def test_urls():
    assert c.url_diario(date(2026, 10, 18)).endswith("/diario/Brasil/focos_diario_br_20261018.csv")
    assert c.url_mensal(2026, 1).endswith("/mensal/Brasil/focos_mensal_br_202601.csv")
    assert c.url_anual_ref(2025).endswith("/anual/Brasil_sat_ref/focos_br_ref_2025.zip")


def test_janela_recente_covers_today_and_previous_days():
    assert c.janela_recente(date(2026, 10, 19), 2) == [date(2026, 10, 18), date(2026, 10, 19)]


def test_parse_handles_utf8_bom_on_header():
    linhas = ["\ufeff" + HEADER, ROW_REF]

    assert [f.fonte_id for f in c.parse_focos(linhas)] == ["aaa"]


def test_parse_estrito_fails_when_layout_changes():
    linhas = ["identificador,latitude", "x,1"]

    with pytest.raises(ValueError):
        c.parse_focos_estrito(linhas)
    assert c.parse_focos_estrito([HEADER]) == []


def test_num_rejects_nan_and_inf():
    assert c._num("nan") is None
    assert c._num("inf") is None
