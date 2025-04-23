import os
import gspread
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
from collections import defaultdict
from enviar_whatsapp import enviar_whatsapp
import mensagens
from estado_usuario import carregar_estado, salvar_estado
from planilhas import get_gastos_diarios, get_limites

# === CONFIG ===
load_dotenv()
fuso = pytz.timezone("America/Sao_Paulo")

# === BUSCA LIMITES DEFINIDOS PELO USUÁRIO ===
def buscar_limites_do_usuario(numero_usuario):
    aba = get_limites()
    linhas = aba.get_all_records()
    limites = {}

    for linha in linhas:
        if linha["NÚMERO"].strip() != numero_usuario:
            continue
        categoria = linha["CATEGORIA"].strip()
        limite_mes = linha.get("LIMITE_MENSAL", "")
        if isinstance(limite_mes, str):
            limite_mes = limite_mes.replace("R$", "").replace(".", "").replace(",", ".").strip()
        try:
            limites[categoria] = float(limite_mes)
        except:
            continue

    return limites

# === ALERTAS PERSONALIZADOS ===
def verificar_alertas():
    aba = get_gastos_diarios()
    dados = aba.get_all_records()
    hoje = datetime.now(fuso).date()

    usuarios_gastos = defaultdict(lambda: defaultdict(float))

    for linha in dados:
        numero = linha["NÚMERO"]
        try:
            data_gasto = datetime.strptime(linha["DATA DO GASTO"], "%d/%m/%Y").date()
            if data_gasto.month != hoje.month or data_gasto.year != hoje.year:
                continue
        except:
            continue

        valor_str = str(linha["VALOR (R$)"]).replace("R$", "").replace(".", "").replace(",", ".").strip()
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
            if not limite_cat:
                continue

            percentual = (total / limite_cat) * 100
            faixa = None
            if 45 < percentual <= 55:
                faixa = "50"
            elif 65 < percentual <= 75:
                faixa = "70"
            elif 85 < percentual <= 95:
                faixa = "90"
            elif 95 < percentual <= 105:
                faixa = "100"
            elif percentual > 105:
                faixa = ">100"

            if faixa:
                mensagem = mensagens.alerta_limite_excedido(cat, total, limite_cat, faixa)

                estado_alertas = carregar_estado(numero)
                alertas_enviados = estado_alertas.get("alertas_enviados", [])

                if mensagem not in alertas_enviados:
                    enviar_whatsapp(numero, mensagem)
                    alertas_enviados.append(mensagem)
                    estado_alertas["alertas_enviados"] = alertas_enviados
                    salvar_estado(numero, estado_alertas)

# === GERA RESUMO DE ALERTAS (sem envio direto) ===
def gerar_resumo_limites(numero_usuario):
    aba = get_gastos_diarios()
    dados = aba.get_all_records()
    hoje = datetime.now(fuso).date()

    categorias_usuario = defaultdict(float)

    for linha in dados:
        numero = linha["NÚMERO"]
        if numero != numero_usuario:
            continue

        try:
            data_gasto = datetime.strptime(linha["DATA DO GASTO"], "%d/%m/%Y").date()
            if data_gasto.month != hoje.month or data_gasto.year != hoje.year:
                continue
        except:
            continue

        valor_str = str(linha["VALOR (R$)"]).replace("R$", "").replace(".", "").replace(",", ".").strip()
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
            percentual = (total / limite_cat) * 100
            faixa = None
            if 45 < percentual <= 55:
                faixa = "50"
            elif 65 < percentual <= 75:
                faixa = "70"
            elif 85 < percentual <= 95:
                faixa = "90"
            elif 95 < percentual <= 105:
                faixa = "100"
            elif percentual > 105:
                faixa = ">100"

            if faixa:
                alerta = mensagens.alerta_limite_excedido(cat, total, limite_cat, faixa)
                alertas.append(alerta)

    return "\n\n".join(alertas) if alertas else ""

if __name__ == "__main__":
    verificar_alertas()