from twilio.rest import Client
from configuracoes import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, MESSAGING_SERVICE_SID

def enviar_whatsapp(mensagem, numero_destino):
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    try:
        message = client.messages.create(
            messaging_service_sid=MESSAGING_SERVICE_SID,
            body=mensagem,
            to=f'whatsapp:{numero_destino}'
        )
        print(f"✅ Mensagem enviada com sucesso para {numero_destino}. SID: {message.sid}")
    except Exception as e:
        print(f"❌ Erro ao enviar WhatsApp: {e}")
