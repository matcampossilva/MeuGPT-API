import os
from dotenv import load_dotenv
from datetime import datetime
import pytz
from collections import defaultdict
from planilhas import get_gastos_diarios

load_dotenv()

def gerar_resumo(numero_usuario, periodo="mensal"):
    numero_usuario = numero_usuario.replace("whatsapp:", "").strip()
    aba = get_gastos_diarios()
    dados = aba.get_all_records()

    hoje = datetime.now().astimezone(pytz.timezone("America/Sao_Paulo"))
    print(f"[DEBUG] Hoje é {hoje.date()} no servidor")

    resumo = defaultdict(lambda: {"total": 0.0, "formas": defaultdict(float)})
    total_geral = 0.0

    for linha in dados:
        if linha.get("NÚMERO", "").strip() != numero_usuario:
            continue

        try:
            data_str = linha.get("DATA DO GASTO", "")
            data = datetime.strptime(data_str, "%d/%m/%Y")
        except Exception as e:
            print(f"[ERRO] Data inválida: {linha.get('DATA DO GASTO')} | {e}")
            continue

        print(f"[DEBUG] data={data.date()} | hoje={hoje.date()}")

        if periodo == "diario" and data.date() != hoje.date():
            continue
        if periodo == "mensal" and (data.month != hoje.month or data.year != hoje.year):
            continue

        categoria = linha.get("CATEGORIA", "A DEFINIR").strip()
        valor_bruto = str(linha.get("VALOR (R$)", "0")).replace("R$", "").replace(",", ".").strip()

        try:
            valor = float(valor_bruto)
            if valor < 0:
                continue
        except Exception as e:
            print(f"[ERRO] Valor inválido: {linha.get('VALOR (R$)')} | {e}")
            continue

        forma = linha.get("FORMA DE PAGAMENTO", "Outro").strip()

        resumo[categoria]["total"] += valor
        resumo[categoria]["formas"][forma] += valor
        total_geral += valor

    if total_geral == 0.0:
        return f"Resumo {periodo} dos seus gastos:\n\nTotal geral: R$0.00"

    linhas = [f"Resumo {periodo} dos seus gastos:", ""]
    for cat, dados in resumo.items():
        linhas.append(f"{cat}: R${dados['total']:.2f}")
        for forma, val in dados["formas"].items():
            linhas.append(f"  - {forma}: R${val:.2f}")
        linhas.append("")

    linhas.append(f"Total geral: R${total_geral:.2f}")
    return "\n".join(linhas)