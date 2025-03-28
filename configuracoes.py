import os
import pytz
import gspread
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv()

# Variáveis de ambiente
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
MESSAGING_SERVICE_SID = os.getenv('MESSAGING_SERVICE_SID')

EMAIL_REMETENTE = os.getenv('EMAIL_REMETENTE')
SENHA_REMETENTE = os.getenv('SENHA_REMETENTE')

# Nome do arquivo .json da credencial do Google
CREDS_FILE = "credenciais_gspread.json"

# Escopo e credenciais para Google Sheets
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
client = gspread.authorize(creds)

# Nome da planilha
SPREADSHEET_NAME = "Controle de usuários"

# Abas
spreadsheet = client.open(SPREADSHEET_NAME)
aba_pagantes = spreadsheet.worksheet("Pagantes")
aba_gratuitos = spreadsheet.worksheet("Gratuitos")

def verificar_usuario(numero):
    try:
        numeros = aba_pagantes.col_values(2) + aba_gratuitos.col_values(2)
        return numero in numeros
    except:
        return False

def obter_status_usuario(numero):
    try:
        if numero in aba_pagantes.col_values(2):
            return "ativo", None
        elif numero in aba_gratuitos.col_values(2):
            celula = aba_gratuitos.find(numero)
            interacoes_restantes = int(aba_gratuitos.cell(celula.row, 4).value)
            if interacoes_restantes <= 0:
                return "bloqueado", 0
            return "gratuito", interacoes_restantes
        else:
            return "novo", None
    except:
        return "erro", None

def registrar_usuario(nome, numero, email):
    try:
        numero = str(numero)
        if not numero.startswith("+"):
            numero = f"+{numero}"
        aba_gratuitos.append_row([nome, numero, email, 10])
    except Exception as e:
        print(f"Erro ao registrar usuário: {e}")

def atualizar_interacoes(numero):
    try:
        celula = aba_gratuitos.find(numero)
        interacoes = int(aba_gratuitos.cell(celula.row, 4).value)
        if interacoes > 0:
            aba_gratuitos.update_cell(celula.row, 4, interacoes - 1)
    except Exception as e:
        print(f"Erro ao atualizar interações: {e}")
