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
from gastos import registrar_gasto, categorizar, corrigir_gasto, atualizar_categoria 
from estado_usuario import salvar_estado, carregar_estado, resetar_estado, resposta_enviada_recentemente, salvar_ultima_resposta
from gerar_resumo import gerar_resumo
from resgatar_contexto import buscar_conhecimento_relevante
from upgrade import verificar_upgrade_automatico
from armazenar_mensagem import armazenar_mensagem
from definir_limite import salvar_limite_usuario
from memoria_usuario import resumo_do_mes, verificar_limites, contexto_principal_usuario
from emocional import detectar_emocao, aumento_pos_emocao
from registrar_gastos_fixos import salvar_gastos_fixos
from planilhas import get_pagantes, get_gratuitos
from engajamento import avaliar_engajamento
from indicadores import get_indicadores
from enviar_alertas import verificar_alertas
from enviar_lembretes import enviar_lembretes
from consultas import consultar_status_limites # Importa a nova função

# Configuração básica de logging (CORRIGIDAlogging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
    with open("prompt.txt", "r", encoding="utf-8") as arquivo_prompt:
        prompt_base = arquivo_prompt.read().strip()
except FileNotFoundError:
    logging.error("ERRO CRÍTICO: Arquivo prompt.txt não encontrado.")
    prompt_base = "Você é um assistente financeiro."
except Exception as e:
    logging.error(f"ERRO CRÍTICO: Falha ao ler prompt.txt: {e}")
    prompt_base = "Você é um assistente financeiro." # Fallback adicionado
    prompt_base = "Você é um assistente financeiro."

# Complemento contextual (revisado para desencorajar menção a ferramentas externas)
complemento_contextual = (
    "Você sempre trata o usuário pelo primeiro nome (que foi informado no início da conversa na resposta à saudação inicial) ou com um vocativo amigável e intimista. "
    "Você nunca recomenda divórcio ou separação por questões financeiras. "
    "O casamento é sagrado, indissolúvel e deve ser defendido com firmeza, clareza e profundidade espiritual. "
    "Seja sempre amigável, intimista, interessado e firme. Utilize explicitamente ensinamentos cristãos, católicos e do Opus Dei. "
    "Utilize o método de comunicação de Dale Carnegie, mostrando-se sempre interessado no usuário, demonstrando escuta ativa. "
    "Não use \'olá\' no início de uma resposta se o usuário já tiver feito a primeira interação. "
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

# === FUNÇÃO PARA INTERPRETAR GASTOS COM GPT (mantida) ===
def interpretar_gasto_com_gpt(mensagem_usuario):
    """Usa o GPT para extrair detalhes de um gasto a partir da mensagem do usuário."""
    prompt_extracao = f"""
Você é um assistente de finanças pessoais. Analise a seguinte mensagem do usuário e extraia as seguintes informações sobre um gasto:
- Descrição do gasto (o que foi comprado/pago)
- Valor do gasto (em formato numérico com ponto decimal, ex: 50.00)
- Forma de pagamento (crédito, débito, pix, boleto, dinheiro. Se não mencionado, retorne N/A)
- Categoria sugerida (escolha uma destas: Alimentação, Transporte, Moradia, Saúde, Lazer, Educação, Vestuário, Doações, Outros. Se não tiver certeza, retorne \'A DEFINIR\')

Mensagem do usuário: "{mensagem_usuario}"

Retorne a resposta APENAS no formato JSON, sem nenhum outro texto antes ou depois:
{{
  "descricao": "...",
  "valor": ..., 
  "forma_pagamento": "...",
  "categoria_sugerida": "..."
}}
"""
    try:
        logging.info(f"Chamando GPT para extrair gasto da mensagem: \'{mensagem_usuario[:50]}...\'")
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo", 
            messages=[{"role": "system", "content": prompt_extracao}],
            temperature=0.1,
        )
        resposta_gpt = response["choices"][0]["message"]["content"].strip()
        logging.info(f"Resposta bruta do GPT (extração): {resposta_gpt}")
        
        # Tenta corrigir JSON malformado (comum com GPT-3.5)
        try:
            dados_gasto = json.loads(resposta_gpt)
        except json.JSONDecodeError:
            logging.warning(f"[GPT JSONDecodeError Inicial] Tentando corrigir JSON: {resposta_gpt}")
            # Tenta encontrar o JSON dentro do texto
            match = re.search(r"\{.*?\}", resposta_gpt, re.DOTALL)
            if match:
                json_str = match.group(0)
                try:
                    dados_gasto = json.loads(json_str)
                    logging.info("JSON corrigido e decodificado com sucesso.")
                except json.JSONDecodeError as e_inner:
                    logging.error(f"[GPT JSONDecodeError Final] Falha ao decodificar JSON mesmo após correção: {json_str}. Erro: {e_inner}")
                    return None
            else:
                logging.error(f"[GPT JSONDecodeError] Não foi possível encontrar ou decodificar JSON na resposta: {resposta_gpt}")
                return None

        if not dados_gasto.get("descricao") or not isinstance(dados_gasto.get("valor"), (int, float)):
            logging.warning("[GPT Gasto] Descrição ou valor inválido/ausente no JSON.")
            return None 
            
        dados_gasto["valor"] = float(dados_gasto["valor"])
        
        logging.info(f"Dados do gasto extraídos com sucesso: {dados_gasto}")
        return dados_gasto
        
    except Exception as e:
        logging.error(f"[ERRO GPT] Erro ao chamar API OpenAI para extração de gasto: {e}")
        return None
# === FIM DA FUNÇÃO DE EXTRAÇÃO ===

# === FUNÇÕES AUXILIARES (planilhas, formatação, envio, etc. - mantidas) ===
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
    return len(text.split()) # Aproximação simples

def send_message(to, body):
    """Envia mensagem via Twilio com logging e tratamento de erro."""
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
    saudacoes = ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "e aí", "opa"]
    text_lower = text.lower().strip()
    return any(text_lower.startswith(sauda) for sauda in saudacoes)

def precisa_direcionamento(msg):
    frases_vagas = ["me ajuda", "preciso de ajuda", "me orienta", "o que eu faço", "não sei por onde começar", "como começar", "tô perdido", "me explica", "quero ajuda", "quero controlar", "quero começar", "começar a usar"]
    msg_lower = msg.lower()
    return any(frase in msg_lower for frase in frases_vagas)

def quer_resumo_mensal(msg):
    msg_lower = msg.lower()
    termos = ["quanto gastei", "resumo do mês", "gastos do mês", "como estão meus gastos", "meu resumo financeiro", "me mostra meus gastos", "meus gastos recentes", "gastando muito", "gastei demais"]
    return any(t in msg_lower for t in termos)

def quer_lista_comandos(texto):
    texto_lower = texto.lower()
    termos = ["quais comandos", "comandos disponíveis", "o que você faz", "como usar", "me ajuda com comandos", "o que posso pedir", "me manda os comandos", "comando", "menu", "como funciona", "/comandos", "/ajuda"]
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

