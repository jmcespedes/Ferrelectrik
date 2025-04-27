import os
import psycopg2
from flask import Flask, jsonify, request
from twilio.rest import Client

app = Flask(__name__)

# ======================
# CONFIGURACIÓN
# ======================
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASS'),
    'port': os.getenv('DB_PORT', '5432')
}

TWILIO_CONFIG = {
    'account_sid': os.getenv('TWILIO_ACCOUNT_SID'),
    'auth_token': os.getenv('TWILIO_AUTH_TOKEN'),
    'phone_number': os.getenv('TWILIO_PHONE_NUMBER')
}

# ======================
# INICIALIZACIÓN
# ======================
twilio_client = Client(TWILIO_CONFIG['account_sid'], TWILIO_CONFIG['auth_token'])

# ======================
# FUNCIONES UTILITARIAS
# ======================
def get_db_connection():
    """Establece conexión con PostgreSQL"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        app.logger.error(f"Error de conexión a DB: {str(e)}")
        return None

def send_sms(to, body):
    """Envía SMS usando Twilio"""
    try:
        message = twilio_client.messages.create(
            body=body,
            from_=TWILIO_CONFIG['phone_number'],
            to=to
        )
        return message.sid
    except Exception as e:
        app.logger.error(f"Error Twilio: {str(e)}")
        return None

# ======================
# RUTAS PRINCIPALES
# ======================
@app.route('/')
def home():
    """Endpoint raíz"""
    return jsonify({
        "status": "active",
        "service": "Ferrelectrik API",
        "version": "1.0"
    })

@app.route('/health')
def health_check():
    """Health check para Render"""
    db_status = "OK" if get_db_connection() else "Error"
    return jsonify({
        "status": "running",
        "database": db_status,
        "twilio": "configured"
    })

@app.route('/test-sms')
def test_sms():
    """Endpoint de prueba para Twilio"""
    sid = send_sms(
        to=os.getenv('ADMIN_PHONE'),  # Añade esta variable en Render
        body="Prueba exitosa desde Ferrelectrik API"
    )
    return jsonify({"sms_sid": sid}) if sid else jsonify({"error": "Failed to send SMS"}), 500

@app.route('/whatsapp', methods=['POST'])
def whatsapp_webhook():
    """Manejo de los mensajes entrantes de WhatsApp"""
    try:
        # Extrae el mensaje entrante y el número de teléfono desde Twilio
        from_number = request.form.get('From')
        body = request.form.get('Body')

        # Aquí puedes agregar lógica para almacenar el mensaje en la base de datos
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO mensajes (numero, cuerpo) VALUES (%s, %s)", (from_number, body))
            conn.commit()
            cursor.close()

        # Responde con un mensaje automático (puedes personalizarlo)
        send_sms(from_number, "Gracias por tu mensaje. Te responderemos pronto.")

        return jsonify({"status": "success"}), 200
    except Exception as e:
        app.logger.error(f"Error en webhook de WhatsApp: {str(e)}")
        return jsonify({"error": "Internal Server Error"}), 500

# ======================
# INICIALIZACIÓN
# ======================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
