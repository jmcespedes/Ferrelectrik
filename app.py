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

def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)  # Paréntesis correctamente cerrado
        return conn
    except Exception as e:
        print(f"Error de conexión: {e}")
        return None

# Resto del código...