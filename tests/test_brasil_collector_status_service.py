from datetime import datetime, timezone

import pytest

from app.services import brasil_collector_status_service as svc

T = datetime(2026, 10, 21, 14, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("status,sem_sinal,esperado", [
    ("running", 30, "running"),
    ("running", svc.SEGUNDOS_SEM_SINAL + 1, "parado"),
    ("running", None, "running"),
    ("ok", 99999, "ok"),
    ("erro", 99999, "erro"),
])
def test_estado_marks_silent_running_as_stopped(status, sem_sinal, esperado):
    assert svc.estado(status, sem_sinal) == esperado


@pytest.mark.parametrize("feitas,total,esperado", [
    (62, 123, 50.4), (0, 10, 0.0), (10, 10, 100.0), (12, 10, 100.0),
    (None, 10, None), (5, None, None), (5, 0, None), (-1, 10, None),
])
def test_percentual(feitas, total, esperado):
    assert svc.percentual(feitas, total) == esperado


def test_execucao_builds_label_progress_and_truncates_error():
    linha = (7, "deter_desmatamento", "running", T, None, None, "x" * 900, "deter-amz · 2021-05", 62, 123, T, 30)

    e = svc._execucao(linha)

    assert e["rotulo"] == "Desmatamento · alertas DETER"
    assert e["estado"] == "running" and e["percentual"] == 50.4
    assert e["inicio"] == T.isoformat() and e["fim"] is None
    assert len(e["erro"]) == svc._MAX_ERRO_EXIBIDO


def test_execucao_keeps_unknown_source_name_as_label():
    linha = (1, "outra_fonte", "ok", T, T, 10, None, None, None, None, None, 5)

    assert svc._execucao(linha)["rotulo"] == "outra_fonte"


class _Cur:
    def __init__(self, linhas):
        self.linhas = linhas

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        pass

    def fetchall(self):
        return self.linhas


class _Conn:
    def __init__(self, linhas):
        self.linhas, self.fechada = linhas, False

    def cursor(self):
        return _Cur(self.linhas)

    def close(self):
        self.fechada = True


def test_execucoes_flags_in_progress_and_closes_connection(monkeypatch):
    conn = _Conn([(2, "inpe_focos", "ok", T, T, 5, None, None, None, None, None, 9),
                  (1, "deter_desmatamento", "running", T, None, None, None, "deter-amz · 2021-05", 1, 4, T, 20)])
    monkeypatch.setattr(svc, "conectar", lambda: conn)

    r = svc.execucoes()

    assert r["em_andamento"] is True and len(r["execucoes"]) == 2
    assert conn.fechada


def test_execucoes_not_in_progress_when_run_is_stopped(monkeypatch):
    conn = _Conn([(1, "deter_desmatamento", "running", T, None, None, None, None, None, None, None, 99999)])
    monkeypatch.setattr(svc, "conectar", lambda: conn)

    r = svc.execucoes()

    assert r["em_andamento"] is False and r["execucoes"][0]["estado"] == "parado"
