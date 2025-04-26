import os
import psycopg2
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import logging

# Configuración de Twilio
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')  # Formato: whatsapp:+14155238886

# Inicialización de Flask y Twilio
app = Flask(__name__)
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Configuración de logs
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuración de base de datos (igual que tu código original) ---
DB_CONFIG = {
    'host': os.environ['DB_HOST'],
    'dbname': os.environ['DB_NAME'],
    'user': os.environ['DB_USER'],
    'password': os.environ['DB_PASS'],
    'port': os.environ.get('DB_PORT', 5432)
}

# --- Funciones de base de datos (igual que tu código original) ---
def conectar_db():
    logging.debug("Conectando a la base de datos...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        logging.debug("Conexión establecida con la base de datos.")
        return conn
    except Exception as e:
        logging.error(f"Error al conectar a la base de datos: {e}")
        return None

def obtener_cliente_por_telefono(telefono):
    logging.debug(f"Obteniendo cliente con teléfono {telefono}...")
    conn = conectar_db()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id_cliente, nombre FROM clientes WHERE telefono = %s", (telefono,))
        cliente = cursor.fetchone()
        conn.close()
        logging.debug(f"Cliente encontrado: {cliente}")
        return cliente
    else:
        logging.error("No se pudo obtener conexión con la base de datos.")
        return None

def crear_cliente(nombre, telefono):
    logging.debug(f"Creando cliente: {nombre}, {telefono}...")
    conn = conectar_db()
    if conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO clientes (nombre, telefono) VALUES (%s, %s) RETURNING id_cliente", (nombre, telefono))
        id_cliente = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        logging.debug(f"Cliente creado con ID: {id_cliente}")
        return id_cliente
    else:
        logging.error("No se pudo conectar para crear el cliente.")
        return None

def crear_carrito(id_cliente):
    logging.debug(f"Creando carrito para el cliente ID: {id_cliente}...")
    conn = conectar_db()
    if conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO carritos (id_cliente, estado) VALUES (%s, 'activo') RETURNING id_carrito", (id_cliente,))
        id_carrito = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        logging.debug(f"Carrito creado con ID: {id_carrito}")
        return id_carrito
    else:
        logging.error("No se pudo conectar para crear el carrito.")
        return None

def crear_sesion(id_cliente):
    logging.debug(f"Creando sesión para el cliente ID: {id_cliente}...")
    conn = conectar_db()
    if conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO sesiones (id_cliente, estado) VALUES (%s, 'iniciada') RETURNING id_sesion", (id_cliente,))
        id_sesion = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        logging.debug(f"Sesión creada con ID: {id_sesion}")
        return id_sesion
    else:
        logging.error("No se pudo conectar para crear la sesión.")
        return None

def ver_categorias(id_carrito, user_phone):
    logging.debug(f"Obteniendo categorías para el carrito ID: {id_carrito}...")
    conn = conectar_db()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id_categoria, nombre FROM categorias")
        categorias = cursor.fetchall()
        conn.close()

        mensaje = "Elige una categoría:\n"
        for cat in categorias:
            mensaje += f"{cat[0]}️⃣ {cat[1]}\n"
        
        enviar_whatsapp(user_phone, mensaje)
        logging.debug(f"Enviado mensaje con categorías a {user_phone}.")
        return categorias
    else:
        logging.error("No se pudo conectar para obtener categorías.")
        return None

def enviar_whatsapp(destino, mensaje):
    logging.debug(f"Enviando mensaje a {destino}: {mensaje}")
    try:
        twilio_client.messages.create(
            body=mensaje,
            from_=TWILIO_PHONE_NUMBER,
            to=f"whatsapp:{destino}"
        )
        logging.debug("Mensaje enviado con éxito.")
    except Exception as e:
        logging.error(f"Error al enviar mensaje por WhatsApp: {e}")

# Estado de las conversaciones (para manejar flujos)
conversaciones = {}

@app.route('/whatsapp', methods=['POST'])
def whatsapp_webhook():
    user_phone = request.values.get('From', '').replace('whatsapp:', '')
    user_message = request.values.get('Body', '').strip()

    logging.debug(f"Mensaje recibido de {user_phone}: {user_message}")
    
    # Inicializar respuesta
    resp = MessagingResponse()
    
    # Obtener o crear estado de conversación
    estado = conversaciones.get(user_phone, {})
    
    if 'esperando' in estado:
        # Continuar flujo existente
        if estado['esperando'] == 'nombre':
            logging.debug("Esperando nombre de cliente...")
            id_cliente = crear_cliente(user_message, user_phone)
            estado['id_cliente'] = id_cliente
            estado['id_carrito'] = crear_carrito(id_cliente)
            estado['esperando'] = None
            mostrar_menu_whatsapp(user_phone)
            
        elif estado['esperando'] == 'opcion_menu':
            logging.debug("Esperando opción de menú...")
            manejar_opcion_menu(user_phone, user_message, estado)
            
        elif estado['esperando'] == 'id_categoria':
            logging.debug(f"Esperando ID de categoría, mensaje recibido: {user_message}")
            productos = ver_productos_por_categoria(int(user_message), estado['id_carrito'], user_phone)
            if productos:
                estado['productos'] = productos
                estado['esperando'] = 'id_producto'
                
        elif estado['esperando'] == 'id_producto':
            if user_message.isdigit():
                logging.debug(f"Esperando cantidad para el producto con ID {estado['id_producto']}.")
                estado['id_producto'] = int(user_message)
                enviar_whatsapp(user_phone, "¿Cuántas unidades deseas agregar?")
                estado['esperando'] = 'cantidad'
            else:
                enviar_whatsapp(user_phone, "❌ ID inválido. Intenta nuevamente.")
                
        elif estado['esperando'] == 'cantidad':
            if user_message.isdigit():
                agregar_producto_a_carrito(estado['id_producto'], estado['id_carrito'], int(user_message), user_phone)
                estado['esperando'] = None
                mostrar_menu_whatsapp(user_phone)
            else:
                enviar_whatsapp(user_phone, "❌ Cantidad inválida. Intenta nuevamente.")
                
        # ... (manejar otros estados de espera)
        
    elif user_message.lower() == 'hola':
        # Iniciar nueva conversación
        cliente = obtener_cliente_por_telefono(user_phone)
        if cliente:
            estado['id_cliente'] = cliente[0]
            estado['id_carrito'] = crear_carrito(cliente[0])
            enviar_whatsapp(user_phone, f"👋 ¡Bienvenido nuevamente, {cliente[1]}!")
            mostrar_menu_whatsapp(user_phone)
        else:
            enviar_whatsapp(user_phone, "👋 ¡Bienvenido a Ferretería Chocálan! Por favor, escribe tu nombre para registrarte.")
            estado['esperando'] = 'nombre'
            
    else:
        # Mensaje no reconocido
        enviar_whatsapp(user_phone, "No entendí tu mensaje. Envía 'hola' para comenzar.")
    
    # Actualizar estado de la conversación
    conversaciones[user_phone] = estado
    
    return str(resp)

def mostrar_menu_whatsapp(user_phone):
    menu = """
¿Qué te gustaría hacer hoy?
1️⃣ Ver categorías de productos
2️⃣ Preguntar precio de un producto
3️⃣ Ver carrito
4️⃣ Eliminar producto del carrito
5️⃣ Finalizar compra
6️⃣ Salir
    """
    enviar_whatsapp(user_phone, menu)
    conversaciones[user_phone]['esperando'] = 'opcion_menu'

def manejar_opcion_menu(user_phone, opcion, estado):
    if opcion == "1":
        ver_categorias(estado['id_carrito'], user_phone)
        estado['esperando'] = 'id_categoria'
    elif opcion == "2":
        enviar_whatsapp(user_phone, "🔎 ¿Qué producto deseas saber el precio?")
        estado['esperando'] = 'nombre_producto'
    elif opcion == "3":
        ver_carrito(estado['id_carrito'], user_phone)
        mostrar_menu_whatsapp(user_phone)
    elif opcion == "4":
        enviar_whatsapp(user_phone, "🗑️ ¿Qué producto deseas eliminar del carrito?")
        estado['esperando'] = 'producto_eliminar'
    elif opcion == "5":
        finalizar_compra(estado['id_carrito'], user_phone)
        del conversaciones[user_phone]
    elif opcion == "6":
        enviar_whatsapp(user_phone, "👋 ¡Hasta pronto!")
        del conversaciones[user_phone]
    else:
        enviar_whatsapp(user_phone, "❌ Opción inválida. Intenta nuevamente.")
        mostrar_menu_whatsapp(user_phone)

