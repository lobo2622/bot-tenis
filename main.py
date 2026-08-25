import os
import json
import io
import requests
import pandas as pd
from flask import Flask, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# Configuración de Claves de Entorno
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "mi_token_secreto_tenis")

# Configuración de Gemini AI
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Enlace de tu base de datos en Google Sheets convertida a formato de descarga directa CSV
SHEET_URL = "https://docs.google.com/spreadsheets/d/1VuEgzEqKc2SExRap6JXfgyhx2v7OJom3/export?format=csv"

def obtener_inventario():
    try:
        response = requests.get(SHEET_URL)
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text))
            # Limpiar filas vacías
            df = df.dropna(subset=['ID'])
            return df.to_dict(orient='records')
    except Exception as e:
        print(f"Error al leer Google Sheets: {e}")
    return []

SYSTEM_PROMPT_BASE = """
Eres el asistente virtual amigable y profesional de la tienda de tenis.
Tu objetivo es ayudar a los clientes a encontrar pares disponibles según su talla, marca o modelo, resolver dudas sobre compras y facilitar el pago o entrega.

REGLAS DEL NEGOCIO:
1. Métodos de Pago: Efectivo, transferencia o tarjeta con terminal Mercado Pago.
2. Entregas: Sin costo en El Salto (radio de 10 km). Fuera de ahí, $50 MXN adicionales.
3. Apartados: A 30 días abonando desde el 30%.
4. Cambios: Solo por talla y con calzado impecable y sin usar.

INSTRUCCIONES:
- Responde de forma concisa, educada y natural por WhatsApp.
- Si preguntan por modelos o tallas, revisa estrictamente el inventario actual, da el precio y comparte el Link_Foto si está disponible.
"""

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200
        return "Forbidden", 403
    return "Verificación exitosa del Webhook", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json
        print("Datos recibidos de WhatsApp:", json.dumps(data, indent=2))
        
        if data.get("object") == "whatsapp_business_account":
            for entry in data.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    messages = value.get("messages", [])
                    if messages:
                        msg = messages[0]
                        from_number = msg.get("from")
                        
                        if msg.get("type") == "text":
                            user_text = msg.get("text", {}).get("body", "")
                            
                            # Cargar inventario actualizado desde tu Google Sheet
                            inventario_actual = obtener_inventario()
                            
                            prompt_dinamico = f"""
{SYSTEM_PROMPT_BASE}

INVENTARIO ACTUALIZADO:
{json.dumps(inventario_actual, ensure_ascii=False, indent=2)}

Cliente dice: {user_text}
"""
                            # Generar respuesta con Gemini
                            chat = model.start_chat(history=[])
                            response = chat.send_message(prompt_dinamico)
                            bot_reply = response.text
                            
                            # Enviar respuesta automática por la API de Meta
                            send_whatsapp_message(from_number, bot_reply)
                            
    except Exception as e:
        print(f"Error procesando el mensaje: {e}")
        
    return jsonify({"status": "ok"}), 200

def send_whatsapp_message(to_number, text):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text}
    }
    response = requests.post(url, json=payload, headers=headers)
    print("Respuesta de envío a WhatsApp:", response.text)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
