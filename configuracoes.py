import os
import requests
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Configurações de autenticação
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
MESSAGING_SERVICE_SID = os.getenv('MESSAGING_SERVICE_SID')

EMAIL_REMETENTE = os.getenv('EMAIL_REMETENTE')
SENHA_REMETENTE = os.getenv('SENHA_REMETENTE')

# === Função 1: Verificar se o usuário existe na planilha ===
def verificar_usuario(numero, aba):
    """
    Verifica se o número do WhatsApp já está registrado na aba correta (Pagantes ou Gratuitos)
    e retorna os dados do usuário, se existirem. Caso contrário, retorna None.
    """
    try:
        url = f"https://script.google.com/macros/s/AKfycbyyChxdjQiNv8jmJEI--6vamvK6VSqWAZ0bh2gl0ky-vjsus0fYxjdQtHFj8vbHlSjP/exec"
        response = requests.get(f"{url}?numero={numero}&aba={aba}")
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "encontrado":
                return data
    except Exception as e:
        print(f"Erro ao verificar usuário na planilha: {e}")
    return None

# === Função 2: Atualizar o número de interações do usuário ===
def atualizar_interacoes(numero, nova_contagem, aba):
    """
    Atualiza o número de interações do usuário na planilha.
    """
    try:
        url = f"https://script.google.com/macros/s/AKfycbyyChxdjQiNv8jmJEI--6vamvK6VSqWAZ0bh2gl0ky-vjsus0fYxjdQtHFj8vbHlSjP/exec"
        payload = {
            "numero": numero,
            "interacoes": nova_contagem,
            "aba": aba
        }
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            print(f"✅ Interações atualizadas com sucesso: {numero} -> {nova_contagem}")
        else:
            print(f"⚠️ Erro ao atualizar interações: {response.status_code}")
    except Exception as e:
        print(f"Erro na requisição para atualizar interações: {e}")
