import os
import openai
import requests
from fastapi import FastAPI, Request, HTTPException # Adicionado HTTPException
from twilio.rest import Client
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pytz
import datetime
import re
import json 
import logging # Adicionado para logs mais robustos
import mensagens
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

# Configuração básica de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()
app = FastAPI()

# Validação inicial das variáveis de ambiente essenciais
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
MESSAGING_SERVICE_SID = os.getenv("TWILIO_MESSAGING_SERVICE_SID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, MESSAGING_SERVICE_SID, OPENAI_API_KEY]):
    logging.error("ERRO CRÍTICO: Variáveis de ambiente essenciais (Twilio SID/Token/MessagingSID, OpenAI Key) não configuradas.")
    # Considerar encerrar a aplicação ou lidar de outra forma

openai.api_key = OPENAI_API_KEY
try:
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    logging.info("Cliente Twilio inicializado com sucesso.")
except Exception as e:
    logging.error(f"ERRO CRÍTICO: Falha ao inicializar cliente Twilio: {e}")
    client = None # Garante que o cliente não será usado se falhar

# Função de leitura do prompt.txt para contexto inicial
try:
    with open("prompt.txt", "r", encoding='utf-8') as arquivo_prompt:
        prompt_base = arquivo_prompt.read().strip()
except FileNotFoundError:
    logging.error("ERRO CRÍTICO: Arquivo prompt.txt não encontrado.")
    prompt_base = "Você é um assistente financeiro." # Fallback
except Exception as e:
    logging.error(f"ERRO CRÍTICO: Falha ao ler prompt.txt: {e}")
    prompt_base = "Você é um assistente financeiro."

# Complemento claro e incisivo de contexto obrigatório:
complemento_contextual = (
    "Você sempre trata o usuário pelo primeiro nome (que foi informado no início da conversa na resposta à saudação inicial) ou com um vocativo amigável e intimista. "
    "Você nunca recomenda divórcio ou separação por questões financeiras. "
    "O casamento é sagrado, indissolúvel e deve ser defendido com firmeza, clareza e profundidade espiritual. "
    "Seja sempre amigável, intimista, interessado e firme. Utilize explicitamente ensinamentos cristãos, católicos e do Opus Dei. "
    "Utilize o método de comunicação de Dale Carnegie, mostrando-se sempre interessado no usuário, demonstrando escuta ativa. "
    "Não use 'olá' no início de uma resposta se o usuário já tiver feito a primeira interação. "
    "Nunca sugira imediatamente ajuda externa (como conselheiros matrimoniais), a não ser que seja estritamente necessário após várias interações. "
    "Trate crises financeiras conjugais com responsabilidade cristã e financeira, lembrando sempre que a cruz matrimonial é uma oportunidade de crescimento espiritual e amadurecimento na vocação do casamento."
    "Trate questoões de moral e ética com os ensinamentos de Santo Tomás de Aquino e da doutrina católica. "
)

mensagens_gpt_base = [
    {"role": "system", "content": prompt_base},
    {"role": "system", "content": complemento_contextual},
    {"role": "system", "content": "Sempre consulte a pasta Knowledge via embeddings para complementar respostas de acordo com o contexto."}
]

# === NOVA FUNÇÃO PARA INTERPRETAR GASTOS COM GPT ===
def interpretar_gasto_com_gpt(mensagem_usuario):
    """Usa o GPT para extrair detalhes de um gasto a partir da mensagem do usuário."""
    prompt_extracao = f"""
Você é um assistente de finanças pessoais. Analise a seguinte mensagem do usuário e extraia as seguintes informações sobre um gasto:
- Descrição do gasto (o que foi comprado/pago)
- Valor do gasto (em formato numérico com ponto decimal, ex: 50.00)
- Forma de pagamento (crédito, débito, pix, boleto, dinheiro. Se não mencionado, retorne N/A)
- Categoria sugerida (escolha uma destas: Alimentação, Transporte, Moradia, Saúde, Lazer, Educação, Vestuário, Doações, Outros. Se não tiver certeza, retorne 'A DEFINIR')

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
        logging.info(f"Chamando GPT para extrair gasto da mensagem: '{mensagem_usuario[:50]}...'" )
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo", 
            messages=[{"role": "system", "content": prompt_extracao}],
            temperature=0.1,
        )
        resposta_gpt = response["choices"][0]["message"]["content"].strip()
        logging.info(f"Resposta bruta do GPT (extração): {resposta_gpt}")
        
        dados_gasto = json.loads(resposta_gpt)
        
        if not dados_gasto.get("descricao") or not isinstance(dados_gasto.get("valor"), (int, float)):
            logging.warning("[GPT Gasto] Descrição ou valor inválido/ausente no JSON.")
            return None 
            
        dados_gasto["valor"] = float(dados_gasto["valor"])
        
        logging.info(f"Dados do gasto extraídos com sucesso: {dados_gasto}")
        return dados_gasto
        
    except json.JSONDecodeError as e:
        logging.error(f"[GPT JSONDecodeError] Não foi possível decodificar a resposta do GPT: {resposta_gpt}. Erro: {e}")
        return None
    except Exception as e:
        logging.error(f"[ERRO GPT] Erro ao chamar API OpenAI para extração de gasto: {e}")
        return None
# === FIM DA NOVA FUNÇÃO ===

# === PLANILHAS ===
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
    user_number_fmt = format_number(user_number) # Formata antes de usar
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
            # Garante que todos os campos necessários existem, mesmo que vazios
            aba_gratuitos.append_row(["", user_number_fmt, "", now, 0, 0]) 
            logging.info(f"Usuário {user_number_fmt} adicionado com sucesso.")
            return aba_gratuitos
    except Exception as e:
        logging.error(f"Erro CRÍTICO ao obter/criar planilha para usuário {user_number_fmt}: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao acessar dados do usuário.") # Levanta erro HTTP

def nome_valido(text):
    if not text:
        return False
    partes = text.strip().split()
    if len(partes) < 1:
        return False
    if not re.fullmatch(r"[a-zA-ZáéíóúÁÉÍÓÚâêîôûÂÊÎÔÛãõÃÕçÇ\s]+", text.strip()):
        return False
    if any(char in text for char in "@!?0123456789#$%*()[]{}"):
        return False
    return True

def format_number(raw_number):
    return raw_number.replace("whatsapp:", "").replace("+", "").replace(" ", "").strip()

def extract_email(text):
    match = re.search(r'[\w\.-]+@[\w\.-]+', text)
    return match.group(0) if match else None

def count_tokens(text):
    return len(text.split())

def send_message(to, body):
    """Envia mensagem via Twilio com logging e tratamento de erro."""
    if not client:
        logging.error(f"Tentativa de enviar mensagem para {to} falhou: Cliente Twilio não inicializado.")
        return False # Indica falha
        
    if not body or not body.strip():
        logging.warning(f"Tentativa de enviar mensagem VAZIA para {to}. Ignorado.")
        return False
        
    # Verifica duplicidade ANTES de tentar enviar
    if resposta_enviada_recentemente(to, body):
        logging.info(f"Resposta duplicada para {to} detectada e não enviada.")
        return False

    partes = [body[i:i+1500] for i in range(0, len(body), 1500)]
    success = True
    try:
        logging.info(f"Tentando enviar mensagem para {to}: '{body[:50]}...' ({len(partes)} parte(s))")
        for i, parte in enumerate(partes):
            message = client.messages.create(
                body=parte,
                messaging_service_sid=MESSAGING_SERVICE_SID,
                to=f"whatsapp:{to}"
            )
            logging.info(f"Parte {i+1}/{len(partes)} enviada para {to}. SID: {message.sid}")
        salvar_ultima_resposta(to, body) # Salva só se todas as partes foram enviadas com sucesso
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
        if status != "Gratuitos":
            return False
        return get_interactions(sheet, row) >= 10
    except Exception as e:
        logging.error(f"[ERRO Planilha] passou_limite (linha {row}): {e}")
        return False

def is_boas_vindas(text):
    saudacoes = ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "e aí", "opa"]
    text_lower = text.lower().strip()
    return any(text_lower.startswith(sauda) for sauda in saudacoes)

def precisa_direcionamento(msg):
    frases_vagas = [
        "me ajuda", "preciso de ajuda", "me orienta", "o que eu faço",
        "não sei por onde começar", "como começar", "tô perdido", "me explica",
        "quero ajuda", "quero controlar", "quero começar", "começar a usar"
    ]
    msg_lower = msg.lower()
    return any(frase in msg_lower for frase in frases_vagas)

def quer_resumo_mensal(msg):
    msg_lower = msg.lower()
    termos = [
        "quanto gastei", 
        "resumo do mês",
        "gastos do mês", 
        "como estão meus gastos",
        "meu resumo financeiro",
        "me mostra meus gastos",
        "meus gastos recentes",
        "gastando muito",
        "gastei demais"
    ]
    return any(t in msg_lower for t in termos)

def quer_lista_comandos(texto):
    texto_lower = texto.lower()
    termos = [
        "quais comandos", "comandos disponíveis", "o que você faz",
        "como usar", "me ajuda com comandos", "o que posso pedir",
        "me manda os comandos", "comando", "menu", "como funciona",
        "/comandos", "/ajuda"
    ]
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

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    # Log inicial para confirmar recebimento
    logging.info("Recebida requisição POST em /webhook")
    try:
        form = await request.form()
        incoming_msg = form.get("Body", "").strip()
        from_number_raw = form.get("From", "")
        
        if not incoming_msg or not from_number_raw:
            logging.warning("Requisição recebida sem 'Body' ou 'From'. Ignorando.")
            return {"status": "requisição inválida"}
            
        from_number = format_number(from_number_raw)
        logging.info(f"Mensagem recebida de {from_number}: '{incoming_msg[:50]}...'" )

    except Exception as e:
        logging.error(f"Erro ao processar formulário da requisição: {e}")
        # Retornar um erro HTTP pode ajudar o Twilio a diagnosticar
        raise HTTPException(status_code=400, detail="Erro ao processar dados da requisição.")

    try: # Bloco try principal para capturar erros inesperados no fluxo
        estado = carregar_estado(from_number)
        ultima_msg_registrada = estado.get("ultima_msg", "")

        if incoming_msg == ultima_msg_registrada:
            logging.info(f"Mensagem duplicada de {from_number} detectada e ignorada.")
            return {"status": "mensagem duplicada ignorada"}

        estado["ultima_msg"] = incoming_msg
        # Salvar estado será feito no final ou em pontos chave

        # --- INÍCIO SETUP USUÁRIO ---
        try:
            sheet_usuario = get_user_sheet(from_number) # Já loga internamente
            # Encontra a linha do usuário (necessário após get_user_sheet garantir que existe)
            col_numeros = sheet_usuario.col_values(2)
            linha_index = col_numeros.index(from_number) + 1
            linha_usuario = sheet_usuario.row_values(linha_index)
            logging.info(f"Dados da linha {linha_index} recuperados para {from_number}.")
        except ValueError: # Caso raro onde index falha mesmo após get_user_sheet
             logging.error(f"ERRO CRÍTICO: Usuário {from_number} deveria existir na planilha mas index falhou.")
             raise HTTPException(status_code=500, detail="Erro interno crítico ao localizar dados do usuário.")
        except Exception as e: # Captura outros erros de planilha
             logging.error(f"ERRO CRÍTICO: Falha ao obter dados da linha para {from_number}: {e}")
             raise HTTPException(status_code=500, detail="Erro interno ao obter dados do usuário.")

        interactions = increment_interactions(sheet_usuario, linha_index)
        logging.info(f"Interações para {from_number}: {interactions}")

        # Garante que linha_usuario tem tamanho suficiente antes de acessar índices
        name = linha_usuario[0].strip() if len(linha_usuario) > 0 and linha_usuario[0] else "Usuário"
        email = linha_usuario[2].strip() if len(linha_usuario) > 2 and linha_usuario[2] else None

        tokens_msg = count_tokens(incoming_msg)
        total_tokens = increment_tokens(sheet_usuario, linha_index, tokens_msg)
        logging.info(f"Tokens para {from_number}: +{tokens_msg} = {total_tokens}")
        # --- FIM SETUP USUÁRIO ---

        # --- INÍCIO FLUXO ONBOARDING/CADASTRO ---
        if is_boas_vindas(incoming_msg):
            if not name or name == "Usuário" or not email:
                if estado.get("ultimo_fluxo") != "aguardando_cadastro":
                    logging.info(f"Usuário {from_number} iniciou onboarding.")
                    send_message(from_number, mensagens.estilo_msg(mensagens.solicitacao_cadastro()))
                    estado["ultimo_fluxo"] = "aguardando_cadastro"
                    salvar_estado(from_number, estado)
                else: 
                    logging.info(f"Usuário {from_number} já estava aguardando cadastro.")
                return {"status": "aguardando nome e email"}

            if estado.get("saudacao_realizada"):
                logging.info(f"Saudação repetida de {from_number} ignorada.")
                # Não retorna, deixa seguir
            else:
                logging.info(f"Completando saudação para {from_number}.")
                primeiro_nome = name.split()[0] if name != "Usuário" else ""
                resposta_curta = mensagens.cadastro_completo(primeiro_nome)
                send_message(from_number, mensagens.estilo_msg(resposta_curta))
                estado["ultimo_fluxo"] = "cadastro_completo" 
                estado["saudacao_realizada"] = True
                salvar_estado(from_number, estado)
                return {"status": "cadastro completo e saudação feita"}

        if not name or name == "Usuário" or not email:
            logging.info(f"Processando possível resposta de cadastro de {from_number}.")
            nome_capturado = None
            email_capturado = None
            linhas = incoming_msg.split("\n")
            for linha in linhas:
                if not nome_capturado and nome_valido(linha):
                    nome_capturado = linha.title().strip()
                if not email_capturado and extract_email(linha):
                    email_capturado = extract_email(linha).lower().strip()

            nome_atualizado = False
            email_atualizado = False

            if nome_capturado and (not name or name == "Usuário"):
                try:
                    sheet_usuario.update_cell(linha_index, 1, nome_capturado)
                    name = nome_capturado
                    nome_atualizado = True
                    logging.info(f"Nome de {from_number} atualizado para {name}")
                except Exception as e:
                     logging.error(f"[ERRO Planilha] Falha ao atualizar nome para {nome_capturado} (linha {linha_index}): {e}")

            if email_capturado and not email:
                try:
                    sheet_usuario.update_cell(linha_index, 3, email_capturado)
                    email = email_capturado
                    email_atualizado = True
                    logging.info(f"Email de {from_number} atualizado para {email}")
                except Exception as e:
                     logging.error(f"[ERRO Planilha] Falha ao atualizar email para {email_capturado} (linha {linha_index}): {e}")

            if not name or name == "Usuário":
                if not email_atualizado: # Só pede se não acabou de pegar o email
                    logging.info(f"Solicitando nome para {from_number}.")
                    send_message(from_number, mensagens.estilo_msg("Ótimo! E qual seu nome completo, por favor? ✍️"))
                    estado["ultimo_fluxo"] = "aguardando_cadastro"
                    salvar_estado(from_number, estado)
                    return {"status": "aguardando nome"}
            elif not email:
                if not nome_atualizado: # Só pede se não acabou de pegar o nome
                    logging.info(f"Solicitando email para {from_number}.")
                    send_message(from_number, mensagens.estilo_msg("Perfeito! Agora só preciso do seu e-mail. 📧"))
                    estado["ultimo_fluxo"] = "aguardando_cadastro"
                    salvar_estado(from_number, estado)
                    return {"status": "aguardando email"}
            
            if name and name != "Usuário" and email:
                logging.info(f"Cadastro de {from_number} completo via captura.")
                primeiro_nome = name.split()[0]
                send_message(from_number, mensagens.estilo_msg(mensagens.cadastro_completo(primeiro_nome)))
                estado["ultimo_fluxo"] = "cadastro_completo"
                estado["saudacao_realizada"] = True 
                salvar_estado(from_number, estado)
                return {"status": "cadastro completo via captura"}
            else:
                logging.info(f"Ainda aguardando dados de cadastro de {from_number}.")
                estado["ultimo_fluxo"] = "aguardando_cadastro"
                salvar_estado(from_number, estado)
                # Mensagem pedindo o que falta já foi enviada (ou será na próxima interação)
                return {"status": "continuando aguardando cadastro"}
                
        # --- FIM FLUXO ONBOARDING/CADASTRO ---

        # --- INÍCIO PROCESSAMENTO DE MENSAGEM (PÓS-CADASTRO) ---
        logging.info(f"Iniciando processamento da mensagem pós-cadastro de {from_number}.")
        mensagem_tratada = False 
        estado_modificado_fluxo_gastos = False # Flag para salvar estado no fim se modificado aqui

        # --- INÍCIO NOVO FLUXO DE REGISTRO DE GASTOS (GPT + CONVERSACIONAL) ---
        ultimo_fluxo_gasto = estado.get("ultimo_fluxo")
        gasto_pendente = estado.get("gasto_pendente")

        # 1. Usuário está respondendo sobre FORMA DE PAGAMENTO?
        if ultimo_fluxo_gasto == "aguardando_forma_pagamento" and gasto_pendente:
            logging.info(f"{from_number} respondeu sobre forma de pagamento.")
            forma_pagamento_resposta = incoming_msg.strip().capitalize()
            if forma_pagamento_resposta and len(forma_pagamento_resposta) > 2:
                gasto_pendente["forma_pagamento"] = forma_pagamento_resposta
                categoria_sugerida = gasto_pendente.get("categoria_sugerida", "A DEFINIR")
                valor_formatado = f"R${gasto_pendente['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                
                if categoria_sugerida != "A DEFINIR":
                    mensagem_confirmacao = (
                        f"Entendido: {gasto_pendente['descricao']} - {valor_formatado} ({forma_pagamento_resposta}).\n"
                        f"Sugeri a categoria *{categoria_sugerida}*. Está correto? (Sim/Não/Ou diga a categoria certa)"
                    )
                    estado["ultimo_fluxo"] = "aguardando_confirmacao_categoria"
                else:
                     mensagem_confirmacao = (
                        f"Entendido: {gasto_pendente['descricao']} - {valor_formatado} ({forma_pagamento_resposta}).\n"
                        f"Qual seria a categoria para este gasto? (Ex: Alimentação, Transporte, Lazer...)"
                    )
                     estado["ultimo_fluxo"] = "aguardando_definicao_categoria"
                     
                estado_modificado_fluxo_gastos = True
                send_message(from_number, mensagens.estilo_msg(mensagem_confirmacao))
                mensagem_tratada = True
            else:
                logging.warning(f"Forma de pagamento inválida recebida de {from_number}: '{incoming_msg}'")
                send_message(from_number, mensagens.estilo_msg("Não entendi a forma de pagamento. Pode repetir? (crédito, débito, pix, etc.)"))
                estado_modificado_fluxo_gastos = True # Salva estado mesmo se inválido para manter fluxo
                mensagem_tratada = True

        # 2. Usuário está respondendo sobre CONFIRMAÇÃO DE CATEGORIA?
        elif ultimo_fluxo_gasto == "aguardando_confirmacao_categoria" and gasto_pendente:
            logging.info(f"{from_number} respondeu sobre confirmação de categoria.")
            resposta_categoria = incoming_msg.strip().lower()
            categoria_final = ""
            
            if resposta_categoria in ["sim", "s", "correto", "ok", "isso", "tá certo", "pode ser"]:
                categoria_final = gasto_pendente.get("categoria_sugerida")
            elif resposta_categoria not in ["não", "nao", "errado"]:
                categoria_final = incoming_msg.strip().capitalize()
            
            if categoria_final:
                logging.info(f"Categoria final definida para gasto de {from_number}: {categoria_final}")
                fuso = pytz.timezone("America/Sao_Paulo")
                hoje = datetime.datetime.now(fuso).strftime("%d/%m/%Y")
                resposta_registro = registrar_gasto(
                    nome_usuario=name,
                    numero_usuario=from_number, 
                    descricao=gasto_pendente["descricao"],
                    valor=gasto_pendente["valor"],
                    forma_pagamento=gasto_pendente["forma_pagamento"],
                    data_gasto=hoje,
                    categoria_manual=categoria_final
                )
                # Limpa estado APÓS tentativa de registro
                # Se falhar, o usuário pode tentar de novo ou o estado será resetado na próxima msg
                if resposta_registro["status"] == "ok":
                    valor_formatado = f"R${gasto_pendente['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    send_message(from_number, mensagens.estilo_msg(f"✅ Gasto registrado: {gasto_pendente['descricao']} ({valor_formatado}) em {categoria_final}."))
                    resetar_estado(from_number) # Sucesso, limpa tudo
                elif resposta_registro["status"] == "ignorado":
                     send_message(from_number, mensagens.estilo_msg("📝 Hmm, parece que esse gasto já foi registrado antes."))
                     resetar_estado(from_number) # Gasto já existe, limpa estado pendente
                else:
                     send_message(from_number, mensagens.estilo_msg(f"⚠️ Tive um problema ao registrar o gasto na planilha. Por favor, tente de novo ou verifique mais tarde."))
                     logging.error(f"[ERRO REGISTRO GASTO] {resposta_registro.get('mensagem')}")
                     # Não reseta estado aqui, permite tentar de novo? Ou reseta?
                     # Resetar pode ser mais seguro para evitar loops
                     resetar_estado(from_number)
                mensagem_tratada = True
            else:
                logging.info(f"{from_number} negou categoria sugerida, pedindo a correta.")
                send_message(from_number, mensagens.estilo_msg("Ok. Qual seria a categoria correta para este gasto?"))
                estado["ultimo_fluxo"] = "aguardando_definicao_categoria"
                estado_modificado_fluxo_gastos = True
                mensagem_tratada = True

        # 3. Usuário está respondendo sobre DEFINIÇÃO DE CATEGORIA?
        elif ultimo_fluxo_gasto == "aguardando_definicao_categoria" and gasto_pendente:
            logging.info(f"{from_number} respondeu definindo a categoria.")
            categoria_resposta = incoming_msg.strip().capitalize()
            if categoria_resposta and len(categoria_resposta) > 2: 
                logging.info(f"Categoria final definida para gasto de {from_number}: {categoria_resposta}")
                fuso = pytz.timezone("America/Sao_Paulo")
                hoje = datetime.datetime.now(fuso).strftime("%d/%m/%Y")
                resposta_registro = registrar_gasto(
                    nome_usuario=name,
                    numero_usuario=from_number,
                    descricao=gasto_pendente["descricao"],
                    valor=gasto_pendente["valor"],
                    forma_pagamento=gasto_pendente["forma_pagamento"],
                    data_gasto=hoje,
                    categoria_manual=categoria_resposta
                )
                if resposta_registro["status"] == "ok":
                    valor_formatado = f"R${gasto_pendente['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    send_message(from_number, mensagens.estilo_msg(f"✅ Gasto registrado: {gasto_pendente['descricao']} ({valor_formatado}) em {categoria_resposta}."))
                    resetar_estado(from_number)
                elif resposta_registro["status"] == "ignorado":
                     send_message(from_number, mensagens.estilo_msg("📝 Hmm, parece que esse gasto já foi registrado antes."))
                     resetar_estado(from_number)
                else:
                     send_message(from_number, mensagens.estilo_msg(f"⚠️ Tive um problema ao registrar o gasto na planilha. Por favor, tente de novo ou verifique mais tarde."))
                     logging.error(f"[ERRO REGISTRO GASTO] {resposta_registro.get('mensagem')}")
                     resetar_estado(from_number)
                mensagem_tratada = True
            else:
                logging.warning(f"Categoria inválida recebida de {from_number}: '{incoming_msg}'")
                send_message(from_number, mensagens.estilo_msg("Não entendi a categoria. Pode me dizer de novo? (Ex: Alimentação, Transporte, Lazer...)"))
                estado_modificado_fluxo_gastos = True
                mensagem_tratada = True
                
        # 4. Se não estava respondendo a perguntas anteriores, TENTA INTERPRETAR A MENSAGEM COMO UM NOVO GASTO
        if not mensagem_tratada:
            contem_valor = any(char.isdigit() for char in incoming_msg)
            palavras_chave_gasto = ["gastei", "paguei", "comprei", "custou", "foi R$", "deu R$", "gasto de", "compra de"]
            # Melhora heurística para evitar falso positivo com resumos
            pediu_resumo = quer_resumo_mensal(incoming_msg) or any(t in incoming_msg.lower() for t in ["resumo do dia", "resumo de hoje", "/resumo"])
            indica_gasto = contem_valor and not pediu_resumo and (re.search(r'R\$\s*\d', incoming_msg, re.IGNORECASE) or any(p in incoming_msg.lower() for p in palavras_chave_gasto))
            
            if indica_gasto and not quer_lista_comandos(incoming_msg):
                logging.info(f"Mensagem de {from_number} parece ser um gasto. Tentando interpretar via GPT...")
                dados_gasto_gpt = interpretar_gasto_com_gpt(incoming_msg)

                if dados_gasto_gpt: 
                    descricao = dados_gasto_gpt.get("descricao")
                    valor = dados_gasto_gpt.get("valor")
                    forma_pagamento = dados_gasto_gpt.get("forma_pagamento")
                    categoria_sugerida = dados_gasto_gpt.get("categoria_sugerida")
                    valor_formatado = f"R${valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

                    if forma_pagamento and forma_pagamento != "N/A":
                        logging.info(f"Gasto interpretado para {from_number}. Perguntando sobre categoria.")
                        if categoria_sugerida and categoria_sugerida != "A DEFINIR":
                            mensagem = (
                                f"Entendi: {descricao} - {valor_formatado} ({forma_pagamento}).\n"
                                f"Sugeri a categoria *{categoria_sugerida}*. Está correto? (Sim/Não/Ou diga a categoria certa)"
                            )
                            estado["ultimo_fluxo"] = "aguardando_confirmacao_categoria"
                        else:
                            mensagem = (
                                f"Entendi: {descricao} - {valor_formatado} ({forma_pagamento}).\n"
                                f"Qual seria a categoria para este gasto? (Ex: Alimentação, Transporte, Lazer...)"
                            )
                            estado["ultimo_fluxo"] = "aguardando_definicao_categoria"
                        
                        estado["gasto_pendente"] = dados_gasto_gpt
                        estado_modificado_fluxo_gastos = True
                        send_message(from_number, mensagens.estilo_msg(mensagem))
                        mensagem_tratada = True
                        
                    else:
                        logging.info(f"Gasto interpretado para {from_number}. Perguntando sobre forma de pagamento.")
                        mensagem = f"Entendi: {descricao} - {valor_formatado}. Como você pagou (crédito, débito, pix, etc.)?"
                        estado["ultimo_fluxo"] = "aguardando_forma_pagamento"
                        estado["gasto_pendente"] = dados_gasto_gpt
                        estado_modificado_fluxo_gastos = True
                        send_message(from_number, mensagens.estilo_msg(mensagem))
                        mensagem_tratada = True
                else:
                    logging.info(f"GPT não conseguiu interpretar '{incoming_msg[:50]}...' como gasto para {from_number}. Seguindo para conversa.")
                    # Deixa seguir para a conversa normal
            # Se não indica gasto, segue para conversa normal

        # --- FIM NOVO FLUXO DE REGISTRO DE GASTOS ---

        # --- INÍCIO FLUXOS DE COMANDOS E CONVERSA GERAL ---
        if not mensagem_tratada:
            logging.info(f"Mensagem de {from_number} não tratada como gasto, seguindo para comandos/conversa...")
            
            if quer_lista_comandos(incoming_msg):
                logging.info(f"Enviando lista de comandos para {from_number}.")
                comandos_txt = (
                    "📋 *Comandos disponíveis:*\n"
                    "/resumo – Ver seu resumo financeiro do dia\n"
                    "/limites – Mostrar seus limites por categoria\n"
                    "/ajuda – Mostrar esta lista de comandos\n\n"
                    "💡 *Para registrar gastos, apenas me diga o que gastou!*\n"
                    "Ex: 'Gastei 50 reais no almoço com pix' ou 'Compra de pão por 10 reais no débito'"
                )
                send_message(from_number, mensagens.estilo_msg(comandos_txt))
                mensagem_tratada = True # Marcar como tratada
            
            elif quer_resumo_mensal(incoming_msg):
                logging.info(f"Gerando resumo mensal para {from_number}.")
                resumo = resumo_do_mes(from_number)
                limites_txt = verificar_limites(from_number)
                send_message(from_number, mensagens.estilo_msg(resumo + "\n\n" + limites_txt))
                mensagem_tratada = True

            elif any(t in incoming_msg.lower() for t in [
                "resumo do dia", "resumo de hoje", "quanto gastei hoje",
                "novo resumo", "resumo agora", "resumo atualizado",
                "quero o resumo", "meu resumo", "resumo aqui", "/resumo"
            ]):
                logging.info(f"Gerando resumo diário para {from_number}.")
                resumo = gerar_resumo(from_number, periodo="diario")
                send_message(from_number, mensagens.estilo_msg(resumo))
                mensagem_tratada = True

            elif any(t in incoming_msg.lower() for t in ["resumo de ontem", "quanto gastei ontem"]):
                logging.info(f"Gerando resumo de ontem para {from_number}.")
                ontem = datetime.datetime.now(pytz.timezone("America/Sao_Paulo")) - datetime.timedelta(days=1)
                resumo = gerar_resumo(from_number, periodo="custom", data_personalizada=ontem.date())
                send_message(from_number, mensagens.estilo_msg(resumo))
                mensagem_tratada = True
                
            # Lógica de Upgrade (mantida)
            if not mensagem_tratada and verificar_upgrade_automatico(from_number):
                 logging.info(f"Informando {from_number} sobre upgrade automático.")
                 send_message(from_number, mensagens.estilo_msg(
                    "🔓 Seu acesso premium foi liberado!\nBem-vindo ao grupo dos que escolheram dominar a vida financeira com dignidade e IA de primeira. 🙌"))
                 # Não marca como tratada, pois a mensagem original pode ser outra coisa

            # Alerta de limite gratuito (mantido)
            user_status = get_user_status(from_number)
            if not mensagem_tratada and user_status == "Gratuitos" and passou_limite(sheet_usuario, linha_index):
                    logging.warning(f"Usuário gratuito {from_number} atingiu o limite de interações.")
                    contexto_usuario = contexto_principal_usuario(from_number, ultima_msg=incoming_msg)
                    mensagem_alerta = mensagens.alerta_limite_gratuito(contexto_usuario)
                    send_message(from_number, mensagens.estilo_msg(mensagem_alerta, leve=False))
                    # Salva estado aqui para garantir que ultima_msg seja registrada
                    salvar_estado(from_number, estado)
                    return {"status": "limite gratuito atingido"}

            # --- INÍCIO CONVERSA GERAL COM GPT --- 
            if not mensagem_tratada:
                logging.info(f"Iniciando fluxo de conversa geral com GPT para {from_number}...")
                conversa_path = f"conversas/{from_number}.txt"
                if not os.path.exists("conversas"): os.makedirs("conversas")
                if not os.path.isfile(conversa_path): 
                    with open(conversa_path, "w", encoding='utf-8') as f: f.write("")
                
                try:
                    with open(conversa_path, "r", encoding='utf-8') as f: linhas_conversa = f.readlines()
                except Exception as e: 
                    logging.error(f"Falha ao ler histórico {conversa_path}: {e}"); linhas_conversa = []

                historico_filtrado = [l for l in linhas_conversa if not any(f in l.lower() for f in ["sou seu conselheiro financeiro","perfeito,","tô aqui pra te ajudar","posso te ajudar com controle de gastos","por onde quer começar"])]
                historico_relevante = historico_filtrado[-6:] 

                mensagens_para_gpt = list(mensagens_gpt_base) 

                # Contexto da Knowledge Base
                termos_resumo = ["resumo", "quanto gastei", "gastos hoje"]
                if not any(t in incoming_msg.lower() for t in termos_resumo):
                    categoria_detectada_conversa = "geral"
                    texto_lower_conversa = incoming_msg.lower()
                    PALAVRAS_CHAVE_CATEGORIAS = {
                        "espiritualidade": ["oração", "culpa", "confissão", "direção espiritual", "vida espiritual", "fé", "deus", "confessar"],
                        "financeiro": ["gasto", "dinheiro", "investimento", "renda", "salário", "orçamento", "juros", "empréstimo", "dívida"],
                        "casamento": ["cônjuge", "esposa", "marido", "matrimônio", "casamento", "vida a dois", "parceiro"],
                        "filosofia": ["virtude", "temperamento", "aristóteles", "santo tomás", "ética", "filosofia", "psicologia"],
                    }
                    for cat, pals in PALAVRAS_CHAVE_CATEGORIAS.items():
                        if any(p in texto_lower_conversa for p in pals): categoria_detectada_conversa = cat; break
                    
                    contexto_resgatado = buscar_conhecimento_relevante(incoming_msg, categoria=categoria_detectada_conversa, top_k=3)
                    if contexto_resgatado:
                        logging.info(f"Adicionando contexto Knowledge ({categoria_detectada_conversa}) para {from_number}.")
                        mensagens_para_gpt.append({"role": "system", "content": f"Contexto relevante:\n{contexto_resgatado}"}) 
                    else: logging.info(f"Nenhum contexto Knowledge encontrado para '{incoming_msg[:30]}...' ({categoria_detectada_conversa}).")

                # Histórico da conversa
                for linha in historico_relevante:
                    try:
                        partes = linha.split(":", 1)
                        if len(partes) == 2:
                            role = "user" if "Usuário:" in partes[0] else "assistant"
                            conteudo = partes[1].strip()
                            if conteudo: mensagens_para_gpt.append({"role": role, "content": conteudo})
                    except Exception as e: logging.error(f"Falha ao processar linha do histórico: {linha} - {e}")

                mensagens_para_gpt.append({"role": "user", "content": incoming_msg})

                # Indicadores econômicos
                termos_macro = ["empréstimo", "juros", "selic", "ipca", "cdi", "inflação", "investimento", "cenário econômico"]
                if any(p in incoming_msg.lower() for p in termos_macro):
                    indicadores = get_indicadores()
                    if indicadores:
                        texto_indicadores = "\n".join([f"{n.upper()}: {v}%" if isinstance(v, (int, float)) else f"{n.upper()}: {v}" for n, v in indicadores.items() if v is not None])
                        mensagens_para_gpt.append({"role": "system", "content": f"Indicadores econômicos atuais:\n{texto_indicadores}"})

                # Chama GPT
                try:
                    logging.info(f"Chamando GPT para conversa de {from_number} ({len(mensagens_para_gpt)} mensagens)." )
                    response = openai.ChatCompletion.create(model="gpt-4-turbo", messages=mensagens_para_gpt, temperature=0.7)
                    reply = response["choices"][0]["message"]["content"].strip()
                    logging.info(f"Resposta GPT (conversa) para {from_number}: '{reply[:50]}...'" )
                except Exception as e:
                    logging.error(f"[ERRO OpenAI Conversa] {e}")
                    reply = "⚠️ Tive um problema ao processar sua mensagem agora. Poderia tentar de novo, por favor?"

                # Pós-processamento
                reply = re.sub(r'^(oi|olá|opa|e aí)[,.!]?\s*', '', reply, flags=re.IGNORECASE).strip()
                if "[Nome]" in reply:
                    primeiro_nome = name.split()[0] if name and name != "Usuário" else ""
                    reply = reply.replace("[Nome]", primeiro_nome)

                assuntos_sensiveis = ["violência", "agressão", "abuso", "depressão", "ansiedade", "suicídio", "terapia"]
                if any(t in incoming_msg.lower() for t in assuntos_sensiveis):
                    disclaimer = "\n\n⚠️ *Lembre-se: Sou uma IA e não substituo acompanhamento profissional especializado.*"
                    if disclaimer not in reply: reply += disclaimer

                # Salva conversa
                try:
                    with open(conversa_path, "a", encoding='utf-8') as f:
                        f.write(f"Usuário: {incoming_msg}\n")
                        f.write(f"Conselheiro: {reply}\n")
                except Exception as e: logging.error(f"Falha ao salvar conversa {conversa_path}: {e}")

                # Envia resposta
                if reply:
                    send_message(from_number, mensagens.estilo_msg(reply))
                else:
                    logging.warning(f"Resposta vazia do GPT para conversa de {from_number}.")
                    send_message(from_number, mensagens.estilo_msg("Não entendi muito bem. Pode reformular, por favor?"))
                
                mensagem_tratada = True # Marca como tratada pela conversa geral
            # --- FIM CONVERSA GERAL COM GPT --- 

        # --- FIM FLUXOS DE COMANDOS E CONVERSA GERAL ---

        # Se a mensagem não foi tratada por nenhum fluxo (nem gasto, nem comando, nem conversa)
        if not mensagem_tratada:
             logging.warning(f"Mensagem de {from_number} não tratada por nenhum fluxo: '{incoming_msg}'")
             # Enviar uma mensagem padrão de fallback?
             send_message(from_number, mensagens.estilo_msg("Hmm, não tenho certeza de como ajudar com isso agora. Pode tentar de outra forma?"))

        # --- INÍCIO TAREFAS ASSÍNCRONAS / FINALIZAÇÃO ---
        try:
            fuso = pytz.timezone("America/Sao_Paulo")
            data_msg_str = datetime.datetime.now(fuso).strftime("%Y-%m-%d %H:%M:%S")
            emocao = detectar_emocao(incoming_msg)
            if emocao:
                alerta_emocao = aumento_pos_emocao(from_number, emocao, data_msg_str)
                if alerta_emocao: logging.info(f"[INFO Emoção] Alerta gerado para {from_number}: {alerta_emocao}")
        except Exception as e: logging.error(f"[ERRO Emoção] Falha na detecção/alerta para {from_number}: {e}")
        
        # Salva o estado final (incluindo ultima_msg e possíveis modificações do fluxo de gastos)
        # Salvar mesmo se estado_modificado_fluxo_gastos for False, para registrar ultima_msg
        salvar_estado(from_number, estado)

        logging.info(f"Processamento da mensagem de {from_number} concluído.")
        return {"status": "processamento concluído"}
        # --- FIM PROCESSAMENTO DE MENSAGEM ---

    except HTTPException as http_exc:
        # Re-levanta exceções HTTP para FastAPI tratar corretamente
        logging.error(f"HTTP Exception durante processamento para {from_number}: {http_exc.status_code} - {http_exc.detail}")
        raise http_exc
    except Exception as e:
        # Captura qualquer outro erro inesperado no fluxo principal
        logging.exception(f"ERRO INESPERADO ao processar mensagem de {from_number}: {e}") # Usar .exception para incluir traceback no log
        # Enviar uma mensagem genérica de erro para o usuário?
        try:
            send_message(from_number, "Desculpe, ocorreu um erro inesperado ao processar sua mensagem. Por favor, tente novamente.")
        except Exception as send_err:
            logging.error(f"Falha ao enviar mensagem de erro para {from_number}: {send_err}")
        # Retornar um erro 500 pode ajudar o Twilio
        raise HTTPException(status_code=500, detail="Erro interno do servidor.")

@app.get("/health")
def health_check():
    # Verifica se o cliente Twilio foi inicializado
    if not client:
         raise HTTPException(status_code=503, detail="Serviço indisponível: Falha na inicialização do Twilio.")
    # Adicionar outras verificações se necessário (ex: conexão com DB, OpenAI key)
    logging.info("Health check OK.")
    return {"status": "vivo, lúcido e com fé"}

# Adicionar para rodar com Uvicorn (se não estiver usando um Procfile ou similar)
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True) # reload=True para desenvolvimento