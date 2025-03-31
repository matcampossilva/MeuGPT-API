# enviar_whatsapp.py
from twilio.rest import Client
from configuracoes import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN

def enviar_whatsapp(mensagem, numero_destino):
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    try:
        message = client.messages.create(
            from_='whatsapp:+14155238886',
            body=mensagem,
            to=f'whatsapp:{numero_destino}'
        )
        print(f"✅ Mensagem enviada com sucesso para {numero_destino}. SID: {message.sid}")
    except Exception as e:
        print(f"❌ Erro ao enviar WhatsApp: {e}")

# Exemplo prático para testar:
if __name__ == "__main__":
    numero_teste = input("Digite o número de destino (+55...): ")
    enviar_whatsapp("Teste do Meu Conselheiro Financeiro!", numero_teste)