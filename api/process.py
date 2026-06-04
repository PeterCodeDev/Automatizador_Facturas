import json
import os
import base64
import io
import hashlib
from http.server import BaseHTTPRequestHandler
from google import genai
from PIL import Image
import gspread
from google.oauth2.service_account import Credentials

def get_sheet():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
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

def calcular_totales(mes_anio=None):
    hoja = get_sheet()
    filas = hoja.get_all_values()
    if len(filas) <= 1:
        return 0
    
    total_importe = 0
    for fila in filas[1:]:
        if len(fila) > 5 and fila[5]:
            try:
                val = float(str(fila[5]).replace('€', '').replace(',', '.').strip())
                if mes_anio:
                    fecha = fila[0] if len(fila) > 0 else ""
                    if mes_anio in fecha:
                        total_importe += val
                else:
                    total_importe += val
            except ValueError:
                pass
    return round(total_importe, 2)

def analizar_documento(file_data, mime_type):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Falta la variable GEMINI_API_KEY")

    client_gemini = genai.Client(api_key=api_key)
    
    prompt = """Extrae en JSON exacto: empresa, cif, fecha, base, iva, total, categoria.
Las categorías permitidas son SOLAMENTE: Transporte, Alimentacion, Software, Material, Oficina, Otros.
Asegúrate de que 'total', 'base' e 'iva' sean números o strings numéricos.
Añade un campo numérico 'confianza' (0 a 100) que indique tu grado de seguridad en la extracción de los datos visuales.
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


# 🚀 CLASE DE ENTRADA REQUERIDA POR VERCEL (en minúsculas)
class handler(BaseHTTPRequestHandler):

    def _set_headers(self, status_code=200):
        self.send_response(status_code)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS, PUT")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(204)

    def do_GET(self):
        self._set_headers(200)
        try:
            # Replicar comportamiento de rutas por el path
            if "stats" in self.path:
                total_historico = calcular_totales()
                self.wfile.write(json.dumps({"historico": total_historico}).encode('utf-8'))
                return

            hoja = get_sheet()
            todas_filas = hoja.get_all_values()
            
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
                        "nombre_archivo": fila[7] if len(fila) > 7 else "",
                        "verificada": fila[8] if len(fila) > 8 else "NO",
                        "confianza": fila[9] if len(fila) > 9 else "100"
                    })
                self.wfile.write(json.dumps({"history": history}).encode('utf-8'))
            else:
                self.wfile.write(json.dumps({"history": []}).encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            self.wfile.write(json.dumps({"error": f"Error fetch history: {str(e)}"}).encode('utf-8'))

    def do_PUT(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            body = json.loads(post_data.decode('utf-8'))

            nombre_archivo = body.get("nombre_archivo")
            if not nombre_archivo:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Falta nombre_archivo para verificar."}).encode('utf-8'))
                return
                
            hoja = get_sheet()
            col_archivos = hoja.col_values(8)
            
            try:
                fila_idx = col_archivos.index(nombre_archivo) + 1
                empresa_nueva = body.get("empresa")
                categoria_nueva = body.get("categoria")
                total_nuevo = body.get("total")
                
                if empresa_nueva:
                    hoja.update_cell(fila_idx, 2, empresa_nueva)
                if categoria_nueva:
                    hoja.update_cell(fila_idx, 7, categoria_nueva)
                if total_nuevo is not None:
                    hoja.update_cell(fila_idx, 6, total_nuevo)
                    
                hoja.update_cell(fila_idx, 9, "SI")
                self._set_headers(200)
                self.wfile.write(json.dumps({"success": True}).encode('utf-8'))
            except ValueError:
                self._set_headers(404)
                self.wfile.write(json.dumps({"error": "Factura no encontrada."}).encode('utf-8'))
        except Exception as e:
            self._set_headers(500)
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            body = json.loads(post_data.decode('utf-8'))

            file_b64 = body.get("file") or body.get("image")
            mime_type = body.get("mimeType", "image/jpeg")

            if not file_b64:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "No se recibió archivo"}).encode('utf-8'))
                return

            file_data = base64.b64decode(file_b64)
            datos = analizar_documento(file_data, mime_type)
            hoja = get_sheet()
            
            campos_requeridos = ['fecha', 'empresa', 'cif', 'base', 'iva', 'total', 'categoria', 'confianza']
            for campo in campos_requeridos:
                if campo not in datos:
                    datos[campo] = None

            for num_field in ['base', 'iva', 'total']:
                if datos.get(num_field):
                    val = str(datos[num_field]).replace(',', '.').replace('€', '').strip()
                    try:
                        datos[num_field] = round(float(val), 2)
                    except ValueError:
                        datos[num_field] = 0

            if not hoja.acell("A1").value:
                hoja.insert_row(["FECHA", "EMPRESA", "CIF", "BASE", "IVA", "TOTAL", "CATEGORIA", "NOMBRE ARCHIVO", "VERIFICADA", "CONFIANZA"], 1)

            extension = ".pdf" if "pdf" in mime_type else ".jpg"
            nombre_archivo = f"doc_{hashlib.md5(file_data).hexdigest()[:12]}{extension}"
            
            fila = [
                datos.get("fecha"), datos.get("empresa"), datos.get("cif"),
                datos.get("base"), datos.get("iva"), datos.get("total"),
                datos.get("categoria"), nombre_archivo, "NO", datos.get("confianza")
            ]
            hoja.append_row(fila)

            result = {
                "success": True,
                "empresa": datos.get("empresa"),
                "total": datos.get("total"),
                "fecha": datos.get("fecha"),
                "iva": datos.get("iva"),
                "categoria": datos.get("categoria"),
                "confianza": datos.get("confianza"),
                "nombre_archivo": nombre_archivo
            }
            self._set_headers(200)
            self.wfile.write(json.dumps(result).encode('utf-8'))

        except Exception as e:
            self._set_headers(500)
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))