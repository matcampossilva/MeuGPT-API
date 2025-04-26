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

def get_pagantes():
    return gs.open_by_key(GOOGLE_SHEET_ID).worksheet("Pagantes")

def get_gratuitos():
    return gs.open_by_key(GOOGLE_SHEET_ID).worksheet("Gratuitos")

def get_gastos_diarios():
    return gs.open_by_key(GOOGLE_SHEET_GASTOS_ID).worksheet("Gastos Diários")

def get_limites():
    return gs.open_by_key(GOOGLE_SHEET_GASTOS_ID).worksheet("Limites")

def get_gastos_fixos():
    return gs.open_by_key(GOOGLE_SHEET_GASTOS_ID).worksheet("Gastos Fixos")