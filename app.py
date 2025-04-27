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

def ver_productos_por_categoria(id_categoria, id_carrito, telefono):
    conn = conectar_db()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id_producto, nombre, precio FROM productos WHERE id_categoria = %s", (id_categoria,))
        productos = cursor.fetchall()
        conn.close()

        if productos:
            mensaje_bot("🔧 Productos disponibles:", telefono)
            for prod in productos:
                mensaje_bot(f"💡 {prod[0]} - {prod[1]} - ${int(prod[2]):,}".replace(",", "."), telefono)

            mensaje_bot("Escribe el ID del producto que quieres agregar al carrito:", telefono)

def agregar_producto_a_carrito(id_producto, id_carrito, cantidad, telefono):
    conn = conectar_db()
    if conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO carrito_items (id_carrito, id_producto, cantidad) VALUES (%s, %s, %s)", (id_carrito, id_producto, cantidad))
        conn.commit()
        conn.close()
        mensaje_bot(f"✅ Producto agregado al carrito ({cantidad} unidades).", telefono)

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

def eliminar_producto(id_carrito, telefono):
    mensaje_bot("🗑️ ¿Qué producto deseas eliminar del carrito?", telefono)

    conn = conectar_db()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""SELECT p.id_producto, p.nombre, c.cantidad
                          FROM carrito_items c
                          JOIN productos p ON p.id_producto = c.id_producto
                          WHERE c.id_carrito = %s""", (id_carrito,))
        productos = cursor.fetchall()

        if not productos:
            mensaje_bot("❌ No encontré ese producto en tu carrito.", telefono)
            conn.close()
            return

        if len(productos) == 1:
            id_producto, nombre, cantidad = productos[0]
            mensaje_bot(f"¿Eliminar {cantidad} unidad(es) de {nombre}? (Sí/No):", telefono)
        else:
            mensaje_bot("🔍 Encontré varios productos:", telefono)
            for p in productos:
                mensaje_bot(f"{p[0]} - {p[1]} ({p[2]}x)", telefono)
            mensaje_bot("Escribe el ID del producto que quieres eliminar:", telefono)

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
        mensaje_bot("¿Cuál es tu nombre?", telefono)
        nombre = mensaje.strip()
        id_cliente = crear_cliente(nombre, telefono)
        mensaje_bot(f"👋 ¡Bienvenido, {nombre}! Te hemos registrado.", telefono)

    crear_sesion(id_cliente)
    id_carrito = crear_carrito(id_cliente)
    mostrar_menu(id_carrito, telefono)

def mostrar_menu(id_carrito, telefono):
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
        mensaje_bot("❌ Opción no válida.", telefono)

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
