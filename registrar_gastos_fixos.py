"""
Função para registrar gastos fixos mensais na planilha.
"""
import logging
import re
from planilhas import get_gastos_fixos, formatar_numero

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

CATEGORIAS_VALIDAS = [
    'Moradia', 'Educação', 'Cartão', 'Saúde', 'Lazer', 'Transporte',
    'Alimentação', 'Utilidades', 'Investimentos', 'Outros'
]

def salvar_gasto_fixo(numero_usuario, descricao, valor, dia_vencimento, categoria):
    try:
        # Validação ROBUSTA
        try:
            valor_float = float(valor)
            if valor_float < 0: raise ValueError("Valor negativo")
        except ValueError:
            logging.error(f"Valor inválido '{valor}' para gasto fixo '{descricao}' do usuário {numero_usuario}.")
            return {"status": "erro", "mensagem": f"O valor '{valor}' não é válido. Use o formato 1234.56"}

        try:
            dia_int = int(dia_vencimento)
            if not 1 <= dia_int <= 31: raise ValueError("Dia inválido")
        except ValueError:
            logging.error(f"Dia inválido '{dia_vencimento}' para gasto fixo '{descricao}' do usuário {numero_usuario}.")
            return {"status": "erro", "mensagem": f"O dia '{dia_vencimento}' não é válido. Deve ser um número entre 1 e 31."}

        if categoria not in CATEGORIAS_VALIDAS:
            logging.error(f"Categoria inválida '{categoria}' para gasto fixo '{descricao}' do usuário {numero_usuario}.")
            return {"status": "erro", "mensagem": f"A categoria '{categoria}' não é válida. Escolha uma categoria da lista."}

        aba_gastos_fixos = get_gastos_fixos()
        # Colunas esperadas: NÚMERO, DESCRIÇÃO, VALOR, FORMA_PGTO, CATEGORIA, DIA_DO_MÊS
        linha = [
            str(numero_usuario), # Garante que seja string
            str(descricao).strip().capitalize(),
            f'{valor_float:.2f}'.replace('.', ','), # Usa valor_float validado
            "", # FORMA_PGTO (deixar em branco por enquanto)
            str(categoria).strip().capitalize(),
            str(dia_int) # Usa dia_int validado
        ]
        aba_gastos_fixos.append_row(linha)
        logging.info(f"Gasto fixo '{str(descricao)}' para {numero_usuario} salvo com sucesso.")
        return {"status": "ok"}
    except Exception as e:
        logging.error(f"Erro ao salvar gasto fixo '{str(descricao)}' para {numero_usuario}: {e}", exc_info=True)
        # Mensagem de erro mais amigável
        return {
            "status": "erro", 
            "mensagem": f"Ops! Algo deu errado ao tentar salvar o gasto '{str(descricao)}'. Verifique se todos os dados estão corretos e tente novamente. Detalhe técnico: {str(e)}"
        }

def atualizar_categoria_gasto_fixo(numero_usuario, descricao_gasto, dia_gasto, nova_categoria):
    try:
        aba_gastos_fixos = get_gastos_fixos()
        
        todos_os_valores = aba_gastos_fixos.get_all_values()
        if not todos_os_valores:
            logging.warning(f"A planilha 'Gastos Fixos' está vazia. Não é possível atualizar categoria para {numero_usuario}.")
            return False
            
        headers = todos_os_valores[0]
        try:
            idx_numero = headers.index('NÚMERO') 
            idx_descricao = headers.index('DESCRIÇÃO') 
            idx_categoria = headers.index('CATEGORIA') 
            idx_dia = headers.index('DIA_DO_MÊS') 
        except ValueError:
            logging.warning("Headers não encontradas como esperado na planilha 'Gastos Fixos'. Usando índices fixos.")
            idx_numero = 0
            idx_descricao = 1
            idx_categoria = 4
            idx_dia = 5

        linha_para_atualizar = -1
        for i, linha_valores in enumerate(todos_os_valores[1:], start=2): 
            if len(linha_valores) > max(idx_numero, idx_descricao, idx_dia, idx_categoria):
                num_planilha = str(linha_valores[idx_numero]).strip()
                desc_planilha = str(linha_valores[idx_descricao]).strip().lower()
                dia_planilha_str = str(linha_valores[idx_dia]).strip()

                if (
                    num_planilha == str(numero_usuario) and
                    desc_planilha == str(descricao_gasto).strip().lower() and
                    dia_planilha_str == str(dia_gasto) 
                ):
                    linha_para_atualizar = i
                    break
            
        if linha_para_atualizar != -1:
            aba_gastos_fixos.update_cell(linha_para_atualizar, idx_categoria + 1, str(nova_categoria).strip().capitalize()) 
            logging.info(f"Categoria do gasto fixo '{str(descricao_gasto)}' (dia {str(dia_gasto)}) para {str(numero_usuario)} atualizada para '{str(nova_categoria)}'.")
            return True
        else:
            logging.warning(f"Gasto fixo '{str(descricao_gasto)}' (dia {str(dia_gasto)}) para {str(numero_usuario)} não encontrado para atualização de categoria.")
            return False

    except Exception as e:
        logging.error(f"Erro ao atualizar categoria do gasto fixo '{str(descricao_gasto)}' para {str(numero_usuario)}: {e}", exc_info=True)
        return False

# Alias para compatibilidade com import antigo, se necessário
salvar_gastos_fixos = salvar_gasto_fixo
