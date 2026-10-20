from datetime import date

import pytest

from collector import sar_reservoir_collector as c

SIN_ATTRS = {
    "SAR_ID": 19001, "SAR_NM": "CAMARGOS ", "SAR_SG_UF": "MG", "SAR_NM_MUNICIPIO": "ITUTINGA",
    "SAR_NM_BACIA": "GRANDE", "SAR_QT_CAPACIDADE": 672.0, "SAR_NU_LATITUDE": -21.3, "SAR_NU_LONGITUDE": -44.6,
    "SAR_PC_VOLUME": None, "SAR_VO_UTIL_ULTIMA": 84.68, "SAR_VO_ULTIMA": 1234.0, "SAR_CO_ULTIMA": 907.1,
    "SAR_DT_ULTIMA_MEDICAO": "18/10/2026", "SAR_ULT_AFLUENCIA": 120.5, "SAR_ULT_DEFLUENCIA": 98.0,
}
NORDESTE_ATTRS = {
    "SAR_ID": 12001, "SAR_NM": "25 DE MARÇO", "SAR_SG_UF": "RN", "SAR_QT_CAPACIDADE": 4.72,
    "SAR_PC_VOLUME": 4.23549343, "SAR_VO_ULTIMA": 0.2, "SAR_CO_ULTIMA": 96.9,
    "SAR_DT_ULTIMA_MEDICAO": "13/10/2026",
}


def test_normalizar_sin_uses_useful_volume_and_hides_absolute_volume():
    reservatorio, leitura = c.normalizar_feature(SIN_ATTRS, "SIN")

    assert reservatorio.nome == "CAMARGOS"
    assert reservatorio.sistema == "SIN" and reservatorio.uf == "MG"
    assert leitura.volume_pct == pytest.approx(84.68)
    assert leitura.volume_hm3 is None
    assert leitura.data == date(2026, 10, 18)
    assert leitura.fonte == "sar_api"


def test_normalizar_nordeste_uses_pc_volume_and_keeps_hm3():
    _, leitura = c.normalizar_feature(NORDESTE_ATTRS, "NORDESTE")

    assert leitura.volume_pct == pytest.approx(4.2355, abs=1e-3)
    assert leitura.volume_hm3 == pytest.approx(0.2)


def test_normalizar_falls_back_to_the_other_percentage_field():
    attrs = {**NORDESTE_ATTRS, "SAR_PC_VOLUME": None, "SAR_VO_UTIL_ULTIMA": 12.5}

    assert c.normalizar_feature(attrs, "NORDESTE")[1].volume_pct == 12.5


def test_normalizar_drops_out_of_range_coordinates_and_capacity():
    attrs = {**SIN_ATTRS, "SAR_NU_LATITUDE": 999, "SAR_NU_LONGITUDE": -400, "SAR_QT_CAPACIDADE": 1e12}

    reservatorio, _ = c.normalizar_feature(attrs, "SIN")

    assert reservatorio.latitude is None
    assert reservatorio.longitude is None
    assert reservatorio.capacidade_hm3 is None


def test_normalizar_truncates_overlong_text():
    reservatorio, _ = c.normalizar_feature({**SIN_ATTRS, "SAR_NM": "X" * 5000}, "SIN")

    assert len(reservatorio.nome) == 200


def test_normalizar_invalid_date_keeps_reservoir_but_drops_reading():
    reservatorio, leitura = c.normalizar_feature({**SIN_ATTRS, "SAR_DT_ULTIMA_MEDICAO": "sem data"}, "SIN")

    assert reservatorio is not None
    assert leitura is None


@pytest.mark.parametrize("attrs", [{}, {"SAR_ID": "x", "SAR_NM": "A"}, {"SAR_ID": 1, "SAR_NM": "  "}])
def test_normalizar_rejects_rows_without_id_or_name(attrs):
    assert c.normalizar_feature(attrs, "SIN") == (None, None)


def test_normalizar_rejects_absurd_percentage():
    _, leitura = c.normalizar_feature({**NORDESTE_ATTRS, "SAR_PC_VOLUME": 9999, "SAR_VO_UTIL_ULTIMA": None}, "NORDESTE")

    assert leitura.volume_pct is None


SIN_HTML = """
<table><tr><th>Código</th><th>Reservatório</th></tr>
<tr><td>19001</td><td>CAMARGOS</td><td>907,27</td><td>198,75</td><td>180,00</td><td>0,00</td><td>180,00</td>
<td>195,81</td><td>46,66</td><td></td><td>01/01/2021</td></tr>
<tr><td>19001</td><td>CAMARGOS</td><td>1.907,23</td><td>156,00</td><td>181,00</td><td>0,00</td><td>181,00</td>
<td>159,45</td><td>46,34</td><td>141,76</td><td>02/01/2021</td></tr>
</table>
"""
NORDESTE_HTML = """
<table><tr><td>Estado</td></tr>
<tr><td>Rio Grande do Norte</td><td>25 DE MAR&#199;O</td><td>4,72</td><td>96,88</td><td>1,78</td><td>37,70</td><td>01/01/2024</td></tr>
<tr><td>Rio Grande do Norte</td><td>25 DE MAR&#199;O</td><td>4,72</td><td>96,88</td><td>1,78</td><td>37,70</td><td>01/01/2024</td></tr>
</table>
"""


