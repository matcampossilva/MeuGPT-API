import os
from dotenv import load_dotenv
from datetime import datetime
import pytz
from collections import defaultdict
import random

from enviar_whatsapp import enviar_whatsapp
from planilhas import get_gastos_diarios

load_dotenv()

# === FRASES COMENTÁRIOS ===
def gerar_comentario(total):
    if total == 0:
        return random.choice([
            "Silêncio absoluto nos gastos hoje. Isso é paz... ou esquecimento?",
            "Sem gastos hoje? Milagre moderno.",
            "Seu cartão tá dormindo. Bom sinal. ⭐️",
        ])
    elif total < 50:
        return random.choice([
            "Gastinho modesto. Isso é autocontrole ou só falta de boleto?",
            "Você passou o dia como um monge. Financeiramente, pelo menos.",
            "Tá gastando menos que influencer bloqueado pela Shopee."
        ])
    elif total < 200:
        return random.choice([
            "Gastos ok. Nenhum escândalo financeiro hoje.",
            "Tudo sob controle, aparentemente. Mas sigo de olho. 👀",
            "Seu dinheiro foi e voltou. Tipo relacionamento adolescente."
        ])
    else:
        return random.choice([
            "Você tá vivendo como se não houvesse amanhã, né?",
            "Seu cartão de crédito tá quente. Precisa de férias.",
            "Tá financiando o PIB da Frédéric sozinho? Calma, campeão."
        ])

# === ENVIA RESUMO PROATIVO ===
def enviar_resumo_automatico(periodo="diario"):
    from gerar_resumo import gerar_resumo  # para reaproveitar
    from enviar_alertas import gerar_resumo_limites

    aba = get_gastos_diarios()
    registros = aba.get_all_records()

    hoje = datetime.now(pytz.timezone("America/Sao_Paulo"))
    usuarios = defaultdict(lambda: defaultdict(float))

    for linha in registros:
        numero = linha["NÚMERO"]
        categoria = linha["CATEGORIA"]
        try:
            data = datetime.strptime(linha["DATA DO GASTO"], "%d/%m/%Y")
        except:
            continue

        if periodo == "diario" and data.date() != hoje.date():
            continue
        if periodo == "semanal" and (hoje - data).days > 7:
            continue

        try:
            valor = float(str(linha["VALOR (R$)"]).replace("R$", "").replace(",", "."))
        except:
            valor = 0.0

        usuarios[numero][categoria] += valor

    for numero, categorias in usuarios.items():
        if not categorias:
            continue

        texto = [f"📊 Resumo {periodo} dos seus gastos:", ""]
        total = 0
        for cat, val in categorias.items():
            texto.append(f"{cat}: R${val:.2f}")
            total += val
        texto.append("")
        texto.append(f"Total geral: R${total:.2f}")
        texto.append("")
        texto.append(gerar_comentario(total))

        enviar_whatsapp(numero, "\n".join(texto))

        # Envia limites, se houver
        try:
            limites = gerar_resumo_limites(numero)
            if limites:
                enviar_whatsapp(numero, limites)
        except:
            pass

        print(f"✅ Resumo enviado para {numero}")

if __name__ == "__main__":
    enviar_resumo_automatico(periodo="diario")