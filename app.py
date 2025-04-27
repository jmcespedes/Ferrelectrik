import psycopg2
from flask import Flask

app = Flask(__name__)

# Configuración de la base de datos
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'dbname': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASS'),
    'port': os.getenv('DB_PORT', 5432)  # Asegúrate de que este puerto sea correcto
}

def conectar_db():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("Conexión exitosa a la base de datos")
        conn.close()
    except Exception as e:
        print(f"Error al conectar a la base de datos: {e}")

@app.route('/')
def index():
    conectar_db()
    return "Hola, conexión con la base de datos exitosa!"

if __name__ == '__main__':
    app.run(debug=True)