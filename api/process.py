import json
import os
import base64
import io
import hashlib
from google import genai
from PIL import Image
import gspread
from google.oauth2.service_account import Credentials


def get_sheet():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        # Intento leer desde el archivo si no hay variable de entorno, util para testing local
        if os.path.exists('credentials.json'):
            client = gspread.service_account(filename='credentials.json')
            sheet_name = os.environ.get("SHEET_NAME", "Facturas_Adrian")
            return client.open(sheet_name).sheet1
        raise ValueError("Falta la variable GOOGLE_CREDENTIALS o archivo credentials.json")

    creds_dict = json.loads(creds_json)
    credentials = Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    )
    client = gspread.authorize(credentials)
    sheet_name = os.environ.get("SHEET_NAME", "Facturas_Adrian")
    return client.open(sheet_name).sheet1


def analizar_ticket(imagen_pil):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Falta la variable GEMINI_API_KEY")

    client_gemini = genai.Client(api_key=api_key)
    response = client_gemini.models.generate_content(
        model="gemini-2.5-flash",
        contents=["Extrae en JSON: empresa, cif, fecha, base, iva, total, categoria.", imagen_pil]
    )
    texto = response.text
    if "```json" in texto:
        texto = texto.split("```json")[1].split("```")[0]
    return json.loads(texto.strip())


def handler(event, context=None):
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Content-Type": "application/json"
    }

    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method")

    if method == "OPTIONS":
        return {"statusCode": 204, "headers": headers, "body": ""}

    if method != "POST":
        return {"statusCode": 405, "headers": headers, "body": json.dumps({"error": "Método no permitido"})}

    try:
        body_str = event.get("body", "{}")
        body = json.loads(body_str) if isinstance(body_str, str) else body_str
        image_b64 = body.get("image")

        if not image_b64:
            return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "No se recibió imagen"})}

        image_data = base64.b64decode(image_b64)
        img = Image.open(io.BytesIO(image_data))
        img.thumbnail((1024, 1024))

        datos = analizar_ticket(img)
        hoja = get_sheet()
        
        # Validacion del JSON devuelto por Gemini para campos requeridos
        campos_requeridos = ['fecha', 'empresa', 'cif', 'base', 'iva', 'total', 'categoria']
        for campo in campos_requeridos:
            if campo not in datos:
                datos[campo] = None

        if not hoja.acell("A1").value:
            hoja.insert_row(["FECHA", "EMPRESA", "CIF", "BASE", "IVA", "TOTAL", "CATEGORIA", "NOMBRE ARCHIVO", "VERIFICADA"], 1)

        nombre_archivo = f"ticket_{hashlib.md5(image_data).hexdigest()[:12]}.jpg"
        
        # Guardaremos un campo más "VERIFICADA" para que una persona pueda revisar que la IA no alucinó
        fila = [
            datos.get("fecha"), datos.get("empresa"), datos.get("cif"),
            datos.get("base"), datos.get("iva"), datos.get("total"),
            datos.get("categoria"), nombre_archivo, "NO"
        ]
        hoja.append_row(fila)

        result = {
            "success": True,
            "empresa": datos.get("empresa"),
            "total": datos.get("total"),
            "fecha": datos.get("fecha"),
            "iva": datos.get("iva"),
            "nombre_archivo": nombre_archivo
        }
        return {"statusCode": 200, "headers": headers, "body": json.dumps(result)}

    except Exception as e:
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": str(e)})}
