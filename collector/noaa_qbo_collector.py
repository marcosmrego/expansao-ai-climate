from dotenv import load_dotenv

from database.db import conectar
from collector.noaa_psl_base import (
    baixar_dados, salvar_payload_bruto, parse_noaa_psl_monthly, inserir_registros_mensais,
)
from app.services.climate_alert_repository import check_and_save_qbo_alerts

URL = "https://psl.noaa.gov/data/correlation/qbo.data"
ORIGEM = "NOAA_PSL_QBO"

load_dotenv()


def classificar_qbo(valor: float) -> str:
    """QBO measured in m/s at 30mb level. Positive = westerly, negative = easterly."""
    if valor >= 5.0:
        return "OESTE"
    if valor <= -5.0:
        return "LESTE"
    return "NEUTRO"


def main():
    conn = conectar()
    try:
        texto = baixar_dados(URL)
        registros = parse_noaa_psl_monthly(texto)
        raw_payload_id = salvar_payload_bruto(conn, texto, ORIGEM, URL)
        total = inserir_registros_mensais(
            conn, registros, raw_payload_id, "noaa_qbo", "qbo", classificar_qbo, ORIGEM
        )
        conn.commit()

        print(f"Payload salvo: {raw_payload_id}")
        print(f"Registros QBO processados: {total}")

        result = check_and_save_qbo_alerts()
        print(f"Alertas QBO: {result}")

    except Exception as erro:
        conn.rollback()
        print(f"Erro na coleta QBO: {erro}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
