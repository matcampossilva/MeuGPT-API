# planilhas.py
import os
import gspread
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv()

GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_SHEETS_KEY_FILE = os.getenv("GOOGLE_SHEETS_KEY_FILE")

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_KEY_FILE, scope)
gs = gspread.authorize(creds)

# === Cache das abas ===
_abas_controle = {}

def get_aba(nome):
    if nome not in _abas_controle:
        planilha = gs.open_by_key(GOOGLE_SHEET_ID)
        aba = planilha.worksheet(nome)
        _abas_controle[nome] = aba
    return _abas_controle[nome]

def get_pagantes():
    return get_aba("Pagantes")

def get_gratuitos():
    return get_aba("Gratuitos")