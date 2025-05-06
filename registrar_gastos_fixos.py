"""
Função para registrar gastos fixos mensais na planilha.
"""
import logging
import re
from planilhas import get_gastos_fixos, formatar_numero

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def salvar_gasto_fixo(numero_usuario, descricao, valor, categoria, dia_vencimento):
    """Salva um gasto fixo na aba 'Gastos Fixos'.

    Args:
        numero_usuario (str): Número do usuário (já formatado).
        descricao (str): Descrição do gasto.
        valor (float): Valor do gasto.
        categoria (str): Categoria do gasto.
        dia_vencimento (int): Dia do mês para o vencimento.

    Returns:
        dict: {"status": "ok"} ou {"status": "erro", "mensagem": ...}
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
        return {"status": "ok"}
    except Exception as e:
        logging.error(f"Erro ao salvar gasto fixo '{descricao}' para {numero_usuario}: {e}", exc_info=True)
        return {"status": "erro", "mensagem": str(e)}

def atualizar_categoria_gasto_fixo(numero_usuario, descricao_gasto, dia_gasto, nova_categoria):
    """Atualiza a categoria de um gasto fixo específico na planilha.

    Args:
        numero_usuario (str): Número do usuário (já formatado).
        descricao_gasto (str): Descrição original do gasto.
        dia_gasto (int or str): Dia do vencimento original do gasto.
        nova_categoria (str): Nova categoria a ser definida.

    Returns:
        bool: True se a categoria foi atualizada com sucesso, False caso contrário.
    """
    try:
        aba_gastos_fixos = get_gastos_fixos()
        todos_os_gastos = aba_gastos_fixos.get_all_records() # Obtém como lista de dicionários

        linha_para_atualizar = -1
        # As colunas na planilha são: NÚMERO, DESCRIÇÃO, VALOR, FORMA_PGTO, CATEGORIA, DIA_DO_MÊS
        # Os headers no get_all_records() podem ser diferentes se a primeira linha não for um header padrão.
        # Vamos assumir que os headers são os esperados ou iterar pelas linhas e checar pelos índices.
        
        # Tentativa com get_all_values para ter controle sobre os índices
        todos_os_valores = aba_gastos_fixos.get_all_values()
        headers = todos_os_valores[0] if todos_os_valores else []
        # Encontrar os índices corretos pelas headers, se possível
        try:
            idx_numero = headers.index('NÚMERO') # Coluna A
            idx_descricao = headers.index('DESCRIÇÃO') # Coluna B
            idx_categoria = headers.index('CATEGORIA') # Coluna E
            idx_dia = headers.index('DIA_DO_MÊS') # Coluna F
        except ValueError:
            # Fallback para índices fixos se headers não corresponderem
            logging.warning("Headers não encontradas como esperado na planilha 'Gastos Fixos'. Usando índices fixos.")
            idx_numero = 0
            idx_descricao = 1
            idx_categoria = 4
            idx_dia = 5

        for i, linha_valores in enumerate(todos_os_valores[1:], start=2): # start=2 para número da linha na planilha
            if len(linha_valores) > max(idx_numero, idx_descricao, idx_dia):
                num_planilha = linha_valores[idx_numero].strip()
                desc_planilha = linha_valores[idx_descricao].strip().lower()
                dia_planilha_str = str(linha_valores[idx_dia]).strip()

                if (
                    num_planilha == numero_usuario and
                    desc_planilha == descricao_gasto.strip().lower() and
                    dia_planilha_str == str(dia_gasto) 
                ):
                    linha_para_atualizar = i
                    break
            
        if linha_para_atualizar != -1:
            aba_gastos_fixos.update_cell(linha_para_atualizar, idx_categoria + 1, nova_categoria.strip().capitalize()) # +1 porque gspread é 1-based
            logging.info(f"Categoria do gasto fixo '{descricao_gasto}' (dia {dia_gasto}) para {numero_usuario} atualizada para '{nova_categoria}'.")
            return True
        else:
            logging.warning(f"Gasto fixo '{descricao_gasto}' (dia {dia_gasto}) para {numero_usuario} não encontrado para atualização de categoria.")
            return False

    except Exception as e:
        logging.error(f"Erro ao atualizar categoria do gasto fixo '{descricao_gasto}' para {numero_usuario}: {e}", exc_info=True)
        return False

# Alias para compatibilidade com import antigo, se necessário
salvar_gastos_fixos = salvar_gasto_fixo

# Exemplo de uso (para teste local, se necessário)
if __name__ == '__main__':
    # Mock da função get_gastos_fixos para teste
    class MockAba:
        def __init__(self):
            self.data = [
                ['NÚMERO', 'DESCRIÇÃO', 'VALOR', 'FORMA_PGTO', 'CATEGORIA', 'DIA_DO_MÊS'],
                ['5511999998888', 'Aluguel', '1500,00', '', 'Moradia', '10'],
                ['5511999998888', 'Condomínio', '500,50', '', 'Moradia', '5'],
                ['5511999998888', 'Internet', '99,90', '', 'Utilidades', '20'],
                ['5511999998888', 'Escola Teste', '100,00', '', 'A definir', '15']
            ]

        def append_row(self, data_row):
            print(f"[MOCK] Appending row: {data_row}")
            self.data.append(data_row)
            return {"updates": {"updatedRange": "Gastos Fixos!A10:D10"}}
        
        def get_all_values(self):
            print("[MOCK] get_all_values() chamado")
            return self.data

        def update_cell(self, row, col, value):
            print(f"[MOCK] Updating cell ({row}, {col}) to: {value}")
            if row > 0 and row <= len(self.data) and col > 0 and col <= len(self.data[0]):
                self.data[row-1][col-1] = value
                return True
            return False

    _original_get_gastos_fixos = get_gastos_fixos 
    def mock_get_gastos_fixos():
        return MockAba()

    get_gastos_fixos = mock_get_gastos_fixos

    print("--- Testando salvar_gasto_fixo ---")
    print(salvar_gasto_fixo("5511999998888", "Luz", 150.00, "Moradia", 25))
    print(salvar_gasto_fixo("5511999998888", "Academia", 120.00, "Saúde", 1))
    
    print("\n--- Testando atualizar_categoria_gasto_fixo ---")
    print("Antes da atualização:", mock_get_gastos_fixos().data)
    print(f"Atualizando 'Escola Teste' dia 15 para 'Educação': {atualizar_categoria_gasto_fixo('5511999998888', 'Escola Teste', 15, 'Educação')}")
    print(f"Tentando atualizar inexistente: {atualizar_categoria_gasto_fixo('5511999998888', 'Gasto X', 10, 'Lazer')}")
    print("Depois da atualização:", mock_get_gastos_fixos().data)

    # Restaurar a função original se necessário em um contexto maior
    get_gastos_fixos = _original_get_gastos_fixos
