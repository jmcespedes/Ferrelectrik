from transformers import pipeline

# Cargar un modelo liviano en español (puedes probar otros más grandes si tienes GPU o paciencia)
chat = pipeline("text-generation", model="dbmdz/gpt2-spanish", max_length=150)

def responder_consulta_construccion(pregunta_usuario):
    prompt = (
        "Eres un experto en ferretería y construcción en Chile. "
        "Ayuda al usuario a calcular materiales como cemento, arena y ripio para proyectos de construcción. "
        "Ejemplo: 'Necesito hacer un radier de 30 m²'\n\n"
        f"Usuario: {pregunta_usuario}\nAsistente:"
    )
    respuesta = chat(prompt)[0]['generated_text']
    return respuesta.split("Asistente:")[-1].strip()
