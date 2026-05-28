from dotenv import load_dotenv

from database.db import conectar
from collector.noaa_psl_base import (
    baixar_dados, salvar_payload_bruto, parse_noaa_psl_monthly, inserir_registros_mensais,
)
from app.services.climate_alert_repository import check_and_save_nao_alerts

URL = "https://psl.noaa.gov/data/correlation/nao.data"
ORIGEM = "NOAA_PSL_NAO"

load_dotenv()


def classificar_nao(valor: float) -> str:
    if valor >= 0.5:
        return "POSITIVO"
    if valor <= -0.5:
        return "NEGATIVO"
    return "NEUTRO"


def main():
    conn = conectar()
    try:
        texto = baixar_dados(URL)
        registros = parse_noaa_psl_monthly(texto)
        raw_payload_id = salvar_payload_bruto(conn, texto, ORIGEM, URL)
        total = inserir_registros_mensais(
            conn, registros, raw_payload_id, "noaa_nao", "nao", classificar_nao, ORIGEM
        )
        conn.commit()

        print(f"Payload salvo: {raw_payload_id}")
        print(f"Registros NAO processados: {total}")

        result = check_and_save_nao_alerts()
        print(f"Alertas NAO: {result}")

    except Exception as erro:
        conn.rollback()
        print(f"Erro na coleta NAO: {erro}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
