# -*- coding: utf-8 -*-
import os
import hashlib
from datetime import datetime
import pytz
from dotenv import load_dotenv

from planilhas import get_gastos_diarios

load_dotenv()

# === CATEGORIAS AUTOMÁTICAS ===
# Expanded dictionary with more keywords and variations
CATEGORIAS_AUTOMATICAS = {
    # Alimentação
    "almoço": "Alimentação", "jantar": "Alimentação", "café": "Alimentação", "padaria": "Alimentação",
    "mercado": "Alimentação", "supermercado": "Alimentação", "feira": "Alimentação", "restaurante": "Alimentação",
    "lanche": "Alimentação", "comida": "Alimentação", "bebida": "Alimentação",
    # Saúde
    "farmácia": "Saúde", "remedio": "Saúde", "drogaria": "Saúde", "plano de saúde": "Saúde",
    "bradesco saúde": "Saúde", "consulta médica": "Saúde", "exame": "Saúde", "dentista": "Saúde",
    "terapia": "Saúde", "psicólogo": "Saúde", "hospital": "Saúde",
    # Transporte
    "combustível": "Transporte", "gasolina": "Transporte", "etanol": "Transporte", "diesel": "Transporte",
    "uber": "Transporte", "99": "Transporte", "táxi": "Transporte", "passagem": "Transporte", # Passagem de onibus/metro
    "manutenção carro": "Transporte", "pedágio": "Transporte", "estacionamento": "Transporte",
    # Moradia
    "água": "Moradia", "luz": "Moradia", "energia": "Moradia", "equatorial": "Moradia", "saneago": "Moradia",
    "internet": "Moradia", "aluguel": "Moradia", "condomínio": "Moradia", "condominio": "Moradia",
    "gás": "Moradia", "iptu": "Moradia", # IPTU é mais moradia que imposto geral
    # Educação
    "escola": "Educação", "faculdade": "Educação", "curso": "Educação", "livro": "Educação", # Livro pode ser lazer também, mas priorizar educação
    "material escolar": "Educação", "mensalidade": "Educação",
    # Lazer & Bem-estar
    "shopping": "Lazer", "cinema": "Lazer", "netflix": "Lazer", "spotify": "Lazer", "streaming": "Lazer",
    "show": "Lazer", "bar": "Lazer", "viagem": "Lazer", "passeio": "Lazer", "hotel": "Lazer",
    "academia": "Lazer/Bem-estar", "clube": "Lazer/Bem-estar", "beleza": "Lazer/Bem-estar", "salão": "Lazer/Bem-estar",
    "jogo": "Lazer",
    # Presentes & Doações
    "presente": "Presentes/Doações", "doação": "Presentes/Doações", "caridade": "Presentes/Doações",
    # Serviços & Domésticos
    "sra": "Serviços/Domésticos", "diarista": "Serviços/Domésticos", "funcionária": "Serviços/Domésticos", "faxina": "Serviços/Domésticos",
    "lavanderia": "Serviços/Domésticos",
    # Impostos & Taxas (Gerais)
    "imposto": "Impostos/Taxas", "taxa": "Impostos/Taxas", "ipva": "Impostos/Taxas", # IPVA é mais taxa que transporte direto
    "irpf": "Impostos/Taxas",
    # Outros
    "seguro": "Seguros",
    "telefone": "Utilidades", "celular": "Utilidades",
    "vestuário": "Vestuário", "roupa": "Vestuário", "sapato": "Vestuário",
    "pet": "Pet", "veterinário": "Pet", "ração": "Pet",
    "investimento": "Investimentos", # Para diferenciar de gasto
    "transferência": "Transferências", # Para diferenciar de gasto
    "empréstimo": "Financeiro", # Pagamento de empréstimo
    "fatura": "Financeiro", # Pagamento de fatura (pode ser desmembrado, mas aqui como fallback)
    "cartão de crédito": "Financeiro" # Pagamento da fatura
}

