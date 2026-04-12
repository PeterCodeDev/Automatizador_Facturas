import os
import json
import gspread
from dotenv import load_dotenv
from google import genai
from PIL import Image
from oauth2client.service_account import ServiceAccountCredentials

# 1. CARGAR CLAVES
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
client_gemini = genai.Client(api_key=api_key)

# 2. CONECTAR A GOOGLE SHEETS
def conectar_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # Reutilizamos tu archivo de credenciales
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    
    # --- AQUÍ PONES EL NOMBRE DE TU EXCEL ---
    # Asegúrate de que el nombre sea EXACTO al que ves en Google Drive
    nombre_del_excel = "Facturas_Adrian" 
    return client.open(nombre_del_excel).sheet1

# 3. LÓGICA DE IA (LEER IMAGEN)
def analizar_ticket(ruta_imagen):
    print(f"📸 Analizando imagen: {ruta_imagen}...")
    img = Image.open(ruta_imagen)

    prompt = """
    Eres un experto contable. Analiza este ticket y extrae:
    CIF, Empresa, Fecha (DD/MM/AAAA), Base Imponible, IVA, Total y Categoría.
    Responde ÚNICAMENTE en JSON:
    {"cif": "", "empresa": "", "fecha": "", "base": 0.0, "iva": 0.0, "total": 0.0, "categoria": ""}
    """

    response = client_gemini.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt, img]
    )
    print("--- MODELOS DISPONIBLES ---")
    for m in client_gemini.models.list():
        print(m.name)
    print("---------------------------")

    res_text = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(res_text)

# 4. FLUJO PRINCIPAL
def procesar_y_guardar(ruta_foto):
    # 1. La IA analiza la imagen
    datos = analizar_ticket(ruta_foto)
    
    if "error" in datos:
        print(f"❌ Error de IA: {datos['error']}")
        return

    # 2. Conectar a la hoja
    hoja = conectar_sheets() # Asegúrate de tener esta función definida arriba
    
    # --- NUEVO: LÓGICA DE ENCABEZADOS ---
    # Si la celda A1 está vacía, ponemos los títulos
    if not hoja.acell('A1').value:
        encabezados = ["Fecha", "Empresa", "CIF", "Base Imponible", "IVA", "Total", "Categoría", "Nombre Archivo"]
        hoja.append_row(encabezados)
        print("📊 Encabezados creados en el Excel.")

    # 3. Preparar los datos en el orden de los encabezados
    # Usamos .get() para evitar errores si Gemini olvida algún campo
    fila = [
        datos.get('fecha', 'N/A'),
        datos.get('empresa', 'N/A'),
        datos.get('cif', 'N/A'),
        datos.get('base', 0),
        datos.get('iva', 0),
        datos.get('total', 0),
        datos.get('categoria', 'Otros'),
        ruta_foto # Para saber de qué archivo vino
    ]
    
    # 4. Guardar en el Excel
    hoja.append_row(fila)
    print(f"✅ ¡Éxito! Gastos de '{datos.get('empresa')}' guardados correctamente.")

# EJECUCIÓN
if __name__ == "__main__":
    # Asegúrate de tener una foto llamada ticket.jpg en la carpeta
    procesar_y_guardar("ticket_ejemplo.jpeg")