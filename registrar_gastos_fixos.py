# -*- coding: utf-8 -*-
"""
Função para registrar gastos fixos mensais na planilha.
"""
import logging
import re
from planilhas import get_gastos_fixos, formatar_numero

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def salvar_gasto_fixo(numero_usuario, descricao, valor, dia_vencimento):
    """Salva um gasto fixo na aba 'Gastos Fixos'.

    Args:
        numero_usuario (str): Número do usuário (já formatado).
        descricao (str): Descrição do gasto.
        valor (float): Valor do gasto.
        dia_vencimento (int): Dia do mês para o vencimento.

    Returns:
        bool: True se salvou com sucesso, False caso contrário.
    """
    try:
        aba_gastos_fixos = get_gastos_fixos()
        # Verifica se já existe um gasto fixo com a mesma descrição para o usuário
        # (Pode ser útil para evitar duplicatas ou permitir atualização - por ora, apenas adiciona)
        # TODO: Considerar lógica de atualização ou verificação de duplicatas no futuro.
        
        # Formata os dados para a linha da planilha
        # Colunas esperadas: NÚMERO, DESCRIÇÃO, VALOR, DIA_DO_MÊS (conforme enviar_lembretes.py)
        linha = [
            numero_usuario,
            descricao.strip().capitalize(),
            f'{valor:.2f}'.replace('.', ','), # Formata como string BRL para a planilha
            str(dia_vencimento) # Dia como string
        ]
        aba_gastos_fixos.append_row(linha)
        logging.info(f"Gasto fixo '{descricao}' para {numero_usuario} salvo com sucesso.")
        return True
    except Exception as e:
        logging.error(f"Erro ao salvar gasto fixo '{descricao}' para {numero_usuario}: {e}", exc_info=True)
        return False

# Exemplo de uso (para teste local, se necessário)
if __name__ == '__main__':
    # Mock da função get_gastos_fixos para teste
    class MockAba:
        def append_row(self, data):
            print(f"[MOCK] Appending row: {data}")
            # Simula erro ocasional
            # if data[1] == "Erro Simulado": raise Exception("Erro simulado no append")
            return {"updates": {"updatedRange": "Gastos Fixos!A10:D10"}}

    def mock_get_gastos_fixos():
        return MockAba()

    # Substitui a função real pela mock
    get_gastos_fixos = mock_get_gastos_fixos

    # Testes
    print(salvar_gasto_fixo("5511999998888", "Aluguel", 1500.0, 10))
    print(salvar_gasto_fixo("5511999998888", "Condomínio", 500.50, 5))
    print(salvar_gasto_fixo("5511999998888", "Internet", 99.90, 20))
    # print(salvar_gasto_fixo("5511999998888", "Erro Simulado", 10.0, 1))