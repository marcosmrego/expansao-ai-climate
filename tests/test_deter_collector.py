from datetime import date, timedelta

import pytest

from collector import deter_collector as d

@pytest.fixture(autouse=True)
def sem_pausas(monkeypatch):
    monkeypatch.setattr(d.time, "sleep", lambda _s: None)


FEATURE = {
    "type": "Feature", "id": "deter_amz.4711",
    "properties": {
        "classname": "DESMATAMENTO_CR", "view_date": "2026-10-10", "areamunkm": 0.1234,
        "municipality": "Altamira ", "uf": "pa", "sensor": "AWFI", "satellite": "CBERS-4",
        "publish_month": "2026-10-01",
    },
}


def test_normalizar_maps_fields_and_group():
    alerta = d.normalizar_feature(FEATURE, "deter-amz")

    assert alerta.projeto == "deter-amz"
    assert alerta.fonte_id == "deter_amz.4711"
    assert alerta.data_alerta == date(2026, 10, 10)
    assert alerta.publicado_em == date(2026, 10, 1)
    assert alerta.classe == "DESMATAMENTO_CR"
    assert alerta.grupo == "desmatamento"
    assert alerta.area_km2 == pytest.approx(0.1234)
    assert alerta.uf == "PA"
    assert alerta.municipio == "Altamira"
    assert alerta.experimental is False


def test_normalizar_accepts_cerrado_layer_without_municipality():
    feature = {**FEATURE, "id": "deter_cerrado.9", "properties": {**FEATURE["properties"], "municipality": None}}

    alerta = d.normalizar_feature(feature, "deter-cerrado")

    assert alerta.projeto == "deter-cerrado"
    assert alerta.municipio is None


@pytest.mark.parametrize("campo,valor", [
    ("view_date", None), ("view_date", "ontem"), ("view_date", "2999-01-01"),
    ("classname", None), ("classname", "  "),
    ("areamunkm", None), ("areamunkm", "x"), ("areamunkm", -1), ("areamunkm", 1e9), ("areamunkm", float("nan")),
])
def test_normalizar_rejects_unusable_features(campo, valor):
    feature = {**FEATURE, "properties": {**FEATURE["properties"], campo: valor}}

    assert d.normalizar_feature(feature, "deter-amz") is None


def test_normalizar_rejects_feature_without_id():
    assert d.normalizar_feature({"properties": FEATURE["properties"]}, "deter-amz") is None
    assert d.normalizar_feature("lixo", "deter-amz") is None


def test_normalizar_truncates_text_and_bad_uf():
    props = {**FEATURE["properties"], "municipality": "M" * 900, "uf": "Pará"}

    alerta = d.normalizar_feature({**FEATURE, "properties": props}, "deter-amz")

    assert len(alerta.municipio) == 200
    assert alerta.uf == "PA"


def test_normalizar_drops_invalid_uf():
    props = {**FEATURE["properties"], "uf": "1"}

    assert d.normalizar_feature({**FEATURE, "properties": props}, "deter-amz").uf is None


def test_janelas_mensais_cover_range_without_gaps():
    janelas = list(d.janelas_mensais(date(2026, 8, 15), date(2026, 10, 20)))

    assert janelas == [
        (date(2026, 8, 15), date(2026, 9, 1)),
        (date(2026, 9, 1), date(2026, 10, 1)),
        (date(2026, 10, 1), date(2026, 10, 21)),
    ]


def test_janelas_mensais_empty_when_start_after_end():
    assert list(d.janelas_mensais(date(2026, 10, 21), date(2026, 10, 20))) == []


def test_cql_uses_half_open_interval():
    assert d.filtro_cql(date(2026, 9, 1), date(2026, 10, 1)) == "view_date>='2026-09-01' AND view_date<'2026-10-01'"


def test_inicio_incremental_reaches_back_lookback_days():
    assert d.inicio_incremental(date(2026, 10, 10)) == date(2026, 10, 10) - timedelta(days=d.DIAS_RECUO)
    assert d.inicio_incremental(None) == d.INICIO_HISTORICO


