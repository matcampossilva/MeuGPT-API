# -*- coding: utf-8 -*-
"""
Função para registrar e atualizar gastos fixos mensais na planilha.
"""
import logging
import re
from planilhas import get_gastos_fixos, formatar_numero

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
            f'{valor:.2f}'.replace('.', ','), # Formata como string BRL para a planilha
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
            if (str(registro.get('NÚMERO')) == numero_usuario and 
                str(registro.get('DESCRIÇÃO', '')).strip().lower() == descricao.strip().lower() and
                str(registro.get('DIA_DO_MÊS')) == str(dia_vencimento)):
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

# Exemplo de uso (para teste local, se necessário)
if __name__ == '__main__':
    # Mock das funções para teste
    class MockAba:
        def __init__(self):
            self.dados = [
                {'NÚMERO': '5511999998888', 'DESCRIÇÃO': 'Aluguel', 'VALOR': '1500,00', 'FORMA_PGTO': '', 'CATEGORIA': 'Moradia', 'DIA_DO_MÊS': '10'},
                {'NÚMERO': '5511999998888', 'DESCRIÇÃO': 'Condomínio', 'VALOR': '500,50', 'FORMA_PGTO': '', 'CATEGORIA': 'A definir', 'DIA_DO_MÊS': '5'},
                {'NÚMERO': '5511999998888', 'DESCRIÇÃO': 'Internet', 'VALOR': '99,90', 'FORMA_PGTO': '', 'CATEGORIA': 'Utilidades', 'DIA_DO_MÊS': '20'}
            ]
        def append_row(self, data):
            print(f"[MOCK] Appending row: {data}")
            return {"updates": {"updatedRange": "Gastos Fixos!A10:F10"}}
        def get_all_records(self):
            print("[MOCK] Getting all records")
            return self.dados
        def update_cell(self, row, col, value):
            print(f"[MOCK] Updating cell ({row}, {col}) to '{value}'")
            # Simula atualização nos dados mockados
            if 1 < row <= len(self.dados) + 1 and col == 5:
                 self.dados[row-2]['CATEGORIA'] = value
                 print(f"[MOCK] Dados atualizados: {self.dados[row-2]}")
            else:
                 print(f"[MOCK] Erro: Célula ({row}, {col}) fora dos limites ou coluna inválida.")
            return {"updates": {"updatedCells": 1}}

    mock_aba_instance = MockAba()
    def mock_get_gastos_fixos():
        return mock_aba_instance

    # Substitui a função real pela mock
    get_gastos_fixos = mock_get_gastos_fixos

    # Testes salvar
    print(salvar_gasto_fixo("5511999998888", "Academia", 150.0, 15, "Lazer/Bem-estar"))
    
    # Testes atualizar
    print("--- Testando Atualização ---")
    print(f"Atualizando Condomínio (dia 5) para Moradia: {atualizar_categoria_gasto_fixo('5511999998888', 'Condomínio', 5, 'Moradia')}")
    print(f"Tentando atualizar item inexistente: {atualizar_categoria_gasto_fixo('5511999998888', 'Netflix', 10, 'Lazer')}")
    print(f"Tentando atualizar com dia errado: {atualizar_categoria_gasto_fixo('5511999998888', 'Aluguel', 15, 'Moradia')}")
    print(f"Tentando atualizar com descrição errada (case): {atualizar_categoria_gasto_fixo('5511999998888', 'condomínio', 5, 'Moradia')}") # Deve funcionar

# Alias para compatibilidade com import antigo (se necessário, mas idealmente não usar)
# salvar_gastos_fixos = salvar_gasto_fixo