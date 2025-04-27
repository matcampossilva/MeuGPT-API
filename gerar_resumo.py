import os
from dotenv import load_dotenv
from datetime import datetime
import pytz
from collections import defaultdict
from planilhas import get_gastos_diarios

load_dotenv()

# === GERA RESUMO ===
def gerar_resumo(numero_usuario, periodo="mensal", data_personalizada=None):
    numero_usuario = numero_usuario.replace("whatsapp:", "").replace("+", "").strip()
    aba = get_gastos_diarios()
    dados = aba.get_all_records()

    hoje = datetime.now(pytz.timezone("America/Sao_Paulo"))
    print(f"[DEBUG] Hoje é {hoje.date()} no servidor")

    resumo = defaultdict(lambda: {"total": 0.0, "formas": defaultdict(float)})
    total_geral = 0.0

    for linha in dados:
        numero_linha = str(linha.get("NÚMERO", "")).replace("whatsapp:", "").replace("+", "").strip()
        if numero_linha != numero_usuario:
            continue

        data_str = linha.get("DATA DO GASTO", "")
        try:
            data = datetime.strptime(data_str, "%d/%m/%Y").date()
        except Exception as e:
            print(f"[ERRO] Data inválida ({data_str}): {e}")
            continue

        if periodo == "diario" and data != hoje.date():
            continue
        if periodo == "custom" and data_personalizada and data != data_personalizada:
            continue
        if periodo == "mensal" and (data.month != hoje.month or data.year != hoje.year):
            continue

        categoria = linha.get("CATEGORIA", "A DEFINIR").strip()
        forma = linha.get("FORMA DE PAGAMENTO", "Outro").strip()
        valor_raw = linha.get("VALOR (R$)", 0)

        try:
            valor = float(str(valor_raw).replace("R$", "").replace(".", "").replace(",", ".").strip())
            if valor <= 0:
                continue
        except Exception as e:
            print(f"[ERRO] Valor inválido ({valor_raw}): {e}")
            continue

        resumo[categoria]["total"] += valor
        resumo[categoria]["formas"][forma] += valor
        total_geral += valor

    # === FORMATAÇÃO DO TEXTO ===
    if total_geral == 0.0:
        return f"Resumo {periodo} dos seus gastos:\n\nTotal geral: R$0,00"

    def formatar_valor(valor):
        return f"R${valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    linhas = [f"Resumo {periodo} dos seus gastos:", ""]
    for cat, dados in resumo.items():
        linhas.append(f"{cat}: {formatar_valor(dados['total'])}")
        for forma, val in dados["formas"].items():
            linhas.append(f"  - {forma}: {formatar_valor(val)}")
        linhas.append("")

    linhas.append(f"Total geral: {formatar_valor(total_geral)}")
    return "\n".join(linhas)