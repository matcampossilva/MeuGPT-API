import os
import gspread
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import pytz

load_dotenv()

GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_SHEET_GASTOS_ID = os.getenv("GOOGLE_SHEET_GASTOS_ID")
GOOGLE_SHEETS_KEY_FILE = os.getenv("GOOGLE_SHEETS_KEY_FILE")

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_KEY_FILE, scope)
gs = gspread.authorize(creds)

def get_aba(sheet_id, nome_aba):
    planilha = gs.open_by_key(sheet_id)
    return planilha.worksheet(nome_aba)

def get_pagantes():
    return get_aba(GOOGLE_SHEET_ID, "Pagantes")

def get_gratuitos():
    return get_aba(GOOGLE_SHEET_ID, "Gratuitos")

def get_gastos_diarios():
    return get_aba(GOOGLE_SHEET_GASTOS_ID, "Gastos Diários")

def get_limites():
    return get_aba(GOOGLE_SHEET_GASTOS_ID, "Limites")

def get_gastos_fixos():
    return get_aba(GOOGLE_SHEET_GASTOS_ID, "Gastos Fixos")

def get_user_sheet(user_number):
    user_number = formatar_numero(user_number)
    aba_pagantes = get_pagantes()
    aba_gratuitos = get_gratuitos()

    pagantes = [formatar_numero(num) for num in aba_pagantes.col_values(2)]
    gratuitos = [formatar_numero(num) for num in aba_gratuitos.col_values(2)]

    if user_number in pagantes:
        return aba_pagantes
    elif user_number in gratuitos:
        return aba_gratuitos
    else:
        now = datetime.datetime.now(pytz.timezone("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S")
        aba_gratuitos.append_row(["", user_number, "", now, 0, 0])
        return aba_gratuitos