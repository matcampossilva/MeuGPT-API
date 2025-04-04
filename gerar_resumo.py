import os
import gspread
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
from collections import defaultdict

# === CONFIG ===
load_dotenv()
GOOGLE_SHEET_GASTOS_ID = os.getenv("GOOGLE_SHEET_GASTOS_ID")
GOOGLE_SHEETS_KEY_FILE = os.getenv("GOOGLE_SHEETS_KEY_FILE")

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_KEY_FILE, scope)
gs = gspread.authorize(creds)

# === GERA RESUMO ===
def gerar_resumo(numero_usuario, periodo="mensal"):
    aba = gs.open_by_key(GOOGLE_SHEET_GASTOS_ID).worksheet("Gastos Diários")
    dados = aba.get_all_records()

    hoje = datetime.now(pytz.timezone("America/Sao_Paulo"))
    resumo = defaultdict(lambda: {"total": 0.0, "formas": defaultdict(float)})
    total_geral = 0.0

    for linha in dados:
        if linha["NÚMERO"] != numero_usuario:
            continue

        try:
            data = datetime.strptime(linha["DATA DO GASTO"], "%d/%m/%Y")
        except:
            continue

        if periodo == "diario" and data.date() != hoje.date():
            continue
        if periodo == "mensal" and (data.month != hoje.month or data.year != hoje.year):
            continue

        categoria = linha["CATEGORIA"]

        valor_str = str(linha["VALOR (R$)"]).replace("R$", "").replace(" ", "").replace(",", ".")
        try:
            valor = float(valor_str)
        except ValueError:
            valor = 0.0

        forma = linha["FORMA DE PAGAMENTO"]

        resumo[categoria]["total"] += valor
        resumo[categoria]["formas"][forma] += valor
        total_geral += valor

    # === FORMATAÇÃO DO TEXTO ===
    linhas = [f"Resumo {periodo} dos seus gastos:", ""]
    for cat, dados in resumo.items():
        linhas.append(f"{cat}: R${dados['total']:.2f}")
        for forma, val in dados["formas"].items():
            linhas.append(f"  - {forma}: R${val:.2f}")
        linhas.append("")

    linhas.append(f"Total geral: R${total_geral:.2f}")
    return "\n".join(linhas)

# Exemplo de teste local (só se quiser testar por fora)
# print(gerar_resumo("+556292782150", periodo="diario"))