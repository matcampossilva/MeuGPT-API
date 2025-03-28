import os
from dotenv import load_dotenv
import requests

# Carrega variáveis do .env
load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
MESSAGING_SERVICE_SID = os.getenv('MESSAGING_SERVICE_SID')  # 👈🏽 NOVO!

EMAIL_REMETENTE = os.getenv('EMAIL_REMETENTE')
SENHA_REMETENTE = os.getenv('SENHA_REMETENTE')

# 🔍 Função de verificação de usuário
def verificar_usuario(numero, aba):
    """
    Verifica se o número do WhatsApp já está registrado na aba correta (Pagantes ou Gratuitos)
    e retorna os dados do usuário, se existirem. Caso contrário, retorna None.
    """
    try:
        response = requests.get(f"{GOOGLE_SHEETS_URL}?numero={numero}&aba={aba}")
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "encontrado":
                return data
    except Exception as e:
        print(f"Erro ao verificar usuário na planilha: {e}")
    return None
