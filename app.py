import os
import psycopg2
from flask import Flask, jsonify
from twilio.rest import Client

app = Flask(__name__)

# Conexión a PostgreSQL para Render
def get_db_connection():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASS'),
        port=os.getenv('DB_PORT', 5432)
    return conn

# Configuración Twilio
twilio_client = Client(
    os.getenv('TWILIO_ACCOUNT_SID'),
    os.getenv('TWILIO_AUTH_TOKEN')
)

@app.route('/test-db')
def test_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT version();')
        db_version = cur.fetchone()
        cur.close()
        conn.close()
        
        # Notificación vía Twilio
        twilio_client.messages.create(
            body=f'Conexión exitosa a PostgreSQL: {db_version[0]}',
            from_=os.getenv('TWILIO_PHONE_NUMBER'),
            to=os.getenv('YOUR_PHONE')  # Añade esta variable en Render
        )
        
        return jsonify({
            'status': 'success',
            'db_version': db_version[0]
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/')
def home():
    return "¡App funcionando en Render con PostgreSQL y Twilio!"

if __name__ == '__main__':
    app.run(debug=os.getenv('DEBUG', 'False') == 'True')