import os
import psycopg2
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
    
# Configuración de Twilio
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')  # Formato: whatsapp:+14155238886

# Inicialización de Flask y Twilio
app = Flask(__name__)
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# --- Configuración de base de datos (igual que tu código original) ---
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'dpg-d00re5c9c44c73ckj38g-a.oregon-postgres.render.com'),
    'user': os.getenv('DB_USER', 'reservas_0m08_user'),
    'password': os.getenv('DB_PASS', 'gJ6CvycTBwpsWe7j166vb7nA5RqQPx9k'),
    'dbname': os.getenv('DB_NAME', 'ferreteria_chatbot'),
    'port': os.getenv('DB_PORT', '5432')
}

# --- Funciones de base de datos (igual que tu código original) ---
def conectar_db():
    return psycopg2.connect(**DB_CONFIG)

def obtener_cliente_por_telefono(telefono):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id_cliente, nombre FROM clientes WHERE telefono = %s", (telefono,))
    cliente = cursor.fetchone()
    conn.close()
    return cliente

def crear_cliente(nombre, telefono):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO clientes (nombre, telefono) VALUES (%s, %s) RETURNING id_cliente", (nombre, telefono))
    id_cliente = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    return id_cliente

def crear_carrito(id_cliente):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO carritos (id_cliente, estado) VALUES (%s, 'activo') RETURNING id_carrito", (id_cliente,))
    id_carrito = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    return id_carrito

def crear_sesion(id_cliente):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO sesiones (id_cliente, estado) VALUES (%s, 'iniciada') RETURNING id_sesion", (id_cliente,))
    id_sesion = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    return id_sesion

def ver_categorias(id_carrito, user_phone):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id_categoria, nombre FROM categorias")
    categorias = cursor.fetchall()
    conn.close()

    mensaje = "Elige una categoría:\n"
    for cat in categorias:
        mensaje += f"{cat[0]}️⃣ {cat[1]}\n"
    
    enviar_whatsapp(user_phone, mensaje)
    return categorias

def ver_productos_por_categoria(id_categoria, id_carrito, user_phone):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id_producto, nombre, precio FROM productos WHERE id_categoria = %s", (id_categoria,))
    productos = cursor.fetchall()
    conn.close()

    if productos:
        mensaje = "🔧 Productos disponibles:\n"
        for prod in productos:
            mensaje += f"💡 {prod[0]} - {prod[1]} - ${int(prod[2]):,}\n".replace(",", ".")
        
        mensaje += "\nEscribe el ID del producto que quieres agregar al carrito:"
        enviar_whatsapp(user_phone, mensaje)
        return productos
    else:
        enviar_whatsapp(user_phone, "❌ No hay productos en esta categoría.")
        return None

def agregar_producto_a_carrito(id_producto, id_carrito, cantidad, user_phone):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO carrito_items (id_carrito, id_producto, cantidad) VALUES (%s, %s, %s)", (id_carrito, id_producto, cantidad))
    conn.commit()
    conn.close()
    enviar_whatsapp(user_phone, f"✅ Producto agregado al carrito ({cantidad} unidades).")

def preguntar_precio(id_carrito, user_phone, nombre_producto=None):
    if nombre_producto is None:
        enviar_whatsapp(user_phone, "🔎 ¿Qué producto deseas saber el precio?")
        return "esperando_producto"
    
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id_producto, nombre, precio FROM productos WHERE LOWER(nombre) LIKE %s", (f"%{nombre_producto.lower()}%",))
    resultados = cursor.fetchall()
    conn.close()

    if not resultados:
        enviar_whatsapp(user_phone, "🔍 No encontré ese producto.")
        return None

    if len(resultados) == 1:
        id_producto, nombre, precio = resultados[0]
        mensaje = f"🔍 El precio de {nombre} es: ${int(precio):,}\n".replace(",", ".")
        mensaje += f"¿Quieres agregar {nombre} al carrito? (Sí/No):"
        enviar_whatsapp(user_phone, mensaje)
        return {'id_producto': id_producto, 'nombre': nombre}
    else:
        mensaje = "🔍 Encontré varios productos:\n"
        for p in resultados:
            mensaje += f"💡 {p[0]} - {p[1]} - ${int(p[2]):,}\n".replace(",", ".")
        mensaje += "Escribe el ID del producto que quieres agregar:"
        enviar_whatsapp(user_phone, mensaje)
        return resultados

