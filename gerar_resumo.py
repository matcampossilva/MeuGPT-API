import os
from dotenv import load_dotenv
from datetime import datetime
import pytz
from collections import defaultdict
from planilhas import get_gastos_diarios

load_dotenv()

# === GERA RESUMO ===
def gerar_resumo(numero_usuario, periodo="mensal", data_personalizada=None):
    numero_usuario = numero_usuario.replace("whatsapp:", "").strip()
    aba = get_gastos_diarios()
    dados = aba.get_all_records()

    hoje = datetime.now().astimezone(pytz.timezone("America/Sao_Paulo"))
    print(f"[DEBUG] Hoje é {hoje.date()} no servidor")

    resumo = defaultdict(lambda: {"total": 0.0, "formas": defaultdict(float)})
    total_geral = 0.0

    for linha in dados:
        print(f"[DEBUG] Linha bruta: {linha}")
        print(f"[DEBUG] NÚMERO: {linha.get('NÚMERO')} == {numero_usuario}")
        print(f"[DEBUG] DATA DO GASTO: {linha.get('DATA DO GASTO')}")

        numero_linha = str(linha.get("NÚMERO", "")).strip().replace("+", "").replace("whatsapp:", "")
        numero_requisicao = numero_usuario.replace("+", "").replace("whatsapp:", "").strip()
        if numero_linha != numero_requisicao:
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
        if periodo == "custom" and data_personalizada and data.date() != data_personalizada:
            continue

        if periodo == "mensal" and (data.month != hoje.month or data.year != hoje.year):
            continue

        categoria = linha.get("CATEGORIA", "A DEFINIR").strip()
        forma = linha.get("FORMA DE PAGAMENTO", "Outro").strip()
        valor_raw = linha.get("VALOR (R$)", 0)

        try:
            valor_str = str(valor_raw).replace("R$ ", "").replace("R$", "").replace(",", ".").strip()
            valor = float(valor_str)

            print(f"[DEBUG] valor_str={valor_str} | valor={valor}")
            if valor < 0:
                continue
        except Exception as e:
            print(f"[ERRO] Valor inválido: {valor_raw} | {e}")
            continue

        resumo[categoria]["total"] += valor
        resumo[categoria]["formas"][forma] += valor
        total_geral += valor

    # === FORMATAÇÃO DO TEXTO ===
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