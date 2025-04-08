# planilhas.py
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

# === Cache planilha de controle ===
_cache_abas = {}

def get_aba(nome_aba):
    if nome_aba not in _cache_abas:
        planilha = gs.open_by_key(GOOGLE_SHEET_ID)
        aba = planilha.worksheet(nome_aba)
        _cache_abas[nome_aba] = aba
    return _cache_abas[nome_aba]

def get_pagantes():
    return get_aba("Pagantes")

def get_gratuitos():
    return get_aba("Gratuitos")


# === Cache planilha de gastos ===
_cache_abas_gastos = {}

def get_gastos_diarios():
    if "Gastos Diários" not in _cache_abas_gastos:
        planilha = gs.open_by_key(GOOGLE_SHEET_GASTOS_ID)
        aba = planilha.worksheet("Gastos Diários")
        _cache_abas_gastos["Gastos Diários"] = aba
    return _cache_abas_gastos["Gastos Diários"]

# === Cache planilha de limites ===
_cache_abas_limites = {}

def get_limites():
    if "Limites" not in _cache_abas_limites:
        planilha = gs.open_by_key(GOOGLE_SHEET_GASTOS_ID)
        aba = planilha.worksheet("Limites")
        _cache_abas_limites["Limites"] = aba
    return _cache_abas_limites["Limites"]
