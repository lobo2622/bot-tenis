import os
import json
import requests
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

# Base de datos local derivada de tu Google Sheets
INVENTARIO = [
    {
        "ID": "TNS-1",
        "Marca": "Reebok",
        "Modelo": "Tenis court retro",
        "Diseño": "Casual",
        "Color": "Blanco",
        "Tallas_Disponibles": ["25"],
        "Precio_MXN": 700,
        "Link_Foto": "https://drive.google.com/file/d/1pefzjfv3JbZY5Ye1W1E0BRh-ZtuwxrP8/view?usp=sharing",
        "Estado": "Disponible"
    },
    {
        "ID": "TNS-2",
        "Marca": "Reebok",
        "Modelo": "Tenis detalles a contraste",
        "Diseño": "Sport",
        "Color": "Negro",
        "Tallas_Disponibles": ["25"],
        "Precio_MXN": 700,
        "Link_Foto": "https://drive.google.com/file/d/1p4iauxnVq7fo3B9ykKjuInHPN4S0MA55/view?usp=drive_link",
        "Estado": "Disponible"
    }
]

SYSTEM_PROMPT = f"""
Eres el asistente virtual amigable y profesional de la tienda de tenis.
Tu objetivo es ayudar a los clientes a encontrar pares disponibles, resolver dudas sobre compras y facilitar el proceso de pago/entrega.

INVENTARIO ACTUAL EN TIEMPO REAL:
{json.dumps(INVENTARIO, ensure_ascii=False, indent=2)}

REGLAS Y POLÍTICAS DEL NEGOCIO:
1. Métodos de Pago:
   - Efectivo.
   - Transferencia bancaria.
   - Pago con tarjeta presencial mediante terminal Mercado Pago (aceptamos todas las tarjetas de crédito, débito y vales de despensa).
2. Entregas y Envíos:
   - Entrega sin costo adicional en El Salto dentro de un radio de 10 km.
   - Envíos a zonas fuera de los 10 km en El Salto o alrededores: $50 MXN adicionales.
3. Sistema de Apartado:
   - Puedes apartar cualquier par a 30 días abonando desde un 30% del costo total.
4. Cambios y Devoluciones:
   - Aceptamos cambios únicamente por talla.
   - Requisito obligatorio: El calzado debe devolverse impecable, nuevo, sin usar y en las mismas condiciones entregadas.

INSTRUCCIONES DE RESPUESTA:
- Responde de forma concisa, educada y natural por WhatsApp.
- Si preguntan por un modelo o talla, consulta el INVENTARIO. Si está disponible, menciona el precio y comparte el Link_Foto correspondiente para que puedan verlo.
- Si solicitan comprar o apartar, confirma los detalles e indícales los pasos para realizar el pago o la entrega.
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
    return "Bad Request", 400

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
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
                        
                        # Generar respuesta con Gemini
                        chat = model.start_chat(history=[])
                        full_prompt = f"{SYSTEM_PROMPT}\n\nCliente dice: {user_text}"
                        response = chat.send_message(full_prompt)
                        bot_reply = response.text
                        
                        # Enviar respuesta a WhatsApp Meta API
                        send_whatsapp_message(from_number, bot_reply)
                        
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
    requests.post(url, json=payload, headers=headers)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