# === WEBHOOK PRINCIPAL ===
@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    logging.info("Recebida requisição POST em /webhook")
    try:
        form = await request.form()
        incoming_msg = form.get("Body", "").strip()
        from_number_raw = form.get("From", "")
        
        if not incoming_msg or not from_number_raw:
            logging.warning("Requisição recebida sem \'Body\' ou \'From\'. Ignorando.")
            return {"status": "requisição inválida"}
            
        from_number = format_number(from_number_raw)
        logging.info(f"Mensagem recebida de {from_number}: \'{incoming_msg[:50]}...\'")

    except Exception as e:
        logging.error(f"Erro ao processar formulário da requisição: {e}")
        raise HTTPException(status_code=400, detail="Erro ao processar dados da requisição.")

    try: # Bloco try principal
        estado = carregar_estado(from_number)
        ultima_msg_registrada = estado.get("ultima_msg", "")

        # Evita processar a mesma mensagem duas vezes (problema comum com webhooks)
        if incoming_msg == ultima_msg_registrada:
            logging.info(f"Mensagem duplicada de {from_number} detectada e ignorada.")
            return {"status": "mensagem duplicada ignorada"}

        estado["ultima_msg"] = incoming_msg # Registra a mensagem atual para evitar duplicidade futura

        # --- SETUP USUÁRIO (mantido) ---
        try:
            sheet_usuario = get_user_sheet(from_number) 
            col_numeros = sheet_usuario.col_values(2)
            linha_index = col_numeros.index(from_number) + 1
            linha_usuario = sheet_usuario.row_values(linha_index)
            logging.info(f"Dados da linha {linha_index} recuperados para {from_number}.")
        except ValueError: 
             logging.error(f"ERRO CRÍTICO: Usuário {from_number} deveria existir na planilha mas index falhou.")
             raise HTTPException(status_code=500, detail="Erro interno crítico ao localizar dados do usuário.")
        except Exception as e: 
             logging.error(f"ERRO CRÍTICO: Falha ao obter dados da linha para {from_number}: {e}")
             # Correção: Completar o HTTPException
             raise HTTPException(status_code=500, detail="Erro interno ao obter dados do usuário.")

        interactions = increment_interactions(sheet_usuario, linha_index)
        logging.info(f"Interações para {from_number}: {interactions}")
        name = linha_usuario[0].strip() if len(linha_usuario) > 0 and linha_usuario[0] else "Usuário"
        email = linha_usuario[2].strip() if len(linha_usuario) > 2 and linha_usuario[2] else None
        tokens_msg = count_tokens(incoming_msg)
        total_tokens = increment_tokens(sheet_usuario, linha_index, tokens_msg)
        logging.info(f"Tokens para {from_number}: +{tokens_msg} = {total_tokens}")
        # --- FIM SETUP USUÁRIO ---

        # --- ALTA PRIORIDADE: DETECTAR INTENÇÃO DE DEFINIR LIMITES ---
        # Check if user wants to define limits NOW, regardless of previous state (unless already waiting)
        msg_lower = incoming_msg.lower() # Ensure msg_lower is defined early
        quer_definir_limites = any(term in msg_lower for term in ["definir limites", "limites por categoria", "colocar limites", "estabelecer limites", "limite de gasto"])
        if quer_definir_limites and estado.get("ultimo_fluxo") != "aguardando_definicao_limites":
             logging.info(f"{from_number} quer definir limites (detecção prioritária).")
             msg_instrucao_limites = (
                 "Entendido! Para definir seus limites, envie a categoria e o valor mensal, um por linha. Exemplo:\n"
                 "Lazer: 500\n"
                 "Alimentação: 1500\n"
                 "Transporte: 300"
             )
             send_message(from_number, mensagens.estilo_msg(msg_instrucao_limites))
             estado["ultimo_fluxo"] = "aguardando_definicao_limites"
             estado_modificado_fluxo = True
             mensagem_tratada = True
             # Salva o estado imediatamente para garantir que o fluxo seja definido
             salvar_estado(from_number, estado)
             logging.info(f"Instruções para definir limites enviadas para {from_number}. Estado definido como 'aguardando_definicao_limites'. Retornando.")
             return {"status": "instruções de limite enviadas, aguardando lista"}
        # --- FLUXO ONBOARDING/CADASTRO ---
        elif is_boas_vindas(incoming_msg): # Mudado para elif
            if not name or name == "Usuário" or not email:
                if estado.get("ultimo_fluxo") != "aguardando_cadastro":
                    logging.info(f"Usuário {from_number} iniciou onboarding.")
                    send_message(from_number, mensagens.estilo_msg(mensagens.solicitacao_cadastro()))
                    estado["ultimo_fluxo"] = "aguardando_cadastro"
                    salvar_estado(from_number, estado)
                else: 
                    logging.info(f"Usuário {from_number} já estava aguardando cadastro.")
                return {"status": "aguardando nome e email"}
            else: # Usuário conhecido
                logging.info(f"Saudação de usuário conhecido: {from_number} ({name}).")
                primeiro_nome = name.split()[0] if name != "Usuário" else ""
                # Envia uma saudação curta e personalizada
                resposta_curta = f"Olá, {primeiro_nome}! Como posso te ajudar hoje?"
                send_message(from_number, mensagens.estilo_msg(resposta_curta))
                # Marca a mensagem como tratada e retorna para evitar duplicidade
                mensagem_tratada = True
                estado_modificado_fluxo = True # Garante que o estado (ultima_msg) seja salvo
                salvar_estado(from_number, estado) # Salva o estado aqui para registrar ultima_msg
                return {"status": "saudação enviada para usuário conhecido"}
                # Não precisa definir estado["saudacao_realizada"] aqui, pois é só uma resposta a uma saudação.
                # O estado será salvo no final se 'mensagem_tratada' ou 'estado_modificado_fluxo' for True.

        if not name or name == "Usuário" or not email:
            logging.info(f"Processando possível resposta de cadastro de {from_number}.")
            nome_capturado = None; email_capturado = None
            linhas = incoming_msg.split("\n")
            for linha in linhas:
                if not nome_capturado and nome_valido(linha): nome_capturado = linha.title().strip()
                if not email_capturado and extract_email(linha): email_capturado = extract_email(linha).lower().strip()
            nome_atualizado = False; email_atualizado = False
            if nome_capturado and (not name or name == "Usuário"):
                try: sheet_usuario.update_cell(linha_index, 1, nome_capturado); name = nome_capturado; nome_atualizado = True; logging.info(f"Nome de {from_number} atualizado para {name}")
                except Exception as e: logging.error(f"[ERRO Planilha] Falha ao atualizar nome para {nome_capturado} (linha {linha_index}): {e}")
            if email_capturado and not email:
                try: sheet_usuario.update_cell(linha_index, 3, email_capturado); email = email_capturado; email_atualizado = True; logging.info(f"Email de {from_number} atualizado para {email}")
                except Exception as e: logging.error(f"[ERRO Planilha] Falha ao atualizar email para {email_capturado} (linha {linha_index}): {e}")
            if not name or name == "Usuário":
                if not email_atualizado: 
                    logging.info(f"Solicitando nome para {from_number}.")
                    send_message(from_number, mensagens.estilo_msg("Ótimo! E qual seu nome completo, por favor? ✍️"))
                    estado["ultimo_fluxo"] = "aguardando_cadastro"; salvar_estado(from_number, estado); return {"status": "aguardando nome"}
            elif not email:
                if not nome_atualizado: 
                    logging.info(f"Solicitando email para {from_number}.")
                    send_message(from_number, mensagens.estilo_msg("Perfeito! Agora só preciso do seu e-mail. 📧"))
                    estado["ultimo_fluxo"] = "aguardando_cadastro"; salvar_estado(from_number, estado); return {"status": "aguardando email"}
            if name and name != "Usuário" and email:
                logging.info(f"Cadastro de {from_number} completo via captura.")
                primeiro_nome = name.split()[0]
                send_message(from_number, mensagens.estilo_msg(mensagens.cadastro_completo(primeiro_nome)))
                estado["ultimo_fluxo"] = "cadastro_completo"; estado["saudacao_realizada"] = True; salvar_estado(from_number, estado); return {"status": "cadastro completo via captura"}
            else:
                logging.info(f"Ainda aguardando dados de cadastro de {from_number}.")
                estado["ultimo_fluxo"] = "aguardando_cadastro"; salvar_estado(from_number, estado); return {"status": "continuando aguardando cadastro"}
        # --- FIM FLUXO ONBOARDING/CADASTRO ---

        # --- INÍCIO PROCESSAMENTO PÓS-CADASTRO ---
        logging.info(f"Iniciando processamento da mensagem pós-cadastro de {from_number}.")
        mensagem_tratada = False 
        estado_modificado_fluxo = False # Flag geral para salvar estado no fim

        # --- INÍCIO FLUXO ESPECÍFICO: CONTROLE DE GASTOS (CORRIGIDO) ---
        msg_lower = incoming_msg.lower()
        # Verifica se o usuário está pedindo sobre controle de gastos
        gatilho_controle_gastos = (
            ("controle" in msg_lower and ("gasto" in msg_lower or "despesa" in msg_lower)) or 
            ("controlar" in msg_lower and ("gasto" in msg_lower or "despesa" in msg_lower)) or 
            ("controle inteligente" in msg_lower and "automático de gastos" in msg_lower) # Pega o texto exato do botão/sugestão
        )

        if gatilho_controle_gastos:
            # Evita re-apresentar as opções se já estiver em um sub-fluxo de gastos
            if estado.get("ultimo_fluxo") not in ["aguardando_escolha_funcao_gastos", "aguardando_forma_pagamento", "aguardando_confirmacao_categoria", "aguardando_definicao_categoria", "aguardando_registro_gasto"]:
                logging.info(f"{from_number} indicou interesse em Controle de Gastos. Apresentando as 3 opções OBJETIVAS.")
                # Mensagem EXATA das 3 opções (como no print do usuário)
                msg_opcoes_gastos = (
                    "🚀 Para um controle eficiente das suas finanças, temos três funções importantes:\n\n"
                    "1️⃣ *Relacionar gastos fixos mensais:* ajuda a entender o seu padrão de vida e garante que você não perca datas importantes, evitando atrasos e juros desnecessários.\n\n"
                    "2️⃣ *Registrar gastos diários:* permite acompanhar de perto seu comportamento financeiro em tempo real, corrigindo pequenos hábitos antes que eles se tornem grandes problemas na fatura.\n\n"
                    "3️⃣ *Definir limites por categoria:* receba alertas automáticos quando estiver próximo do seu limite definido, facilitando ajustes rápidos e mantendo sua vida financeira organizada e equilibrada.\n\n"
                    "Por qual dessas funções gostaria de começar? Para melhor resultado, recomendo utilizar todas! 😉"
                 )
                send_message(from_number, mensagens.estilo_msg(msg_opcoes_gastos))
                estado["ultimo_fluxo"] = "aguardando_escolha_funcao_gastos"
                estado_modificado_fluxo = True
                mensagem_tratada = True
            else:                 logging.info(f"{from_number} mencionou controle de gastos, mas já está em um fluxo relacionado ({estado.get('ultimo_fluxo')}). Ignorando gatilho das 3 opções.")        
        # Verifica se o usuário está respondendo qual função de gastos quer usar
        elif estado.get("ultimo_fluxo") == "aguardando_escolha_funcao_gastos":
            if "2" in msg_lower or "registrar gastos diários" in msg_lower or "gastos diários" in msg_lower:
                logging.info(f"{from_number} escolheu Registrar Gastos Diários.")
                # Mensagem de instrução SIMPLIFICADA para registrar gastos
                msg_instrucao_gastos = (
                    "Ok! Para registrar gastos, me diga o que foi, o valor e como pagou.\n"
                    "Ex: Almoço 55 pix / Uber R$25,30 crédito / Pão 12 débito"
                )
                send_message(from_number, mensagens.estilo_msg(msg_instrucao_gastos))
                estado["ultimo_fluxo"] = "aguardando_registro_gasto" # Estado para indicar que a próxima msg pode ser um gasto
                estado_modificado_fluxo = True
                mensagem_tratada = True
            elif "1" in msg_lower or "gastos fixos" in msg_lower:
                 logging.info(f"{from_number} escolheu Gastos Fixos (Fluxo a implementar)." )
                 # TODO: Implementar fluxo para gastos fixos
                 send_message(from_number, mensagens.estilo_msg("Entendido! A função de registrar gastos fixos ainda está em desenvolvimento, mas logo estará disponível. Que tal começarmos com os gastos diários (opção 2)?"))
                 # Mantém o estado aguardando_escolha_funcao_gastos para permitir escolher outra opção
                 estado_modificado_fluxo = True
                 mensagem_tratada = True
            elif "3" in msg_lower or any(term in msg_lower for term in ["definir limites", "limites por categoria", "colocar limites", "estabelecer limites", "limite de gasto"]):
                 logging.info(f"{from_number} escolheu Definir Limites.")
                 msg_instrucao_limites = (
                     "Entendido! Para definir seus limites, envie a categoria e o valor mensal, um por linha. Exemplo:\n"
                     "Lazer: 500\n"
                     "Alimentação: 1500\n"
                     "Transporte: 300"
                 )
                 send_message(from_number, mensagens.estilo_msg(msg_instrucao_limites))
                 estado["ultimo_fluxo"] = "aguardando_definicao_limites" # Define o estado para aguardar a lista de limites
                 estado_modificado_fluxo = True
                 mensagem_tratada = True
                 # Salva o estado imediatamente e retorna para aguardar a lista
                 salvar_estado(from_number, estado)
                 logging.info(f"Instruções para definir limites enviadas para {from_number} via menu. Estado definido como \'aguardando_definicao_limites\'. Retornando.")
                 return {"status": "instruções de limite enviadas via menu, aguardando lista"}
            else:
                 # Não entendeu a escolha, pede de novo
                 logging.warning(f"{from_number} respondeu algo inesperado à escolha da função de gastos: {incoming_msg}")
                 send_message(from_number, mensagens.estilo_msg("Não entendi qual função você quer usar. Pode me dizer o número (1, 2 ou 3)?"))
                 # Mantém o estado aguardando_escolha_funcao_gastos
                 estado_modificado_fluxo = True
                 mensagem_tratada = True
        # --- FIM FLUXO ESPECÍFICO: CONTROLE DE GASTOS ---

        # --- INÍCIO FLUXO DE REGISTRO DE GASTOS (GPT + CONVERSACIONAL) ---
        # Só entra aqui se não foi tratado pelo fluxo de escolha acima
        if not mensagem_tratada:
            ultimo_fluxo_gasto = estado.get("ultimo_fluxo")
            gasto_pendente = estado.get("gasto_pendente")

            # 1. Resposta sobre FORMA DE PAGAMENTO?
            if ultimo_fluxo_gasto == "aguardando_forma_pagamento" and gasto_pendente:
                logging.info(f"{from_number} respondeu sobre forma de pagamento.")
                forma_pagamento_resposta = incoming_msg.strip().capitalize()
                # Validação simples da forma de pagamento
                formas_validas = ["Crédito", "Debito", "Débito", "Pix", "Boleto", "Dinheiro"]
                forma_encontrada = next((f for f in formas_validas if f.lower() in forma_pagamento_resposta.lower()), None)
                
                if forma_encontrada:
                    gasto_pendente["forma_pagamento"] = forma_encontrada
                    categoria_sugerida = gasto_pendente.get("categoria_sugerida", "A DEFINIR")
                    valor_formatado = f"R${gasto_pendente['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    if categoria_sugerida != "A DEFINIR":
                        mensagem_confirmacao = f"Entendido: {gasto_pendente['descricao']} - {valor_formatado} ({forma_encontrada}).\nSugeri a categoria *{categoria_sugerida}*. Está correto? (Sim/Não/Ou diga a categoria certa)"
                        estado["ultimo_fluxo"] = "aguardando_confirmacao_categoria"
                    else:
                        mensagem_confirmacao = f"Entendido: {gasto_pendente['descricao']} - {valor_formatado} ({forma_encontrada}).\nQual seria a categoria para este gasto? (Ex: Alimentação, Transporte, Lazer...)"
                        estado["ultimo_fluxo"] = "aguardando_definicao_categoria"
                    estado_modificado_fluxo = True
                    send_message(from_number, mensagens.estilo_msg(mensagem_confirmacao))
                    mensagem_tratada = True
                else:
                    logging.warning(f"Forma de pagamento inválida ou não reconhecida de {from_number}: \'{incoming_msg}\'")
                    send_message(from_number, mensagens.estilo_msg("Não entendi a forma de pagamento. Pode repetir? (crédito, débito, pix, etc.)"))
                    # Mantém o estado aguardando_forma_pagamento
                    estado_modificado_fluxo = True 
                    mensagem_tratada = True

            # 2. Resposta sobre CONFIRMAÇÃO DE CATEGORIA?
            elif ultimo_fluxo_gasto == "aguardando_confirmacao_categoria" and gasto_pendente:
                logging.info(f"{from_number} respondeu sobre confirmação de categoria.")
                resposta_categoria = incoming_msg.strip().lower()
                categoria_final = ""
                if resposta_categoria in ["sim", "s", "correto", "ok", "isso", "tá certo", "pode ser"]:
                    categoria_final = gasto_pendente.get("categoria_sugerida")
                elif resposta_categoria not in ["não", "nao", "errado"]:
                    # Assume que a resposta é a categoria correta
                    categoria_final = incoming_msg.strip().capitalize()
                    # Remove prefixo "Categoria:" se existir (case-insensitive)
                    if categoria_final.lower().startswith("categoria:"):
                        categoria_final = categoria_final[len("categoria:"):].strip()
                
                if categoria_final:
                    logging.info(f"Categoria final definida para gasto de {from_number}: {categoria_final}")
                    fuso = pytz.timezone("America/Sao_Paulo"); hoje = datetime.datetime.now(fuso).strftime("%d/%m/%Y")
                    resposta_registro = registrar_gasto(nome_usuario=name, numero_usuario=from_number, descricao=gasto_pendente["descricao"], valor=gasto_pendente["valor"], forma_pagamento=gasto_pendente["forma_pagamento"], data_gasto=hoje, categoria_manual=categoria_final)
                    if resposta_registro["status"] == "ok":
                        valor_formatado = f"R${gasto_pendente['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        send_message(from_number, mensagens.estilo_msg(f"✅ Gasto registrado: {gasto_pendente['descricao']} ({valor_formatado}) em {categoria_final}."))
                        resetar_estado(from_number); estado = carregar_estado(from_number) # Limpa estado após sucesso e recarrega
                    elif resposta_registro["status"] == "ignorado":
                         send_message(from_number, mensagens.estilo_msg("📝 Hmm, parece que esse gasto já foi registrado antes."))
                         resetar_estado(from_number); estado = carregar_estado(from_number) # Limpa estado mesmo se ignorado e reca                    else:
                         send_message(from_number, mensagens.estilo_msg(f"⚠️ Tive um problema ao registrar o gasto na planilha: {resposta_registro.get('mensagem', 'Erro desconhecido')}. Por favor, tente de novo ou verifique mais tarde."))
                         logging.error(f"[ERRO REGISTRO GASTO] {resposta_registro.get('mensagem')}")
                         resetar_estado(from_number); estado = carregar_estado(from_number) # Limpa estado após erro e recarrega
                    mensagem_tratada = True
                else: # Usuário respondeu \'não\' ou algo não reconhecido como categoria
                    logging.info(f"{from_number} negou categoria sugerida ou respondeu \'não\'. Pedindo a correta.")
                    send_message(from_number, mensagens.estilo_msg("Ok. Qual seria a categoria correta para este gasto?"))
                    estado["ultimo_fluxo"] = "aguardando_definicao_categoria"
                    estado_modificado_fluxo = True
                        # 3. Resposta sobre DEFINIÇÃO DE CATEGORIA?
            elif ultimo_fluxo_gasto == "aguardando_definicao_categoria" and gasto_pendente:
                logging.info(f"{from_number} respondeu definindo a categoria.")
                categoria_resposta = incoming_msg.strip().capitalize()
                if categoria_resposta and len(categoria_resposta) > 2: # Validação mínima da categoria
                    logging.info(f"Categoria final definida para gasto de {from_number}: {categoria_resposta}")
                    fuso = pytz.timezone("America/Sao_Paulo"); hoje = datetime.datetime.now(fuso).strftime("%d/%m/%Y")
                    resposta_registro = registrar_gasto(nome_usuario=name, numero_usuario=from_number, descricao=gasto_pendente["descricao"], valor=gasto_pendente["valor"], forma_pagamento=gasto_pendente["forma_pagamento"], data_gasto=hoje, categoria_manual=categoria_resposta)
                    if resposta_registro["status"] == "ok":
                        valor_formatado = f"R${gasto_pendente['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        send_message(from_number, mensagens.estilo_msg(f"✅ Gasto registrado: {gasto_pendente['descricao']} ({valor_formatado}) em {categoria_resposta}."))
                        resetar_estado(from_number); estado = carregar_estado(from_number) # Limpa estado após sucesso e recarrega
                    elif resposta_registro["status"] == "ignorado":
                         send_message(from_number, mensagens.estilo_msg("📝 Hmm, parece que esse gasto já foi registrado antes."))
                         resetar_estado(from_number); estado = carregar_estado(from_number) # Limpa estado mesmo se ignorado e recarrega
                    else:
                         send_message(from_number, mensagens.estilo_msg(f"⚠️ Tive um problema ao registrar o gasto na planilha: {resposta_registro.get('mensagem', 'Erro desconhecido')}. Por favor, tente de novo ou verifique mais tarde."))
                         logging.error(f"[ERRO REGISTRO GASTO] {resposta_registro.get('mensagem')}")
                         resetar_estado(from_number); estado = carregar_estado(from_number) # Limpa estado após erro e recarrega
                    mensagem_tratada = True
                else:
                    logging.warning(f"Categoria inválida ou muito curta de {from_number}: '{incoming_msg}'")
                    send_message(from_number, mensagens.estilo_msg("Não entendi a categoria. Pode me dizer de novo? (Ex: Alimentação, Transporte, Lazer...)"))
                    # Mantém o estado aguardando_definicao_categoria
                    estado_modificado_fluxo = True
                    mensagem_tratada = True

            # === INÍCIO FLUXO DEFINIÇÃO DE LIMITES (Adaptado do ChatGPT) ===
            elif estado.get("ultimo_fluxo") == "aguardando_definicao_limites":
                logging.info(f"{from_number} enviou mensagem para definir limites.")
                linhas_limites = incoming_msg.strip().split('\n')
                limites_salvos, limites_erro = [], []
                numero_usuario_fmt = format_number(from_number)

                for linha in linhas_limites:
                    linha = linha.strip()
                    # Ignora linhas vazias ou comentários/confirmações simples (mais específico)
                    if not linha or re.match(r"^(certo|ok|entendido|beleza|blz|sim|tá bom|tabom|tá|ta)\.?$", linha, re.I):
                        logging.info(f"Ignorando linha irrelevante/comentário: '{linha}'")
                        continue
                    # Ignora explicitamente o cabeçalho "Limites:" (case-insensitive)
                    if linha.strip().lower() == "limites:":
                        logging.info(f"Ignorando cabeçalho 'Limites:': '{linha}'")
                        continue

                    # Regex para capturar Categoria e Valor (mais tolerante)
                    match = re.match(r"^\s*([a-zA-ZÀ-ú\s]+?)\s*[:\-]?\s*(R\$)?\s*([\d.,]+)\s*(/mês)?\s*$", linha, re.I)

                    if match:
                        categoria = match.group(1).strip().capitalize()
                        valor_str_raw = match.group(3).replace('.', '').replace(',', '.').strip()

                        try:
                            valor = float(valor_str_raw)
                            if valor > 0:
                                # Chama a função para salvar o limite (agora retorna True/False)
                                sucesso_salvar = salvar_limite_usuario(numero_usuario_fmt, categoria, valor, "mensal")
                                
                                if sucesso_salvar:
                                    # Formata valor para exibição (R$ 1.234,56)
                                    valor_fmt = f"R${valor:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
                                    limites_salvos.append(f"✅ {categoria}: {valor_fmt}/mês")
                                else:
                                    # Adiciona erro específico de falha ao salvar
                                    limites_erro.append(f"❌ Erro ao salvar limite para '{categoria}'. Verifique os logs ou tente novamente.")
                                    logging.error(f"Falha retornada por salvar_limite_usuario para {categoria} do usuário {numero_usuario_fmt}.")
                            else: # Este else corresponde ao if valor > 0
                                limites_erro.append(f"❌ Valor inválido (não positivo) para '{categoria}': {valor_str_raw}")

                        except ValueError:
                            limites_erro.append(f"❌ Valor numérico inválido para '{categoria}': {valor_str_raw}")
                        except Exception as e:
                            limites_erro.append(f"❌ Erro inesperado ao salvar '{categoria}': {str(e)}")
                            logging.error(f"Falha crítica ao salvar limite '{categoria}': {str(e)}")

                    else:
                        limites_erro.append(f"❌ Formato inválido na linha: '{linha}' (Use: Categoria Valor. Ex: Lazer 500)")

                # Se chegou aqui, a mensagem foi processada (com sucesso ou erro de formato)
                resposta = ""
                if limites_salvos:
                    # Mantém a lista de sucessos
                    resposta += "\n💡 Limites definidos:\n" + "\n".join(limites_salvos)

                if limites_erro:
                    # Mantém a lista de erros
                    resposta += "\n❌ Linhas com erro:\n" + "\n".join(limites_erro)
                
                # Adiciona frase final apenas se houve sucesso e nenhum erro de formato
                if limites_salvos and not limites_erro:
                    resposta += "\n\nOk! Limites registrados. 👀"
                # Se só houve erros, a resposta já os contém.
                # Se não houve nem sucesso nem erro (caso tratado acima), esta parte não é executada.

                # Reset state because we processed the expected list (or found format errors in it)
                logging.info(f"Resetando estado para {from_number} após processar/tentar processar limites.")
                resetar_estado(from_number)
                estado = carregar_estado(from_number) # Reload local state to reflect the reset immediately

                # Send the final confirmation/error message AFTER resetting the state
                send_message(from_number, mensagens.estilo_msg(resposta))

                # No need to set estado_modificado_fluxo = False, as the state IS modified (reset)
                # Let the final save handle it if needed, though reset should persist.
                mensagem_tratada = True # Mark message as handled by this block
                logging.info("Fluxo de definição de limites concluído (sucesso ou erro de formato), estado resetado.")
            # === FIM FLUXO DEFINIÇÃO DE LIMITES ===
                    
            # 4. TENTA INTERPRETAR COMO NOVO GASTO(S)
            # Só tenta se não estava em nenhum fluxo de gasto anterior E se o estado indica que pode ser um gasto
            elif estado.get("ultimo_fluxo") == "aguardando_registro_gasto" or not estado.get("ultimo_fluxo"):
                linhas_mensagem = incoming_msg.strip().split('\n')
                gastos_processados = []
                gastos_pendentes_confirmacao = []
                linhas_com_erro = []
                primeiro_gasto_pendente = None # Para lidar com o fluxo conversacional do primeiro item pendente
                mensagem_tratada = False # Inicializa como False, será True se algum gasto for processado ou pendente

                # Verifica se a mensagem provavelmente contém gastos (heurística na mensagem inteira primeiro)
                contem_valor = any(char.isdigit() for char in incoming_msg)
                palavras_chave_gasto = ["gastei", "paguei", "comprei", "custou", "foi R$", "deu R$", "gasto de", "compra de"]
                pediu_resumo = quer_resumo_mensal(incoming_msg) or any(t in incoming_msg.lower() for t in ["resumo do dia", "resumo de hoje", "/resumo"])
                pediu_comandos = quer_lista_comandos(incoming_msg)

                indica_gasto_geral = contem_valor and not pediu_resumo and not pediu_comandos and \
                                       (re.search(r'R\$\s*\d|\d+\s*(reais|real)', incoming_msg, re.IGNORECASE) or \
                                        any(p in incoming_msg.lower() for p in palavras_chave_gasto))

                # Só prossegue se parecer conter gastos e tiver mais de uma linha OU a linha única parecer um gasto
                if indica_gasto_geral and (len(linhas_mensagem) > 1 or (len(linhas_mensagem) == 1 and indica_gasto_geral)):
                    logging.info(f"Mensagem de {from_number} parece conter gasto(s). Processando {len(linhas_mensagem)} linha(s)...")
                    mensagem_tratada = True # Assume que vamos tratar isso, mesmo que algumas linhas falhem

                    for linha in linhas_mensagem:
                        linha = linha.strip()
                        if not linha: continue # Pula linhas vazias

                        # Heurística por linha (opcional, pode confiar apenas no GPT)
                        contem_valor_linha = any(char.isdigit() for char in linha)
                        if not contem_valor_linha and len(linhas_mensagem) > 1: # Só ignora se for multilinha
                             logging.info(f"Linha '{linha[:30]}...' ignorada (sem valor numérico em contexto multilinha).")
                             continue
                        elif not contem_valor_linha and len(linhas_mensagem) == 1:
                             # Se for linha única e não tiver valor, provavelmente não é gasto
                             logging.info(f"Linha única '{linha[:30]}...' sem valor numérico. Não parece gasto.")
                             mensagem_tratada = False # Reverte, deixa cair na conversa geral
                             break # Sai do loop de l                        logging.info(f"Tentando interpretar linha via GPT: 	\'{linha[:50]}...\		\'")
                        dados_gasto_gpt = interpretar_gasto_com_gpt(linha)
                        if dados_gasto_gpt:
                            # Ex: "Clube Frédéric - 476,00 - Pix - Frédéric" -> Captura "Frédéric"
                            # Procura por " - " seguido por texto até o fim da linha (após o último " - ")
                            match_cat_explicita = re.search(r'.*-\s*(.+)$', linha)
                            if match_cat_explicita:
                                # Verifica se o que foi capturado não é apenas a forma de pagamento (caso comum)
                                cat_potencial = match_cat_explicita.group(1).strip()
                                formas_pagamento_lower = ["crédito", "debito", "débito", "pix", "boleto", "dinheiro"]
                                if cat_potencial.lower() not in formas_pagamento_lower:
                                    categoria_explicita = cat_potencial.capitalize()
                                    logging.info(f"Categoria explícita encontrada na linha: 	\'{categoria_explicita}\	'")
                            # --- FIM EXTRAÇÃO CATEGORIA EXPLÍCITA ---

                            # Verifica se temos informações mínimas
                            if not descricao or valor is None:
                                logging.warning(f"GPT retornou dados incompletos para linha 	\'{linha[:30]}...\	': {dados_gasto_gpt}")
                                linhas_com_erro.append(f"❓ Não consegui extrair detalhes de: 	\'{linha}\	'")
                                continue

                            # Define a categoria final: Prioriza explícita > Sugerida pelo GPT (se válida)
                            categoria_final = categoria_explicita if categoria_explicita else categoria_sugerida_gpt
                            if not categoria_final or categoria_final == "A DEFINIR":
                                categoria_final = None # Indica que precisa ser definida

                            if forma_pagamento and forma_pagamento != "N/A":
                                if categoria_final:
                                    # Todas as informações presentes, registra diretamente
                                    logging.info(f"Gasto completo na linha 	\'{linha[:30]}...\	'. Registrando diretamente com categoria 	\'{categoria_final}\	'.")
                                    fuso = pytz.timezone("America/Sao_Paulo"); hoje = datetime.datetime.now(fuso).strftime("%d/%m/%Y")
                                    resposta_registro = registrar_gasto(nome_usuario=name, numero_usuario=from_number, descricao=descricao, valor=valor, forma_pagamento=forma_pagamento, data_gasto=hoje, categoria_manual=categoria_final)
                                    valor_fmt_reg = f"R${valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                                    if resposta_registro["status"] == "ok":
                                        gastos_processados.append(f"✅ {descricao} ({valor_fmt_reg}) em {categoria_final}")
                                    elif resposta_registro["status"] == "ignorado":
                                        gastos_processados.append(f"📝 {descricao} ({valor_fmt_reg}) - Já registrado")
                                    else:
                                         linhas_com_erro.append(f"⚠️ Erro ao registrar 	\'{descricao}\': {resposta_registro.get(	'mensagem', 'Desconhecido')}")
                                else:
                                    # Falta categoria
                                    logging.info(f"Gasto na linha 	\'{linha[:30]}...\	' precisa de categoria.")
                                    dados_gasto_gpt["linha_original"] = linha # Guarda linha original para contexto
                                    gastos_pendentes_confirmacao.append({"tipo": "definicao_categoria", "dados": dados_gasto_gpt})
                                    if not primeiro_gasto_pendente: primeiro_gasto_pendente = gastos_pendentes_confirmacao[-1]
                            else:
                                # Falta forma de pagamento (pode faltar categoria também)
                                logging.info(f"Gasto na linha 	\'{linha[:30]}...\	' precisa de forma de pagamento.")
                                dados_gasto_gpt["linha_original"] = linha # Guarda linha original para contexto
                                gastos_pendentes_confirmacao.append({"tipo": "forma_pagamento", "dados": dados_gasto_gpt})
                                if not primeiro_gasto_pendente: primeiro_gasto_pendente = gastos_pendentes_confirmacao[-1]
                    
                    # Saiu do loop de linhas, agora compila a resposta
                    resposta_final = [] # Inicializa aqui para garantir que sempre exista
                    if not mensagem_tratada: # Se foi revertido no loop (linha única sem valor)
                         logging.info(f"Mensagem '{incoming_msg[:50]}...' de {from_number} não parece ser um gasto novo. Seguindo para conversa/comandos.")
                    else:
                        # --- Processamento Pós-Loop ---
                        if gastos_processados:
                            resposta_final.append("*Gastos Registrados:*")
                            resposta_final.extend(gastos_processados)

                        if linhas_com_erro:
                            if resposta_final: resposta_final.append("") # Adiciona separador
                            resposta_final.append("*Gastos que deram ruim:*")
                            resposta_final.extend(linhas_com_erro)

                        if primeiro_gasto_pendente:
                            # Pergunta sobre o primeiro item pendente
                            if resposta_final: resposta_final.append("") # Adiciona separador
                            gasto_pend = primeiro_gasto_pendente["dados"]
                            valor_fmt = f"R${gasto_pend['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

                            if primeiro_gasto_pendente["tipo"] == "forma_pagamento":
                                pergunta = f"Para o gasto '{gasto_pend['descricao']}' ({valor_fmt}), como você pagou (crédito, débito, pix, etc.)?"
                                estado["ultimo_fluxo"] = "aguardando_forma_pagamento"
                            elif primeiro_gasto_pendente["tipo"] == "definicao_categoria":
                                 cat_sug = gasto_pend.get("categoria_sugerida") # Verifica se GPT sugeriu algo
                                 if cat_sug and cat_sug != "A DEFINIR":
                                      pergunta = f"Para '{gasto_pend['descricao']}' ({valor_fmt}, {gasto_pend['forma_pagamento']}), sugeri a categoria *{cat_sug}*. Está correto? (Sim/Não/Ou diga a categoria certa)"
                                      estado["ultimo_fluxo"] = "aguardando_confirmacao_categoria"
                                 else:
                                      pergunta = f"Para '{gasto_pend['descricao']}' ({valor_fmt}, {gasto_pend['forma_pagamento']}), qual seria a categoria? (Ex: Alimentação, Transporte...)"
                                      estado["ultimo_fluxo"] = "aguardando_definicao_categoria"

                            resposta_final.append(pergunta)
                            estado["gasto_pendente"] = gasto_pend # Guarda o primeiro item pendente
                            # Guarda os itens pendentes restantes para processamento posterior (se necessário, complexo)
                            # estado["gastos_pendentes_lista"] = gastos_pendentes_confirmacao[1:]
                            estado_modificado_fluxo = True
                        elif not gastos_processados and not linhas_com_erro:
                             # Caso estranho: indica_gasto_geral foi True, mas nada processado/pendente/erro
                             logging.info(f"Mensagem de {from_number} parecia gasto, mas nenhuma linha resultou em ação.")
                             mensagem_tratada = False # Deixa cair na conversa geral
                        elif not primeiro_gasto_pendente:
                             # Todos processados ou falharam, sem itens pendentes
                             resetar_estado(from_number); estado = carregar_estado(from_number) # Reseta estado pois o processamento multilinha terminou e recarrega
                             estado_modificado_fluxo = False # Estado foi resetado

                        if resposta_final:
                            send_message(from_number, mensagens.estilo_msg("\n".join(resposta_final)))
                        elif not mensagem_tratada: # Se chegou aqui sem resposta final e msg não tratada
                             pass # Deixa cair na conversa geral
                        # Se só houve erros, a resposta_final já contém os erros e será enviada

                # Se a verificação inicial não indicou gastos
                elif not indica_gasto_geral:
                     logging.info(f"Mensagem '{incoming_msg[:50]}...' de {from_number} não parece ser um gasto novo. Seguindo para conversa/comandos.")
                     # mensagem_tratada permanece False

            # Fallback se não tratado pelo fluxo de registro de gastos
            else:
                 logging.info(f"Mensagem de {from_number} não tratada pelo fluxo de registro de gastos (estado atual: {estado.get('ultimo_fluxo')}). Seguindo...")
                 # mensagem_tratada permanece Falseue
        # --- FIM FLUXO DE REGISTRO DE GASTOS ---

        # --- FLUXOS DE COMANDOS E CONVERSA GERAL (Só entra se não foi tratado antes) ---
        if not mensagem_tratada:
            logging.info(f"Mensagem de {from_number} não tratada por fluxos específicos, seguindo para comandos/conversa...")
            
            if quer_lista_comandos(incoming_msg):
                logging.info(f"Enviando lista de comandos para {from_number}.")
                comandos_txt = (
                    "📋 *Comandos disponíveis:*\n"
                    "/resumo – Ver seu resumo financeiro do dia\n"
                    "/limites – Mostrar seus limites por categoria\n"
                    "/ajuda – Mostrar esta lista de comandos\n\n"
                    "💡 *Para registrar gastos, apenas me diga o que gastou!*\n"
                    "Ex: \'Gastei 50 reais no almoço com pix\' ou \'Compra de pão por 10 reais no débito\\'"
                )
                send_message(from_number, mensagens.estilo_msg(comandos_txt))
                mensagem_tratada = True 
                resetar_estado(from_number) # Limpa estado após comando
            
            elif quer_resumo_mensal(incoming_msg):
                logging.info(f"Gerando resumo mensal para {from_number}.")
                resumo = resumo_do_mes(from_number); limites_txt = verificar_limites(from_number)
                send_message(from_number, mensagens.estilo_msg(resumo + "\n\n" + limites_txt))
                mensagem_tratada = True
                resetar_estado(from_number) # Limpa estado após comando

            elif any(t in incoming_msg.lower() for t in ["resumo do dia", "resumo de hoje", "quanto gastei hoje", "novo resumo", "resumo agora", "resumo atualizado", "quero o resumo", "meu resumo", "resumo aqui", "/resumo"]):
                logging.info(f"Gerando resumo diário para {from_number}.")
                resumo = gerar_resumo(from_number, periodo="diario")
                send_message(from_number, mensagens.estilo_msg(resumo))
                mensagem_tratada = True
                resetar_estado(from_number) # Limpa estado após comando

            elif any(t in incoming_msg.lower() for t in ["resumo de ontem", "quanto gastei ontem"]):
                logging.info(f"Gerando resumo de ontem para {from_number}.")
                ontem = datetime.datetime.now(pytz.timezone("America/Sao_Paulo")) - datetime.timedelta(days=1)
                resumo = gerar_resumo(from_number, periodo="custom", data_personalizada=ontem.date())
                send_message(from_number, mensagens.estilo_msg(resumo))
                mensagem_tratada = True
                resetar_estado(from_number) # Limpa estado após comando

            # --- NOVO: Consulta Status dos Limites ---
            elif any(t in msg_lower for t in ["como estão meus limites", "status dos limites", "limites gastos", "ver limites", "meus limites"]):
                logging.info(f"Consultando status dos limites para {from_number}.")
                numero_usuario_fmt = format_number(from_number)
                status_limites_msg = consultar_status_limites(numero_usuario_fmt)
                send_message(from_number, mensagens.estilo_msg(status_limites_msg))
                mensagem_tratada = True
                resetar_estado(from_number) # Limpa estado após comando
            # --- FIM Consulta Status dos Limites ---
                
            # Lógica de Upgrade (mantida)
            if not mensagem_tratada and verificar_upgrade_automatico(from_number):
                 logging.info(f"Informando {from_number} sobre upgrade automático.")
                 send_message(from_number, mensagens.estilo_msg("🔓 Seu acesso premium foi liberado!\nBem-vindo ao grupo dos que escolheram dominar a vida financeira com dignidade e IA de primeira. 🙌"))
                 # Não marca como tratada para permitir que a mensagem original seja processada se houver mais conteúdo

            # Alerta de limite gratuito (mantido)
            user_status = get_user_status(from_number)
            if not mensagem_tratada and user_status == "Gratuitos" and passou_limite(sheet_usuario, linha_index):
                    logging.warning(f"Usuário gratuito {from_number} atingiu o limite de interações.")
                    contexto_usuario = contexto_principal_usuario(from_number, ultima_msg=incoming_msg)
                    mensagem_alerta = mensagens.alerta_limite_gratuito(contexto_usuario)
                    send_message(from_number, mensagens.estilo_msg(mensagem_alerta, leve=False))
                    salvar_estado(from_number, estado); return {"status": "limite gratuito atingido"}

            # --- CONVERSA GERAL COM GPT (Só se nada mais tratou) --- 
            if not mensagem_tratada:
                logging.info(f"Iniciando fluxo de conversa geral com GPT para {from_number}...")
                # Limpa estado pendente se chegou aqui (evita loops)
                if estado.get("ultimo_fluxo") and estado.get("ultimo_fluxo").startswith("aguardando_"):
                    logging.warning(f"Limpando estado pendente {estado.get('ultimo_fluxo')} antes da conversa geral para {from_number}.")
                    resetar_estado(from_number)
                    estado = carregar_estado(from_number) # Recarrega estado limpo
                    estado["ultima_msg"] = incoming_msg # Mantém a msg atual
                    
                conversa_path = f"conversas/{from_number}.txt"
                if not os.path.exists("conversas"): os.makedirs("conversas")
                if not os.path.isfile(conversa_path): 
                   with open(conversa_path, "w", encoding="utf-8") as f: f.write("")                
                # Bloco try/except para leitura do histórico (CORRIGIDO)
                linhas_conversa = []
                try:
                    with open(conversa_path, "r", encoding="utf-8") as f:
                        linhas_conversa = f.readlines()
                except Exception as e:
                    logging.error(f"Falha ao ler histórico {conversa_path}: {e}")
                
                # Filtra histórico (opcional, pode ajustar)
                historico_filtrado = [l for l in linhas_conversa if not any(f in l.lower() for f in ["sou seu conselheiro financeiro","perfeito,","tô aqui pra te ajudar","posso te ajudar com controle de gastos","por onde quer começar"])]
                historico_relevante = historico_filtrado[-6:] # Pega as últimas 6 linhas (3 turnos)
                
                mensagens_para_gpt = list(mensagens_gpt_base) 
                
                # Adiciona contexto Knowledge se não for pedido de resumo/comando
                termos_resumo_comando = ["resumo", "quanto gastei", "gastos hoje", "/resumo", "/comandos", "/ajuda", "comandos"]
                if not any(t in incoming_msg.lower() for t in termos_resumo_comando):
                    categoria_detectada_conversa = "geral"
                    texto_lower_conversa = incoming_msg.lower()
                    PALAVRAS_CHAVE_CATEGORIAS = {"espiritualidade": ["oração", "culpa", "confissão", "direção espiritual", "vida espiritual", "fé", "deus", "confessar"], "financeiro": ["gasto", "dinheiro", "investimento", "renda", "salário", "orçamento", "juros", "empréstimo", "dívida"], "casamento": ["cônjuge", "esposa", "marido", "matrimônio", "casamento", "vida a dois", "parceiro"], "filosofia": ["virtude", "temperamento", "aristóteles", "santo tomás", "ética", "filosofia", "psicologia"]}
                    for cat, pals in PALAVRAS_CHAVE_CATEGORIAS.items():
                        if any(p in texto_lower_conversa for p in pals): categoria_detectada_conversa = cat; break
                    contexto_resgatado = buscar_conhecimento_relevante(incoming_msg, categoria=categoria_detectada_conversa, top_k=3)
                    if contexto_resgatado:
                        logging.info(f"Adicionando contexto Knowledge ({categoria_detectada_conversa}) para {from_number}.")
                        mensagens_para_gpt.append({"role": "system", "content": f"Contexto relevante:\n{contexto_resgatado}"}) 
                    else: logging.info(f"Nenhum contexto Knowledge encontrado para \'{incoming_msg[:30]}...\' ({categoria_detectada_conversa}).")
                
                # Adiciona histórico da conversa
                for linha in historico_relevante:
                    try:
                        partes = linha.split(":", 1)
                        if len(partes) == 2:
                            role = "user" if "Usuário:" in partes[0] else "assistant"
                            conteudo = partes[1].strip()
                            if conteudo: mensagens_para_gpt.append({"role": role, "content": conteudo})
                    except Exception as e: logging.error(f"Falha ao processar linha do histórico: {linha} - {e}")
                
                # Adiciona mensagem atual do usuário
                mensagens_para_gpt.append({"role": "user", "content": incoming_msg})
                
                # Adiciona indicadores econômicos se relevante
                termos_macro = ["empréstimo", "juros", "selic", "ipca", "cdi", "inflação", "investimento", "cenário econômico"]
                if any(p in incoming_msg.lower() for p in termos_macro):
                    indicadores = get_indicadores()
                    if indicadores:
                        texto_indicadores = "\n".join([f"{n.upper()}: {v}%" if isinstance(v, (int, float)) else f"{n.upper()}: {v}" for n, v in indicadores.items() if v is not None])
                        mensagens_para_gpt.append({"role": "system", "content": f"Indicadores econômicos atuais:\n{texto_indicadores}"})
                
                # Chama GPT para conversa
                try:
                    logging.info(f"Chamando GPT para conversa de {from_number} ({len(mensagens_para_gpt)} mensagens)." )
                    response = openai.ChatCompletion.create(model="gpt-4-turbo", messages=mensagens_para_gpt, temperature=0.7)
                    reply = response["choices"][0]["message"]["content"].strip()
                    logging.info(f"Resposta GPT (conversa) para {from_number}: \'{reply[:50]}...\'")
                except Exception as e:
                    logging.error(f"[ERRO OpenAI Conversa] {e}")
                    reply = "⚠️ Tive um problema ao processar sua mensagem agora. Poderia tentar de novo, por favor?"
                
                # Pós-processamento da resposta
                # reply = re.sub(r'^(oi|olá|opa|e aí)[,.!]?\s*', '', reply, flags=re.IGNORECASE).strip() # REMOVIDO - Pode causar problemas com respostas curtas
                if "[Nome]" in reply:
                    primeiro_nome = name.split()[0] if name and name != "Usuário" else ""
                    reply = reply.replace("[Nome]", primeiro_nome)
                
                # Disclaimer para tópicos sensíveis
                assuntos_sensiveis = ["violência", "agressão", "abuso", "depressão", "ansiedade", "suicídio", "terapia"]
                if any(t in incoming_msg.lower() for t in assuntos_sensiveis):
                    disclaimer = "\n\n⚠️ *Lembre-se: Sou uma IA e não substituo acompanhamento profissional especializado.*"
                    if disclaimer not in reply: reply += disclaimer
                
                # Salva no histórico e envia
                try:
                    with open(conversa_path, "a", encoding="utf-8") as f:
                        f.write(f"Usuário: {incoming_msg}\n")
                        f.write(f"Conselheiro: {reply}\n")
                except Exception as e: logging.error(f"Falha ao salvar conversa {conversa_path}: {e}")
                
                if reply: send_message(from_number, mensagens.estilo_msg(reply))
                else: logging.warning(f"Resposta vazia do GPT para conversa de {from_number}."); send_message(from_number, mensagens.estilo_msg("Não entendi muito bem. Pode reformular, por favor?"))
                
                mensagem_tratada = True 
            # --- FIM CONVERSA GERAL --- 

        # Fallback final se nada tratou a mensagem
        if not mensagem_tratada:
             logging.warning(f"Mensagem de {from_number} não tratada por nenhum fluxo: \'{incoming_msg}\'")
             send_message(from_number, mensagens.estilo_msg("Hmm, não tenho certeza de como ajudar com isso agora. Pode tentar de outra forma?"))
             resetar_estado(from_number) # Limpa estado em caso de falha total

        # --- FINALIZAÇÃO (Logs de emoção, salvar estado) ---
        try:
            fuso = pytz.timezone("America/Sao_Paulo"); data_msg_str = datetime.datetime.now(fuso).strftime("%Y-%m-%d %H:%M:%S")
            emocao = detectar_emocao(incoming_msg)
            if emocao: alerta_emocao = aumento_pos_emocao(from_number, emocao, data_msg_str); logging.info(f"[INFO Emoção] Alerta gerado para {from_number}: {alerta_emocao}")
        except Exception as e: logging.error(f"[ERRO Emoção] Falha na detecção/alerta para {from_number}: {e}")
        
        # Salva estado se foi modificado em algum fluxo ou para registrar ultima_msg
        # Não salva se o estado foi explicitamente resetado (ex: após registro de gasto)
        if estado_modificado_fluxo and not estado.get("_resetado_"):
             salvar_estado(from_number, estado)
        elif not os.path.exists(f"estados/{from_number}.json"): # Salva se for a primeira vez
             salvar_estado(from_number, estado)
             
        logging.info(f"Processamento da mensagem de {from_number} concluído.")
        return {"status": "processamento concluído"}

    except HTTPException as http_exc:
        logging.error(f"HTTP Exception durante processamento para {from_number}: {http_exc.status_code} - {http_exc.detail}")
        raise http_exc # Re-levanta a exceção HTTP para o FastAPI tratar
    except Exception as e:
        logging.exception(f"ERRO INESPERADO ao processar mensagem de {from_number}: {e}") 
        try: send_message(from_number, "Desculpe, ocorreu um erro inesperado ao processar sua mensagem. Por favor, tente novamente.")
        except Exception as send_err: logging.error(f"Falha ao enviar mensagem de erro para {from_number}: {send_err}")
        # Não levanta HTTPException aqui para evitar expor detalhes internos, mas o log captura o erro.
        return {"status": "erro interno"} # Retorna um status genérico

@app.get("/health")
def health_check():
    if not client: raise HTTPException(status_code=503, detail="Serviço indisponível: Falha na inicialização do Twilio.")
    logging.info("Health check OK.")
    return {"status": "vivo, lúcido e com fé"}

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)