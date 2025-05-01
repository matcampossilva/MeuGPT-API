from planilhas import get_gastos_diarios, get_limites
from datetime import datetime
import pytz
from collections import Counter
import re

def get_gastos_usuario(numero_usuario):
    aba = get_gastos_diarios()
    registros = aba.get_all_values()[1:]
    gastos_usuario = [
        linha for linha in registros if linha[1].strip() == numero_usuario
    ]
    return gastos_usuario

def resumo_do_mes(numero_usuario, mes=None, ano=None):
    fuso = pytz.timezone("America/Sao_Paulo")
    agora = datetime.now(fuso)
    mes = mes or agora.month
    ano = ano or agora.year

    gastos = get_gastos_usuario(numero_usuario)
    total = 0
    categorias = []

    for linha in gastos:
        try:
            data = datetime.strptime(linha[6], "%d/%m/%Y")
            if data.month == mes and data.year == ano:
                valor = float(linha[4])
                total += valor
                categorias.append(linha[3])
        except:
            continue

    if not categorias:
        return "Nenhum gasto encontrado neste mês."

    contagem = Counter(categorias)
    mais_frequentes = contagem.most_common(3)
    resumo = f"📅 *Resumo das suas finanças em {mes}/{ano}:*\n"
    resumo += f"Total gasto: R$ {total:.2f}\n"
    resumo += "Categorias mais frequentes:\n"

    for cat, qtd in mais_frequentes:
        total_cat = sum(float(linha[4]) for linha in gastos if linha[3] == cat)
        resumo += f"- {cat}: R${total_cat:.2f} ({qtd}x)\n"

    return resumo

def verificar_limites(numero_usuario):
    try:
        limites = get_limites()
        gastos = get_gastos_usuario(numero_usuario)
        total_por_categoria = {}

        for linha in gastos:
            categoria = linha[3]
            valor = float(linha[4])
            total_por_categoria[categoria] = total_por_categoria.get(categoria, 0) + valor

        resposta = "🔎 *Status dos limites*\n"
        for linha in limites.get_all_values()[1:]:
            if linha[1] == numero_usuario:
                categoria = linha[2]
                limite = float(linha[3])
                total = total_por_categoria.get(categoria, 0)
                if total > limite:
                    resposta += f"⚠️ *{categoria}* passou do limite (R$ {total:.2f} / R$ {limite:.2f})\n"
                else:
                    resposta += f"✅ *{categoria}* está dentro (R$ {total:.2f} / R$ {limite:.2f})\n"

        return resposta or "Sem limites registrados."

    except Exception as e:
        return f"[Erro ao verificar limites] {str(e)}"

def contexto_principal_usuario(numero_usuario, ultima_msg=None):
    historico = resumo_do_mes(numero_usuario).lower()
    if ultima_msg:
        historico += " " + ultima_msg.lower()

    palavras = {
        "casamento": ["casamento", "esposa", "marido", "matrimônio", "cônjuge"],
        "dívidas": ["dívida", "devendo", "juros", "negativado", "cobrança"],
        "liberdade_espiritual": ["oração", "espiritualidade", "fé", "deus", "pecado"],
        "controle_gastos": ["controle", "gasto", "gastos", "orçamento", "despesa", "despesas"],
        "decisoes_financeiras": ["decisão", "decisões", "investimento", "financiamento", "empréstimo"],
    }

    for contexto, termos in palavras.items():
        if any(termo in historico for termo in termos):
            return contexto

    return "geral"
    
def palavras_frequentes_usuario(numero_usuario, top_n=5):
    gastos = get_gastos_usuario(numero_usuario)
    todas_descricoes = " ".join([linha[2].lower() for linha in gastos])
    palavras = re.findall(r'\w+', todas_descricoes)
    contagem = Counter(palavras)
    return [palavra for palavra, _ in contagem.most_common(top_n)]