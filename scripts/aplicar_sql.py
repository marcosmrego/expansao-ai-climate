"""Aplica um arquivo .sql de database/sql/ no banco configurado no .env.

Uso: python scripts/aplicar_sql.py database/sql/006_brasil_fire.sql
"""
import sys
from pathlib import Path

from database.db import conectar


def main(caminho: str) -> None:
    sql = Path(caminho).read_text(encoding="utf-8")
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(f"Aplicado: {caminho}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
