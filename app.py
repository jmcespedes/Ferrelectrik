import os
import psycopg2
from flask import Flask, jsonify
from twilio.rest import Client

app = Flask(__name__)

# Configuración corregida
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'database': os.getenv('DB_NAME'),  # Clave corregida de 'dbname' a 'database'
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASS'),
    'port': os.getenv('DB_PORT', '5432')  # Asegúrate de que sea string
}

# Versión corregida (observa el paréntesis cerrado y parámetros correctos)
def get_db_connection():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'),  # ¡Clave importante!
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASS'),
        port=os.getenv('DB_PORT', '5432')  # Puerto como string
    )
    return conn

# Resto del código...