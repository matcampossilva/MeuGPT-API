import os
from dotenv import load_dotenv
from datetime import datetime
import pytz
from collections import defaultdict
from planilhas import get_gastos_diarios

load_dotenv()

# === GERA RESUMO ===
def gerar_resumo(numero_usuario, periodo="mensal"):
    aba = get_gastos_diarios()
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