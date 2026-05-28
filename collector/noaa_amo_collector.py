from dotenv import load_dotenv

from database.db import conectar
from collector.noaa_psl_base import (
    baixar_dados, salvar_payload_bruto, parse_noaa_psl_monthly, inserir_registros_mensais,
)
from app.services.climate_alert_repository import check_and_save_amo_alerts

URL = "https://psl.noaa.gov/data/correlation/amon.us.long.data"
ORIGEM = "NOAA_PSL_AMO"

load_dotenv()


def classificar_amo(valor: float) -> str:
    if valor >= 0.1:
        return "QUENTE"
    if valor <= -0.1:
        return "FRIO"
    return "NEUTRO"


def main():
    conn = conectar()
    try:
        texto = baixar_dados(URL)
        registros = parse_noaa_psl_monthly(texto)
        raw_payload_id = salvar_payload_bruto(conn, texto, ORIGEM, URL)
        total = inserir_registros_mensais(
            conn, registros, raw_payload_id, "noaa_amo", "amo", classificar_amo, ORIGEM
        )
        conn.commit()

        print(f"Payload salvo: {raw_payload_id}")
        print(f"Registros AMO processados: {total}")

        result = check_and_save_amo_alerts()
        print(f"Alertas AMO: {result}")

    except Exception as erro:
        conn.rollback()
        print(f"Erro na coleta AMO: {erro}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
