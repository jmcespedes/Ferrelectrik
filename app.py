from flask import Flask, request
import psycopg2
import os
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

# Función para conectar a la base de datos
def conectar_db():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
    )

# Funciones de lógica de negocio
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

def crear_sesion(id_cliente, estado='inicio', dato_temp=None):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO sesiones (id_cliente, estado, dato_temp) VALUES (%s, %s, %s) RETURNING id_sesion",
        (id_cliente, estado, dato_temp)
    )
    id_sesion = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    return id_sesion

def actualizar_sesion(id_cliente, estado, dato_temp=None):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE sesiones SET estado = %s, dato_temp = %s WHERE id_cliente = %s AND estado != 'finalizado'",
        (estado, dato_temp, id_cliente)
    )
    conn.commit()
    conn.close()

def obtener_sesion(id_cliente):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id_sesion, estado, dato_temp FROM sesiones WHERE id_cliente = %s AND estado != 'finalizado'", (id_cliente,))
    sesion = cursor.fetchone()
    conn.close()
    return sesion

def finalizar_sesion(id_cliente):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE sesiones SET estado = 'finalizado' WHERE id_cliente = %s", (id_cliente,))
    conn.commit()
    conn.close()

def buscar_productos(nombre_producto):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id_producto, nombre, precio FROM productos WHERE LOWER(nombre) LIKE %s", (f"%{nombre_producto.lower()}%",))
    productos = cursor.fetchall()
    conn.close()
    return productos

def agregar_producto_a_carrito(id_carrito, id_producto, cantidad):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO carrito_items (id_carrito, id_producto, cantidad) VALUES (%s, %s, %s)",
        (id_carrito, id_producto, cantidad)
    )
    conn.commit()
    conn.close()

def ver_carrito(id_carrito):
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
    return items

# Ruta webhook de WhatsApp
@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    telefono = request.form['From'].split(":")[-1]
    mensaje = request.form['Body'].strip()
    respuesta = MessagingResponse()

    cliente = obtener_cliente_por_telefono(telefono)
    if not cliente:
        if mensaje.lower() in ["hola", "buenas", "iniciar"]:
            respuesta.message("👋 ¡Bienvenido a Ferretería Moderna! ¿Cuál es tu nombre?")
            return str(respuesta)
        else:
            id_cliente = crear_cliente(mensaje, telefono)
            id_sesion = crear_sesion(id_cliente, estado="menu")
            id_carrito = crear_carrito(id_cliente)
            respuesta.message(f"✅ ¡Hola {mensaje}! Tu cuenta ha sido creada.\n\nEscribe un número para elegir:\n1️⃣ Buscar productos\n2️⃣ Ver carrito\n3️⃣ Finalizar compra")
            return str(respuesta)

    id_cliente, nombre = cliente
    sesion = obtener_sesion(id_cliente)

    if not sesion:
        crear_sesion(id_cliente, estado="menu")
        id_carrito = crear_carrito(id_cliente)
        respuesta.message(f"👋 ¡Hola {nombre}!\n\nEscribe un número para elegir:\n1️⃣ Buscar productos\n2️⃣ Ver carrito\n3️⃣ Finalizar compra")
        return str(respuesta)

    id_sesion, estado, dato_temp = sesion

    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id_carrito FROM carritos WHERE id_cliente = %s AND estado = 'activo' ORDER BY id_carrito DESC LIMIT 1", (id_cliente,))
    carrito = cursor.fetchone()
    conn.close()
    id_carrito = carrito[0] if carrito else crear_carrito(id_cliente)

    if estado == "menu":
        if mensaje == "1":
            actualizar_sesion(id_cliente, estado="buscando_producto")
            respuesta.message("🔍 Escribe el nombre del producto que quieres buscar:")
        elif mensaje == "2":
            items = ver_carrito(id_carrito)
            if not items:
                respuesta.message("🛒 Tu carrito está vacío.")
            else:
                texto = "🛒 Tu carrito contiene:\n"
                total = 0
                for nombre, precio, cantidad in items:
                    subtotal = precio * cantidad
                    total += subtotal
                    texto += f"🔹 {nombre} x{cantidad} = ${subtotal:,}\n"
                texto += f"\n💰 Total: ${total:,}"
                respuesta.message(texto.replace(",", "."))
            actualizar_sesion(id_cliente, estado="menu")
        elif mensaje == "3":
            finalizar_sesion(id_cliente)
            respuesta.message("✅ ¡Gracias por tu compra! 🛠️")
        else:
            respuesta.message("❌ Opción inválida. Por favor elige 1, 2 o 3.")
    
    elif estado == "buscando_producto":
        productos = buscar_productos(mensaje)
        if not productos:
            respuesta.message("❌ No encontré productos con ese nombre. Intenta con otro.")
        else:
            texto = "🔍 Productos encontrados:\n"
            for p in productos:
                texto += f"{p[0]} - {p[1]} - ${int(p[2]):,}\n"
            texto += "\nEscribe el ID del producto que quieres agregar:"
            actualizar_sesion(id_cliente, estado="esperando_id_producto")
            actualizar_sesion(id_cliente, estado="esperando_id_producto", dato_temp=mensaje)
            respuesta.message(texto.replace(",", "."))
    
    elif estado == "esperando_id_producto":
        try:
            id_producto = int(mensaje)
            actualizar_sesion(id_cliente, estado="esperando_cantidad", dato_temp=str(id_producto))
            respuesta.message("📦 ¿Cuántas unidades quieres agregar?")
        except:
            respuesta.message("❌ ID inválido. Intenta de nuevo.")

    elif estado == "esperando_cantidad":
        try:
            cantidad = int(mensaje)
            id_producto = int(dato_temp)
            agregar_producto_a_carrito(id_carrito, id_producto, cantidad)
            actualizar_sesion(id_cliente, estado="menu")
            respuesta.message(f"✅ Producto agregado al carrito ({cantidad} unidades).\n\nEscribe:\n1️⃣ Buscar productos\n2️⃣ Ver carrito\n3️⃣ Finalizar compra")
        except:
            respuesta.message("❌ Cantidad inválida. Intenta de nuevo.")

    else:
        actualizar_sesion(id_cliente, estado="menu")
        respuesta.message("👋 Volviendo al menú principal.\n\n1️⃣ Buscar productos\n2️⃣ Ver carrito\n3️⃣ Finalizar compra")

    return str(respuesta)

# Código para correr localmente
if __name__ == "__main__":
    app.run(port=5000)
