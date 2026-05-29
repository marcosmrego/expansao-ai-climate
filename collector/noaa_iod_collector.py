"""IOD monthly collector — Dipole Mode Index (DMI) calculado via ERSSTv5 OPeNDAP.

Fonte: NOAA PSL THREDDS — sst.mnmean.nc (ERSSTv5, 2° grid)
DMI = anomalia_SST_box_ocidental (50-70E, 10S-10N)
     - anomalia_SST_box_oriental  (90-110E, 10S-0N)
Climatologia de referência: 1981-2010 (padrão OMM).

Coleta incremental: apenas os últimos 24 meses a cada execução.
"""
import json
import re
import urllib.request
from collections import defaultdict
from datetime import date, timedelta

ORIGEM = "NOAA_PSL_ERSST_IOD"
URL_BASE = "https://psl.noaa.gov/thredds/dodsC/Datasets/noaa.ersst.v5/sst.mnmean.nc"
N_TIME_TOTAL = 2068          # atualizar se PSL ampliar a série
INCREMENTAL_MONTHS = 24      # janela de coleta incremental

# Climatologia 1981-2010 por mês (computada em 29/05/2026 a partir do ERSSTv5)
_CLIM_W = {1: 27.9064, 2: 28.1628, 3: 28.8815, 4: 29.5981, 5: 29.3325,
           6: 28.1689, 7: 27.3115, 8: 27.0426, 9: 27.3848, 10: 27.8709,
           11: 28.1838, 12: 28.0903}
_CLIM_E = {1: 28.6038, 2: 28.7482, 3: 29.1042, 4: 29.3748, 5: 29.3996,
           6: 29.0881, 7: 28.5781, 8: 28.2067, 9: 28.0423, 10: 28.2274,
           11: 28.4302, 12: 28.5055}


def classificar_iod(dmi: float) -> str:
    if dmi >= 0.4:
        return "POSITIVO"
    if dmi <= -0.4:
        return "NEGATIVO"
    return "NEUTRO"


def _fetch(url: str, timeout: int = 60) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode(errors="replace")


def _parse_time(raw: str) -> list[float]:
    section = raw.split("-----", 1)[-1]
    vals = []
    for tok in re.split(r"[,\n\s]+", section):
        try:
            vals.append(float(tok))
        except ValueError:
            pass
    return vals


def _parse_sst_box(raw: str) -> dict[int, float]:
    """Parse OPeNDAP ASCII SST → {time_index: mean_sst}."""
    section = raw.split("-----", 1)[-1]
    by_time: dict[int, list] = defaultdict(list)
    for line in section.splitlines():
        m = re.match(r"\[(\d+)\]\[(\d+)\],\s*(.*)", line.strip())
        if not m:
            continue
        t = int(m.group(1))
        for v in m.group(3).split(","):
            try:
                fv = float(v.strip())
                if abs(fv) < 1e30:
                    by_time[t].append(fv)
            except ValueError:
                pass
    return {t: sum(v) / len(v) for t, v in by_time.items() if v}


def baixar_e_calcular(n_time: int = N_TIME_TOTAL,
                      incremental: bool = True) -> list[tuple[date, float, str]]:
    """Return list of (date, dmi, classificacao) tuples.

    When incremental=True fetches only the last INCREMENTAL_MONTHS time steps.
    On first-ever run call with incremental=False to populate the full history.
    """
    t_start = (n_time - INCREMENTAL_MONTHS) if incremental else 0

    # Time axis
    t_raw = _fetch(f"{URL_BASE}.ascii?time[{t_start}:{n_time-1}]", timeout=30)
    times = _parse_time(t_raw)
    dates = [date(1800, 1, 1) + timedelta(days=int(d)) for d in times]

    # Western box: lat[39:49] = 10N→10S, lon[25:35] = 50E→70E
    w_url = f"{URL_BASE}.ascii?sst[{t_start}:{n_time-1}][39:49][25:35]"
    # Eastern box: lat[44:49] = 0N→10S, lon[45:55] = 90E→110E
    e_url = f"{URL_BASE}.ascii?sst[{t_start}:{n_time-1}][44:49][45:55]"

    w_raw = _fetch(w_url, timeout=90)
    e_raw = _fetch(e_url, timeout=90)

    w_by_t = _parse_sst_box(w_raw)
    e_by_t = _parse_sst_box(e_raw)

    results = []
    for local_i, d in enumerate(dates):
        if local_i not in w_by_t or local_i not in e_by_t:
            continue
        w_anom = w_by_t[local_i] - _CLIM_W[d.month]
        e_anom = e_by_t[local_i] - _CLIM_E[d.month]
        dmi = round(w_anom - e_anom, 4)
        results.append((d, dmi, classificar_iod(dmi)))
    return results


def salvar_payload_bruto(conn, origem: str) -> int:
    from collector.noaa_psl_base import gerar_hash
    payload = json.dumps({"fonte": "NOAA_PSL_ERSST_V5", "metodo": "DMI_OPeNDAP"})
    h = gerar_hash(payload)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO climate.raw_payload (origem, url, content_type, payload_text, hash_payload)
            VALUES (%s, %s, %s, %s, %s) RETURNING id;
            """,
            (origem, URL_BASE, "application/json", payload, h),
        )
        return cur.fetchone()[0]


def inserir_registros(conn, registros: list, raw_payload_id: int) -> int:
    total = 0
    with conn.cursor() as cur:
        for d, dmi, classificacao in registros:
            cur.execute(
                """
                INSERT INTO climate.noaa_iod
                    (data_referencia, dmi, classificacao, fonte, payload_bruto)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (data_referencia) DO UPDATE SET
                    dmi           = EXCLUDED.dmi,
                    classificacao = EXCLUDED.classificacao,
                    fonte         = EXCLUDED.fonte,
                    payload_bruto = EXCLUDED.payload_bruto,
                    criado_em     = NOW();
                """,
                (d, dmi, classificacao, ORIGEM,
                 json.dumps({"raw_payload_id": str(raw_payload_id)})),
            )
            total += 1
    return total
