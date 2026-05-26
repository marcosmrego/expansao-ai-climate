import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def conectar():

    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_DATABASE"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

    return conn


if __name__ == "__main__":

    conn = conectar()

    cursor = conn.cursor()

    cursor.execute("SELECT NOW();")

    resultado = cursor.fetchone()

    print("Conectado:", resultado)

    cursor.close()

    conn.close()