import os
import gspread
import json
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

# === BASE DE CATEGORIAS DO USUÁRIO ===
CATEGORIAS_PADRAO = {
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
    "farmácia": "Saúde",
    "remédio": "Saúde",
    "presente": "Presentes",
    "frédéric": "Frédéric"
}

CATEGORIAS_USUARIO_PATH = "categorias_usuario.json"

def carregar_categorias_usuario():
    if not os.path.exists(CATEGORIAS_USUARIO_PATH):
        return {}
    with open(CATEGORIAS_USUARIO_PATH, "r") as f:
        return json.load(f)

def salvar_categorias_usuario(dados):
    with open(CATEGORIAS_USUARIO_PATH, "w") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

def atualizar_categoria_usuario(numero, descricao, categoria):
    dados = carregar_categorias_usuario()
    if numero not in dados:
        dados[numero] = {}
    dados[numero][descricao.lower()] = categoria
    salvar_categorias_usuario(dados)

def categorizar(descricao, numero_usuario):
    desc_lower = descricao.lower()
    categorias_usuario = carregar_categorias_usuario().get(numero_usuario, {})

    for chave, categoria in categorias_usuario.items():
        if chave in desc_lower:
            return categoria

    for chave, categoria in CATEGORIAS_PADRAO.items():
        if chave in desc_lower:
            return categoria

    return "A DEFINIR"

def registrar_gasto(nome_usuario, numero_usuario, descricao, valor, forma_pagamento, data_gasto=None):
    try:
        planilha = gs.open_by_key(GOOGLE_SHEET_GASTOS_ID)
        aba = planilha.worksheet("Gastos Diários")

        fuso = pytz.timezone("America/Sao_Paulo")
        agora = datetime.now(fuso)
        data_registro = agora.strftime("%d/%m/%Y %H:%M:%S")
        data_gasto = data_gasto or agora.strftime("%d/%m/%Y")

        categoria = categorizar(descricao, numero_usuario)

        nova_linha = [
            nome_usuario,
            numero_usuario,
            descricao,
            categoria,
            f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            forma_pagamento,
            data_gasto,
            data_registro
        ]

        aba.append_row(nova_linha)
        return {"status": "ok", "categoria": categoria}

    except Exception as e:
        print(f"[ERRO ao registrar gasto] {e}")
        return {"status": "erro", "mensagem": str(e)}