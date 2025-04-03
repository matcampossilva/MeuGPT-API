import os
import gspread
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz

# === CONFIG ===
load_dotenv()

GOOGLE_SHEET_GASTOS_ID = os.getenv("GOOGLE_SHEET_GASTOS_ID")
GOOGLE_SHEETS_KEY_FILE = os.getenv("GOOGLE_SHEETS_KEY_FILE")

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_KEY_FILE, scope)
gs = gspread.authorize(creds)

# === CATEGORIAS AUTOMÁTICAS ===
CATEGORIAS_AUTOMATICAS = {
    "almoço": "Alimentação",
    "jantar": "Alimentação",
    "café": "Alimentação",
    "ifood": "Alimentação",
    "combustível": "Transporte",
    "gasolina": "Transporte",
    "uber": "Transporte",
    "água": "Moradia",
    "luz": "Moradia",
    "internet": "Moradia",
    "aluguel": "Moradia",
    "shopping": "Lazer",
    "cinema": "Lazer",
    "netflix": "Lazer",
}

# === CATEGORIZAÇÃO INTELIGENTE ===
def categorizar(descricao):
    desc_lower = descricao.lower()
    for chave, categoria in CATEGORIAS_AUTOMATICAS.items():
        if chave in desc_lower:
            return categoria
    return None

# === REGISTRO DE GASTO ===
def registrar_gasto(nome_usuario, numero_usuario, descricao, valor, forma_pagamento, data_gasto=None):
    try:
        planilha = gs.open_by_key(GOOGLE_SHEET_GASTOS_ID)
        aba = planilha.worksheet("Gastos Diários")

        # Datas
        fuso = pytz.timezone("America/Sao_Paulo")
        agora = datetime.now(fuso)
        data_registro = agora.strftime("%d/%m/%Y %H:%M:%S")
        data_gasto = data_gasto or agora.strftime("%d/%m/%Y")

        categoria = categorizar(descricao)
        if not categoria:
            categoria = "A DEFINIR"

        nova_linha = [
            nome_usuario,
            numero_usuario,
            descricao,
            categoria,
            float(valor),
            forma_pagamento,
            data_gasto,
            data_registro
        ]

        aba.append_row(nova_linha)
        return {"status": "ok", "categoria": categoria}

    except Exception as e:
        print(f"[ERRO ao registrar gasto] {e}")
        return {"status": "erro", "mensagem": str(e)}