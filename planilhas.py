import os
import gspread
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import pytz

load_dotenv()

GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_SHEET_GASTOS_ID = os.getenv("GOOGLE_SHEET_GASTOS_ID")
GOOGLE_SHEETS_KEY_FILE = os.getenv("GOOGLE_SHEETS_KEY_FILE")

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_KEY_FILE, scope)
gs = gspread.authorize(creds)

_cache_abas = {}

def formatar_numero(numero):
    return numero.replace("whatsapp:", "").replace("+", "").replace(" ", "").strip()

def get_aba(sheet_id, nome_aba):
    chave = f"{sheet_id}_{nome_aba}"
    if chave not in _cache_abas:
        planilha = gs.open_by_key(sheet_id)
        aba = planilha.worksheet(nome_aba)
        _cache_abas[chave] = aba
    return _cache_abas[chave]

def get_pagantes():
    return get_aba(GOOGLE_SHEET_ID, "Pagantes")

def get_gratuitos():
    return get_aba(GOOGLE_SHEET_ID, "Gratuitos")

def get_gastos_diarios():
    return get_aba(GOOGLE_SHEET_GASTOS_ID, "Gastos Diários")

def get_limites():
    return get_aba(GOOGLE_SHEET_GASTOS_ID, "Limites")

def get_gastos_fixos():
    return get_aba(GOOGLE_SHEET_GASTOS_ID, "Gastos Fixos")

def get_user_sheet(user_number):
    user_number = formatar_numero(user_number)
    aba_pagantes = get_pagantes()
    aba_gratuitos = get_gratuitos()

    pagantes = [formatar_numero(num) for num in aba_pagantes.col_values(2)]
    gratuitos = [formatar_numero(num) for num in aba_gratuitos.col_values(2)]

    if user_number in pagantes:
        return aba_pagantes
    elif user_number in gratuitos:
        return aba_gratuitos
    else:
        now = datetime.datetime.now(pytz.timezone("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S")
        aba_gratuitos.append_row(["", user_number, "", now, 0, 0])
        return aba_gratuitos


def ler_limites_usuario(numero_usuario):
    """Lê os limites mensais definidos por um usuário na aba 'Limites'.

    Args:
        numero_usuario (str): Número do usuário formatado (sem + ou whatsapp:).

    Returns:
        dict: Dicionário com {categoria: limite_mensal_float} ou {} se não encontrado/erro.
    """
    try:
        aba_limites = get_limites()
        todos_limites = aba_limites.get_all_records() # Assume cabeçalhos na linha 1
        limites_usuario = {}
        for linha in todos_limites:
            # Assume que a coluna 'NÚMERO' contém o número formatado
            if str(linha.get('NÚMERO')) == numero_usuario:
                categoria = linha.get('CATEGORIA')
                limite_str = linha.get('LIMITE_MENSAL') # Pega da coluna E
                if categoria and limite_str:
                    try:
                        # Tenta converter para float, removendo 'R$', '.' e substituindo ',' por '.'
                        limite_float = float(str(limite_str).replace('R$', '').replace('.', '').replace(',', '.').strip())
                        limites_usuario[categoria] = limite_float
                    except ValueError:
                        print(f"[WARN] Valor de limite inválido para {categoria} do usuário {numero_usuario}: {limite_str}")
        return limites_usuario
    except Exception as e:
        print(f"[ERROR] Erro ao ler limites para {numero_usuario}: {e}")
        return {}

def ler_gastos_usuario_periodo(numero_usuario, data_inicio):
    """Lê os gastos de um usuário a partir de uma data de início na aba 'Gastos Diários'.

    Args:
        numero_usuario (str): Número do usuário formatado.
        data_inicio (datetime.datetime): Data e hora de início do período (com timezone).

    Returns:
        list: Lista de dicionários [{coluna: valor}, ...] ou [] se não encontrado/erro.
    """
    try:
        aba_gastos = get_gastos_diarios()
        todos_gastos = aba_gastos.get_all_records()
        gastos_filtrados = []
        fuso_sp = pytz.timezone("America/Sao_Paulo")

        for gasto in todos_gastos:
            # Assume coluna 'NÚMERO' para usuário e 'DATA' para data/hora
            if str(gasto.get('NÚMERO')) == numero_usuario:
                data_gasto_str = gasto.get('DATA')
                valor_str = gasto.get('VALOR') # Assume coluna 'VALOR'
                categoria = gasto.get('CATEGORIA') # Assume coluna 'CATEGORIA'
                
                if data_gasto_str and valor_str and categoria:
                    try:
                        # Tenta parsear a data/hora - ajuste o formato se necessário
                        # Formato comum: 'DD/MM/YYYY HH:MM:SS'
                        data_gasto = fuso_sp.localize(datetime.datetime.strptime(data_gasto_str, '%d/%m/%Y %H:%M:%S'))
                        
                        # Compara com a data de início (considerando o mesmo mês/ano)
                        if data_gasto >= data_inicio and data_gasto.year == data_inicio.year and data_gasto.month == data_inicio.month:
                            try:
                                # Tenta converter valor para float
                                valor_float = float(str(valor_str).replace('R$', '').replace('.', '').replace(',', '.').strip())
                                gastos_filtrados.append({
                                    "Categoria": categoria,
                                    "Valor": valor_float,
                                    "Data": data_gasto_str, # Mantém string original se precisar
                                    # Adicione outras colunas se necessário
                                    "Descrição": gasto.get('DESCRIÇÃO'),
                                    "Forma Pagamento": gasto.get('FORMA_PAGAMENTO')
                                })
                            except ValueError:
                                print(f"[WARN] Valor de gasto inválido para {categoria} do usuário {numero_usuario}: {valor_str}")
                    except ValueError as ve:
                        print(f"[WARN] Formato de data inválido para gasto do usuário {numero_usuario}: {data_gasto_str} - {ve}")
                    except Exception as e_inner:
                         print(f"[ERROR] Erro ao processar linha de gasto para {numero_usuario}: {gasto} - {e_inner}")
                        
        return gastos_filtrados
    except Exception as e:
        print(f"[ERROR] Erro ao ler gastos para {numero_usuario} desde {data_inicio}: {e}")
        return []

def salvar_gasto_fixo(numero_usuario, descricao, valor, dia, categoria, lembrete_ativo=False):
    try:
        aba_gastos_fixos = get_gastos_fixos()
        lembrete = "SIM" if lembrete_ativo else "NÃO"
        nova_linha = [numero_usuario, descricao, valor, "", categoria, dia, lembrete]
        aba_gastos_fixos.append_row(nova_linha)
        return {"status": "ok"}
    except Exception as e:
        print(f"[ERRO] ao salvar gasto fixo: {e}")
        return {"status": "erro", "detalhe": str(e)}
    