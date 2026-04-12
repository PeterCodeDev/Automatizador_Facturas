import os
import json
from dotenv import load_dotenv
from google import genai
from PIL import Image

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def analizar_ticket(ruta_imagen):
    print(f"📸 Analizando imagen: {ruta_imagen}...")
    
    # Abrimos la imagen con Pillow
    img = Image.open(ruta_imagen)

    prompt = """
    Eres un experto contable español. Analiza la imagen de este ticket o factura y extrae:
    1. CIF del Proveedor.
    2. Nombre de la empresa.
    3. Fecha (DD/MM/AAAA).
    4. Base Imponible (sin IVA).
    5. Cuota de IVA (dinero total de IVA).
    6. Importe Total.
    7. Categoría de gasto (Materiales, Herramientas, Gasolina, Comidas, Otros).

    Responde ÚNICAMENTE en formato JSON plano:
    {
        "cif": "", "empresa": "", "fecha": "", 
        "base": 0.0, "iva": 0.0, "total": 0.0, "categoria": ""
    }
    """

    # Enviamos la imagen y el texto a Gemini 2.0 Flash
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[prompt, img]
    )

    # Limpieza de la respuesta
    res_text = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(res_text)

# --- PRUEBA LOCAL ---
if __name__ == "__main__":
    # Pon una foto de un ticket en la carpeta y cambia el nombre aquí
    resultado = analizar_ticket("ticket_ejemplo.jpeg")
    print(resultado)