def test_parse_pagina_sin():
    leituras = c.parse_pagina_historico(SIN_HTML, 19001, "SIN")

    assert [l.data for l in leituras] == [date(2021, 1, 1), date(2021, 1, 2)]
    assert leituras[0].volume_pct == pytest.approx(46.66)
    assert leituras[0].cota_m == pytest.approx(907.27)
    assert leituras[1].cota_m == pytest.approx(1907.23)
    assert leituras[1].afluencia_m3s == pytest.approx(156.0)
    assert all(l.fonte == "sar_pagina" and l.reservatorio_id == 19001 for l in leituras)


def test_parse_pagina_nordeste_dedupes_same_day():
    leituras = c.parse_pagina_historico(NORDESTE_HTML, 12001, "NORDESTE")

    assert len(leituras) == 1
    assert leituras[0].volume_pct == pytest.approx(37.70)
    assert leituras[0].volume_hm3 == pytest.approx(1.78)


def test_parse_pagina_ignores_header_and_garbage():
    assert c.parse_pagina_historico("<html>nada</html>", 1, "SIN") == []
    assert c.parse_pagina_historico("<tr><td>a</td><td>b</td></tr>", 1, "NORDESTE") == []


def test_num_br():
    assert c._num_br("1.234,56") == 1234.56
    assert c._num_br("") is None
    assert c._num_br("abc") is None


def test_normalizar_rejects_reading_dated_in_the_future():
    attrs = {**NORDESTE_ATTRS, "SAR_DT_ULTIMA_MEDICAO": "18/05/2027"}

    reservatorio, leitura = c.normalizar_feature(attrs, "NORDESTE", hoje=date(2026, 10, 20))

    assert reservatorio is not None
    assert leitura is None


class _RespostaFalsa:
    def __init__(self, blocos):
        self._blocos = blocos
        self.fechada = False

    def iter_content(self, chunk_size=0):
        yield from self._blocos

    def close(self):
        self.fechada = True


def test_ler_limitado_joins_chunks_and_closes():
    r = _RespostaFalsa([b"abc", b"def"])

    out = c._ler_limitado(r)

    assert out._content == b"abcdef"
    assert r.fechada


def test_ler_limitado_rejects_oversized_body(monkeypatch):
    monkeypatch.setattr(c, "_MAX_BYTES", 5)
    r = _RespostaFalsa([b"abc", b"def"])

    with pytest.raises(c._ErroDefinitivo):
        c._ler_limitado(r)
    assert r.fechada


def test_baixar_camada_stops_on_runaway_pagination(monkeypatch):
    class R:
        @staticmethod
        def json():
            return {"features": [{"attributes": {"SAR_ID": 1}}], "exceededTransferLimit": True}

    monkeypatch.setattr(c, "_get", lambda *a, **k: R())
    monkeypatch.setattr(c, "_MAX_PAGINAS", 3)

    with pytest.raises(RuntimeError):
        c.baixar_camada(0)


def test_num_br_handles_percent_and_dot_decimals():
    assert c._num_br("85,3 %") == 85.3
    assert c._num_br("85.5") == 85.5
    assert c._num_br("1.234,5") == 1234.5


def test_data_br_ignores_time_suffix():
    assert c._data_br("19/10/2026 00:00") == date(2026, 10, 19)
    assert c._data_br("") is None


def test_normalizar_drops_out_of_range_numbers_instead_of_failing_the_batch():
    attrs = {**NORDESTE_ATTRS, "SAR_CO_ULTIMA": 1e12, "SAR_VO_ULTIMA": -9999}

    _, leitura = c.normalizar_feature(attrs, "NORDESTE", hoje=date(2026, 10, 20))

    assert leitura.cota_m is None
    assert leitura.volume_hm3 is None
    assert leitura.volume_pct is not None


def test_parse_sin_page_drops_rows_of_other_reservoirs():
    html_ = SIN_HTML.replace("<td>19001</td><td>CAMARGOS</td><td>1.907,23", "<td>19002</td><td>OUTRO</td><td>1.907,23")

    leituras = c.parse_pagina_historico(html_, 19001, "SIN")

    assert [l.data for l in leituras] == [date(2021, 1, 1)]


def test_parse_nordeste_page_checks_reservoir_name():
    assert len(c.parse_pagina_historico(NORDESTE_HTML, 12001, "NORDESTE", "25 de março")) == 1
    assert c.parse_pagina_historico(NORDESTE_HTML, 12001, "NORDESTE", "OUTRO") == []


def test_parse_accepts_uppercase_tags():
    assert len(c.parse_pagina_historico(SIN_HTML.upper(), 19001, "SIN")) == 2


def test_baixar_camada_empty_layer_is_an_error(monkeypatch):
    class R:
        @staticmethod
        def json():
            return {"features": []}

    monkeypatch.setattr(c, "_get", lambda *a, **k: R())

    with pytest.raises(RuntimeError):
        c.baixar_camada(0)
