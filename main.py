import os
import openai
import requests
from fastapi import FastAPI, Request
from twilio.rest import Client
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pytz
import datetime
import re
import json # Adicionado para o novo fluxo de gastos
import mensagens
# Removido parsear_gastos_em_lote das importações de gastos, pois será substituído
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

load_dotenv()
app = FastAPI()

openai.api_key = os.getenv("OPENAI_API_KEY")
client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
MESSAGING_SERVICE_SID = os.getenv("TWILIO_MESSAGING_SERVICE_SID")

# Função de leitura do prompt.txt para contexto inicial
with open("prompt.txt", "r") as arquivo_prompt:
    prompt_base = arquivo_prompt.read().strip()

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

# Removido a leitura duplicada do prompt.txt

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
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo", # Usando um modelo mais rápido e barato para esta tarefa específica
            messages=[{"role": "system", "content": prompt_extracao}],
            temperature=0.1,
        )
        resposta_gpt = response["choices"][0]["message"]["content"].strip()
        
        # Tenta analisar o JSON
        dados_gasto = json.loads(resposta_gpt)
        
        # Validação básica
        if not dados_gasto.get("descricao") or not isinstance(dados_gasto.get("valor"), (int, float)):
            print("[DEBUG GPT Gasto] Descrição ou valor inválido/ausente no JSON.")
            return None # Não conseguiu extrair descrição ou valor válidos
            
        # Garante que valor seja float
        dados_gasto["valor"] = float(dados_gasto["valor"])
        
        print(f"[DEBUG GPT Gasto] Dados extraídos: {dados_gasto}")
        return dados_gasto
        
    except json.JSONDecodeError as e:
        print(f"[ERRO GPT JSONDecodeError] Não foi possível decodificar a resposta do GPT: {resposta_gpt}. Erro: {e}")
        return None
    except Exception as e:
        print(f"[ERRO GPT] Erro ao chamar API OpenAI para extração de gasto: {e}")
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
        print(f"Erro ao verificar status do usuário: {e}")
        return "Novo"

def get_user_sheet(user_number):
    user_number = format_number(user_number)
    aba_pagantes = get_pagantes()
    aba_gratuitos = get_gratuitos()

    pagantes = aba_pagantes.col_values(2)
    gratuitos = aba_gratuitos.col_values(2)

    if user_number in pagantes:
        return aba_pagantes
    elif user_number in gratuitos:
        return aba_gratuitos
    else:
        now = datetime.datetime.now(pytz.timezone("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S")
        aba_gratuitos.append_row(["", user_number, "", now, 0, 0])
        return aba_gratuitos

def nome_valido(text):
    if not text:
        return False
    partes = text.strip().split()
    # Permitir nomes compostos, verificar se tem pelo menos 1 parte
    if len(partes) < 1:
        return False
    # Permitir apenas letras, espaços e acentos comuns
    if not re.fullmatch(r"[a-zA-ZáéíóúÁÉÍÓÚâêîôûÂÊÎÔÛãõÃÕçÇ\s]+", text.strip()):
        return False
    # Evitar caracteres especiais ainda pode ser útil
    if any(char in text for char in "@!?0123456789#$%*()[]{}"):
        return False
    return True

def format_number(raw_number):
    return raw_number.replace("whatsapp:", "").replace("+", "").replace(" ", "").strip()

def extract_email(text):
    match = re.search(r'[\w\.-]+@[\w\.-]+', text)
    return match.group(0) if match else None

def count_tokens(text):
    # Uma contagem mais simples, pode ser ajustada se necessário
    return len(text.split())

def send_message(to, body):
    if not body or not body.strip():
        print(f"[ERRO] Tentativa de enviar mensagem vazia para {to}. Ignorado.")
        return
    if resposta_enviada_recentemente(to, body):
        print("[DEBUG] Resposta duplicada detectada e não enviada.")
        return

    # Divide a mensagem em partes menores (Twilio tem limite)
    partes = [body[i:i+1500] for i in range(0, len(body), 1500)]
    try:
        for parte in partes:
            client.messages.create(
                body=parte,
                messaging_service_sid=MESSAGING_SERVICE_SID,
                to=f"whatsapp:{to}"
            )
        salvar_ultima_resposta(to, body)
        print(f"[DEBUG] Mensagem enviada para {to}")
    except Exception as e:
        print(f"[ERRO TWILIO] Falha ao enviar mensagem para {to}: {e}")

def get_interactions(sheet, row):
    try:
        val = sheet.cell(row, 6).value
        return int(val) if val else 0
    except Exception as e:
        print(f"[ERRO Planilha] get_interactions: {e}")
        return 0

def increment_interactions(sheet, row):
    try:
        count = get_interactions(sheet, row) + 1
        sheet.update_cell(row, 6, count)
        return count
    except Exception as e:
        print(f"[ERRO Planilha] increment_interactions: {e}")
        return get_interactions(sheet, row) # Retorna o valor antigo em caso de erro

def passou_limite(sheet, row):
    try:
        status = sheet.title
        if status != "Gratuitos":
            return False
        return get_interactions(sheet, row) >= 10
    except Exception as e:
        print(f"[ERRO Planilha] passou_limite: {e}")
        return False

def is_boas_vindas(text):
    saudacoes = ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "e aí", "opa"]
    text_lower = text.lower().strip()
    # Verifica se a mensagem *começa* com uma saudação (evita acionar no meio de frases)
    return any(text_lower.startswith(sauda) for sauda in saudacoes)

