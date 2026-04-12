import os
import telebot
from dotenv import load_dotenv
from google import genai
from PIL import Image
import io
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# 1. CONFIGURACIÓN INICIAL
load_dotenv()
token_tg = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(token_tg)

client_gemini = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# 2. FUNCIÓN PARA CONECTAR AL EXCEL
def conectar_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    return client.open("Facturas_Adrian").sheet1 # Asegúrate de que el nombre coincide

# 3. LÓGICA DE IA
def analizar_ticket(imagen_pil):
    prompt = "Eres un contable. Extrae en JSON: empresa, cif, fecha, base, iva, total, categoria."
    # Usamos gemini-1.5-flash que es el más estable para esto
    response = client_gemini.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt, imagen_pil]
    )
    texto = response.text
    if "```json" in texto:
        texto = texto.split("```json")[1].split("```")[0]
    import json
    return json.loads(texto.strip())

# 4. EL BOT "ESCUCHANDO" FOTOS
@bot.message_handler(content_types=['photo'])
def manejar_foto(message):
    print("🔔 ¡Ha llegado una foto!")
    msg_espera = bot.reply_to(message, "📸 Analizando y guardando nombre de archivo...")
    
    try:
        # 1. Obtener información del archivo
        file_info = bot.get_file(message.photo[-1].file_id)
        # Usamos el file_unique_id o parte del path como nombre de referencia
        nombre_archivo = f"ticket_{file_info.file_unique_id}.jpg"
        
        downloaded_file = bot.download_file(file_info.file_path)
        img = Image.open(io.BytesIO(downloaded_file))
        img.thumbnail((1024, 1024))

        # 2. Analizar con Gemini
        datos = analizar_ticket(img)

        # 3. Conectar y Guardar
        hoja = conectar_sheets()
        
        # Si la hoja está vacía, ponemos los encabezados (ahora con NOMBRE ARCHIVO)
        if not hoja.acell('A1').value:
            encabezados = ["FECHA", "EMPRESA", "CIF", "BASE", "IVA", "TOTAL", "CATEGORIA", "NOMBRE ARCHIVO"]
            hoja.insert_row(encabezados, 1)

        # 4. Preparamos la fila incluyendo el nombre del archivo al final
        fila = [
            datos.get('fecha'), 
            datos.get('empresa'), 
            datos.get('cif'), 
            datos.get('base'), 
            datos.get('iva'), 
            datos.get('total'), 
            datos.get('categoria'),
            nombre_archivo  # <--- Esta es la nueva columna
        ]
        
        hoja.append_row(fila)

        bot.edit_message_text(
            f"✅ ¡Guardado!\n📂 Archivo: {nombre_archivo}\n🏢 Empresa: {datos.get('empresa')}\n💰 Total: {datos.get('total')}€", 
            message.chat.id, msg_espera.message_id
        )

    except Exception as e:
        print(f"❌ Error: {e}")
        bot.edit_message_text(f"❌ Error: {str(e)}", message.chat.id, msg_espera.message_id)

print("🚀 Bot en marcha... Dile a tu padre que envíe una foto.")
keep_alive()
bot.polling()