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
    desc_lower = descricao.lower()
    for chave, categoria in CATEGORIAS_AUTOMATICAS.items():
        if chave in desc_lower:
            return categoria
    return None

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

        registros = aba.get_all_values()
        for linha in registros[1:]:
            if len(linha) >= 9 and linha[8].strip() == id_unico:
                print("[IGNORADO] Gasto duplicado detectado.")
                return {"status": "ignorado", "mensagem": "Gasto já registrado anteriormente.", "categoria": categoria}

        nova_linha = [
            nome_usuario,
            numero_usuario,
            descricao,
            categoria,
            float(valor),
            forma_pagamento,
            data_gasto,
            data_registro,
            id_unico  # Nova coluna oculta para controle
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