import os
import psycopg2
from flask import Flask, jsonify, request
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import logging
from celery import Celery
import threading
import time

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

# Configura el logger de Flask para mayor detalle
app.config['DEBUG'] = True
app.logger.setLevel(logging.DEBUG)

# ======================
# CONFIGURACIÓN CELERY
# ======================
app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'  # Asegúrate de que Redis esté instalado
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])

# ======================
# FUNCIONES UTILITARIAS
# ======================
def conectar_db():
    """Establece la conexión con la base de datos PostgreSQL"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        app.logger.debug("Conexión a la base de datos exitosa")
        return conn
    except Exception as e:
        app.logger.error(f"Error al conectar a la base de datos: {e}")
        return None

def obtener_cliente_por_telefono(telefono):
    conn = conectar_db()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id_cliente, nombre FROM clientes WHERE telefono = %s", (telefono,))
        cliente = cursor.fetchone()
        conn.close()
        app.logger.debug(f"Cliente encontrado: {cliente}")
        return cliente
    return None

def crear_cliente(nombre, telefono):
    conn = conectar_db()
    if conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO clientes (nombre, telefono) VALUES (%s, %s) RETURNING id_cliente", (nombre, telefono))
        id_cliente = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        app.logger.debug(f"Cliente creado con ID: {id_cliente}")
        return id_cliente
    return None

def crear_carrito(id_cliente):
    conn = conectar_db()
    if conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO carritos (id_cliente, estado) VALUES (%s, 'activo') RETURNING id_carrito", (id_cliente,))
        id_carrito = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        app.logger.debug(f"Carrito creado con ID: {id_carrito}")
        return id_carrito
    return None

def crear_sesion(id_cliente):
    conn = conectar_db()
    if conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO sesiones (id_cliente, estado) VALUES (%s, 'iniciada') RETURNING id_sesion", (id_cliente,))
        id_sesion = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        app.logger.debug(f"Sesión creada con ID: {id_sesion}")
        return id_sesion
    return None

def mensaje_bot(mensaje, telefono):
    """Enviar mensaje de vuelta al cliente por WhatsApp"""
    app.logger.debug(f"Mensaje al bot: {mensaje}")
    twilio_client.messages.create(
        body=mensaje,
        from_=TWILIO_CONFIG['phone_number'],
        to=telefono
    )

def mensaje_usuario(mensaje):
    """Simular mensaje del usuario"""
    app.logger.debug(f"🧍 Tú: {mensaje}")

# ======================
# FUNCIONES DEL CHATBOT
# ======================
def ver_categorias(id_carrito, telefono):
    conn = conectar_db()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id_categoria, nombre FROM categorias")
        categorias = cursor.fetchall()
        conn.close()

        mensaje_bot("Elige una categoría:", telefono)
        for cat in categorias:
            mensaje_bot(f"{cat[0]}️⃣ {cat[1]}", telefono)

def ver_carrito(id_carrito, telefono):
    conn = conectar_db()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""SELECT p.nombre, p.precio, c.cantidad
                          FROM carrito_items c
                          JOIN productos p ON p.id_producto = c.id_producto
                          WHERE c.id_carrito = %s""", (id_carrito,))
        items = cursor.fetchall()
        conn.close()

        if not items:
            mensaje_bot("🛒 Tu carrito está vacío.", telefono)
            return

        total = 0
        mensaje_bot("📋 Cotización de productos en tu carrito:", telefono)
        for nombre, precio, cantidad in items:
            subtotal = precio * cantidad
            total += subtotal
            mensaje_bot(f"🔹 {nombre} - {cantidad} unidad(es) - ${int(subtotal):,}".replace(",", "."), telefono)
        mensaje_bot(f"💰 Total estimado: ${int(total):,}".replace(",", "."), telefono)

def finalizar_compra(id_carrito, telefono):
    conn = conectar_db()
    if conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE carritos SET estado = 'finalizado' WHERE id_carrito = %s", (id_carrito,))
        conn.commit()
        conn.close()
        mensaje_bot("✅ ¡Gracias por tu compra! 🛠️", telefono)

def manejar_conversacion(telefono, mensaje):
    cliente = obtener_cliente_por_telefono(telefono)
    
    if cliente:
        id_cliente, nombre = cliente
        mensaje_bot(f"👋 ¡Bienvenido nuevamente, {nombre}!", telefono)
    else:
        # Si el cliente no existe, pedir su nombre
        mensaje_bot("¿Cuál es tu nombre?", telefono)
        return  # Salimos aquí para esperar el nombre del usuario

    # En este punto, ya tenemos al usuario registrado y podemos continuar con el flujo
    id_cliente = crear_cliente(nombre, telefono)  # Si el cliente no estaba, lo creamos
    id_carrito = crear_carrito(id_cliente)  # Creamos el carrito para este cliente
    crear_sesion(id_cliente)  # Sesión iniciada para el cliente

    # Mostrar el menú principal de opciones al usuario
    mostrar_menu(id_carrito, telefono, mensaje)

def mostrar_menu(id_carrito, telefono, mensaje):
    """Envía un menú principal al usuario"""
    mensaje_bot("""¿Qué te gustaría hacer hoy?
1️⃣ Ver categorías de productos
2️⃣ Ver carrito
3️⃣ Finalizar compra""", telefono)

    # Aquí procesamos el mensaje de Twilio
    if mensaje == "1":
        ver_categorias(id_carrito, telefono)
    elif mensaje == "2":
        ver_carrito(id_carrito, telefono)
    elif mensaje == "3":
        finalizar_compra(id_carrito, telefono)
    else:
        mensaje_bot("❌ Opción no válida. Por favor, elige una opción del menú.", telefono)

# ======================
# RUTAS
# ======================
@app.route('/whatsapp', methods=['POST'])
def whatsapp_webhook():
    app.logger.debug("Recibiendo datos de Twilio")
    
    # Datos recibidos
    from_number = request.form.get('From')
    mensaje = request.form.get('Body').strip().lower()

    # Ejecutar la lógica de la conversación en segundo plano
    threading.Thread(target=manejar_conversacion, args=(from_number, mensaje)).start()

    # Responder a Twilio
    response = MessagingResponse()
    response.message("🛠️ ¡Hola! Estoy procesando tu solicitud.")
    return str(response)

if __name__ == '__main__':
    app.run(debug=True)