class _Resp:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status

    def json(self):
        return self._payload


def _cheia():
    return [FEATURE] * d.PAGE_SIZE


def test_baixar_janela_single_request_when_page_not_full(monkeypatch):
    chamadas = []
    monkeypatch.setattr(d, "_consultar", lambda p: chamadas.append(p) or _Resp({"features": [FEATURE] * 3}))

    brutos = d.baixar_janela("deter-amz", date(2026, 10, 1), date(2026, 11, 1))

    assert len(brutos) == 3
    assert len(chamadas) == 1


def test_baixar_janela_splits_window_that_fills_a_page(monkeypatch):
    consultas = []

    def falso(params):
        consultas.append(params["cql_filter"])
        inteira = params["cql_filter"] == d.filtro_cql(date(2026, 10, 1), date(2026, 10, 5))
        return _Resp({"features": _cheia() if inteira else [FEATURE] * 2})

    monkeypatch.setattr(d, "_consultar", falso)

    brutos = d.baixar_janela("deter-amz", date(2026, 10, 1), date(2026, 10, 5))

    assert len(brutos) == 4
    assert consultas == [
        d.filtro_cql(date(2026, 10, 1), date(2026, 10, 5)),
        d.filtro_cql(date(2026, 10, 1), date(2026, 10, 3)),
        d.filtro_cql(date(2026, 10, 3), date(2026, 10, 5)),
    ]


def test_baixar_janela_paginates_only_a_single_day_that_overflows(monkeypatch):
    paginas = [{"features": _cheia()}, {"features": [FEATURE] * 3}]
    indices = []

    def falso(params):
        indices.append(params["startIndex"])
        return _Resp(paginas[len(indices) - 1])

    monkeypatch.setattr(d, "_consultar", falso)

    brutos = d.baixar_janela("deter-amz", date(2026, 10, 1), date(2026, 10, 2))

    assert len(brutos) == d.PAGE_SIZE + 3
    assert indices == [0, d.PAGE_SIZE]


def test_baixar_janela_raises_when_a_day_never_ends(monkeypatch):
    monkeypatch.setattr(d, "_consultar", lambda params: _Resp({"features": _cheia()}))

    with pytest.raises(RuntimeError, match="paginação"):
        d.baixar_janela("deter-amz", date(2026, 10, 1), date(2026, 10, 2))


def test_baixar_janela_rejects_non_geojson(monkeypatch):
    monkeypatch.setattr(d, "_consultar", lambda params: _Resp({"unexpected": True}))

    with pytest.raises(RuntimeError, match="FeatureCollection"):
        d.baixar_janela("deter-amz", date(2026, 10, 1), date(2026, 11, 1))


class _Conn:
    def __init__(self):
        self.rollbacks = 0

    def rollback(self):
        self.rollbacks += 1


@pytest.fixture
def orquestracao(monkeypatch):
    eventos = {"lock": True, "liberado": 0, "final": None}
    monkeypatch.setattr(d, "_obter_lock", lambda conn: eventos["lock"])
    monkeypatch.setattr(d, "_liberar_lock", lambda conn: eventos.__setitem__("liberado", eventos["liberado"] + 1))
    monkeypatch.setattr(d, "iniciar_execucao", lambda *a, **k: 1)
    monkeypatch.setattr(d, "finalizar_execucao",
                        lambda conn, run_id, registros, erro: eventos.__setitem__("final", (registros, erro)))
    return eventos


def test_coletar_skips_when_another_run_holds_the_lock(orquestracao):
    orquestracao["lock"] = False

    resultado = d.coletar(_Conn(), hoje=date(2026, 10, 20))

    assert resultado["ignorado"] == "coleta já em andamento"
    assert orquestracao["liberado"] == 0