# Palavras-chave ambíguas que requerem confirmação do usuário
CATEGORIAS_AMBIGUAS = {
    "ifood": ["Alimentação", "Lazer"],
    # Adicionar outras se necessário, por exemplo:
    # "livro": ["Educação", "Lazer"],
}

# === CATEGORIZAÇÃO INTELIGENTE ===
def categorizar(descricao):
    # Normalização: minúsculas, remover acentos comuns
    descricao_norm = descricao.lower()
    # Mapeamento simples de acentos (pode ser expandido)
    accent_map = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'â': 'a', 'ê': 'e', 'ô': 'o', 'ç': 'c', '~': '', '`': '', '^': ''}
    for char, replacement in accent_map.items():
        descricao_norm = descricao_norm.replace(char, replacement)
    
    # 1. Verificar palavras-chave ambíguas
    for chave_ambigua, opcoes in CATEGORIAS_AMBIGUAS.items():
        if chave_ambigua in descricao_norm:
            # Retorna um marcador especial indicando ambiguidade e as opções
            return f"AMBIGUO:{chave_ambigua.upper()}:{'/'.join(opcoes)}" 

    # 2. Verificar palavras-chave diretas (mais longas primeiro para evitar submatches)
    # Ordena as chaves por comprimento descendente
    chaves_ordenadas = sorted(CATEGORIAS_AUTOMATICAS.keys(), key=len, reverse=True)
    
    for chave in chaves_ordenadas:
        # Usar busca simples por substring por enquanto
        if chave in descricao_norm:
            return CATEGORIAS_AUTOMATICAS[chave]
            
    # 3. Se nenhuma chave encontrada, retornar "A definir"
    return "A definir" # Mantido 'A definir' em vez de None para consistência

# === GERA ID ÚNICO ===
def gerar_id_unico(numero_usuario, descricao, valor, data_gasto):
    base = f"{numero_usuario}-{descricao}-{valor}-{data_gasto}"
    return hashlib.md5(base.encode()).hexdigest()

# === REGISTRO DE GASTO ===
# Esta função registra gastos DIÁRIOS, não fixos. Precisa ser adaptada ou 
# a lógica de categorização precisa ser usada também no registrar_gastos_fixos.py
def registrar_gasto(nome_usuario, numero_usuario, descricao, valor, forma_pagamento, data_gasto=None, categoria_manual=None):
    try:
        aba = get_gastos_diarios()

        fuso = pytz.timezone("America/Sao_Paulo")
        agora = datetime.now(fuso)
        data_registro = agora.strftime("%d/%m/%Y %H:%M:%S")
        data_gasto = data_gasto or agora.strftime("%d/%m/%Y")

        # Usa a nova função categorizar
        categoria_auto = categorizar(descricao)
        
        # Se a categoria for ambígua, por enquanto, marca como 'A definir' e retorna marcador
        # A lógica de perguntar ao usuário ficará no main.py
        if categoria_auto.startswith("AMBIGUO:"):
            categoria_final = "A definir"
            status_retorno = categoria_auto # Retorna o marcador de ambiguidade
        else:
            categoria_final = categoria_manual or categoria_auto
            status_retorno = "ok" # Ou "ignorado" se duplicado
            
        id_unico = gerar_id_unico(numero_usuario, descricao, valor, data_gasto)

        # Verifica duplicidade (simplificado, pode precisar de ajuste)
        registros = [linha[8] for linha in aba.get_all_values()[1:] if len(linha) >= 9]
        if id_unico in registros:
            # Mesmo se duplicado, retorna a categoria encontrada/ambígua para informação
            return {"status": "ignorado", "mensagem": "Esse gasto já foi registrado.", "categoria": categoria_final, "status_categorizacao": categoria_auto}

        nova_linha = [
            nome_usuario if nome_usuario else "Usuário",
            numero_usuario,
            descricao,
            categoria_final, # Salva 'A definir' se for ambíguo por enquanto
            f"R${valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            forma_pagamento,
            data_gasto,
            data_registro,
            id_unico
        ]
        print("[DEBUG] Inserindo na planilha (Gastos Diários):", nova_linha)

        try:
            aba.append_row(nova_linha, value_input_option="USER_ENTERED")
            print("[SUCESSO APPEND_ROW] Dados enviados:", nova_linha)
        except Exception as e:
            print("[ERRO GRAVE APPEND_ROW]:", e)
            # Retorna o status da categorização mesmo em caso de erro de escrita
            return {"status": "erro", "mensagem": str(e), "status_categorizacao": categoria_auto}

        # Retorna o status da categorização junto com o status ok
        return {"status": status_retorno, "categoria": categoria_final, "status_categorizacao": categoria_auto}

    except Exception as e:
        print(f"[ERRO ao registrar gasto] {e}")
        # Retorna um status de erro genérico se a exceção ocorrer antes da categorização
        return {"status": "erro", "mensagem": str(e), "status_categorizacao": "ERRO_PRE_CATEGORIZACAO"}

