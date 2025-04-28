import os
import hashlib
from datetime import datetime
import pytz
from dotenv import load_dotenv

from planilhas import get_gastos_diarios

load_dotenv()

# === CATEGORIAS AUTOMÁTICAS ===
CATEGORIAS_AUTOMATICAS = {
    "almoço": "Alimentação",
    "jantar": "Alimentação",
    "café": "Alimentação",
    "ifood": "Alimentação",
    "padaria": "Alimentação",
    "farmácia": "Saúde",
    "remédio": "Saúde",
    "combustível": "Transporte",
    "gasolina": "Transporte",
    "uber": "Transporte",
    "água": "Moradia",
    "luz": "Moradia",
    "internet": "Moradia",
    "aluguel": "Moradia",
    "shopping": "Lazer",
    "cinema": "Lazer",
    "netflix": "Lazer"
}

# === CATEGORIZAÇÃO INTELIGENTE ===
def categorizar(descricao):
    descricao = descricao.lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u").replace("ç", "c")
    for chave, categoria in CATEGORIAS_AUTOMATICAS.items():
        if chave in descricao:
            return categoria
    return "A DEFINIR"

# === GERA ID ÚNICO ===
def gerar_id_unico(numero_usuario, descricao, valor, data_gasto):
    base = f"{numero_usuario}-{descricao}-{valor}-{data_gasto}"
    return hashlib.md5(base.encode()).hexdigest()

# === REGISTRO DE GASTO ===
def registrar_gasto(nome_usuario, numero_usuario, descricao, valor, forma_pagamento, data_gasto=None, categoria_manual=None):
    try:
        aba = get_gastos_diarios()

        fuso = pytz.timezone("America/Sao_Paulo")
        agora = datetime.now(fuso)
        data_registro = agora.strftime("%d/%m/%Y %H:%M:%S")
        data_gasto = data_gasto or agora.strftime("%d/%m/%Y")

        categoria = categoria_manual or categorizar(descricao) or "A DEFINIR"
        id_unico = gerar_id_unico(numero_usuario, descricao, valor, data_gasto)

        registros = [linha[8] for linha in aba.get_all_values()[1:] if len(linha) >= 9]
        if id_unico in registros:
            return {"status": "ignorado", "mensagem": "Esse gasto já foi registrado.", "categoria": categoria}

        nova_linha = [
            nome_usuario if nome_usuario else "Usuário",
            numero_usuario,
            descricao,
            categoria,
            f"{valor:.2f}".replace('.', ','),
            forma_pagamento,
            data_gasto,
            data_registro,
            id_unico
        ]

        aba.append_row(nova_linha)
        return {"status": "ok", "categoria": categoria}

    except Exception as e:
        print(f"[ERRO ao registrar gasto] {e}")
        return {"status": "erro", "mensagem": str(e)}

# === ALTERAR CATEGORIA ===
def atualizar_categoria(numero_usuario, descricao, data_gasto, nova_categoria):
    try:
        aba = get_gastos_diarios()
        registros = aba.get_all_values()

        for i, linha in enumerate(registros[1:], start=2):  # pula cabeçalho
            numero = linha[1].strip()
            desc = linha[2].strip().lower()
            data = linha[6].strip()

            if (
                numero == numero_usuario
                and desc == descricao.strip().lower()
                and data == data_gasto
            ):
                aba.update_cell(i, 4, nova_categoria)  # coluna D (categoria)
                return True

        print("[ATUALIZAR CATEGORIA] Nenhum gasto correspondente encontrado.")
        return False

    except Exception as e:
        print(f"[ERRO ao atualizar categoria] {e}")
        return False

# === CORREÇÃO DE GASTO ===
def corrigir_gasto(numero_usuario, descricao, valor, forma_pagamento, categoria, data_gasto):
    aba = get_gastos_diarios()
    registros = aba.get_all_values()

    for i, linha in enumerate(registros[1:], start=2):  
        if (linha[1].strip() == numero_usuario and
            linha[2].strip().lower() == descricao.strip().lower() and
            linha[6].strip() == data_gasto):
            aba.update_cell(i, 3, descricao)
            aba.update_cell(i, 4, categoria)
            aba.update_cell(i, 5, f"{valor:.2f}".replace('.', ','))
            aba.update_cell(i, 6, forma_pagamento)
            return True

    return False

import re

def parsear_gastos_em_lote(texto):
    """
    Recebe uma string com várias linhas no formato:
    Descrição – Valor – Forma de pagamento – Categoria (opcional)
    Retorna uma lista de dicionários com os campos extraídos ou uma lista de erros.
    """
    linhas = texto.strip().split('\n')
    gastos = []
    erros = []

    for linha in linhas:
        partes = [p.strip() for p in re.split(r'[-–]', linha)]

        if len(partes) < 3:
            erros.append(f"Linha inválida: '{linha}'. Formato esperado: Descrição – Valor – Forma – Categoria (opcional)")
            continue

        descricao = partes[0]
        valor_str = partes[1].replace("R$", "").replace(",", ".").strip()
        forma_pagamento = partes[2].capitalize()

        categoria = partes[3].capitalize() if len(partes) > 3 else None

        try:
            valor = float(valor_str)
        except ValueError:
            erros.append(f"Linha inválida: '{linha}'. Valor '{valor_str}' não é numérico.")
            continue

        gastos.append({
            "descricao": descricao,
            "valor": valor,
            "forma_pagamento": forma_pagamento,
            "categoria": categoria
        })

    return gastos, erros