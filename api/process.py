import os
import json
import base64
import io
from http.server import BaseHTTPRequestHandler
from google import genai
from PIL import Image
import gspread
from google.oauth2.service_account import Credentials


def get_sheet():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise Exception("GOOGLE_CREDENTIALS environment variable not set")

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
        raise Exception("GEMINI_API_KEY environment variable not set")

    client_gemini = genai.Client(api_key=api_key)

    response = client_gemini.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            "Extrae en JSON: empresa, cif, fecha, base, iva, total, categoria.",
            imagen_pil
        ]
    )

    texto = response.text
    if "```json" in texto:
        texto = texto.split("```json")[1].split("```")[0]

    return json.loads(texto.strip())


def handler(request):
    if request.method == "OPTIONS":
        from http import HTTPStatus
        return ("", HTTPStatus.NO_CONTENT, {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        })

    if request.method != "POST":
        return (json.dumps({"error": "Method not allowed"}), 405, {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        })

    try:
        body = json.loads(request.body.read())
        image_b64 = body.get("image")

        if not image_b64:
            return (json.dumps({"error": "No image provided"}), 400, {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            })

        image_data = base64.b64decode(image_b64)
        img = Image.open(io.BytesIO(image_data))
        img.thumbnail((1024, 1024))

        datos = analizar_ticket(img)

        hoja = get_sheet()

        if not hoja.acell("A1").value:
            encabezados = ["FECHA", "EMPRESA", "CIF", "BASE", "IVA", "TOTAL", "CATEGORIA", "NOMBRE ARCHIVO"]
            hoja.insert_row(encabezados, 1)

        import hashlib
        nombre_archivo = f"ticket_{hashlib.md5(image_data).hexdigest()[:12]}.jpg"

        fila = [
            datos.get("fecha"),
            datos.get("empresa"),
            datos.get("cif"),
            datos.get("base"),
            datos.get("iva"),
            datos.get("total"),
            datos.get("categoria"),
            nombre_archivo
        ]

        hoja.append_row(fila)

        result = {
            "success": True,
            "empresa": datos.get("empresa"),
            "total": datos.get("total"),
            "nombre_archivo": nombre_archivo
        }

        return (json.dumps(result), 200, {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        })

    except Exception as e:
        return (json.dumps({"error": str(e)}), 500, {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        })