# === ALTERAR CATEGORIA ===
def atualizar_categoria(numero_usuario, descricao, data_gasto, nova_categoria):
    try:
        aba = get_gastos_diarios()
        registros = aba.get_all_values()

        for i, linha in enumerate(registros[1:], start=2):  # pula cabeçalho
            # Adiciona verificação de comprimento da linha para evitar IndexError
            if len(linha) < 7: continue 
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
    try:
        aba = get_gastos_diarios()
        registros = aba.get_all_values()

        for i, linha in enumerate(registros[1:], start=2):  
            # Adiciona verificação de comprimento da linha para evitar IndexError
            if len(linha) < 7: continue
            if (linha[1].strip() == numero_usuario and
                linha[2].strip().lower() == descricao.strip().lower() and
                linha[6].strip() == data_gasto):
                # Formata o valor corretamente para a planilha
                valor_formatado = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                aba.update_cell(i, 3, descricao)       # Coluna C: Descrição
                aba.update_cell(i, 4, categoria)       # Coluna D: Categoria
                aba.update_cell(i, 5, valor_formatado) # Coluna E: Valor
                aba.update_cell(i, 6, forma_pagamento) # Coluna F: Forma Pgto
                # Assumindo que data_gasto (coluna G) não precisa ser atualizada aqui
                return True

        print("[CORRIGIR GASTO] Nenhum gasto correspondente encontrado.")
        return False
    except Exception as e:
        print(f"[ERRO ao corrigir gasto] {e}")
        return False

import re

def parsear_gastos_em_lote(texto):
    linhas = texto.strip().split('\n')
    gastos = []
    erros = []

    # Regex para capturar: Descrição - Valor - Forma - Categoria (opcional)
    # Permite R$, vírgulas e pontos no valor
    # Permite hífens ou travessões como separadores
    padrao = re.compile(r'^(.*?)*[-–]*(R??[]*[]*[\d.,]+)*[-–]*([^–-]+?)*(?:[-–]*(.*?))?$', re.IGNORECASE)

    for linha in linhas:
        match = padrao.match(linha.strip())
        if not match:
            erros.append(f"Linha inválida: '{linha}'. Formato esperado: Descrição – Valor – Forma – Categoria (opcional)")
            continue

        descricao = match.group(1).strip()
        valor_str = match.group(2).replace("R$", "").replace(".", "").replace(",", ".").strip() # Normaliza para ponto decimal
        forma_pagamento = match.group(3).strip().capitalize()
        categoria = match.group(4).strip().capitalize() if match.group(4) else None

        try:
            valor = float(valor_str)
            if valor < 0: raise ValueError("Valor não pode ser negativo")
        except ValueError:
            erros.append(f"Linha inválida: '{linha}'. Valor '{match.group(2)}' não é numérico válido ou é negativo.")
            continue

        gastos.append({
            "descricao": descricao,
            "valor": valor,
            "forma_pagamento": forma_pagamento,
            "categoria": categoria # Pode ser None se não informado
        })

    return gastos, erros