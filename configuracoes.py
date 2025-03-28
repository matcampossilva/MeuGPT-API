import os
import requests
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Variáveis de configuração
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
MESSAGING_SERVICE_SID = os.getenv('MESSAGING_SERVICE_SID')

EMAIL_REMETENTE = os.getenv('EMAIL_REMETENTE')
SENHA_REMETENTE = os.getenv('SENHA_REMETENTE')

# 🔹 1. Verifica se o usuário já está registrado na planilha
def verificar_usuario(numero, aba):
    try:
        url = f"https://script.google.com/macros/s/AKfycbyyChxdjQiNv8jmJEI--6vamvK6VSqWAZ0bh2gl0ky-vjsus0fYxjdQtHFj8vbHlSjP/exec"
        response = requests.get(f"{url}?numero={numero}&aba={aba}")
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "encontrado":
                return data
    except Exception as e:
        print(f"Erro ao verificar usuário: {e}")
    return None

# 🔹 2. Registra novo usuário na planilha
def registrar_usuario(nome, email, numero, aba):
    try:
        url = f"https://script.google.com/macros/s/AKfycbyyChxdjQiNv8jmJEI--6vamvK6VSqWAZ0bh2gl0ky-vjsus0fYxjdQtHFj8vbHlSjP/exec"
        payload = {
            "nome": nome,
            "email": email,
            "numero": numero,
            "aba": aba
        }
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            print(f"✅ Novo usuário registrado com sucesso ({aba})")
        else:
            print(f"⚠️ Erro ao registrar usuário: {response.status_code}")
    except Exception as e:
        print(f"Erro na requisição de registro: {e}")

# 🔹 3. Atualiza contagem de interações
def atualizar_interacoes(numero, nova_contagem, aba):
    try:
        url = f"https://script.google.com/macros/s/AKfycbyyChxdjQiNv8jmJEI--6vamvK6VSqWAZ0bh2gl0ky-vjsus0fYxjdQtHFj8vbHlSjP/exec"
        payload = {
            "numero": numero,
            "interacoes": nova_contagem,
            "aba": aba
        }
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            print(f"✅ Interações atualizadas: {numero} -> {nova_contagem}")
        else:
            print(f"⚠️ Erro ao atualizar interações: {response.status_code}")
    except Exception as e:
        print(f"Erro ao atualizar interações: {e}")
