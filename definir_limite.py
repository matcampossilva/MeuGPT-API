import random
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv
from enviar_whatsapp import enviar_whatsapp
from planilhas import get_gastos_diarios, get_limites
import mensagens
import pytz
from estado_usuario import carregar_estado, salvar_estado

load_dotenv()

fuso = pytz.timezone("America/Sao_Paulo")

def buscar_limites_do_usuario(numero_usuario):
    try:
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
    except Exception as e:
        print(f"Erro ao buscar limites: {e}")
        return {}

def verificar_alertas():
    aba = get_gastos_diarios()
    dados = aba.get_all_records()
    hoje = datetime.now(fuso).date()

    usuarios_gastos = defaultdict(lambda: defaultdict(float))

    for linha in dados:
        numero = linha["NÚMERO"]
        try:
            data_gasto = datetime.strptime(linha["DATA DO GASTO"], "%d/%m/%Y").date()
            if data_gasto != hoje:
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

def salvar_limite_usuario(numero, categoria, valor, tipo="mensal"):
    aba = get_limites()
    linhas = aba.get_all_records()
    linha_existente = None

    for i, linha in enumerate(linhas, start=2):
        # Convert to string before stripping/lowering to handle potential integer values from sheet
        if str(linha["NÚMERO"]).strip() == numero and str(linha["CATEGORIA"]).strip().lower() == categoria.lower():
            linha_existente = i
            break

    coluna = {"diario": 3, "semanal": 4, "mensal": 5}.get(tipo.lower(), 5)

    if linha_existente:
        aba.update_cell(linha_existente, coluna, valor)
    else:
        nova_linha = [numero, categoria, "", "", ""]
        nova_linha[coluna - 1] = valor
        aba.append_row(nova_linha)

if __name__ == "__main__":
    verificar_alertas()