def ver_carrito(id_carrito, user_phone):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.nombre, p.precio, c.cantidad
        FROM carrito_items c
        JOIN productos p ON p.id_producto = c.id_producto
        WHERE c.id_carrito = %s
    """, (id_carrito,))
    items = cursor.fetchall()
    conn.close()

    if not items:
        enviar_whatsapp(user_phone, "🛒 Tu carrito está vacío.")
        return

    total = 0
    mensaje = "📋 Cotización de productos en tu carrito:\n"
    for nombre, precio, cantidad in items:
        subtotal = precio * cantidad
        total += subtotal
        mensaje += f"🔹 {nombre} - {cantidad} unidad(es) - ${int(subtotal):,}\n".replace(",", ".")
    mensaje += f"💰 Total estimado: ${int(total):,}".replace(",", ".")
    enviar_whatsapp(user_phone, mensaje)

def eliminar_producto(id_carrito, user_phone, nombre_producto=None):
    if nombre_producto is None:
        enviar_whatsapp(user_phone, "🗑️ ¿Qué producto deseas eliminar del carrito?")
        return "esperando_producto"
    
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id_producto, p.nombre, c.cantidad
        FROM carrito_items c
        JOIN productos p ON p.id_producto = c.id_producto
        WHERE c.id_carrito = %s AND LOWER(p.nombre) LIKE %s
    """, (id_carrito, f"%{nombre_producto.lower()}%"))
    productos = cursor.fetchall()

    if not productos:
        enviar_whatsapp(user_phone, "❌ No encontré ese producto en tu carrito.")
        conn.close()
        return None

    if len(productos) == 1:
        id_producto, nombre, cantidad = productos[0]
        enviar_whatsapp(user_phone, f"¿Eliminar {cantidad} unidad(es) de {nombre}? (Sí/No):")
        return {'id_producto': id_producto}
    else:
        mensaje = "🔍 Encontré varios productos:\n"
        for p in productos:
            mensaje += f"{p[0]} - {p[1]} ({p[2]}x)\n"
        mensaje += "Escribe el ID del producto que quieres eliminar:"
        enviar_whatsapp(user_phone, mensaje)
        return productos

def finalizar_compra(id_carrito, user_phone):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE carritos SET estado = 'finalizado' WHERE id_carrito = %s", (id_carrito,))
    conn.commit()
    conn.close()
    enviar_whatsapp(user_phone, "✅ ¡Gracias por tu compra! 🛠️")

# Función para enviar mensajes por WhatsApp
def enviar_whatsapp(destino, mensaje):
    twilio_client.messages.create(
        body=mensaje,
        from_=TWILIO_PHONE_NUMBER,
        to=f"whatsapp:{destino}"
    )

# Estado de las conversaciones (para manejar flujos)
conversaciones = {}

@app.route('/whatsapp', methods=['POST'])
def whatsapp_webhook():
    user_phone = request.values.get('From', '').replace('whatsapp:', '')
    user_message = request.values.get('Body', '').strip()
    
    # Inicializar respuesta
    resp = MessagingResponse()
    
    # Obtener o crear estado de conversación
    estado = conversaciones.get(user_phone, {})
    
    if 'esperando' in estado:
        # Continuar flujo existente
        if estado['esperando'] == 'nombre':
            id_cliente = crear_cliente(user_message, user_phone)
            estado['id_cliente'] = id_cliente
            estado['id_carrito'] = crear_carrito(id_cliente)
            estado['esperando'] = None
            mostrar_menu_whatsapp(user_phone)
            
        elif estado['esperando'] == 'opcion_menu':
            manejar_opcion_menu(user_phone, user_message, estado)
            
        elif estado['esperando'] == 'id_categoria':
            productos = ver_productos_por_categoria(int(user_message), estado['id_carrito'], user_phone)
            if productos:
                estado['productos'] = productos
                estado['esperando'] = 'id_producto'
                
        elif estado['esperando'] == 'id_producto':
            if user_message.isdigit():
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

if __name__ == '__main__':
    app.run(debug=True)