# Funções antigas de detecção/parsing de gastos foram removidas
# def detectar_gastos(texto): ...
# def detectar_gastos_com_categoria_direta(texto): ...
# def extrair_gastos(texto): ...
# def quer_corrigir_gasto(msg): ...

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
        return int(val) if val else 0
    except Exception as e:
        print(f"[ERRO Planilha] get_tokens: {e}")
        return 0

def increment_tokens(sheet, row, novos_tokens):
    try:
        tokens_atuais = get_tokens(sheet, row)
        sheet.update_cell(row, 5, tokens_atuais + novos_tokens)
        return tokens_atuais + novos_tokens
    except Exception as e:
        print(f"[ERRO Planilha] increment_tokens: {e}")
        return get_tokens(sheet, row)

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    incoming_msg = form["Body"].strip()
    from_number = format_number(form["From"])

    estado = carregar_estado(from_number)
    ultima_msg_registrada = estado.get("ultima_msg", "")

    # Verificação de duplicidade mais robusta
    if incoming_msg == ultima_msg_registrada:
        print("[DEBUG] Mensagem duplicada detectada e ignorada.")
        return {"status": "mensagem duplicada ignorada"}

    estado["ultima_msg"] = incoming_msg
    # Salvar estado *após* processar a mensagem ou em pontos chave

    # --- INÍCIO SETUP USUÁRIO ---
    try:
        sheet_usuario = get_user_sheet(from_number)
        linha_index = sheet_usuario.col_values(2).index(from_number) + 1
        linha_usuario = sheet_usuario.row_values(linha_index)
    except ValueError:
        print(f"[INFO] Usuário {from_number} não encontrado, adicionando.")
        now_str = datetime.datetime.now(pytz.timezone("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S")
        try:
            sheet_usuario.append_row(["", from_number, "", now_str, 0, 0])
            linha_index = sheet_usuario.col_values(2).index(from_number) + 1
            linha_usuario = ["", from_number, "", now_str, 0, 0]
        except Exception as e:
            print(f"[ERRO GRAVE Planilha] Falha ao adicionar novo usuário {from_number}: {e}")
            # Enviar mensagem de erro genérica e sair?
            send_message(from_number, "Tivemos um problema interno ao processar sua solicitação. Por favor, tente novamente mais tarde.")
            return {"status": "erro crítico ao adicionar usuário"}
    except Exception as e:
        print(f"[ERRO GRAVE Planilha] Falha ao buscar/criar usuário {from_number}: {e}")
        send_message(from_number, "Tivemos um problema interno ao processar sua solicitação. Por favor, tente novamente mais tarde.")
        return {"status": "erro crítico ao buscar usuário"}

    increment_interactions(sheet_usuario, linha_index)

    name = linha_usuario[0].strip() if len(linha_usuario) > 0 and linha_usuario[0] else "Usuário"
    email = linha_usuario[2].strip() if len(linha_usuario) > 2 and linha_usuario[2] else None

    tokens_msg = count_tokens(incoming_msg)
    increment_tokens(sheet_usuario, linha_index, tokens_msg)
    # --- FIM SETUP USUÁRIO ---

    # --- INÍCIO FLUXO ONBOARDING/CADASTRO ---
    if is_boas_vindas(incoming_msg):
        if not name or name == "Usuário" or not email:
            # Se já está aguardando cadastro, não manda a msg de novo
            if estado.get("ultimo_fluxo") != "aguardando_cadastro":
                send_message(from_number, mensagens.estilo_msg(mensagens.solicitacao_cadastro()))
                estado["ultimo_fluxo"] = "aguardando_cadastro"
                salvar_estado(from_number, estado)
            return {"status": "aguardando nome e email"}

        # Se já tem nome/email e já saudou antes, evita repetir
        if estado.get("saudacao_realizada"):
            # Poderia ter uma resposta mais dinâmica aqui? Ou só ignorar?
            # send_message(from_number, mensagens.estilo_msg("Já estou aqui com você! Como posso te ajudar agora? 😉"))
            print("[DEBUG] Saudação repetida ignorada.")
            # Não retorna aqui, deixa o fluxo seguir para interpretar a mensagem
        else:
            primeiro_nome = name.split()[0] if name != "Usuário" else ""
            resposta_curta = mensagens.cadastro_completo(primeiro_nome)
            send_message(from_number, mensagens.estilo_msg(resposta_curta))
            estado["ultimo_fluxo"] = "cadastro_completo" # Ou talvez "inicio_conversa"?
            estado["saudacao_realizada"] = True
            salvar_estado(from_number, estado)
            return {"status": "cadastro completo e saudação feita"}

    # Lógica para capturar nome/email se ainda não tiver
    if not name or name == "Usuário" or not email:
        nome_capturado = None
        email_capturado = None
        
        # Tenta capturar das linhas da mensagem atual
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
                print(f"[INFO] Nome atualizado para {name}")
            except Exception as e:
                 print(f"[ERRO Planilha] Falha ao atualizar nome para {nome_capturado}: {e}")

        if email_capturado and not email:
            try:
                sheet_usuario.update_cell(linha_index, 3, email_capturado)
                email = email_capturado
                email_atualizado = True
                print(f"[INFO] Email atualizado para {email}")
            except Exception as e:
                 print(f"[ERRO Planilha] Falha ao atualizar email para {email_capturado}: {e}")

        # Verifica o que ainda falta e pede
        if not name or name == "Usuário":
            # Se acabou de atualizar o email, não pede nome de novo na mesma msg
            if not email_atualizado:
                send_message(from_number, mensagens.estilo_msg("Ótimo! E qual seu nome completo, por favor? ✍️"))
                estado["ultimo_fluxo"] = "aguardando_cadastro"
                salvar_estado(from_number, estado)
                return {"status": "aguardando nome"}
        elif not email:
             # Se acabou de atualizar o nome, não pede email de novo na mesma msg
            if not nome_atualizado:
                send_message(from_number, mensagens.estilo_msg("Perfeito! Agora só preciso do seu e-mail. 📧"))
                estado["ultimo_fluxo"] = "aguardando_cadastro"
                salvar_estado(from_number, estado)
                return {"status": "aguardando email"}
        
        # Se ambos foram atualizados ou já existiam
        if name and name != "Usuário" and email:
            primeiro_nome = name.split()[0]
            send_message(from_number, mensagens.estilo_msg(mensagens.cadastro_completo(primeiro_nome)))
            estado["ultimo_fluxo"] = "cadastro_completo"
            estado["saudacao_realizada"] = True # Assume que se completou cadastro, saudação tá feita
            salvar_estado(from_number, estado)
            return {"status": "cadastro completo via captura"}
        else:
            # Se algo deu errado ou só capturou um, mantém aguardando cadastro
            estado["ultimo_fluxo"] = "aguardando_cadastro"
            salvar_estado(from_number, estado)
            # Mensagem já foi enviada pedindo o que falta
            return {"status": "continuando aguardando cadastro"}
            
    # --- FIM FLUXO ONBOARDING/CADASTRO ---

    # --- INÍCIO PROCESSAMENTO DE MENSAGEM (PÓS-CADASTRO) ---
    
    # Flag para saber se a mensagem foi tratada por um fluxo específico
    mensagem_tratada = False 

    # --- INÍCIO NOVO FLUXO DE REGISTRO DE GASTOS (GPT + CONVERSACIONAL) ---
    ultimo_fluxo_gasto = estado.get("ultimo_fluxo")
    gasto_pendente = estado.get("gasto_pendente")

    # 1. Usuário está respondendo sobre FORMA DE PAGAMENTO?
    if ultimo_fluxo_gasto == "aguardando_forma_pagamento" and gasto_pendente:
        forma_pagamento_resposta = incoming_msg.strip().capitalize()
        # Validação simples da forma de pagamento (pode melhorar)
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
                 
            # Mantém gasto_pendente no estado
            salvar_estado(from_number, estado)
            send_message(from_number, mensagens.estilo_msg(mensagem_confirmacao))
            mensagem_tratada = True
        else:
            # Forma de pagamento inválida ou vazia, pede de novo
            send_message(from_number, mensagens.estilo_msg("Não entendi a forma de pagamento. Pode repetir? (crédito, débito, pix, etc.)"))
            # Mantém o estado como aguardando_forma_pagamento
            salvar_estado(from_number, estado)
            mensagem_tratada = True

    # 2. Usuário está respondendo sobre CONFIRMAÇÃO DE CATEGORIA?
    elif ultimo_fluxo_gasto == "aguardando_confirmacao_categoria" and gasto_pendente:
        resposta_categoria = incoming_msg.strip().lower()
        categoria_final = ""
        
        if resposta_categoria in ["sim", "s", "correto", "ok", "isso", "tá certo", "pode ser"]:
            categoria_final = gasto_pendente.get("categoria_sugerida")
        elif resposta_categoria not in ["não", "nao", "errado"]:
            # Assume que o usuário digitou a categoria correta
            categoria_final = incoming_msg.strip().capitalize()
        
        if categoria_final:
            # REGISTRA O GASTO COMPLETO
            fuso = pytz.timezone("America/Sao_Paulo")
            hoje = datetime.datetime.now(fuso).strftime("%d/%m/%Y")
            resposta_registro = registrar_gasto(
                nome_usuario=name,
                numero_usuario=from_number, # Usar número formatado
                descricao=gasto_pendente["descricao"],
                valor=gasto_pendente["valor"],
                forma_pagamento=gasto_pendente["forma_pagamento"],
                data_gasto=hoje,
                categoria_manual=categoria_final
            )
            resetar_estado(from_number) # Limpa estado após tentativa de registro
            if resposta_registro["status"] == "ok":
                valor_formatado = f"R${gasto_pendente['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                send_message(from_number, mensagens.estilo_msg(f"✅ Gasto registrado: {gasto_pendente['descricao']} ({valor_formatado}) em {categoria_final}."))
            elif resposta_registro["status"] == "ignorado":
                 send_message(from_number, mensagens.estilo_msg("📝 Hmm, parece que esse gasto já foi registrado antes."))
            else:
                 send_message(from_number, mensagens.estilo_msg(f"⚠️ Tive um problema ao registrar o gasto na planilha. Por favor, tente de novo ou verifique mais tarde."))
                 print(f"[ERRO REGISTRO] {resposta_registro.get('mensagem')}")
            mensagem_tratada = True
        else:
            # Usuário disse 'não' mas não informou a categoria
            send_message(from_number, mensagens.estilo_msg("Ok. Qual seria a categoria correta para este gasto?"))
            estado["ultimo_fluxo"] = "aguardando_definicao_categoria"
            # Mantém gasto_pendente
            salvar_estado(from_number, estado)
            mensagem_tratada = True

    # 3. Usuário está respondendo sobre DEFINIÇÃO DE CATEGORIA?
    elif ultimo_fluxo_gasto == "aguardando_definicao_categoria" and gasto_pendente:
        categoria_resposta = incoming_msg.strip().capitalize()
        if categoria_resposta and len(categoria_resposta) > 2: # Validação simples
            # REGISTRA O GASTO COMPLETO
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
            resetar_estado(from_number)
            if resposta_registro["status"] == "ok":
                valor_formatado = f"R${gasto_pendente['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                send_message(from_number, mensagens.estilo_msg(f"✅ Gasto registrado: {gasto_pendente['descricao']} ({valor_formatado}) em {categoria_resposta}."))
            elif resposta_registro["status"] == "ignorado":
                 send_message(from_number, mensagens.estilo_msg("📝 Hmm, parece que esse gasto já foi registrado antes."))
            else:
                 send_message(from_number, mensagens.estilo_msg(f"⚠️ Tive um problema ao registrar o gasto na planilha. Por favor, tente de novo ou verifique mais tarde."))
                 print(f"[ERRO REGISTRO] {resposta_registro.get('mensagem')}")
            mensagem_tratada = True
        else:
            # Categoria inválida ou vazia, pede de novo
            send_message(from_number, mensagens.estilo_msg("Não entendi a categoria. Pode me dizer de novo? (Ex: Alimentação, Transporte, Lazer...)"))
            # Mantém o estado
            salvar_estado(from_number, estado)
            mensagem_tratada = True
            
    # 4. Se não estava respondendo a perguntas anteriores, TENTA INTERPRETAR A MENSAGEM COMO UM NOVO GASTO
    if not mensagem_tratada:
        # Verifica se a mensagem parece um gasto antes de chamar o GPT (otimização)
        # Heurística simples: contém números e talvez R$ ou palavras como gastei/paguei/comprei
        contem_valor = any(char.isdigit() for char in incoming_msg)
        palavras_chave_gasto = ["gastei", "paguei", "comprei", "custou", "foi R$", "deu R$"]
        indica_gasto = contem_valor and (re.search(r'R\$\s*\d', incoming_msg, re.IGNORECASE) or any(p in incoming_msg.lower() for p in palavras_chave_gasto))
        
        # Evita interpretar comandos ou pedidos de resumo como gastos
        if indica_gasto and not quer_lista_comandos(incoming_msg) and not quer_resumo_mensal(incoming_msg) and not incoming_msg.lower().startswith("/resumo"):
            print("[DEBUG] Tentando interpretar mensagem como gasto via GPT...")
            dados_gasto_gpt = interpretar_gasto_com_gpt(incoming_msg)

            if dados_gasto_gpt: 
                # GPT conseguiu extrair informações
                descricao = dados_gasto_gpt.get("descricao")
                valor = dados_gasto_gpt.get("valor")
                forma_pagamento = dados_gasto_gpt.get("forma_pagamento")
                categoria_sugerida = dados_gasto_gpt.get("categoria_sugerida")
                
                valor_formatado = f"R${valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

                if forma_pagamento and forma_pagamento != "N/A":
                    # Temos forma de pagamento, pergunta sobre categoria
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
                    salvar_estado(from_number, estado)
                    send_message(from_number, mensagens.estilo_msg(mensagem))
                    mensagem_tratada = True
                    
                else:
                    # Falta forma de pagamento
                    mensagem = f"Entendi: {descricao} - {valor_formatado}. Como você pagou (crédito, débito, pix, etc.)?"
                    estado["ultimo_fluxo"] = "aguardando_forma_pagamento"
                    estado["gasto_pendente"] = dados_gasto_gpt
                    salvar_estado(from_number, estado)
                    send_message(from_number, mensagens.estilo_msg(mensagem))
                    mensagem_tratada = True
            else:
                # GPT não conseguiu extrair ou falhou
                print("[DEBUG] GPT não retornou dados válidos para o gasto.")
                # Deixa seguir para a conversa normal
                pass 
        # Se não indica gasto, segue para conversa normal

    # --- FIM NOVO FLUXO DE REGISTRO DE GASTOS ---

    # --- INÍCIO FLUXOS DE COMANDOS E CONVERSA GERAL ---
    # Só executa se a mensagem não foi tratada pelo fluxo de gastos
    if not mensagem_tratada:
        print("[DEBUG] Mensagem não tratada como gasto, seguindo para comandos/conversa...")
        
        # Comandos /ajuda, /comandos, etc.
        if quer_lista_comandos(incoming_msg):
            comandos_txt = (
                "📋 *Comandos disponíveis:*\n"
                "/resumo – Ver seu resumo financeiro do dia\n"
                "/limites – Mostrar seus limites por categoria\n"
                # "/relatorio – Análise completa dos seus gastos (em breve)\n"
                # "/ranking – Ver o ranking dos usuários\n"
                # "/minhas_estrelas – Ver suas estrelas acumuladas\n"
                "/ajuda – Mostrar esta lista de comandos\n\n"
                "💡 *Para registrar gastos, apenas me diga o que gastou!*\n"
                "Ex: 'Gastei 50 reais no almoço com pix' ou 'Comprei pão na padaria por 10 reais no débito'"
            )
            send_message(from_number, mensagens.estilo_msg(comandos_txt))
            salvar_estado(from_number, estado) # Salva estado com ultima_msg
            return {"status": "comandos enviados"}
        
        # Resumo Mensal
        if quer_resumo_mensal(incoming_msg):
            resumo = resumo_do_mes(from_number)
            limites_txt = verificar_limites(from_number)
            send_message(from_number, mensagens.estilo_msg(resumo + "\n\n" + limites_txt))
            salvar_estado(from_number, estado)
            return {"status": "resumo mensal enviado"}

        # Resumo Diário / Ontem (simplificado)
        if any(t in incoming_msg.lower() for t in [
            "resumo do dia", "resumo de hoje", "quanto gastei hoje",
            "novo resumo", "resumo agora", "resumo atualizado",
            "quero o resumo", "meu resumo", "resumo aqui", "/resumo"
        ]):
            resumo = gerar_resumo(from_number, periodo="diario")
            send_message(from_number, mensagens.estilo_msg(resumo))
            salvar_estado(from_number, estado)
            return {"status": "resumo hoje enviado"}

        if any(t in incoming_msg.lower() for t in ["resumo de ontem", "quanto gastei ontem"]):
            ontem = datetime.datetime.now(pytz.timezone("America/Sao_Paulo")) - datetime.timedelta(days=1)
            resumo = gerar_resumo(from_number, periodo="custom", data_personalizada=ontem.date())
            send_message(from_number, mensagens.estilo_msg(resumo))
            salvar_estado(from_number, estado)
            return {"status": "resumo ontem enviado"}
            
        # Lógica de Upgrade (mantida)
        if verificar_upgrade_automatico(from_number):
            send_message(from_number, mensagens.estilo_msg(
                "🔓 Seu acesso premium foi liberado!\nBem-vindo ao grupo dos que escolheram dominar a vida financeira com dignidade e IA de primeira. 🙌"))
            # Não retorna, pode ser que a mensagem atual seja outra coisa

        # Alerta de limite gratuito (mantido)
        # Considerar se este limite deve ser verificado antes ou depois da conversa
        user_status = get_user_status(from_number)
        if user_status == "Gratuitos" and passou_limite(sheet_usuario, linha_index):
                contexto_usuario = contexto_principal_usuario(from_number, ultima_msg=incoming_msg)
                mensagem_alerta = mensagens.alerta_limite_gratuito(contexto_usuario)
                send_message(from_number, mensagens.estilo_msg(mensagem_alerta, leve=False))
                salvar_estado(from_number, estado)
                return {"status": "limite gratuito atingido"}

        # --- INÍCIO CONVERSA GERAL COM GPT --- 
        print("[DEBUG] Iniciando fluxo de conversa geral com GPT...")
        
        # Prepara histórico para GPT
        conversa_path = f"conversas/{from_number}.txt"
        if not os.path.exists("conversas"):
            os.makedirs("conversas")
        if not os.path.isfile(conversa_path):
            with open(conversa_path, "w", encoding='utf-8') as f:
                f.write("")
        
        try:
            with open(conversa_path, "r", encoding='utf-8') as f:
                linhas_conversa = f.readlines()
        except Exception as e:
            print(f"[ERRO] Falha ao ler histórico {conversa_path}: {e}")
            linhas_conversa = []

        # Filtra mensagens genéricas do histórico (mantido)
        historico_filtrado = [
            linha for linha in linhas_conversa
            if not any(frase in linha.lower() for frase in [
                "sou seu conselheiro financeiro",
                "perfeito,",
                "tô aqui pra te ajudar",
                "posso te ajudar com controle de gastos",
                "por onde quer começar"
            ])
        ]
        historico_relevante = historico_filtrado[-6:] # Aumentar um pouco o histórico?

        # Monta mensagens para GPT
        mensagens_para_gpt = list(mensagens_gpt_base) # Copia a base

        # Adiciona contexto da Knowledge Base (se não for pedido de resumo)
        termos_resumo_financeiro = ["resumo", "resumo do dia", "resumo financeiro", "quanto gastei", "gastos hoje"]
        if not any(termo in incoming_msg.lower() for termo in termos_resumo_financeiro):
            # Detecta categoria da mensagem atual para busca na knowledge
            categoria_detectada_conversa = "geral"
            texto_lower_conversa = incoming_msg.lower()
            PALAVRAS_CHAVE_CATEGORIAS = {
                "espiritualidade": ["oração", "culpa", "confissão", "direção espiritual", "vida espiritual", "fé", "deus", "confessar"],
                "financeiro": ["gasto", "dinheiro", "investimento", "renda", "salário", "orçamento", "juros", "empréstimo", "dívida"],
                "casamento": ["cônjuge", "esposa", "marido", "matrimônio", "casamento", "vida a dois", "parceiro"],
                # "dívidas": ["dívida", "devendo", "nome sujo", "negativado", "cobrança", "boleto atrasado"], # Incluído em financeiro
                "filosofia": ["virtude", "temperamento", "aristóteles", "santo tomás", "ética", "filosofia", "psicologia"],
            }
            for categoria, palavras in PALAVRAS_CHAVE_CATEGORIAS.items():
                if any(palavra in texto_lower_conversa for palavra in palavras):
                    categoria_detectada_conversa = categoria
                    break
            
            contexto_resgatado = buscar_conhecimento_relevante(incoming_msg, categoria=categoria_detectada_conversa, top_k=3)
            if contexto_resgatado:
                print(f"[DEBUG] Contexto Knowledge: {contexto_resgatado[:100]}...")
                mensagens_para_gpt.append({
                    "role": "system",
                    "content": (
                        "Ao responder, baseie-se prioritariamente nas informações a seguir, respeitando fielmente "
                        "o estilo, tom, e os princípios contidos:\n\n"
                        f"{contexto_resgatado}"
                    )
                })
            else:
                 print("[DEBUG] Nenhum contexto relevante encontrado na Knowledge Base.")

        # Adiciona histórico da conversa
        for linha in historico_relevante:
            try:
                partes = linha.split(":", 1)
                if len(partes) == 2:
                    role = "user" if "Usuário:" in partes[0] else "assistant"
                    conteudo = partes[1].strip()
                    if conteudo: # Evita adicionar mensagens vazias
                        mensagens_para_gpt.append({"role": role, "content": conteudo})
            except Exception as e:
                print(f"[ERRO] Falha ao processar linha do histórico: {linha} - {e}")

        # Adiciona mensagem atual do usuário
        mensagens_para_gpt.append({"role": "user", "content": incoming_msg})

        # Adiciona indicadores econômicos se relevante (mantido)
        termos_macro = ["empréstimo", "juros", "selic", "ipca", "cdi", "inflação", "investimento", "cenário econômico"]
        if any(palavra in incoming_msg.lower() for palavra in termos_macro):
            indicadores = get_indicadores()
            if indicadores:
                texto_indicadores = "\n".join([
                    f"{nome.upper()}: {valor}%" if isinstance(valor, (int, float)) else f"{nome.upper()}: {valor}" 
                    for nome, valor in indicadores.items() if valor is not None
                ])
                mensagens_para_gpt.append({
                    "role": "system", # Ou 'user'? System parece mais apropriado para info contextual
                    "content": f"Lembre-se dos indicadores econômicos atuais ao responder:\n{texto_indicadores}"
                })

        # Chama GPT para obter a resposta da conversa
        try:
            print(f"[DEBUG] Chamando GPT para conversa com {len(mensagens_para_gpt)} mensagens.")
            response = openai.ChatCompletion.create(
                model="gpt-4-turbo", # Ou o modelo que preferir
                messages=mensagens_para_gpt,
                temperature=0.7,
            )
            reply = response["choices"][0]["message"]["content"].strip()
            print(f"[DEBUG] Resposta GPT (conversa): {reply[:100]}...")
        except Exception as e:
            print(f"[ERRO OpenAI Conversa] {e}")
            reply = "⚠️ Tive um problema ao processar sua mensagem agora. Poderia tentar de novo, por favor?"

        # Pós-processamento da resposta (mantido)
        reply = re.sub(r'^(oi|olá|opa|e aí)[,.!]?\s*', '', reply, flags=re.IGNORECASE).strip()
        if "[Nome]" in reply:
            primeiro_nome = name.split()[0] if name and name != "Usuário" else ""
            reply = reply.replace("[Nome]", primeiro_nome)

        # Disclaimer para assuntos sensíveis (mantido)
        assuntos_sensiveis = ["violência", "agressão", "abuso", "depressão", "ansiedade", "suicídio", "terapia"]
        if any(termo in incoming_msg.lower() for termo in assuntos_sensiveis):
            disclaimer = (
                "\n\n⚠️ *Lembre-se: Sou uma IA e não substituo acompanhamento profissional especializado em saúde, orientação espiritual direta ou consultoria financeira personalizada.*"
            )
            if disclaimer not in reply:
                 reply += disclaimer

        # Salva a conversa (User + Assistant)
        try:
            with open(conversa_path, "a", encoding='utf-8') as f:
                f.write(f"Usuário: {incoming_msg}\n")
                f.write(f"Conselheiro: {reply}\n")
        except Exception as e:
            print(f"[ERRO] Falha ao salvar conversa {conversa_path}: {e}")

        # Envia a resposta final
        if reply:
            send_message(from_number, mensagens.estilo_msg(reply))
        else:
            # Fallback se GPT não responder nada
            send_message(from_number, mensagens.estilo_msg("Não entendi muito bem. Pode reformular, por favor?"))
            print("[AVISO] Resposta vazia do GPT para conversa.")
            
        # --- FIM CONVERSA GERAL COM GPT --- 

    # --- INÍCIO TAREFAS ASSÍNCRONAS / FINALIZAÇÃO ---
    # (Estas podem rodar independentemente de ser gasto ou conversa)
    
    # Avaliação de emoção (mantida)
    try:
        fuso = pytz.timezone("America/Sao_Paulo")
        data_msg_str = datetime.datetime.now(fuso).strftime("%Y-%m-%d %H:%M:%S")
        emocao = detectar_emocao(incoming_msg)
        if emocao:
            alerta_emocao = aumento_pos_emocao(from_number, emocao, data_msg_str)
            if alerta_emocao:
                # Enviar como uma mensagem separada? Ou adicionar ao reply?
                # send_message(from_number, mensagens.estilo_msg(alerta_emocao))
                print(f"[INFO Emoção] Alerta gerado: {alerta_emocao}")
    except Exception as e:
        print(f"[ERRO Emoção] Falha na detecção/alerta: {e}")

    # Avaliação de engajamento (mantida, mas talvez precise ajustar)
    # try:
    #     mensagem_estrela = avaliar_engajamento(from_number, incoming_msg)
    #     if mensagem_estrela:
    #         send_message(from_number, mensagens.estilo_msg(mensagem_estrela))
    # except Exception as e:
    #     print(f"[ERRO Engajamento] {e}")

    # Verificação de alertas de limite (mantida - rodar periodicamente?)
    # verificar_alertas() # Chamar isso aqui a cada msg pode ser ineficiente
    
    # Envio de lembretes (mantido - rodar periodicamente?)
    # enviar_lembretes() # Chamar isso aqui a cada msg pode ser ineficiente
    
    # Salva o estado final da interação
    salvar_estado(from_number, estado)

    print(f"[INFO] Processamento da mensagem de {from_number} concluído.")
    return {"status": "processamento concluído"}
    # --- FIM PROCESSAMENTO DE MENSAGEM ---

@app.get("/health")
def health_check():
    return {"status": "vivo, lúcido e com fé"}

# Adicionar para rodar com Uvicorn (se não estiver usando um Procfile ou similar)
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))