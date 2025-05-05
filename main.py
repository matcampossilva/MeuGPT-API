# -*- coding: utf-8 -*-
import os
import openai
import requests
from fastapi import FastAPI, Request, HTTPException 
from twilio.rest import Client
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pytz
import datetime
import re
import json 
import logging 
import mensagens # Importa o módulo mensagens
# Importa funções de gastos.py (categorizar foi atualizada)
from gastos import registrar_gasto, categorizar, corrigir_gasto, atualizar_categoria, parsear_gastos_em_lote 
from estado_usuario import salvar_estado, carregar_estado, resetar_estado, resposta_enviada_recentemente, salvar_ultima_resposta
from gerar_resumo import gerar_resumo
from resgatar_contexto import buscar_conhecimento_relevante
from upgrade import verificar_upgrade_automatico
from armazenar_mensagem import armazenar_mensagem
from definir_limite import salvar_limite_usuario
from memoria_usuario import resumo_do_mes, verificar_limites, contexto_principal_usuario
from emocional import detectar_emocao, aumento_pos_emocao
# Importa função de registrar_gastos_fixos.py - Corrigido para v12
from registrar_gastos_fixos import salvar_gasto_fixo, atualizar_categoria_gasto_fixo 
from planilhas import get_pagantes, get_gratuitos
from engajamento import avaliar_engajamento
from indicadores import get_indicadores
from enviar_alertas import verificar_alertas
from enviar_lembretes import enviar_lembretes
from consultas import consultar_status_limites # Importa a nova função

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

load_dotenv()
app = FastAPI()

