from dotenv import load_dotenv

from database.db import conectar
from collector.noaa_psl_base import (
    baixar_dados, salvar_payload_bruto, parse_noaa_psl_monthly, inserir_registros_mensais,
)
from app.services.climate_alert_repository import check_and_save_pdo_alerts

URL = "https://psl.noaa.gov/data/correlation/pdo.data"
ORIGEM = "NOAA_PSL_PDO"

load_dotenv()


def classificar_pdo(valor: float) -> str:
    if valor >= 0.5:
        return "POSITIVO"
    if valor <= -0.5:
        return "NEGATIVO"
    return "NEUTRO"


def main():
    conn = conectar()
    try:
        texto = baixar_dados(URL)
        # PDO usa -9.9 como sentinela de dado ausente (outros índices PSL usam -99.x)
        registros = parse_noaa_psl_monthly(texto, missing_threshold=-9.0)
        raw_payload_id = salvar_payload_bruto(conn, texto, ORIGEM, URL)
        total = inserir_registros_mensais(
            conn, registros, raw_payload_id, "noaa_pdo", "pdo", classificar_pdo, ORIGEM
        )
        conn.commit()

        print(f"Payload salvo: {raw_payload_id}")
        print(f"Registros PDO processados: {total}")

        result = check_and_save_pdo_alerts()
        print(f"Alertas PDO: {result}")

    except Exception as erro:
        conn.rollback()
        print(f"Erro na coleta PDO: {erro}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
