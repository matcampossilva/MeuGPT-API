# enviar_whatsapp.py
from twilio.rest import Client
from configuracoes import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, MESSAGING_SERVICE_SID

def enviar_whatsapp(mensagem, numero_destino="+5562992782150"):
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    try:
        message = client.messages.create(
            messaging_service_sid=MESSAGING_SERVICE_SID,  # 👈🏽 Aqui está o segredo!
            body=mensagem,
            to=f'whatsapp:{numero_destino}'
        )
        print(f"✅ Mensagem enviada com sucesso para {numero_destino}. SID: {message.sid}")
    except Exception as e:
        print(f"❌ Erro ao enviar WhatsApp: {e}")

if __name__ == "__main__":
    enviar_whatsapp("Teste do Meu Conselheiro Financeiro no número pessoal!")
