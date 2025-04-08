import os
import gspread
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
from collections import defaultdict
from enviar_whatsapp import enviar_whatsapp

# === CONFIG ===
load_dotenv()
GOOGLE_SHEET_GASTOS_ID = os.getenv("GOOGLE_SHEET_GASTOS_ID")
GOOGLE_SHEETS_KEY_FILE = os.getenv("GOOGLE_SHEETS_KEY_FILE")

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_KEY_FILE, scope)
gs = gspread.authorize(creds)

# === BUSCA LIMITES DEFINIDOS PELO USUÁRIO ===
def buscar_limites_do_usuario(numero_usuario):
    try:
        aba = gs.open_by_key(GOOGLE_SHEET_GASTOS_ID).worksheet("Limites")
        linhas = aba.get_all_records()
        limites = defaultdict(dict)

        for linha in linhas:
            if linha["NÚMERO"].strip() != numero_usuario:
                continue
            categoria = linha["CATEGORIA"].strip()
            limite_dia = linha.get("LIMITE_DIÁRIO", "")
            if isinstance(limite_dia, str):
                limite_dia = limite_dia.replace("R$", "").replace(",", ".").strip()
            try:
                limites[categoria] = float(limite_dia)
            except:
                continue

        return limites
    except Exception as e:
        print(f"Erro ao buscar limites: {e}")
        return {}

# === ALERTAS PERSONALIZADOS ===
def verificar_alertas():
    aba = gs.open_by_key(GOOGLE_SHEET_GASTOS_ID).worksheet("Gastos Diários")
    dados = aba.get_all_records()
    hoje = datetime.now(pytz.timezone("America/Sao_Paulo")).date()

    usuarios_gastos = defaultdict(lambda: defaultdict(float))

    for linha in dados:
        numero = linha["NÚMERO"]
        try:
            data_gasto = datetime.strptime(linha["DATA DO GASTO"], "%d/%m/%Y").date()
            if data_gasto != hoje:
                continue
        except:
            continue

        valor_str = str(linha["VALOR (R$)"]).replace("R$", "").replace(",", ".").strip()
        try:
            valor = float(valor_str)
        except:
            valor = 0.0

        categoria = linha["CATEGORIA"] or "A DEFINIR"
        usuarios_gastos[numero][categoria] += valor

    for numero, categorias in usuarios_gastos.items():
        limites_user = buscar_limites_do_usuario(numero)
        for cat, total in categorias.items():
            limite_cat = limites_user.get(cat)
            if limite_cat and total > limite_cat:
                mensagem = (
                    f"🚨 Alerta esperto! Hoje você já gastou R${total:.2f} com *{cat}* e seu limite era R${limite_cat:.2f}.\n"
                    f"Se for pra continuar gastando, que pelo menos valha a pena. Ou quer que eu esconda seu cartão? 😂"
                )
                enviar_whatsapp(numero, mensagem)

# === GERA RESUMO DE ALERTAS (sem envio direto) ===
def gerar_resumo_limites(numero_usuario):
    aba = gs.open_by_key(GOOGLE_SHEET_GASTOS_ID).worksheet("Gastos Diários")
    dados = aba.get_all_records()
    hoje = datetime.now(pytz.timezone("America/Sao_Paulo")).date()

    categorias_usuario = defaultdict(float)

    for linha in dados:
        numero = linha["NÚMERO"]
        if numero != numero_usuario:
            continue

        try:
            data_gasto = datetime.strptime(linha["DATA DO GASTO"], "%d/%m/%Y").date()
            if data_gasto != hoje:
                continue
        except:
            continue

        valor_str = str(linha["VALOR (R$)"]).replace("R$", "").replace(",", ".").strip()
        try:
            valor = float(valor_str)
        except:
            valor = 0.0

        categoria = linha["CATEGORIA"] or "A DEFINIR"
        categorias_usuario[categoria] += valor

    limites_user = buscar_limites_do_usuario(numero_usuario)
    alertas = []

    for cat, total in categorias_usuario.items():
        limite_cat = limites_user.get(cat)
        if limite_cat and total > limite_cat:
            alerta = (
                f"🚨 Alerta esperto! Hoje você já gastou R${total:.2f} com *{cat}* e seu limite era R${limite_cat:.2f}.\n"
                f"Se for pra continuar gastando, que pelo menos valha a pena. Ou quer que eu esconda seu cartão? 😂"
            )
            alertas.append(alerta)

    return "\n\n".join(alertas) if alertas else ""

if __name__ == "__main__":
    verificar_alertas()