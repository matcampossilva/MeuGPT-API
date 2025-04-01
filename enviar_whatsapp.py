import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
MESSAGING_SERVICE_SID = os.getenv("MESSAGING_SERVICE_SID")

def enviar_whatsapp(numero_destino, mensagem):
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    try:
        message = client.messages.create(
            messaging_service_sid=MESSAGING_SERVICE_SID,
            body=mensagem,
            to=f"whatsapp:{numero_destino}"
        )
        print(f"✅ Mensagem enviada com sucesso para {numero_destino}. SID: {message.sid}")
    except Exception as e:
        print(f"❌ Erro ao enviar WhatsApp: {e}")

# Exemplo para teste direto:
if __name__ == "__main__":
    enviar_whatsapp("+5562999022021", "Teste do Meu Conselheiro Financeiro em PRODUÇÃO!")