def test_coletar_isolates_a_failing_project(monkeypatch, orquestracao):
    def processar(conn, projeto, hoje, desde):
        if projeto == "deter-amz":
            raise requests_erro()
        return 5

    monkeypatch.setattr(d, "_processar_projeto", processar)

    resultado = d.coletar(_Conn(), hoje=date(2026, 10, 20))

    assert resultado == {"registros": 5, "erros": ["deter-amz: HTTPError"]}
    assert orquestracao["final"] == (5, "deter-amz: HTTPError")
    assert orquestracao["liberado"] == 1


def test_coletar_releases_the_lock_on_success(monkeypatch, orquestracao):
    monkeypatch.setattr(d, "_processar_projeto", lambda conn, projeto, hoje, desde: 2)

    resultado = d.coletar(_Conn(), hoje=date(2026, 10, 20))

    assert resultado == {"registros": 4, "erros": []}
    assert orquestracao["final"] == (4, None)
    assert orquestracao["liberado"] == 1


def requests_erro():
    return d.requests.HTTPError("HTTP 503")


class _Cursor:
    def __init__(self, registro):
        self.registro, self.rowcount = registro, 7

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.registro.append((sql, params))


class _ConnSQL:
    def __init__(self):
        self.consultas, self.commits = [], 0

    def cursor(self):
        return _Cursor(self.consultas)

    def commit(self):
        self.commits += 1


def test_remover_ausentes_deletes_only_inside_window_for_the_project():
    conn = _ConnSQL()

    apagadas = d.remover_ausentes(conn, "deter-amz", date(2026, 9, 1), date(2026, 10, 1), ["a", "b"])

    sql, params = conn.consultas[0]
    assert apagadas == 7
    assert "DELETE FROM climate.deforestation_alert" in sql
    assert "projeto = %s" in sql and "NOT (fonte_id = ANY(%s))" in sql
    assert params == ("deter-amz", date(2026, 9, 1), date(2026, 10, 1), ["a", "b"])


def test_exigir_aproveitamento_fails_when_most_features_are_unusable():
    with pytest.raises(RuntimeError, match="schema"):
        d._exigir_aproveitamento("deter-amz", date(2026, 10, 1), recebidas=10, aproveitadas=4)


def test_exigir_aproveitamento_accepts_empty_window_and_minor_loss():
    d._exigir_aproveitamento("deter-amz", date(2026, 10, 1), recebidas=0, aproveitadas=0)
    d._exigir_aproveitamento("deter-amz", date(2026, 10, 1), recebidas=10, aproveitadas=9)


@pytest.fixture
def processamento(monkeypatch):
    estado = {"gravados": [], "removidos": [], "janelas": []}
    monkeypatch.setattr(d, "_ultima_data", lambda conn, projeto: estado.get("ultima"))

    def baixar(projeto, inicio, fim):
        estado["janelas"].append((inicio, fim))
        return estado.get("brutos", [FEATURE])

    monkeypatch.setattr(d, "baixar_janela", baixar)
    monkeypatch.setattr(d, "gravar_alertas", lambda conn, alertas: estado["gravados"].append(list(alertas)) or len(estado["gravados"][-1]))
    monkeypatch.setattr(d, "remover_ausentes", lambda *a: estado["removidos"].append(a) or 0)
    estado["progresso"] = []
    monkeypatch.setattr(d, "registrar_progresso", lambda conn, fonte, etapa, feitas, total: estado["progresso"].append((fonte, etapa, feitas, total)))
    monkeypatch.setattr(d, "contar_na_fonte", lambda *a: estado.get("na_fonte", len(estado.get("brutos", [FEATURE]))))
    monkeypatch.setattr(d, "contar_no_banco", lambda *a: estado.get("no_banco", len({f["id"] for f in estado.get("brutos", [FEATURE])})))
    return estado


def test_processar_projeto_first_run_loads_last_90_days(processamento):
    conn = _ConnSQL()

    total = d._processar_projeto(conn, "deter-amz", date(2026, 10, 20), None)

    assert processamento["janelas"][0][0] == date(2026, 10, 20) - timedelta(days=d.DIAS_PRIMEIRA_COLETA)
    assert total == len(processamento["janelas"])
    assert conn.commits == len(processamento["janelas"])


