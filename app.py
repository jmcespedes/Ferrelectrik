from flask import Flask, request
import psycopg2
import os
from twilio.twiml.messaging_response import MessagingResponse
from ia_construccion import es_consulta_construccion, responder_consulta_construccion

app = Flask(__name__)

def conectar_db():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
    )

def es_consulta_construccion(mensaje):
    mensaje = mensaje.lower()
    palabras_clave = [
        "radier", "cemento", "arena", "ripio", "hacer mezcla",
        "cuánto necesito", "cuantos sacos", "materiales", "hormigón",
        "cuanto cemento", "cuanto material", "mezcla radier"
    ]
    return any(p in mensaje for p in palabras_clave)


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
    cursor.execute("SELECT id_producto, nombre, precio, stock, medida FROM productos WHERE LOWER(nombre) LIKE %s", (f"%{nombre_producto.lower()}%",))
    productos = cursor.fetchall()
    conn.close()
    return productos

def buscar_producto_por_id(id_producto):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT nombre, medida FROM productos WHERE id_producto = %s",
        (id_producto,)
    )
    producto = cursor.fetchone()
    conn.close()
    return producto

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
@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    telefono = request.form['From'].split(":")[-1]
    mensaje = request.form['Body'].strip()
    respuesta = MessagingResponse()

    cliente = obtener_cliente_por_telefono(telefono)
    
    if not cliente:
        if mensaje.lower() in ["hola", "buenas", "iniciar"]:
            respuesta.message(
                "✅ ¡Bienvenido a 🟦 *CENTRAL* 🟨 *GRIFERIAS*! 👷‍♂️🔧\n\n"
                "💬 Soy tu Vendedor Virtual 24/7, siempre listo para ayudarte. ✨\n\n"
                  "──────────────────────────\n"
                "🔍 *1.* Buscar productos\n"
                "🛒 *2.* Ver carrito\n"
                "💳 *3.* Finalizar compra\n"
                "──────────────────────────\n"
                "✨ *Responde con el número de la opción que prefieras!*"
                )
            return str(respuesta)
        else:
            id_cliente = crear_cliente(mensaje, telefono)
            id_sesion = crear_sesion(id_cliente, estado="menu")
            id_carrito = crear_carrito(id_cliente)
            respuesta.message(f"✅ ¡Hola {mensaje}! Tu cuenta ha sido creada.\n\nEscribe un número para elegir:\n1️⃣ Buscar productos\n2️⃣ Ver carrito\n3️⃣ Finalizar compra")
            return str(respuesta)

    id_cliente, nombre = cliente
    sesion = obtener_sesion(id_cliente)

    # Si no hay sesión activa, la creamos y mostramos el menú
    if not sesion:
        crear_sesion(id_cliente, estado="menu")
        id_carrito = crear_carrito(id_cliente)
        respuesta.message(
            f"👋 ¡Hola *{nombre}*! Qué bueno tenerte de vuelta en 🛠️🟦 *CENTRAL* 🟨 *GRIFERIAS*! 👷‍♂️🔧\n\n"
            "💬 Soy tu Vendedor Virtual 24/7, siempre listo para ayudarte. ✨\n\n"
            "🔹 ¿En qué podemos ayudarte hoy?\n"
            "──────────────────────────\n"
            "🔍 *1.* Buscar productos\n"
            "🛒 *2.* Ver carrito\n"
            "💳 *3.* Finalizar compra\n"
            "──────────────────────────\n"
            "✨ *Responde con el número de la opción que prefieras!*"
        )
        return str(respuesta)
    id_sesion, estado, dato_temp = sesion

    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id_carrito FROM carritos WHERE id_cliente = %s AND estado = 'activo' ORDER BY id_carrito DESC LIMIT 1", (id_cliente,))
    carrito = cursor.fetchone()
    conn.close()
    id_carrito = carrito[0] if carrito else crear_carrito(id_cliente)

    if estado == "menu":

        if es_consulta_construccion(mensaje):
           ## from ia_construccion import responder_consulta_construccion
            resultado = responder_consulta_construccion(mensaje)
            actualizar_sesion(id_cliente, estado="menu")
            respuesta.message(
                f"📐 Aquí tienes una recomendación:\n\n{resultado}\n\n"
                "¿Deseas agregar alguno de estos productos al carrito? 🛒"
            )
            return str(respuesta)


        if mensaje == "1":
            actualizar_sesion(id_cliente, estado="buscando_producto")
            respuesta.message("🔍 Escribe el nombre del producto que quieres buscar:")
        elif mensaje == "2":
            items = ver_carrito(id_carrito)
            if not items:
                respuesta.message("🛒 Tu carrito está vacío. ¡Agrega productos para comenzar! 🔨")
            else:
                texto = "🛒 *Tu carrito contiene:*\n\n"
                texto += "📦 *Producto*         |  🔢 *Cant.*  |  💲 *Subtotal*\n"
                texto += "────────────────────────────────────────\n"

                total = 0
                for nombre, precio, cantidad in items:
                    subtotal = precio * cantidad
                    total += subtotal
                    # Formateo bonito
                    texto += f"🔹 {nombre.ljust(15)[:15]} | {str(cantidad).rjust(5)}     | ${subtotal:,.0f}\n"

                texto += "────────────────────────────────────────\n"
                texto += f"💰 *Total:* ${total:,.0f}"

                # Para que en WhatsApp se vea el punto como separador de miles
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
            respuesta.message("❌ No encontré productos con ese nombre. Intenta con otro 🔄.")
        else:
            texto = "🔍 *Productos encontrados:*\n\n"
            for p in productos:
                texto += (
                    f"🛠️ *ID:       * `{p[0]}`\n"
                    f"📦 *Producto: * *{p[1]}*\n"
                    f"💲 *Precio:   * ${int(p[2]):,}\n"
                    f"📦 *Stock disponible:* {p[3]}\n"
                    "──────────────────────\n"
                )
            texto += "✏️ *Escribe el ID del producto que quieres agregar:*"
            actualizar_sesion(id_cliente, estado="esperando_id_producto", dato_temp=mensaje)
            respuesta.message(texto.replace(",", "."))
    
    elif estado == "esperando_id_producto":
        try:
            id_producto = int(mensaje)
            producto = buscar_producto_por_id(id_producto)
            if not producto:
                respuesta.message("❌ Producto no encontrado. Intenta de nuevo.")
                return str(respuesta) 
            
            nombre_producto, medida = producto
            actualizar_sesion(id_cliente, estado="esperando_cantidad", dato_temp=str(id_producto))
            respuesta.message(f"📦 ¿Cuántos *{medida}* de *{nombre_producto}* quieres agregar?")
            return str(respuesta)  

        except:
            respuesta.message("❌ ID inválido. Intenta de nuevo.")
            return str(respuesta)  


    elif estado == "esperando_cantidad":
        try:
            cantidad = int(mensaje)
            id_producto = int(dato_temp)
            agregar_producto_a_carrito(id_carrito, id_producto, cantidad)
            actualizar_sesion(id_cliente, estado="menu")
            respuesta.message(
                f"🛒 ¡Listo! Agregué *{cantidad}* unidad(es) del producto al carrito."
                "\n\nElige una opción:\n1️⃣ Buscar productos\n2️⃣ Ver carrito\n3️⃣ Finalizar compra"
            )
        except:
            respuesta.message("❌ Cantidad inválida. Intenta de nuevo.")
        
    return str(respuesta)

if __name__ == "__main__":
    app.run(debug=True)
