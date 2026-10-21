import pytest

from collector import run_log


class _Cursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        if self.conn.falha:
            raise RuntimeError("coluna etapa não existe")
        self.conn.consultas.append((sql, params))


class _Conn:
    def __init__(self, falha=False):
        self.consultas, self.commits, self.rollbacks, self.falha = [], 0, 0, falha

    def cursor(self):
        return _Cursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_registrar_progresso_updates_only_the_running_run_of_the_source():
    conn = _Conn()

    run_log.registrar_progresso(conn, "deter_desmatamento", "deter-amz · 2021-05", 62, 123)

    sql, params = conn.consultas[0]
    assert "status = 'running'" in sql and "WHERE fonte = %s" in sql
    assert params == ("deter-amz · 2021-05", 62, 123, "deter_desmatamento")
    assert conn.commits == 1


def test_registrar_progresso_truncates_long_stage():
    conn = _Conn()

    run_log.registrar_progresso(conn, "x", "a" * 500, 1, 2)

    assert len(conn.consultas[0][1][0]) == run_log._MAX_ETAPA


def test_registrar_progresso_never_breaks_the_collection():
    conn = _Conn(falha=True)

    run_log.registrar_progresso(conn, "x", "etapa", 1, 2)  # não levanta

    assert conn.rollbacks == 1 and conn.commits == 0