# Validação inicial das variáveis de ambiente essenciais
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
MESSAGING_SERVICE_SID = os.getenv("TWILIO_MESSAGING_SERVICE_SID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, MESSAGING_SERVICE_SID, OPENAI_API_KEY]):
    logging.error("ERRO CRÍTICO: Variáveis de ambiente essenciais (Twilio SID/Token/MessagingSID, OpenAI Key) não configuradas.")

openai.api_key = OPENAI_API_KEY
try:
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    logging.info("Cliente Twilio inicializado com sucesso.")
except Exception as e:
    logging.error(f"ERRO CRÍTICO: Falha ao inicializar cliente Twilio: {e}")
    client = None 

try:
    # Usar o prompt atualizado que inclui restrições de citação
    with open("/home/ubuntu/upload/prompt.txt", "r", encoding="utf-8") as arquivo_prompt:
        prompt_base = arquivo_prompt.read().strip()
except FileNotFoundError:
    logging.error("ERRO CRÍTICO: Arquivo prompt.txt não encontrado em /home/ubuntu/upload/prompt.txt.")
    prompt_base = "Você é um assistente financeiro."
except Exception as e:
    logging.error(f"ERRO CRÍTICO: Falha ao ler prompt.txt: {e}")
    prompt_base = "Você é um assistente financeiro." # Fallback adicionado

# Complemento contextual (mantido)
complemento_contextual = (
    "Você sempre trata o usuário pelo primeiro nome (que foi informado no início da conversa na resposta à saudação inicial) ou com um vocativo amigável e intimista. "
    "Você nunca recomenda divórcio ou separação por questões financeiras. "
    "O casamento é sagrado, indissolúvel e deve ser defendido com firmeza, clareza e profundidade espiritual. "
    "Seja sempre amigável, intimista, interessado e firme. Utilize explicitamente ensinamentos cristãos, católicos e do Opus Dei. "
    "Utilize o método de comunicação de Dale Carnegie, mostrando-se sempre interessado no usuário, demonstrando escuta ativa. "
    "Não use \\\\'olá\\\\' no início de uma resposta se o usuário já tiver feito a primeira interação. "
    "Nunca sugira imediatamente ajuda externa (como conselheiros matrimoniais), a não ser que seja estritamente necessário após várias interações. "
    "Trate crises financeiras conjugais com responsabilidade cristã e financeira, lembrando sempre que a cruz matrimonial é uma oportunidade de crescimento espiritual e amadurecimento na vocação do casamento."
    "Trate questoões de moral e ética com os ensinamentos de Santo Tomás de Aquino e da doutrina católica. "
    "NUNCA mencione ou sugira o uso de outros aplicativos ou ferramentas para funcionalidades que VOCÊ MESMO oferece, como controle de gastos, categorização, relatórios ou alertas. Você é a ferramenta completa."
)

mensagens_gpt_base = [
    {"role": "system", "content": prompt_base},
    {"role": "system", "content": complemento_contextual},
    {"role": "system", "content": "Sempre consulte a pasta Knowledge via embeddings para complementar respostas de acordo com o contexto."}
]

# === FUNÇÃO PARA INTERPRETAR GASTOS (SIMPLIFICADA - Regex - Mantida) ===
def interpretar_gasto_simples(mensagem_usuario):
    """Tenta extrair detalhes de um gasto usando Regex."""
    # Padrão: Descrição (qualquer coisa) - Valor (com R$, ",", ".") - Forma Pgto (palavra)
    padrao = re.compile(r"^(.*?)(?:-|\s+)(?:R\$\s*)?([\d,.]+)(?:-|\s+)(\w+)$", re.IGNORECASE)
    match = padrao.match(mensagem_usuario.strip())
    
    if match:
        descricao = match.group(1).strip()
        valor_str = match.group(2).replace(".", "").replace(",", ".") # Normaliza para ponto decimal
        forma_pagamento = match.group(3).strip().capitalize()
        
        try:
            valor = float(valor_str)
            if valor < 0: raise ValueError("Valor negativo")
            
            formas_validas = ["Pix", "Débito", "Debito", "Crédito", "Credito", "Dinheiro", "Boleto"]
            if forma_pagamento not in formas_validas:
                 if forma_pagamento.lower() == "credito": forma_pagamento = "Crédito"
                 elif forma_pagamento.lower() == "debito": forma_pagamento = "Débito"
                 else: 
                     logging.warning(f"Forma de pagamento \'{forma_pagamento}\' não reconhecida em: {mensagem_usuario}")
                     return None
            
            dados_gasto = {
                "descricao": descricao,
                "valor": valor,
                "forma_pagamento": forma_pagamento,
                "categoria_sugerida": None
            }
            logging.info(f"Gasto interpretado via Regex: {dados_gasto}")
            return dados_gasto
        except ValueError:
            logging.warning(f"Valor inválido \'{valor_str}\' encontrado via Regex em: {mensagem_usuario}")
            return None
    else:
        logging.info(f"Mensagem \'{mensagem_usuario[:50]}...\' não correspondeu ao padrão Regex de gasto.")
        return None

# === FUNÇÕES AUXILIARES (planilhas, formatação, envio, etc. - Mantidas) ===
def get_user_status(user_number):
    try:
        pagantes = get_pagantes().col_values(2)
        gratuitos = get_gratuitos().col_values(2)
        if user_number in pagantes:
            return "Pagantes"
        elif user_number in gratuitos:
            return "Gratuitos"
        else:
            return "Novo"
    except Exception as e:
        logging.error(f"Erro ao verificar status do usuário {user_number}: {e}")
        return "Novo"

def get_user_sheet(user_number):
    user_number_fmt = format_number(user_number) 
    try:
        aba_pagantes = get_pagantes()
        aba_gratuitos = get_gratuitos()
        pagantes = aba_pagantes.col_values(2)
        gratuitos = aba_gratuitos.col_values(2)
        if user_number_fmt in pagantes:
            logging.info(f"Usuário {user_number_fmt} encontrado na aba Pagantes.")
            return aba_pagantes
        elif user_number_fmt in gratuitos:
            logging.info(f"Usuário {user_number_fmt} encontrado na aba Gratuitos.")
            return aba_gratuitos
        else:
            logging.info(f"Usuário {user_number_fmt} não encontrado. Adicionando à aba Gratuitos.")
            now = datetime.datetime.now(pytz.timezone("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S")
            aba_gratuitos.append_row(["", user_number_fmt, "", now, 0, 0]) 
            logging.info(f"Usuário {user_number_fmt} adicionado com sucesso.")
            return aba_gratuitos
    except Exception as e:
        logging.error(f"Erro CRÍTICO ao obter/criar planilha para usuário {user_number_fmt}: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao acessar dados do usuário.")

def nome_valido(text):
    if not text: return False
    partes = text.strip().split()
    if len(partes) < 1: return False
    if not re.fullmatch(r"[a-zA-ZáéíóúÁÉÍÓÚâêîôûÂÊÎÔÛãõÃÕçÇ\s]+", text.strip()): return False
    if any(char in text for char in "@!?0123456789#$%*()[]{}"): return False
    return True

def format_number(raw_number):
    return raw_number.replace("whatsapp:", "").replace("+", "").replace(" ", "").strip()

def extract_email(text):
    match = re.search(r'[\w\.-]+@[\w\.-]+', text)
    return match.group(0) if match else None

def count_tokens(text):
    return len(text.split()) 

def send_message(to, body):
    if not client:
        logging.error(f"Tentativa de enviar mensagem para {to} falhou: Cliente Twilio não inicializado.")
        return False
    if not body or not body.strip():
        logging.warning(f"Tentativa de enviar mensagem VAZIA para {to}. Ignorado.")
        return False
    if resposta_enviada_recentemente(to, body):
        logging.info(f"Resposta duplicada para {to} detectada e não enviada.")
        return False

    partes = [body[i:i+1500] for i in range(0, len(body), 1500)]
    success = True
    try:
        logging.info(f"Tentando enviar mensagem para {to}: \'{body[:50]}...\' ({len(partes)} parte(s))")
        for i, parte in enumerate(partes):
            message = client.messages.create(
                body=parte,
                messaging_service_sid=MESSAGING_SERVICE_SID,
                to=f"whatsapp:{to}"
            )
            logging.info(f"Parte {i+1}/{len(partes)} enviada para {to}. SID: {message.sid}")
        salvar_ultima_resposta(to, body)
        logging.info(f"Mensagem completa enviada com sucesso para {to}.")
    except Exception as e:
        logging.error(f"ERRO TWILIO ao enviar mensagem para {to}: {e}")
        success = False
    return success

def get_interactions(sheet, row):
    try:
        val = sheet.cell(row, 6).value
        return int(val) if val and str(val).isdigit() else 0
    except Exception as e:
        logging.error(f"[ERRO Planilha] get_interactions (linha {row}): {e}")
        return 0

def increment_interactions(sheet, row):
    try:
        count = get_interactions(sheet, row) + 1
        sheet.update_cell(row, 6, count)
        return count
    except Exception as e:
        logging.error(f"[ERRO Planilha] increment_interactions (linha {row}): {e}")
        return get_interactions(sheet, row)

def passou_limite(sheet, row):
    try:
        status = sheet.title
        if status != "Gratuitos": return False
        return get_interactions(sheet, row) >= 10
    except Exception as e:
        logging.error(f"[ERRO Planilha] passou_limite (linha {row}): {e}")
        return False

def is_boas_vindas(text):
    saudacoes = ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "e aí", "opa", "ei", "tudo bem", "tudo bom"]
    text_lower = text.lower().strip()
    return any(text_lower.startswith(sauda) for sauda in saudacoes) or text_lower in saudacoes

def precisa_direcionamento(msg):
    frases_vagas = ["me ajuda", "preciso de ajuda", "me orienta", "o que eu faço", "não sei por onde começar", "como começar", "tô perdido", "me explica", "quero ajuda", "quero controlar", "quero começar", "começar a usar", "como funciona", "o que vc faz", "o que você faz"]
    msg_lower = msg.lower()
    return any(frase in msg_lower for frase in frases_vagas)

# --- NOVAS FUNÇÕES DE INTENÇÃO (Adicionadas para melhorar fluxo) ---
def quer_registrar_gasto_diario(msg):
    msg_lower = msg.lower()
    termos = ["registrar gasto", "anotar gasto", "gasto diário", "registra pra mim", "anota aí"]
    # Evita confundir com "gastos fixos"
    if "fixo" in msg_lower or "mensal" in msg_lower: 
        return False
    return any(t in msg_lower for t in termos)

def quer_registrar_gasto_fixo(msg):
    msg_lower = msg.lower()
    termos = ["gasto fixo", "gastos fixos", "gasto mensal", "registrar conta", "contas mensais"]
    return any(t in msg_lower for t in termos)

def quer_definir_limites(msg):
    msg_lower = msg.lower()
    termos = ["definir limites", "limites por categoria", "colocar limites", "estabelecer limites", "limite de gasto", "criar limite"]
    return any(t in msg_lower for t in termos)
# --- FIM NOVAS FUNÇÕES DE INTENÇÃO ---

def quer_resumo_mensal(msg):
    msg_lower = msg.lower()
    termos = ["quanto gastei", "resumo do mês", "gastos do mês", "como estão meus gastos", "meu resumo financeiro", "me mostra meus gastos", "meus gastos recentes", "gastando muito", "gastei demais", "status dos limites", "como estão meus limites"]
    return any(t in msg_lower for t in termos)

def quer_lista_comandos(texto):
    texto_lower = texto.lower()
    termos = ["quais comandos", "comandos disponíveis", "o que você faz", "como usar", "me ajuda com comandos", "o que posso pedir", "me manda os comandos", "comando", "menu", "como funciona", "/comandos", "/ajuda", "opções"]
    return any(t in texto_lower for t in termos)

def get_tokens(sheet, row):
    try:
        val = sheet.cell(row, 5).value
        return int(val) if val and str(val).isdigit() else 0
    except Exception as e:
        logging.error(f"[ERRO Planilha] get_tokens (linha {row}): {e}")
        return 0

def increment_tokens(sheet, row, novos_tokens):
    try:
        tokens_atuais = get_tokens(sheet, row)
        sheet.update_cell(row, 5, tokens_atuais + novos_tokens)
        return tokens_atuais + novos_tokens
    except Exception as e:
        logging.error(f"[ERRO Planilha] increment_tokens (linha {row}): {e}")
        return get_tokens(sheet, row)

CATEGORIAS_VALIDAS = [
    "Alimentação", "Saúde", "Transporte", "Moradia", "Educação", 
    "Lazer", "Lazer/Bem-estar", "Presentes/Doações", "Serviços/Domésticos",
    "Impostos/Taxas", "Seguros", "Utilidades", "Vestuário", "Pet", 
    "Investimentos", "Transferências", "Financeiro", "Outros", "A definir"
]

# === WEBHOOK PRINCIPAL ===
@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    logging.info("Recebida requisição POST em /webhook")
    try:
        form = await request.form()
        incoming_msg = form.get("Body", "").strip()
        from_number_raw = form.get("From", "")
        msg_lower = incoming_msg.lower() # Para facilitar verificações
        
        if not incoming_msg or not from_number_raw:
            logging.warning("Requisição recebida sem 'Body' ou 'From'. Ignorando.")
            return {"status": "requisição inválida"}
            
        from_number = format_number(from_number_raw)
        logging.info(f"Mensagem recebida de {from_number}: '{incoming_msg[:50]}...'")

    except Exception as e:
        logging.error(f"Erro ao processar formulário da requisição: {e}")
        raise HTTPException(status_code=400, detail="Erro ao processar dados da requisição.")

    try: # Bloco try principal
        estado = carregar_estado(from_number)
        ultima_msg_registrada = estado.get("ultima_msg", "")

        if incoming_msg == ultima_msg_registrada:
            logging.info(f"Mensagem duplicada de {from_number} detectada e ignorada.")
            return {"status": "mensagem duplicada ignorada"}

        estado["ultima_msg"] = incoming_msg

        # --- SETUP USUÁRIO (Mantido) --- 
        try:
            sheet_usuario = get_user_sheet(from_number) 
            col_numeros = sheet_usuario.col_values(2)
            linha_index = col_numeros.index(from_number) + 1
            linha_usuario = sheet_usuario.row_values(linha_index)
            logging.info(f"Dados da linha {linha_index} recuperados para {from_number}.")
            while len(linha_usuario) < 7: linha_usuario.append("") 
            name = linha_usuario[0].strip()
            email = linha_usuario[2].strip()
            status_usuario = sheet_usuario.title
        except ValueError: 
             logging.warning(f"Index falhou para {from_number} após get_user_sheet. Tentando recarregar e encontrar.")
             try:
                 sheet_usuario = get_user_sheet(from_number)
                 col_numeros = sheet_usuario.col_values(2)
                 linha_index = col_numeros.index(from_number) + 1
                 linha_usuario = sheet_usuario.row_values(linha_index)
                 while len(linha_usuario) < 7: linha_usuario.append("")
                 name = linha_usuario[0].strip()
                 email = linha_usuario[2].strip()
                 status_usuario = sheet_usuario.title
                 logging.info(f"Usuário {from_number} encontrado na segunda tentativa na linha {linha_index}.")
             except ValueError:
                 logging.error(f"ERRO CRÍTICO: Usuário {from_number} não encontrado na planilha mesmo após adição/verificação.")
                 raise HTTPException(status_code=500, detail="Erro interno crítico ao localizar dados do usuário.")
        except Exception as e:
            logging.error(f"ERRO CRÍTICO ao obter dados da planilha para {from_number}: {e}")
            raise HTTPException(status_code=500, detail="Erro interno ao acessar dados da planilha.")

        # --- VERIFICA LIMITE DE INTERAÇÕES (Mantido) --- 
        convite_premium_enviado = estado.get("convite_premium_enviado", False)
        if status_usuario == "Gratuitos" and not convite_premium_enviado:
            interacoes = get_interactions(sheet_usuario, linha_index)
            if interacoes >= 10:
                logging.info(f"Usuário gratuito {from_number} atingiu o limite de {interacoes} interações.")
                resposta = mensagens.alerta_limite_gratuito(contexto='geral')
                send_message(from_number, mensagens.estilo_msg(resposta))
                estado["convite_premium_enviado"] = True
                salvar_estado(from_number, estado)
                increment_interactions(sheet_usuario, linha_index)
                return {"status": "limite gratuito atingido, convite enviado"}
            else:
                increment_interactions(sheet_usuario, linha_index)
                logging.info(f"Interação {interacoes + 1}/10 para usuário gratuito {from_number}.")
        elif status_usuario == "Pagantes":
             increment_interactions(sheet_usuario, linha_index)
             logging.info(f"Interação registrada para usuário pagante {from_number}.")

        # --- FLUXO DE ONBOARDING/CADASTRO (Mantido) --- 
        if not name or name == "Usuário" or not email:
            # ...(código do onboarding mantido como na v10/v12_base)... 
            # Se já está aguardando cadastro, processa a resposta
            if estado.get("ultimo_fluxo") == "aguardando_cadastro":
                logging.info(f"Processando possível resposta de cadastro de {from_number}.")
                nome_capturado = None; email_capturado = None
                linhas = incoming_msg.split("\n")
                for linha in linhas:
                    linha_strip = linha.strip()
                    if not nome_capturado and nome_valido(linha_strip): nome_capturado = linha_strip.title()
                    if not email_capturado and extract_email(linha_strip): email_capturado = extract_email(linha_strip).lower()
                
                nome_atualizado = False; email_atualizado = False
                if nome_capturado and (not name or name == "Usuário"):
                    try: 
                        sheet_usuario.update_cell(linha_index, 1, nome_capturado)
                        name = nome_capturado
                        nome_atualizado = True
                        logging.info(f"Nome de {from_number} atualizado para {name}")
                    except Exception as e: logging.error(f"[ERRO Planilha] Falha ao atualizar nome para {nome_capturado} (linha {linha_index}): {e}")
                
                if email_capturado and not email:
                    try: 
                        sheet_usuario.update_cell(linha_index, 3, email_capturado)
                        email = email_capturado
                        email_atualizado = True
                        logging.info(f"Email de {from_number} atualizado para {email}")
                    except Exception as e: logging.error(f"[ERRO Planilha] Falha ao atualizar email para {email_capturado} (linha {linha_index}): {e}")
                
                if not name or name == "Usuário":
                    if not email_atualizado:
                        logging.info(f"Solicitando nome para {from_number}.")
                        send_message(from_number, mensagens.estilo_msg("Ótimo! E qual seu nome completo, por favor? ✍️"))
                        salvar_estado(from_number, estado); return {"status": "aguardando nome"}
                elif not email:
                     if not nome_atualizado:
                        logging.info(f"Solicitando email para {from_number}.")
                        send_message(from_number, mensagens.estilo_msg("Perfeito! Agora só preciso do seu e-mail. 📧"))
                        salvar_estado(from_number, estado); return {"status": "aguardando email"}
                
                if name and name != "Usuário" and email:
                    logging.info(f"Cadastro de {from_number} completo via captura.")
                    primeiro_nome = name.split()[0]
                    send_message(from_number, mensagens.estilo_msg(mensagens.cadastro_completo(primeiro_nome)))
                    estado["ultimo_fluxo"] = "cadastro_completo"
                    estado["saudacao_realizada"] = True
                    salvar_estado(from_number, estado)
                    return {"status": "cadastro completo via captura"}
                else:
                    logging.info(f"Dados parciais de cadastro atualizados para {from_number}. Aguardando restante.")
                    salvar_estado(from_number, estado)
                    return {"status": "dados parciais de cadastro atualizados"}
            
            elif is_boas_vindas(incoming_msg) or estado.get("ultimo_fluxo") != "aguardando_cadastro":
                logging.info(f"Usuário {from_number} iniciou interação mas não está cadastrado. Solicitando cadastro.")
                send_message(from_number, mensagens.estilo_msg(mensagens.solicitacao_cadastro()))
                estado["ultimo_fluxo"] = "aguardando_cadastro"
                salvar_estado(from_number, estado)
                return {"status": "solicitando cadastro"}
            else:
                logging.warning(f"Estado inesperado para {from_number}: falta cadastro mas ultimo_fluxo não era aguardando_cadastro. Solicitando novamente.")
                send_message(from_number, mensagens.estilo_msg(mensagens.solicitacao_cadastro()))
                estado["ultimo_fluxo"] = "aguardando_cadastro"
                salvar_estado(from_number, estado)
                return {"status": "re-solicitando cadastro"}
        # --- FIM FLUXO ONBOARDING/CADASTRO ---

        # --- INÍCIO PROCESSAMENTO PÓS-CADASTRO --- 
        logging.info(f"Iniciando processamento da mensagem pós-cadastro de {from_number}.")
        mensagem_tratada = False 
        estado_modificado_fluxo = False
        primeiro_nome = name.split()[0] if name and name != "Usuário" else ""

        # --- TRATAMENTO DE SAUDAÇÕES REPETIDAS (Mantido) --- 
        if is_boas_vindas(incoming_msg) and estado.get("saudacao_realizada"):
            logging.info(f"Saudação repetida de {from_number} ({name}). Enviando resposta curta.")
            resposta_curta = f"Oi, {primeiro_nome}! 😊 Em que posso ajudar?"
            send_message(from_number, mensagens.estilo_msg(resposta_curta))
            mensagem_tratada = True
            salvar_estado(from_number, estado)
            return {"status": "saudação repetida respondida"}
        elif is_boas_vindas(incoming_msg) and not estado.get("saudacao_realizada"):
             logging.info(f"Primeira saudação pós-cadastro de {from_number} ({name}).")
             resposta_curta = f"Olá, {primeiro_nome}! Como posso te ajudar hoje?"
             send_message(from_number, mensagens.estilo_msg(resposta_curta))
             estado["saudacao_realizada"] = True
             estado_modificado_fluxo = True
             mensagem_tratada = True
             salvar_estado(from_number, estado)
             return {"status": "primeira saudação pós-cadastro respondida"}

        # --- FLUXOS ESPECÍFICOS (ANTES DE CAIR NO GPT) ---
        
        # --- FLUXO: DEFINIR LIMITES (Início e Confirmação - Mantido da v10) --- 
        # Verifica se o usuário QUER definir limites (antes de estar no fluxo)
        if quer_definir_limites(msg_lower) and estado.get("ultimo_fluxo") not in ["aguardando_definicao_limites", "aguardando_confirmacao_limites"]:
             logging.info(f"{from_number} pediu para definir limites.")
             # Usar mensagem de mensagens.py
             msg_instrucao_limites = mensagens.instrucao_definir_limites()
             send_message(from_number, mensagens.estilo_msg(msg_instrucao_limites))
             estado["ultimo_fluxo"] = "aguardando_definicao_limites"
             estado_modificado_fluxo = True
             mensagem_tratada = True
             salvar_estado(from_number, estado)
             logging.info(f"Instruções para definir limites enviadas para {from_number}. Estado definido como 'aguardando_definicao_limites'. Retornando.")
             return {"status": "instruções de limite enviadas, aguardando lista"}
        # Processa a lista de limites enviada
        elif estado.get("ultimo_fluxo") == "aguardando_definicao_limites":
            # ...(código de interpretação e pedido de confirmação de limites mantido da v10/v12_base)... 
            logging.info(f"Processando lista de limites enviada por {from_number}.")
            linhas = incoming_msg.strip().split("\n")
            limites_pendentes = []
            limites_erro_parse = []

            for linha in linhas:
                partes = linha.split(":")
                if len(partes) == 2:
                    item_ou_categoria_raw = partes[0].strip()
                    item_ou_categoria = item_ou_categoria_raw.capitalize() if item_ou_categoria_raw.capitalize() in CATEGORIAS_VALIDAS else item_ou_categoria_raw
                    valor_str = partes[1].strip().replace("R$", "").replace(".", "").replace(",", ".")
                    try:
                        valor = float(valor_str)
                        if valor < 0: raise ValueError("Valor negativo")
                        limite_interpretado = {"item_ou_categoria": item_ou_categoria, "valor": valor}
                        limites_pendentes.append(limite_interpretado)
                    except ValueError:
                        limites_erro_parse.append(f"❌ Formato inválido: '{linha}' (Valor '{partes[1].strip()}' inválido)")
                    except Exception as e:
                        limites_erro_parse.append(f"❌ Erro inesperado ao processar '{linha}': {str(e)}")
                        logging.error(f"Erro ao interpretar linha de limite '{linha}' para {from_number}: {e}")
                else:
                    if linha.strip():
                        limites_erro_parse.append(f"❌ Formato inválido: '{linha}' (Use: Categoria ou Item: Valor)")

            resposta_confirmacao = ""
            linhas_confirmacao = []
            algum_para_confirmar = False
            
            if limites_pendentes:
                resposta_confirmacao = "Ok, entendi os seguintes limites:\n"
                for limite in limites_pendentes:
                    valor_fmt = f"R$ {limite['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    linhas_confirmacao.append(f"- {limite['item_ou_categoria']}: {valor_fmt}")
                    algum_para_confirmar = True
                
                resposta_confirmacao += "\n".join(linhas_confirmacao)
                resposta_confirmacao += "\n\nConfirma o registro desses limites? (Sim / Editar)"
                estado["limites_pendentes_confirmacao"] = limites_pendentes
                estado["ultimo_fluxo"] = "aguardando_confirmacao_limites"
                estado_modificado_fluxo = True
            else:
                resposta_confirmacao = "Não consegui entender nenhum limite na sua mensagem." 
                estado["ultimo_fluxo"] = None
                estado_modificado_fluxo = True
                
            if limites_erro_parse:
                 if algum_para_confirmar:
                     resposta_confirmacao += "\n\n⚠️ *Além disso, algumas linhas tiveram erro:*\n" + "\n".join(limites_erro_parse)
                 else:
                     resposta_confirmacao += "\n\n*Linhas com erro:*\n" + "\n".join(limites_erro_parse)
            
            send_message(from_number, mensagens.estilo_msg(resposta_confirmacao))
            mensagem_tratada = True
            logging.info(f"Pedido de confirmação/erros para limites enviado para {from_number}.")
            salvar_estado(from_number, estado)
            return {"status": "aguardando confirmação de limites ou lista corrigida"}
        # Processa a confirmação (Sim/Editar)
        elif estado.get("ultimo_fluxo") == "aguardando_confirmacao_limites":
            # ...(código de registro ou cancelamento de limites mantido da v10/v12_base)... 
            limites_pendentes = estado.get("limites_pendentes_confirmacao", [])
            resposta_usuario_lower = msg_lower

            if "sim" in resposta_usuario_lower or "yes" in resposta_usuario_lower or "confirmo" in resposta_usuario_lower:
                logging.info(f"{from_number} confirmou o registro dos limites pendentes.")
                limites_salvos = []
                limites_erro = []
                algum_sucesso = False

                for limite in limites_pendentes:
                    try:
                        resultado_save = salvar_limite_usuario(from_number, limite['item_ou_categoria'], limite['valor'])
                        if resultado_save["status"] == "ok":
                            valor_fmt = f"R$ {limite['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                            limites_salvos.append(f"✅ {limite['item_ou_categoria']}: {valor_fmt}")
                            algum_sucesso = True
                        else:
                            limites_erro.append(f"❌ Erro ao salvar {limite['item_ou_categoria']}: {resultado_save.get('mensagem', 'Erro desconhecido')}")
                    except Exception as e:
                        limites_erro.append(f"❌ Erro inesperado ao salvar {limite['item_ou_categoria']}: {str(e)}")
                        logging.error(f"Erro ao salvar limite {limite['item_ou_categoria']} para {from_number}: {e}")
                
                resposta = ""
                if limites_salvos:
                    resposta += "\n📊 *Limites Registrados:*\n" + "\n".join(limites_salvos)
                if limites_erro:
                    resposta += "\n❌ *Erros ao registrar:*\n" + "\n".join(limites_erro)
                
                if not resposta:
                    resposta = "Houve um problema e nenhum limite pôde ser registrado." 
                elif algum_sucesso:
                    resposta += "\n\n👍 Limites atualizados!"

                if "limites_pendentes_confirmacao" in estado: del estado["limites_pendentes_confirmacao"]
                estado["ultimo_fluxo"] = None
                estado_modificado_fluxo = True
                mensagem_tratada = True
                send_message(from_number, mensagens.estilo_msg(resposta))
                logging.info(f"Registro de limites confirmado por {from_number} concluído.")
            
            elif "editar" in resposta_usuario_lower or "não" in resposta_usuario_lower or "nao" in resposta_usuario_lower:
                logging.info(f"{from_number} pediu para editar ou cancelou o registro dos limites.")
                send_message(from_number, mensagens.estilo_msg("Ok, cancelado. Se quiser tentar definir os limites novamente, é só me enviar a lista corrigida."))
                estado["ultimo_fluxo"] = None
                if "limites_pendentes_confirmacao" in estado: del estado["limites_pendentes_confirmacao"]
                estado_modificado_fluxo = True
                mensagem_tratada = True
            else:
                logging.warning(f"{from_number} respondeu algo inesperado à confirmação de limites: {incoming_msg}")
                send_message(from_number, mensagens.estilo_msg("Não entendi sua resposta. Por favor, diga 'Sim' para confirmar ou 'Editar' para corrigir."))
                estado_modificado_fluxo = True
                mensagem_tratada = True
            
            salvar_estado(from_number, estado)
            return {"status": "confirmação de limites processada"}

        # --- FLUXO: REGISTRAR GASTOS FIXOS (Início, Confirmação, Correção Cat, Lembretes - Reimplementado) ---
        # Verifica se o usuário QUER registrar gastos fixos
        elif quer_registrar_gasto_fixo(msg_lower) and estado.get("ultimo_fluxo") not in ["aguardando_registro_gastos_fixos", "aguardando_confirmacao_gastos_fixos", "aguardando_decisao_correcao_cat_fixa", "aguardando_categoria_para_correcao_fixa", "aguardando_decisao_lembretes_fixos"]:
            logging.info(f"{from_number} pediu para registrar gastos fixos.")
            # Usar mensagem de mensagens.py
            msg_instrucao = mensagens.instrucao_registrar_gastos_fixos()
            send_message(from_number, mensagens.estilo_msg(msg_instrucao))
            estado["ultimo_fluxo"] = "aguardando_registro_gastos_fixos"
            estado_modificado_fluxo = True
            mensagem_tratada = True
            salvar_estado(from_number, estado)
            logging.info(f"Instruções para registrar gastos fixos enviadas para {from_number}. Estado definido.")
            return {"status": "instruções de gastos fixos enviadas, aguardando lista"}
        # Processa a lista de gastos fixos enviada
        elif estado.get("ultimo_fluxo") == "aguardando_registro_gastos_fixos":
            # ...(código de interpretação e pedido de confirmação de gastos fixos mantido da v10/v12_base)... 
            logging.info(f"Processando lista de gastos fixos enviada por {from_number}.")
            linhas = incoming_msg.strip().split("\n")
            gastos_fixos_pendentes = []
            gastos_fixos_erro_parse = []

            for linha in linhas:
                partes = [p.strip() for p in re.split(r'[-–]', linha)]
                if len(partes) == 3:
                    descricao = partes[0]
                    valor_str = partes[1].replace("R$", "").replace(".", "").replace(",", ".")
                    dia_str = partes[2].lower().replace("dia", "").strip()
                    try:
                        valor = float(valor_str)
                        if valor < 0: raise ValueError("Valor negativo")
                        dia = int(dia_str)
                        if not 1 <= dia <= 31: raise ValueError("Dia inválido")
                        categoria_status = categorizar(descricao)
                        gasto_interpretado = {"descricao": descricao, "valor": valor, "dia": dia, "categoria_status": categoria_status}
                        gastos_fixos_pendentes.append(gasto_interpretado)
                    except ValueError as e:
                        gastos_fixos_erro_parse.append(f"❌ Formato inválido: '{linha}' (Valor ou Dia inválido: {e})")
                    except Exception as e:
                        gastos_fixos_erro_parse.append(f"❌ Erro inesperado ao processar '{linha}': {str(e)}")
                        logging.error(f"Erro ao interpretar linha de gasto fixo '{linha}' para {from_number}: {e}")
                else:
                    if linha.strip():
                        gastos_fixos_erro_parse.append(f"❌ Formato inválido: '{linha}' (Use: Descrição - Valor - dia Dia)")

            resposta_confirmacao = ""
            linhas_confirmacao = []
            algum_para_confirmar = False
            
            if gastos_fixos_pendentes:
                resposta_confirmacao = "Ok, entendi os seguintes gastos fixos:\n"
                for gasto in gastos_fixos_pendentes:
                    cat_status = gasto['categoria_status']
                    cat_display = ""
                    if cat_status.startswith("AMBIGUO:"):
                        partes_amb = cat_status.split(":")
                        opcoes = partes_amb[2]
                        cat_display = f"❓ ({opcoes}?)"
                    elif cat_status != "A definir":
                        cat_display = f"({cat_status})"
                    else:
                        cat_display = "(A definir)"
                    valor_fmt = f"R$ {gasto['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    linhas_confirmacao.append(f"- {gasto['descricao']} {cat_display} - {valor_fmt} - dia {gasto['dia']}")
                    algum_para_confirmar = True
                
                resposta_confirmacao += "\n".join(linhas_confirmacao)
                resposta_confirmacao += "\n\nConfirma o registro? (Sim / Editar)"
                estado["gastos_fixos_pendentes_confirmacao"] = gastos_fixos_pendentes
                estado["ultimo_fluxo"] = "aguardando_confirmacao_gastos_fixos"
                estado_modificado_fluxo = True
            else:
                resposta_confirmacao = "Não consegui entender nenhum gasto fixo na sua mensagem." 
                estado["ultimo_fluxo"] = None
                estado_modificado_fluxo = True
                
            if gastos_fixos_erro_parse:
                 if algum_para_confirmar:
                     resposta_confirmacao += "\n\n⚠️ *Além disso, algumas linhas tiveram erro:*\n" + "\n".join(gastos_fixos_erro_parse)
                 else:
                     resposta_confirmacao += "\n\n*Linhas com erro:*\n" + "\n".join(gastos_fixos_erro_parse)
            
            send_message(from_number, mensagens.estilo_msg(resposta_confirmacao))
            mensagem_tratada = True
            logging.info(f"Pedido de confirmação/erros para gastos fixos enviado para {from_number}.")
            salvar_estado(from_number, estado)
            return {"status": "aguardando confirmação de gastos fixos ou lista corrigida"}
        # Processa a confirmação (Sim/Editar) para gastos fixos
        elif estado.get("ultimo_fluxo") == "aguardando_confirmacao_gastos_fixos":
            # ...(código de registro ou cancelamento de gastos fixos mantido da v10/v12_base)... 
            gastos_pendentes = estado.get("gastos_fixos_pendentes_confirmacao", [])
            resposta_usuario_lower = msg_lower

            if "sim" in resposta_usuario_lower or "yes" in resposta_usuario_lower or "confirmo" in resposta_usuario_lower:
                logging.info(f"{from_number} confirmou o registro dos gastos fixos pendentes.")
                gastos_fixos_salvos = []
                gastos_fixos_erro = []
                categorias_pendentes_definir = []
                algum_sucesso = False

                for gasto in gastos_pendentes:
                    categoria_final = gasto['categoria_status']
                    if categoria_final.startswith("AMBIGUO:") or categoria_final == "A definir":
                        categoria_final = "A definir"
                        categorias_pendentes_definir.append({"descricao": gasto['descricao'], "dia": gasto['dia']})

                    try:
                        # Passa dia_vencimento corretamente
                        resultado_save = salvar_gasto_fixo(from_number, gasto['descricao'], gasto['valor'], gasto['dia'], categoria_final)
                        if resultado_save["status"] == "ok":
                            valor_fmt = f"R$ {gasto['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                            cat_display = f"({categoria_final})" if categoria_final != "A definir" else "(A definir)"
                            gastos_fixos_salvos.append(f"✅ {gasto['descricao']} {cat_display} - {valor_fmt} - dia {gasto['dia']}")
                            algum_sucesso = True
                        else:
                            gastos_fixos_erro.append(f"❌ Erro ao salvar {gasto['descricao']}: {resultado_save.get('mensagem', 'Erro desconhecido')}")
                    except Exception as e:
                        gastos_fixos_erro.append(f"❌ Erro inesperado ao salvar {gasto['descricao']}: {str(e)}")
                        logging.error(f"Erro ao salvar gasto fixo {gasto['descricao']} para {from_number}: {e}")
                
                resposta = ""
                if gastos_fixos_salvos:
                    resposta += "\n📝 *Gastos Fixos Registrados:*\n" + "\n".join(gastos_fixos_salvos)
                if gastos_fixos_erro:
                    resposta += "\n❌ *Erros ao registrar:*\n" + "\n".join(gastos_fixos_erro)
                
                if not resposta:
                    resposta = "Houve um problema e nenhum gasto fixo pôde ser registrado." 
                
                if categorias_pendentes_definir:
                    resposta += "\n\n⚠️ Notei que alguns gastos ficaram com categoria 'A definir'. Gostaria de defini-las agora? (Sim/Não)"
                    estado["categorias_fixas_a_definir"] = categorias_pendentes_definir
                    estado["ultimo_fluxo"] = "aguardando_decisao_correcao_cat_fixa"
                elif algum_sucesso:
                    resposta += "\n\n👍 Gastos fixos registrados! Gostaria de ativar lembretes automáticos para ser avisado *um dia antes e também no dia do vencimento*? (Sim/Não)"
                    estado["ultimo_fluxo"] = "aguardando_decisao_lembretes_fixos"
                else:
                    estado["ultimo_fluxo"] = None
                
                if "gastos_fixos_pendentes_confirmacao" in estado: del estado["gastos_fixos_pendentes_confirmacao"]
                estado_modificado_fluxo = True
                mensagem_tratada = True
                send_message(from_number, mensagens.estilo_msg(resposta))
                logging.info(f"Registro de gastos fixos confirmado por {from_number} concluído.")
            
            elif "editar" in resposta_usuario_lower or "não" in resposta_usuario_lower or "nao" in resposta_usuario_lower:
                logging.info(f"{from_number} pediu para editar ou cancelou o registro dos gastos fixos.")
                send_message(from_number, mensagens.estilo_msg("Ok, cancelado. Se quiser tentar registrar novamente, é só me enviar a lista corrigida."))
                estado["ultimo_fluxo"] = None
                if "gastos_fixos_pendentes_confirmacao" in estado: del estado["gastos_fixos_pendentes_confirmacao"]
                estado_modificado_fluxo = True
                mensagem_tratada = True
            else:
                logging.warning(f"{from_number} respondeu algo inesperado à confirmação de gastos fixos: {incoming_msg}")
                send_message(from_number, mensagens.estilo_msg("Não entendi sua resposta. Por favor, diga 'Sim' para confirmar ou 'Editar' para corrigir."))
                estado_modificado_fluxo = True
                mensagem_tratada = True
            
            salvar_estado(from_number, estado)
            return {"status": "confirmação de gastos fixos processada"}
        # Processa decisão sobre corrigir categorias fixas
        elif estado.get("ultimo_fluxo") == "aguardando_decisao_correcao_cat_fixa":
            # ...(código de início da correção de categorias fixas mantido da v10/v12_base)... 
            resposta_usuario_lower = msg_lower
            categorias_pendentes = estado.get("categorias_fixas_a_definir", [])

            if "sim" in resposta_usuario_lower or "yes" in resposta_usuario_lower or "ajustar" in resposta_usuario_lower:
                if categorias_pendentes:
                    logging.info(f"{from_number} quer corrigir as categorias fixas pendentes.")
                    gasto_para_corrigir = categorias_pendentes[0]
                    estado["corrigindo_cat_fixa_atual"] = gasto_para_corrigir
                    msg_pergunta = f"Ok. Qual categoria você define para '{gasto_para_corrigir['descricao']}' (venc. dia {gasto_para_corrigir['dia']})?"
                    send_message(from_number, mensagens.estilo_msg(msg_pergunta))
                    estado["ultimo_fluxo"] = "aguardando_categoria_para_correcao_fixa"
                    estado_modificado_fluxo = True
                    mensagem_tratada = True
                else:
                    logging.warning(f"{from_number} quis corrigir categorias fixas, mas a lista estava vazia.")
                    send_message(from_number, mensagens.estilo_msg("Parece que não há mais categorias pendentes para ajustar."))
                    estado["ultimo_fluxo"] = None
                    if "categorias_fixas_a_definir" in estado: del estado["categorias_fixas_a_definir"]
                    estado_modificado_fluxo = True
                    mensagem_tratada = True
            elif "não" in resposta_usuario_lower or "nao" in resposta_usuario_lower:
                logging.info(f"{from_number} não quis corrigir as categorias fixas agora.")
                send_message(from_number, mensagens.estilo_msg("Entendido. Você pode pedir para ajustar as categorias pendentes a qualquer momento."))
                estado["ultimo_fluxo"] = None
                estado_modificado_fluxo = True
                mensagem_tratada = True
                resposta_lembrete = "\n\nGostaria de ativar lembretes automáticos para ser avisado *um dia antes e também no dia do vencimento*? (Sim/Não)"
                send_message(from_number, mensagens.estilo_msg(resposta_lembrete))
                estado["ultimo_fluxo"] = "aguardando_decisao_lembretes_fixos"
            else:
                logging.warning(f"{from_number} respondeu algo inesperado à decisão de correção: {incoming_msg}")
                send_message(from_number, mensagens.estilo_msg("Não entendi. Quer ajustar as categorias pendentes agora? (Sim/Não)"))
                estado_modificado_fluxo = True
                mensagem_tratada = True

            salvar_estado(from_number, estado)
            return {"status": "decisão sobre correção de categorias fixas processada"}
        # Processa a categoria informada para correção
        elif estado.get("ultimo_fluxo") == "aguardando_categoria_para_correcao_fixa":
            # ...(código de atualização da categoria e loop de correção mantido da v10/v12_base)... 
            gasto_atual = estado.get("corrigindo_cat_fixa_atual")
            categorias_pendentes = estado.get("categorias_fixas_a_definir", [])
            categoria_informada = incoming_msg.strip().capitalize()

            if not gasto_atual:
                logging.error(f"Erro: {from_number} está em aguardando_categoria_para_correcao_fixa sem gasto atual no estado.")
                estado["ultimo_fluxo"] = None; estado_modificado_fluxo = True; mensagem_tratada = False
            elif categoria_informada not in CATEGORIAS_VALIDAS:
                 logging.warning(f"{from_number} informou categoria inválida '{categoria_informada}' para correção.")
                 send_message(from_number, mensagens.estilo_msg(f"'{categoria_informada}' não parece ser uma categoria válida. Por favor, informe uma categoria como 'Moradia', 'Alimentação', 'Educação', etc."))
                 estado_modificado_fluxo = True
                 mensagem_tratada = True
            else:
                try:
                    # Usa a função reimplementada
                    sucesso_update = atualizar_categoria_gasto_fixo(from_number, gasto_atual['descricao'], gasto_atual['dia'], categoria_informada)
                    if sucesso_update:
                        logging.info(f"Categoria do gasto fixo '{gasto_atual['descricao']}' (dia {gasto_atual['dia']}) atualizada para '{categoria_informada}' para {from_number}.")
                        categorias_pendentes.pop(0)
                        estado["categorias_fixas_a_definir"] = categorias_pendentes
                        
                        if categorias_pendentes:
                            proximo_gasto = categorias_pendentes[0]
                            estado["corrigindo_cat_fixa_atual"] = proximo_gasto
                            msg_proximo = f"✅ Categoria atualizada! Agora, qual categoria para '{proximo_gasto['descricao']}' (venc. dia {proximo_gasto['dia']})?"
                            send_message(from_number, mensagens.estilo_msg(msg_proximo))
                            estado["ultimo_fluxo"] = "aguardando_categoria_para_correcao_fixa"
                        else:
                            logging.info(f"Todas as categorias fixas pendentes foram corrigidas por {from_number}.")
                            send_message(from_number, mensagens.estilo_msg("✅ Ótimo! Todas as categorias pendentes foram ajustadas."))
                            estado["ultimo_fluxo"] = None
                            if "corrigindo_cat_fixa_atual" in estado: del estado["corrigindo_cat_fixa_atual"]
                            if "categorias_fixas_a_definir" in estado: del estado["categorias_fixas_a_definir"]
                            resposta_lembrete = "\n\nGostaria de ativar lembretes automáticos para ser avisado *um dia antes e também no dia do vencimento*? (Sim/Não)"
                            send_message(from_number, mensagens.estilo_msg(resposta_lembrete))
                            estado["ultimo_fluxo"] = "aguardando_decisao_lembretes_fixos"
                            
                        estado_modificado_fluxo = True
                        mensagem_tratada = True
                    else:
                        logging.error(f"Falha ao atualizar categoria fixa '{gasto_atual['descricao']}' para {from_number} na planilha.")
                        send_message(from_number, mensagens.estilo_msg(f"❌ Tive um problema ao atualizar a categoria de '{gasto_atual['descricao']}'. Vamos tentar de novo mais tarde."))
                        estado["ultimo_fluxo"] = None
                        estado_modificado_fluxo = True
                        mensagem_tratada = True
                except Exception as e:
                    logging.error(f"Exceção ao chamar atualizar_categoria_gasto_fixo para {from_number}: {e}")
                    send_message(from_number, mensagens.estilo_msg(f"❌ Ocorreu um erro inesperado ao tentar atualizar a categoria de '{gasto_atual['descricao']}'."))
                    estado["ultimo_fluxo"] = None
                    estado_modificado_fluxo = True
                    mensagem_tratada = True
            
            salvar_estado(from_number, estado)
            return {"status": "processamento de correção de categoria fixa concluído"}
        # Processa decisão sobre lembretes fixos
        elif estado.get("ultimo_fluxo") == "aguardando_decisao_lembretes_fixos":
            # ...(código de ativação/desativação de lembretes mantido da v10/v12_base)... 
            resposta_usuario_lower = msg_lower
            if "sim" in resposta_usuario_lower or "yes" in resposta_usuario_lower:
                logging.info(f"{from_number} confirmou ativação de lembretes para gastos fixos.")
                # AQUI - Lógica para ATIVAR os lembretes
                send_message(from_number, mensagens.estilo_msg("Ótimo! Lembretes ativados. 👍"))
                estado["ultimo_fluxo"] = None
                estado["lembretes_fixos_ativos"] = True
                estado_modificado_fluxo = True
                mensagem_tratada = True
            elif "não" in resposta_usuario_lower or "nao" in resposta_usuario_lower:
                logging.info(f"{from_number} não quis ativar lembretes para gastos fixos.")
                send_message(from_number, mensagens.estilo_msg("Entendido. Sem lembretes por enquanto."))
                estado["ultimo_fluxo"] = None
                estado["lembretes_fixos_ativos"] = False
                estado_modificado_fluxo = True
                mensagem_tratada = True
            else:
                logging.info(f"{from_number} enviou msg não relacionada à decisão de lembretes: {incoming_msg}. Saindo do fluxo de lembretes.")
                estado["ultimo_fluxo"] = None
                estado_modificado_fluxo = True
                # Não marca mensagem_tratada = True, para reprocessar no fluxo geral
                salvar_estado(from_number, estado)
                pass

        # --- FLUXO: REGISTRO DE GASTO DIÁRIO (Início, Interpretação e Confirmação - Mantido da v10) --- 
        # Verifica se o usuário QUER registrar gasto diário
        elif quer_registrar_gasto_diario(msg_lower) and estado.get("ultimo_fluxo") not in ["aguardando_registro_gasto", "aguardando_confirmacao_gasto_diario"]:
            logging.info(f"{from_number} pediu para registrar gasto diário.")
            # Usar mensagem de mensagens.py
            msg_instrucao = mensagens.instrucao_registrar_gasto_diario()
            send_message(from_number, mensagens.estilo_msg(msg_instrucao))
            estado["ultimo_fluxo"] = "aguardando_registro_gasto"
            estado_modificado_fluxo = True
            mensagem_tratada = True
            salvar_estado(from_number, estado)
            logging.info(f"Instruções para registrar gasto diário enviadas para {from_number}. Estado definido.")
            return {"status": "instruções de gasto diário enviadas, aguardando detalhes"}
        # Verifica se a mensagem PARECE um gasto diário E não foi tratada E está no fluxo certo
        elif not mensagem_tratada and estado.get("ultimo_fluxo") in [None, "aguardando_registro_gasto", "cadastro_completo", "saudacao_realizada"]:
            dados_gasto = interpretar_gasto_simples(incoming_msg)
            if dados_gasto:
                # ...(código de interpretação e pedido de confirmação de gasto diário mantido da v10/v12_base)... 
                logging.info(f"Gasto diário interpretado para {from_number}: {dados_gasto}")
                categoria_status = categorizar(dados_gasto["descricao"])
                dados_gasto["categoria_status"] = categoria_status
                
                cat_display = ""
                pergunta_categoria = ""
                if categoria_status.startswith("AMBIGUO:"):
                    partes_amb = categoria_status.split(":")
                    opcoes = partes_amb[2]
                    cat_display = f"❓ Categoria: {opcoes}?" 
                    pergunta_categoria = f"Notei que '{dados_gasto['descricao']}' pode ser {opcoes}. Qual devo usar?"
                    dados_gasto["categoria_final_prov"] = "A definir"
                elif categoria_status != "A definir":
                    cat_display = f"Categoria: {categoria_status}"
                    dados_gasto["categoria_final_prov"] = categoria_status
                else:
                    cat_display = "Categoria: (A definir)" 
                    pergunta_categoria = "Não consegui definir a categoria. Qual devo usar?"
                    dados_gasto["categoria_final_prov"] = "A definir"
                
                valor_fmt = f"R$ {dados_gasto['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                msg_confirmacao = (
                    f"Confirma o registro?\n\n"
                    f"- Descrição: {dados_gasto['descricao']}\n"
                    f"- Valor: {valor_fmt}\n"
                    f"- {cat_display}\n"
                    f"- Forma Pgto: {dados_gasto['forma_pagamento']}\n\n"
                    f"{pergunta_categoria}"
                    f"(Sim / Editar / [Nome da Categoria])"
                )
                
                estado["gasto_diario_pendente_confirmacao"] = dados_gasto
                estado["ultimo_fluxo"] = "aguardando_confirmacao_gasto_diario"
                estado_modificado_fluxo = True
                mensagem_tratada = True
                send_message(from_number, mensagens.estilo_msg(msg_confirmacao))
                logging.info(f"Pedido de confirmação para gasto diário enviado para {from_number}.")
                salvar_estado(from_number, estado)
                return {"status": "aguardando confirmação de gasto diário"}
            else:
                logging.info(f"Mensagem de {from_number} não interpretada como gasto diário simples.")
                pass 
        # Processa confirmação de gasto diário
        elif estado.get("ultimo_fluxo") == "aguardando_confirmacao_gasto_diario":
            # ...(código de registro ou cancelamento de gasto diário mantido da v10/v12_base)... 
            gasto_pendente = estado.get("gasto_diario_pendente_confirmacao")
            resposta_usuario_lower = msg_lower

            if not gasto_pendente:
                logging.error(f"Erro: {from_number} está em aguardando_confirmacao_gasto_diario sem gasto pendente no estado.")
                estado["ultimo_fluxo"] = None
                estado_modificado_fluxo = True
                pass
            else:
                categoria_confirmada = None
                categoria_informada_cap = incoming_msg.strip().capitalize()
                if categoria_informada_cap in CATEGORIAS_VALIDAS:
                    categoria_confirmada = categoria_informada_cap
                    logging.info(f"{from_number} forneceu a categoria '{categoria_confirmada}' para o gasto diário pendente.")
                elif "sim" in resposta_usuario_lower or "yes" in resposta_usuario_lower or "confirmo" in resposta_usuario_lower:
                    if not gasto_pendente["categoria_status"].startswith("AMBIGUO:") and gasto_pendente["categoria_status"] != "A definir":
                        categoria_confirmada = gasto_pendente["categoria_final_prov"]
                        logging.info(f"{from_number} confirmou o registro do gasto diário com categoria {categoria_confirmada}.")
                    else:
                        send_message(from_number, mensagens.estilo_msg(f"Preciso que você me diga a categoria correta para '{gasto_pendente['descricao']}', por favor."))
                        estado_modificado_fluxo = True
                        mensagem_tratada = True
                        salvar_estado(from_number, estado)
                        return {"status": "aguardando categoria para gasto diário"}
                elif "editar" in resposta_usuario_lower or "não" in resposta_usuario_lower or "nao" in resposta_usuario_lower:
                    logging.info(f"{from_number} pediu para editar ou cancelou o registro do gasto diário.")
                    send_message(from_number, mensagens.estilo_msg("Ok, cancelado. Se quiser tentar registrar novamente, é só me enviar os detalhes."))
                    estado["ultimo_fluxo"] = None
                    if "gasto_diario_pendente_confirmacao" in estado: del estado["gasto_diario_pendente_confirmacao"]
                    estado_modificado_fluxo = True
                    mensagem_tratada = True
                else:
                    logging.warning(f"{from_number} respondeu algo inesperado à confirmação de gasto diário: {incoming_msg}")
                    send_message(from_number, mensagens.estilo_msg("Não entendi. Confirma com 'Sim', 'Editar' ou me diga a categoria correta."))
                    estado_modificado_fluxo = True
                    mensagem_tratada = True

                if categoria_confirmada:
                    try:
                        resultado_registro = registrar_gasto(
                            nome_usuario=name,
                            numero_usuario=from_number,
                            descricao=gasto_pendente["descricao"],
                            valor=gasto_pendente["valor"],
                            forma_pagamento=gasto_pendente["forma_pagamento"],
                            categoria_manual=categoria_confirmada
                        )
                        
                        if resultado_registro["status"] == "ok" or resultado_registro["status"] == "ignorado":
                            msg_sucesso = f"✅ Gasto '{gasto_pendente['descricao']}' registrado como {categoria_confirmada}!"
                            if resultado_registro["status"] == "ignorado":
                                msg_sucesso = f"✅ Gasto '{gasto_pendente['descricao']}' ({categoria_confirmada}) já estava registrado."
                            send_message(from_number, mensagens.estilo_msg(msg_sucesso))
                        else:
                            logging.error(f"Erro ao registrar gasto diário confirmado para {from_number}: {resultado_registro.get('mensagem')}")
                            send_message(from_number, mensagens.estilo_msg(f"❌ Ops! Tive um problema ao registrar o gasto '{gasto_pendente['descricao']}'. Tente novamente mais tarde."))
                            
                    except Exception as e:
                        logging.error(f"Exceção ao chamar registrar_gasto para {from_number}: {e}")
                        send_message(from_number, mensagens.estilo_msg(f"❌ Ops! Ocorreu um erro inesperado ao tentar registrar '{gasto_pendente['descricao']}'."))
                    
                    estado["ultimo_fluxo"] = None
                    if "gasto_diario_pendente_confirmacao" in estado: del estado["gasto_diario_pendente_confirmacao"]
                    estado_modificado_fluxo = True
                    mensagem_tratada = True
                
                salvar_estado(from_number, estado)
                return {"status": "confirmação de gasto diário processada"}

        # --- FLUXO: PEDIDO DE RESUMO MENSAL / STATUS LIMITES (Mantido da v10) --- 
        elif quer_resumo_mensal(msg_lower) and not mensagem_tratada:
            logging.info(f"{from_number} pediu resumo mensal ou status dos limites.")
            try:
                resposta_status = consultar_status_limites(from_number)
                send_message(from_number, mensagens.estilo_msg(resposta_status))
            except Exception as e:
                logging.error(f"Erro ao gerar status de limites/resumo para {from_number}: {e}")
                send_message(from_number, mensagens.estilo_msg("Desculpe, tive um problema ao buscar seu resumo financeiro. Tente novamente mais tarde."))
            estado["ultimo_fluxo"] = None
            estado_modificado_fluxo = True
            mensagem_tratada = True
            salvar_estado(from_number, estado)
            return {"status": "resumo/status limites enviado"}

        # --- FLUXO: PEDIDO DE LISTA DE COMANDOS (Mantido da v10) --- 
        elif quer_lista_comandos(msg_lower) and not mensagem_tratada:
            logging.info(f"{from_number} pediu a lista de comandos.")
            resposta_comandos = mensagens.lista_comandos(primeiro_nome)
            send_message(from_number, mensagens.estilo_msg(resposta_comandos))
            estado["ultimo_fluxo"] = None
            estado_modificado_fluxo = True
            mensagem_tratada = True
            salvar_estado(from_number, estado)
            return {"status": "lista de comandos enviada"}
            
        # --- FLUXO GERAL (GPT) --- 
        if not mensagem_tratada:
            logging.info(f"Mensagem de {from_number} não tratada por fluxos específicos. Enviando para GPT.")
            
            contexto_adicional = buscar_conhecimento_relevante(incoming_msg)
            historico_gpt = mensagens_gpt_base.copy()
            if contexto_adicional:
                historico_gpt.append({"role": "system", "content": f"Contexto adicional relevante: {contexto_adicional}"})
            
            historico_conversa = estado.get("historico_chat", [])
            for msg_hist in historico_conversa[-6:]:
                 historico_gpt.append(msg_hist)
            historico_gpt.append({"role": "user", "content": incoming_msg})
            
            try:
                logging.info(f"Chamando GPT para {from_number} com {len(historico_gpt)} mensagens no histórico.")
                # Reduzir max_tokens para tentar controlar verbosidade
                response_gpt = openai.ChatCompletion.create(
                    model="gpt-4-turbo",
                    messages=historico_gpt,
                    temperature=0.7,
                    max_tokens=250 # Reduzido de 300
                )
                resposta_gpt = response_gpt["choices"][0]["message"]["content"].strip()
                tokens_usados = response_gpt["usage"]["total_tokens"]
                logging.info(f"Resposta do GPT recebida para {from_number}. Tokens usados: {tokens_usados}")
                increment_tokens(sheet_usuario, linha_index, tokens_usados)
                
                send_message(from_number, mensagens.estilo_msg(resposta_gpt))
                
                historico_conversa.append({"role": "user", "content": incoming_msg})
                historico_conversa.append({"role": "assistant", "content": resposta_gpt})
                estado["historico_chat"] = historico_conversa[-10:]
                estado["ultimo_fluxo"] = "conversa_gpt"
                estado_modificado_fluxo = True
                mensagem_tratada = True
                
            except Exception as e:
                logging.error(f"[ERRO GPT] Erro ao chamar API OpenAI para {from_number}: {e}")
                send_message(from_number, mensagens.estilo_msg("Desculpe, não consegui processar sua solicitação no momento. Tente novamente mais tarde."))
                mensagem_tratada = True 
                estado_modificado_fluxo = True

        # --- FIM DO PROCESSAMENTO --- 
        
        if estado_modificado_fluxo:
            salvar_estado(from_number, estado)
            logging.info(f"Estado salvo para {from_number} após processamento.")
        else:
            salvar_estado(from_number, estado)
            logging.info(f"Nenhuma modificação de fluxo, mas estado salvo para registrar ultima_msg para {from_number}.")
            
        return {"status": "processamento concluído"}

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logging.exception(f"ERRO INESPERADO ao processar mensagem de {from_number}: {e}")
        try:
            send_message(from_number, mensagens.estilo_msg("Desculpe, ocorreu um erro inesperado ao processar sua mensagem. Já estou verificando o que aconteceu."))
        except Exception as send_err:
            logging.error(f"Falha ao enviar mensagem de erro inesperado para {from_number}: {send_err}")
        raise HTTPException(status_code=500, detail="Erro interno inesperado no servidor.")

@app.get("/")
async def root():
    logging.info("Requisição GET recebida em /")
    return {"message": "Webhook do Conselheiro Financeiro está ativo."}

if __name__ == "__main__":
    import uvicorn
    logging.info("Iniciando servidor Uvicorn para desenvolvimento local...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)