import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

load_dotenv()

# Nome da planilha
SPREADSHEET_NAME = "Controle de Usuários - MeuGPT"

# Nome da aba de cada tipo de usuário
ABA_PAGANTES = "Pagantes"
ABA_GRATUITOS = "Gratuitos"

# Caminho para o arquivo JSON da conta de serviço (usando Secret File no Render)
CREDS_FILE = "/etc/secrets/meugpt-api-sheets-2e29d11818b1.json"  # 👈🏽 agora é este!

# Escopo de acesso
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Autenticação
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
client = gspread.authorize(creds)
spreadsheet = client.open(SPREADSHEET_NAME)


def verificar_usuario(numero):
    for aba in [ABA_PAGANTES, ABA_GRATUITOS]:
        planilha = spreadsheet.worksheet(aba)
        colunas = planilha.col_values(2)  # coluna dos números de WhatsApp
        if numero in colunas:
            return True
    return False


def registrar_usuario(nome, numero, email):
    planilha = spreadsheet.worksheet(ABA_GRATUITOS)
    dados = planilha.get_all_values()

    # Evitar duplicidade
    for linha in dados:
        if len(linha) > 1 and linha[1] == numero:
            return

    nova_linha = [nome, numero, email, "0"]
    planilha.append_row(nova_linha)


def obter_status_usuario(numero):
    planilha_pagantes = spreadsheet.worksheet(ABA_PAGANTES)
    planilha_gratuitos = spreadsheet.worksheet(ABA_GRATUITOS)

    col_pagantes = planilha_pagantes.col_values(2)
    col_gratuitos = planilha_gratuitos.col_values(2)

    if numero in col_pagantes:
        return "ativo", None
    elif numero in col_gratuitos:
        linha = col_gratuitos.index(numero) + 1
        interacoes = int(planilha_gratuitos.cell(linha, 4).value)
        interacoes_restantes = max(0, 10 - interacoes)
        if interacoes >= 10:
            return "bloqueado", 0
        else:
            return "gratuito", interacoes_restantes
    else:
        return "novo", None


def atualizar_interacoes(numero):
    planilha = spreadsheet.worksheet(ABA_GRATUITOS)
    colunas = planilha.col_values(2)

    if numero in colunas:
        linha = colunas.index(numero) + 1
        interacoes_atuais = int(planilha.cell(linha, 4).value)
        planilha.update_cell(linha, 4, str(interacoes_atuais + 1))
