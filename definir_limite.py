import random
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv
from enviar_whatsapp import enviar_whatsapp
from planilhas import get_gastos_diarios, get_limites
import mensagens
import pytz
from estado_usuario import carregar_estado, salvar_estado
import logging # Adicionado para logar erros

load_dotenv()

fuso = pytz.timezone("America/Sao_Paulo")

def buscar_limites_do_usuario(numero_usuario):
    try:
        aba = get_limites()
        linhas = aba.get_all_records()
        limites = {}

        for linha in linhas:
            # Garante que a chave "NÚMERO" exista e seja tratada como string
            num_planilha = str(linha.get("NÚMERO", "")).strip()
            if num_planilha != numero_usuario:
                continue
            
            # Garante que a chave "CATEGORIA" exista e seja tratada como string
            categoria = str(linha.get("CATEGORIA", "")).strip()
            if not categoria: # Pula se categoria for vazia
                continue
                
            limite_mes = linha.get("LIMITE_MENSAL", "")
            if isinstance(limite_mes, str):
                limite_mes = limite_mes.replace("R$", "").replace(".", "").replace(",", ".").strip()
            try:
                limites[categoria] = float(limite_mes)
            except (ValueError, TypeError):
                logging.warning(f"Valor de limite inválido para {categoria} do usuário {numero_usuario}: {limite_mes}")
                continue

        return limites
    except Exception as e:
        logging.error(f"Erro ao buscar limites para {numero_usuario}: {e}")
        return {}

def verificar_alertas():
    try: # Adicionado try/except geral
        aba = get_gastos_diarios()
        dados = aba.get_all_records()
        hoje = datetime.now(fuso).date()

        usuarios_gastos = defaultdict(lambda: defaultdict(float))

        for linha in dados:
            numero = str(linha.get("NÚMERO", "")).strip()
            if not numero: continue
            
            try:
                data_gasto_str = linha.get("DATA DO GASTO", "")
                if not data_gasto_str: continue
                data_gasto = datetime.strptime(data_gasto_str, "%d/%m/%Y").date()
                if data_gasto != hoje:
                    continue
            except (ValueError, TypeError):
                logging.warning(f"Data inválida na linha de gasto: {linha}")
                continue

            valor_str = str(linha.get("VALOR (R$)", "")).replace("R$", "").replace(".", "").replace(",", ".").strip()
            try:
                valor = float(valor_str)
            except (ValueError, TypeError):
                logging.warning(f"Valor inválido na linha de gasto: {linha}")
                valor = 0.0

            categoria = str(linha.get("CATEGORIA", "")) or "A DEFINIR"
            usuarios_gastos[numero][categoria] += valor

        for numero, categorias in usuarios_gastos.items():
            limites_user = buscar_limites_do_usuario(numero)
            if not limites_user: continue # Pula se não encontrou limites
            
            for cat, total in categorias.items():
                limite_cat = limites_user.get(cat)
                if not limite_cat or limite_cat <= 0: # Pula se não há limite ou limite é zero/negativo
                    continue

                percentual = (total / limite_cat) * 100
                faixa = None
                if 45 < percentual <= 55:
                    faixa = "50"
                elif 65 < percentual <= 75:
                    faixa = "70"
                elif 85 < percentual <= 95:
                    faixa = "90"
                elif 95 < percentual <= 105:
                    faixa = "100"
                elif percentual > 105:
                    faixa = ">100"

                if faixa:
                    mensagem = mensagens.alerta_limite_excedido(cat, total, limite_cat, faixa)

                    estado_alertas = carregar_estado(numero)
                    alertas_enviados = estado_alertas.get("alertas_enviados", [])
                    chave_alerta = f"{cat}_{faixa}_{hoje.strftime('%Y-%m-%d')}" # Chave única por categoria, faixa e dia

                    if chave_alerta not in alertas_enviados:
                        if enviar_whatsapp(numero, mensagem): # Verifica se envio foi bem sucedido
                            alertas_enviados.append(chave_alerta)
                            estado_alertas["alertas_enviados"] = alertas_enviados
                            salvar_estado(numero, estado_alertas)
                            logging.info(f"Alerta {faixa}% para {cat} enviado para {numero}.")
                        else:
                            logging.error(f"Falha ao enviar alerta {faixa}% para {cat} para {numero}.")
                    else:
                        logging.info(f"Alerta {faixa}% para {cat} já enviado hoje para {numero}.")
    except Exception as e:
        logging.error(f"Erro geral em verificar_alertas: {e}")

def salvar_limite_usuario(numero, categoria, valor, tipo="mensal"):
    """Salva ou atualiza um limite para o usuário. Retorna True em sucesso, False em falha."""
    try:
        aba = get_limites()
        # Busca todas as linhas para encontrar a correspondente (mais robusto que get_all_records para busca)
        linhas = aba.get_all_values() # Pega como lista de listas
        linha_existente_idx = None

        # Itera pelas linhas (índice baseado em 1 para gspread)
        for i, linha in enumerate(linhas):
            # Verifica se a linha tem colunas suficientes e compara
            if len(linha) >= 2 and str(linha[0]).strip() == numero and str(linha[1]).strip().lower() == categoria.lower():
                linha_existente_idx = i + 1 # Índice da linha na planilha (base 1)
                break

        coluna_idx = {"diario": 3, "semanal": 4, "mensal": 5}.get(tipo.lower(), 5)

        if linha_existente_idx:
            logging.info(f"Atualizando limite {tipo} para {categoria} do usuário {numero} na linha {linha_existente_idx}.")
            aba.update_cell(linha_existente_idx, coluna_idx, valor)
        else:
            logging.info(f"Adicionando novo limite {tipo} para {categoria} do usuário {numero}.")
            nova_linha = ["" for _ in range(aba.col_count)] # Cria linha vazia com tamanho correto
            nova_linha[0] = numero # Coluna 1: NÚMERO
            nova_linha[1] = categoria # Coluna 2: CATEGORIA
            nova_linha[coluna_idx - 1] = valor # Coluna do limite (base 0 para lista)
            aba.append_row(nova_linha)
        return True # Retorna sucesso
    except Exception as e:
        logging.error(f"Erro ao salvar limite para {numero}, categoria {categoria}: {e}")
        return False # Retorna falha

if __name__ == "__main__":
    # Exemplo de teste (requer configuração .env e credenciais)
    # print(buscar_limites_do_usuario("5511999999999"))
    # if salvar_limite_usuario("5511999999999", "Teste", 100.50):
    #     print("Limite de teste salvo com sucesso.")
    # else:
    #     print("Falha ao salvar limite de teste.")
    verificar_alertas()