def test_processar_projeto_incremental_starts_before_last_date(processamento):
    processamento["ultima"] = date(2026, 10, 10)

    d._processar_projeto(_ConnSQL(), "deter-amz", date(2026, 10, 20), None)

    assert processamento["janelas"][0][0] == date(2026, 10, 10) - timedelta(days=d.DIAS_RECUO)


def test_processar_projeto_removes_stale_rows_with_ids_that_arrived(processamento):
    d._processar_projeto(_ConnSQL(), "deter-amz", date(2026, 10, 20), date(2026, 10, 1))

    _, projeto, inicio, fim, ids = processamento["removidos"][0]
    assert (projeto, inicio, fim, ids) == ("deter-amz", date(2026, 10, 1), date(2026, 10, 21), ["deter_amz.4711"])


def test_processar_projeto_keeps_existing_rows_when_source_window_is_empty(processamento):
    processamento["brutos"] = []

    d._processar_projeto(_ConnSQL(), "deter-amz", date(2026, 10, 20), date(2026, 10, 1))

    assert processamento["removidos"] == []


def test_processar_projeto_raises_when_source_has_more_features_than_downloaded(processamento):
    processamento["na_fonte"] = 500

    with pytest.raises(d.ContagemDivergente):
        d._processar_projeto(_ConnSQL(), "deter-amz", date(2026, 10, 20), date(2026, 10, 1))


def test_processar_projeto_raises_when_database_lacks_what_was_written(processamento):
    processamento["no_banco"] = 0

    with pytest.raises(d.ContagemDivergente):
        d._processar_projeto(_ConnSQL(), "deter-amz", date(2026, 10, 20), date(2026, 10, 1))


def test_processar_projeto_keeps_going_through_all_windows_before_raising(processamento):
    processamento["na_fonte"] = 500
    conn = _ConnSQL()

    with pytest.raises(d.ContagemDivergente):
        d._processar_projeto(conn, "deter-amz", date(2026, 12, 20), date(2026, 10, 1))

    assert len(processamento["janelas"]) == 3
    assert conn.commits == 3


def test_processar_projeto_accepts_empty_source_window_even_if_database_has_rows(processamento):
    processamento["brutos"] = []
    processamento["no_banco"] = 40

    d._processar_projeto(_ConnSQL(), "deter-amz", date(2026, 10, 20), date(2026, 10, 1))


def test_contagem_diverge_tolerates_small_drift_only():
    assert not d.contagem_diverge(8000, 7995)
    assert d.contagem_diverge(8000, 7900)
    assert not d.contagem_diverge(0, 1)
    assert d.contagem_diverge(0, 5)


def test_contar_na_fonte_reads_number_matched(monkeypatch):
    chamadas = []
    monkeypatch.setattr(d, "_consultar", lambda p: chamadas.append(p) or _Resp({"features": [], "numberMatched": 8300}))

    assert d.contar_na_fonte("deter-amz", date(2016, 8, 1), date(2016, 9, 1)) == 8300
    assert chamadas[0]["count"] == 1


@pytest.mark.parametrize("payload", [{"features": []}, {"numberMatched": "8300"}, {"numberMatched": -1}, [1]])
def test_contar_na_fonte_rejects_missing_or_invalid_count(monkeypatch, payload):
    monkeypatch.setattr(d, "_consultar", lambda p: _Resp(payload))

    with pytest.raises(RuntimeError):
        d.contar_na_fonte("deter-amz", date(2016, 8, 1), date(2016, 9, 1))


def test_processar_projeto_reports_progress_per_window(processamento):
    d._processar_projeto(_ConnSQL(), "deter-amz", date(2026, 12, 20), date(2026, 10, 1))

    assert processamento["progresso"] == [
        ("deter_desmatamento", "deter-amz · 2026-10", 1, 3),
        ("deter_desmatamento", "deter-amz · 2026-11", 2, 3),
        ("deter_desmatamento", "deter-amz · 2026-12", 3, 3),
    ]
