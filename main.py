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
import os

# Creamos una web mini para que Render esté contento
app = Flask('')

@app.route('/')
def home():
    return "Bot de Facturas Operativo"

def run():
    # Render nos obliga a usar el puerto que ellos digan o el 10000
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

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
def analizar_documento(file_bytes, mime_type):
    # Ya no forzamos PIL. Usamos bytes crudos para soportar PDFs o Imágenes de manera dinámica.
    response = client_gemini.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            "Extrae en JSON exacto: empresa, cif, fecha, base, iva, total, categoria. Los importes deben ser puramente numéricos si es posible.",
            {"mime_type": mime_type, "data": file_bytes}
        ]
    )
    texto = response.text
    if "```json" in texto:
        texto = texto.split("```json")[1].split("```")[0]
    import json
    return json.loads(texto.strip())

# 4. EL BOT "ESCUCHANDO" FOTOS Y DOCUMENTOS (PDF)
@bot.message_handler(commands=['start', 'help'])
def mensaje_bienvenida(message):
    texto = (
        "👋 ¡Hola! Soy tu bot automatizador de facturas.\n\n"
        "📸 Envíame una **FOTO** de un ticket de compra.\n"
        "📕 O envíame un **DOCUMENTO PDF** de una factura.\n\n"
        "Yo me encargaré de extraer los datos con Inteligencia Artificial (Empresa, CIF, Fecha, Base, IVA, Total) "
        "y los guardaré automáticamente en tu Google Sheets.\n\n"
        "También puedes consultar el resumen de gastos escribiendo /stats"
    )
    bot.reply_to(message, texto)

@bot.message_handler(commands=['stats'])
def stats_rapidas(message):
    msg = bot.reply_to(message, "📊 Calculando estadísticas desde Google Sheets...")
    try:
        hoja = conectar_sheets()
        filas = hoja.get_all_values()
        if len(filas) > 1:
            total_gastos = 0
            for f in filas[1:]:
                import re
                if len(f) > 5:
                    valor_str = str(f[5]).replace(',', '.').replace('€', '').strip()
                    numeros = re.findall(r"[-+]?\d*\.\d+|\d+", valor_str)
                    if numeros:
                        total_gastos += float(numeros[0])
            
            respuesta = f"📈 **Resumen de Facturas:**\n\n📄 Facturas registradas: {len(filas)-1}\n💰 Gasto Total: {total_gastos:.2f}€"
        else:
            respuesta = "Aún no tienes facturas registradas."
        
        bot.edit_message_text(respuesta, message.chat.id, msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ Error al consultar las estadísticas: {e}", message.chat.id, msg.message_id)


@bot.message_handler(content_types=['photo', 'document'])
def manejar_archivo(message):
    print("🔔 ¡Ha llegado un archivo!")
    msg_espera = bot.reply_to(message, "📸 Analizando documento...")
    
    try:
        # 1. Obtener información del archivo dependiendo del tipo (Image o Document PDF)
        if message.content_type == 'photo':
            file_info = bot.get_file(message.photo[-1].file_id)
            mime_type = "image/jpeg"
            nombre_archivo = f"ticket_{file_info.file_unique_id}.jpg"
        elif message.content_type == 'document':
            if message.document.mime_type != 'application/pdf':
                bot.edit_message_text("❌ Solo acepto imágenes (fotos) o documentos PDF.", message.chat.id, msg_espera.message_id)
                return
            file_info = bot.get_file(message.document.file_id)
            mime_type = "application/pdf"
            nombre_archivo = f"factura_{file_info.file_unique_id}.pdf"

        downloaded_file = bot.download_file(file_info.file_path)

        # 2. Analizar con Gemini
        datos = analizar_documento(downloaded_file, mime_type)

        # 3. Conectar y Guardar
        hoja = conectar_sheets()
        
        # Validación básica para que no falten campos clave
        campos_requeridos = ['fecha', 'empresa', 'cif', 'base', 'iva', 'total', 'categoria']
        for campo in campos_requeridos:
            if campo not in datos:
                datos[campo] = None

        # Si la hoja está vacía, ponemos los encabezados (ahora con NOMBRE ARCHIVO)
        if not hoja.acell('A1').value:
            encabezados = ["FECHA", "EMPRESA", "CIF", "BASE", "IVA", "TOTAL", "CATEGORIA", "NOMBRE ARCHIVO", "VERIFICADA"]
            hoja.insert_row(encabezados, 1)

        # 4. Preparamos la fila incluyendo el nombre del archivo al final y el campo de verificacion
        fila = [
            datos.get('fecha'), 
            datos.get('empresa'), 
            datos.get('cif'), 
            datos.get('base'), 
            datos.get('iva'), 
            datos.get('total'), 
            datos.get('categoria'),
            nombre_archivo,
            "NO"
        ]
        
        hoja.append_row(fila)

        bot.edit_message_text(
            f"✅ ¡Guardado!\n📂 Archivo: {nombre_archivo}\n🏢 Empresa: {datos.get('empresa')}\n📅 Fecha: {datos.get('fecha')}\n💰 Total: {datos.get('total')}€", 
            message.chat.id, msg_espera.message_id
        )

    except Exception as e:
        print(f"❌ Error: {e}")
        bot.edit_message_text(f"❌ Error: {str(e)}", message.chat.id, msg_espera.message_id)

print("🚀 Bot en marcha... Dile a tu padre que envíe una foto.")
if __name__ == "__main__":
    keep_alive() # Esto arranca la web en segundo plano
    print("🚀 Bot en marcha...")
    bot.polling(none_stop=True)