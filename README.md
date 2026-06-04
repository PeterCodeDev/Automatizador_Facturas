# 📑 Smart Invoice AI: Scanner & Analytics Bot

Una solución de nivel empresarial para la digitalización, control de gastos y gestión inteligente de facturas. Este proyecto combina Inteligencia Artificial multimodal para procesar documentos, automatización de datos en tiempo real en la nube y un flujo de trabajo interactivo a través de una API Serverless y un Bot de Telegram dedicado.

---

## 🎯 Características Principales

* **👁️ Extracción Multimodal con IA (Gemini 2.5):** Procesamiento dinámico de imágenes (`.jpg`, `.jpeg`) capturadas por webcam/cámara y documentos en formato `.pdf` para la extracción de datos fiscales estructurados (Empresa, CIF, Fecha, Bases, IVA y Totales).
* **📊 Pipeline Automatizado hacia Google Sheets:** Inserción y formateo automático de los datos extraídos en una hoja de cálculo centralizada actuando como base de datos distribuida mediante `gspread`.
* **🤖 Bot de Telegram Interactivo:** Interfaz conversacional que permite a los usuarios enviar facturas, consultar estadísticas rápidas de gastos acumulados (`/stats`) y aprobar registros al instante.
* **👥 Verificación Humana (Human-In-The-Loop):** El sistema calcula un grado de confianza (0-100%). Si los datos requieren ajustes, permite la edición y validación manual directa mediante botones dinámicos en Telegram o peticiones HTTP distribuidas.
* **🌐 API Serverless Inteligente:** Arquitectura basada en eventos (`handler`) lista para despliegues Cloud-Native que soporta operaciones `GET` para analíticas del Dashboard, `POST` para procesamiento y `PUT` para correcciones manuales.

---

## 🛠️ Stack Tecnológico

* **Backend Core:** Python 3.10+, Flask (Microservidor de monitoreo).
* **Inteligencia Artificial:** Google GenAI SDK (`gemini-2.5-flash`).
* **Integraciones Cloud:** Google Sheets API, Google Drive API (`gspread`, `oauth2client`).
* **Canales Inbound:** Telegram Bot API (`pyTelegramBotAPI`).
* **Estrategia de Despliegue:** * **API:** Arquitectura Serverless compatible con Vercel Functions / AWS Lambda.
    * **Worker:** Threading asíncrono optimizado para plataformas como Render / AWS EC2.

---

## ⚙️ Variables de Entorno Requeridas

Para desplegar y ejecutar este proyecto de forma segura, configura los siguientes secretos (las plataformas de hosting los inyectarán en producción, nunca subas tu archivo `.env` o `credentials.json` a GitHub):

```text
# --- Token de Canales ---
TELEGRAM_TOKEN=tu_token_de_telegram_bot

# --- API Keys de Inteligencia Artificial ---
GEMINI_API_KEY=tu_clave_de_api_de_google_gemini

# --- Configuraciones de Base de Datos / Hojas ---
SHEET_NAME=Facturas_Adrian
PORT=10000

# --- Producción Serverless (JSON crudo de la cuenta de servicio de Google) ---
GOOGLE_CREDENTIALS={"type": "service_account", "project_id": ...}
