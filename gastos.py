import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_SHEET_GASTOS_ID = os.getenv("GOOGLE_SHEET_GASTOS_ID")
GOOGLE_SHEETS_KEY_FILE = os.getenv("GOOGLE_SHEETS_KEY_FILE")

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_KEY_FILE, scope)
gs = gspread.authorize(creds)

planilha = gs.open_by_key(GOOGLE_SHEET_GASTOS_ID)
sheet = planilha.worksheet("Gastos Diários")

# Categorias padrao
CATEGORIAS_PADRAO = {
    "almoço": "Alimentação",
    "cafe": "Alimentação",
    "supermercado": "Alimentação",
    "presente": "Presentes",
    "esposa": "Presentes",
    "aluguel": "Moradia",
    "condomínio": "Moradia",
    "água": "Moradia",
    "luz": "Moradia",
    "internet": "Moradia",
    "iptu": "Impostos",
    "ipva": "Impostos",
    "remédio": "Saúde",
    "frédéric": "Frédéric",
    "mensalidade": "Frédéric",
    "gasolina": "Transporte",
    "uber": "Transporte",
    "pix": "Extras"
}

def sugerir_categoria(descricao):
    descricao = descricao.lower()
    for chave in CATEGORIAS_PADRAO:
        if chave in descricao:
            return CATEGORIAS_PADRAO[chave]
    return "Extras"

def registrar_gasto(nome_usuario, numero_usuario, descricao, valor, forma_pagamento):
    categoria = sugerir_categoria(descricao)
    data_gasto = datetime.now().strftime("%d/%m/%Y")
    data_registro = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    linha = [
        nome_usuario,
        numero_usuario,
        descricao,
        categoria,
        valor,
        forma_pagamento,
        data_gasto,
        data_registro
    ]

    try:
        sheet.append_row(linha)
        with open("log_registros.txt", "a") as f:
            f.write(f"✅ REGISTRO: {linha}\n")
        return {
            "status": "ok",
            "categoria": categoria
        }

    except Exception as e:
        with open("log_registros.txt", "a") as f:
            f.write(f"❌ ERRO: {e} - Linha: {linha}\n")
        return {
            "status": "erro",
            "mensagem": str(e)
        }