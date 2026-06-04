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


def analizar_documento(file_data, mime_type):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Falta la variable GEMINI_API_KEY")

    client_gemini = genai.Client(api_key=api_key)
    
    prompt = """Extrae en JSON exacto: empresa, cif, fecha, base, iva, total, categoria.
Asegúrate de que 'total', 'base' e 'iva' sean números o strings numéricos.
Devuelve el resultado estructurado estrictamente en JSON y asegúrate de validar los datos fiscales presentes en el documento."""

    response = client_gemini.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            prompt,
            {"mime_type": mime_type, "data": file_data}
        ]
    )
    texto = response.text
    if "```json" in texto:
        texto = texto.split("```json")[1].split("```")[0]
    return json.loads(texto.strip())


def handler(event, context=None):
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Content-Type": "application/json"
    }

    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method")

    if method == "OPTIONS":
        return {"statusCode": 204, "headers": headers, "body": ""}

    if method == "GET":
        try:
            hoja = get_sheet()
            todas_filas = hoja.get_all_values()
            
            # Devolvemos hasta las 50 filas más recientes para alimentar el dashboard frontend
            if len(todas_filas) > 1:
                recientes = todas_filas[1:][-50:]
                history = []
                for fila in reversed(recientes):
                    history.append({
                        "fecha": fila[0] if len(fila) > 0 else "",
                        "empresa": fila[1] if len(fila) > 1 else "",
                        "base": fila[3] if len(fila) > 3 else "0",
                        "iva": fila[4] if len(fila) > 4 else "0",
                        "total": fila[5] if len(fila) > 5 else "0",
                        "categoria": fila[6] if len(fila) > 6 else "Otros",
                        "verificada": fila[8] if len(fila) > 8 else "NO"
                    })
                return {"statusCode": 200, "headers": headers, "body": json.dumps({"history": history})}
            else:
                return {"statusCode": 200, "headers": headers, "body": json.dumps({"history": []})}
        except Exception as e:
            return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": f"Error fetch history: {str(e)}"})}

    if method != "POST":
        return {"statusCode": 405, "headers": headers, "body": json.dumps({"error": "Método no permitido"})}

    try:
        body_str = event.get("body", "{}")
        body = json.loads(body_str) if isinstance(body_str, str) else body_str
        
        # Soportamos la clave antigua (image) o la nueva para docs (file)
        file_b64 = body.get("file") or body.get("image")
        mime_type = body.get("mimeType", "image/jpeg")

        if not file_b64:
            return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "No se recibió archivo"})}

        file_data = base64.b64decode(file_b64)

        datos = analizar_documento(file_data, mime_type)
        hoja = get_sheet()
        
        # Validacion del JSON devuelto por Gemini para campos requeridos
        campos_requeridos = ['fecha', 'empresa', 'cif', 'base', 'iva', 'total', 'categoria']
        for campo in campos_requeridos:
            if campo not in datos:
                datos[campo] = None

        if not hoja.acell("A1").value:
            hoja.insert_row(["FECHA", "EMPRESA", "CIF", "BASE", "IVA", "TOTAL", "CATEGORIA", "NOMBRE ARCHIVO", "VERIFICADA"], 1)

        extension = ".pdf" if "pdf" in mime_type else ".jpg"
        nombre_archivo = f"doc_{hashlib.md5(file_data).hexdigest()[:12]}{extension}"
        
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
            "categoria": datos.get("categoria"),
            "nombre_archivo": nombre_archivo
        }
        return {"statusCode": 200, "headers": headers, "body": json.dumps(result)}

    except Exception as e:
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": str(e)})}
