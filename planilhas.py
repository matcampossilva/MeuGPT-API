import os
import gspread
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv()

GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_SHEET_GASTOS_ID = os.getenv("GOOGLE_SHEET_GASTOS_ID")
GOOGLE_SHEETS_KEY_FILE = os.getenv("GOOGLE_SHEETS_KEY_FILE")

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_KEY_FILE, scope)
gs = gspread.authorize(creds)

_cache_abas = {}

def get_aba(sheet_id, nome_aba):
    chave = f"{sheet_id}_{nome_aba}"
    if chave not in _cache_abas:
        planilha = gs.open_by_key(sheet_id)
        aba = planilha.worksheet(nome_aba)
        _cache_abas[chave] = aba
    return _cache_abas[chave]

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