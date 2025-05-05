# -*- coding: utf-8 -*-
"""
Função para registrar e atualizar gastos fixos mensais na planilha.
"""
import logging
import re
from planilhas import get_gastos_fixos, formatar_numero

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def salvar_gasto_fixo(numero_usuario, descricao, valor, dia_vencimento, categoria="A definir"):
    """Salva um gasto fixo na aba 'Gastos Fixos'.

    Args:
        numero_usuario (str): Número do usuário (já formatado).
        descricao (str): Descrição do gasto.
        valor (float): Valor do gasto.
        dia_vencimento (int): Dia do mês para o vencimento.
        categoria (str, optional): Categoria do gasto. Defaults to "A definir".

    Returns:
        dict: Dicionário com status ("ok" ou "erro") e mensagem.
    """
    try:
        aba_gastos_fixos = get_gastos_fixos()
        # Colunas esperadas: NÚMERO, DESCRIÇÃO, VALOR, FORMA_PGTO, CATEGORIA, DIA_DO_MÊS
        linha = [
            numero_usuario,
            descricao.strip().capitalize(),
            f"{valor:.2f}".replace(".", ","), # Formata como string BRL para a planilha
            "", # FORMA_PGTO (deixar em branco por enquanto)
            categoria.strip().capitalize(),
            str(dia_vencimento) # Dia como string
        ]
        aba_gastos_fixos.append_row(linha)
        logging.info(f"Gasto fixo '{descricao}' para {numero_usuario} salvo com sucesso.")
        return {"status": "ok", "mensagem": "Gasto fixo salvo com sucesso."}
    except Exception as e:
        logging.error(f"Erro ao salvar gasto fixo '{descricao}' para {numero_usuario}: {e}", exc_info=True)
        return {"status": "erro", "mensagem": f"Erro ao salvar gasto fixo na planilha: {e}"}

def atualizar_categoria_gasto_fixo(numero_usuario, descricao, dia_vencimento, nova_categoria):
    """Atualiza a categoria de um gasto fixo específico na planilha.

    Args:
        numero_usuario (str): Número do usuário (já formatado).
        descricao (str): Descrição exata do gasto a ser atualizado.
        dia_vencimento (int): Dia do vencimento exato do gasto a ser atualizado.
        nova_categoria (str): Nova categoria a ser definida.

    Returns:
        bool: True se atualizou com sucesso, False caso contrário.
    """
    try:
        aba_gastos_fixos = get_gastos_fixos()
        # Encontra a linha correspondente (considerando possível capitalização diferente)
        # Colunas: NÚMERO(1), DESCRIÇÃO(2), VALOR(3), FORMA_PGTO(4), CATEGORIA(5), DIA_DO_MÊS(6)
        todos_registros = aba_gastos_fixos.get_all_records()
        linha_para_atualizar = -1

        for i, registro in enumerate(todos_registros):
            # Compara número, descrição (case-insensitive) e dia
            if (str(registro.get("NÚMERO")) == numero_usuario and
                str(registro.get("DESCRIÇÃO", "")).strip().lower() == descricao.strip().lower() and
                str(registro.get("DIA_DO_MÊS")) == str(dia_vencimento)):
                linha_para_atualizar = i + 2 # +1 porque get_all_records ignora header, +1 porque planilhas são 1-based
                break        
        if linha_para_atualizar != -1:
            # Coluna E é a 5ª coluna (CATEGORIA)
            aba_gastos_fixos.update_cell(linha_para_atualizar, 5, nova_categoria.strip().capitalize())
            logging.info(f"Categoria do gasto fixo '{descricao}' (dia {dia_vencimento}) para {numero_usuario} atualizada para '{nova_categoria}'.")
            return True
        else:
            logging.warning(f"Não foi possível encontrar o gasto fixo '{descricao}' (dia {dia_vencimento}) para {numero_usuario} para atualizar a categoria.")
            return False
    except Exception as e:
        logging.error(f"Erro ao atualizar categoria do gasto fixo '{descricao}' para {numero_usuario}: {e}", exc_info=True)
        return False