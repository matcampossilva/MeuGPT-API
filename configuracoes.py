import os
from dotenv import load_dotenv
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv()

# Variáveis de ambiente
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
MESSAGING_SERVICE_SID = os.getenv('MESSAGING_SERVICE_SID')

EMAIL_REMETENTE = os.getenv('EMAIL_REMETENTE')
SENHA_REMETENTE = os.getenv('SENHA_REMETENTE')

GOOGLE_SHEETS_URL = os.getenv("GOOGLE_SHEETS_URL")

# Variáveis para Google Sheets
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDS_FILE = "meugpt-api-sheets-92a9d439900d.json"
SPREADSHEET_NAME = "Controle de Usuários"
PAGANTES_SHEET = "Pagantes"
GRATUITOS_SHEET = "Gratuitos"

# Carrega planilha
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
client = gspread.authorize(creds)
spreadsheet = client.open(SPREADSHEET_NAME)

def obter_status_usuario(whatsapp):
    try:
        sheet_pagantes = spreadsheet.worksheet(PAGANTES_SHEET)
        sheet_gratuitos = spreadsheet.worksheet(GRATUITOS_SHEET)

        pagantes = sheet_pagantes.col_values(1)
        gratuitos = sheet_gratuitos.col_values(1)

        if whatsapp in pagantes:
            return "PAGANTE"
        elif whatsapp in gratuitos:
            return "GRATUITO"
        else:
            return "NOVO"
    except Exception as e:
        print(f"Erro ao obter status do usuário: {e}")
        return "ERRO"

def verificar_usuario(whatsapp):
    try:
        sheet_pagantes = spreadsheet.worksheet(PAGANTES_SHEET)
        pagantes = sheet_pagantes.col_values(1)
        return whatsapp in pagantes
    except Exception as e:
        print(f"Erro ao verificar usuário: {e}")
        return False

def atualizar_interacoes(whatsapp):
    try:
        sheet = spreadsheet.worksheet(GRATUITOS_SHEET)
        data = sheet.get_all_records()

        for idx, row in enumerate(data, start=2):
            if str(row["WhatsApp"]) == whatsapp:
                interacoes = int(row["Interações"])
                sheet.update_cell(idx, 3, interacoes + 1)
                return interacoes + 1
    except Exception as e:
        print(f"Erro ao atualizar interações: {e}")
    return 0

def registrar_usuario(nome, whatsapp, email):
    try:
        sheet = spreadsheet.worksheet(GRATUITOS_SHEET)
        data = sheet.get_all_records()
        telefones_existentes = [str(row["WhatsApp"]) for row in data]

        if whatsapp not in telefones_existentes:
            sheet.append_row([nome, whatsapp, 0, email])
            print(f"✅ Novo usuário registrado: {nome} - {whatsapp}")
        else:
            print(f"ℹ️ Usuário já existente: {whatsapp}")
    except Exception as e:
        print(f"Erro ao registrar usuário: {e}")
