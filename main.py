from fastapi import FastAPI, Request
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from twilio.rest import Client
from openai import OpenAI
import os
import re

app = FastAPI()

# Variáveis de ambiente
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
MESSAGING_SERVICE_SID = os.getenv('MESSAGING_SERVICE_SID')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Configuração OpenAI (SEM passar api_key diretamente)
client_openai = OpenAI()

# Configuração Google Sheets
def conecta_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name('/etc/secrets/meugpt-api-sheets-92a9d439900d.json', scope)
    client = gspread.authorize(creds)
    return client

# Verifica pagante
def verifica_pagante(numero):
    client = conecta_google_sheets()
    sheet = client.open_by_url('https://docs.google.com/spreadsheets/d/1bhnyG0-DaH3gE687_tUEy9kVI7rV-bxJl10bRKkDl2Y/edit?usp=sharing').worksheet('Pagantes')
    lista = sheet.get_all_records()
    for linha in lista:
        if str(linha['WHATSAPP']) == numero and linha['STATUS'].upper() == 'ATIVO':
            return True
    return False

# Valida e-mail com regex
def email_valido(email):
    padrao = r'^[\w\.-]+@[\w\.-]+\.\w{2,}$'
    return re.match(padrao, email)

# Atualiza gratuitos sem duplicação
def atualiza_gratuitos(numero, nome, email):
    client = conecta_google_sheets()
    sheet = client.open_by_url('https://docs.google.com/spreadsheets/d/1bhnyG0-DaH3gE687_tUEy9kVI7rV-bxJl10bRKkDl2Y/edit?usp=sharing').worksheet('Gratuitos')
    cell = sheet.find(numero)
    
    if cell:
        row = cell.row
        dados = sheet.row_values(row)
        nome_atual = dados[0]
        email_atual = dados[2]
        contador_atual = int(dados[3]) + 1
        sheet.update_cell(row, 4, contador_atual)
        if not nome_atual and nome:
            sheet.update_cell(row, 1, nome)
            nome_atual = nome
        if not email_atual and email and email_valido(email):
            sheet.update_cell(row, 3, email)
            email_atual = email
        return contador_atual, nome_atual, email_atual
    else:
        nome_final = nome if nome else ""
        email_final = email if email and email_valido(email) else ""
        sheet.append_row([nome_final, numero, email_final, 1])
        return 1, nome_final, email_final

# Envio WhatsApp
def enviar_whatsapp(mensagem, numero_destino):
    client_twilio = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    try:
        message = client_twilio.messages.create(
            messaging_service_sid=MESSAGING_SERVICE_SID,
            body=mensagem,
            to=f'whatsapp:{numero_destino}'
        )
        print(f"✅ WhatsApp enviado para {numero_destino}. SID: {message.sid}")
    except Exception as e:
        print(f"❌ Erro ao enviar WhatsApp: {e}")

# Consulta GPT (SEM api_key direto)
def consulta_chatgpt(nome, mensagem_usuario):
    prompt = f"""
Você é o Meu Conselheiro Financeiro pessoal, criado por Matheus Campos, CFP®.

Sua missão é organizar a vida financeira do usuário respeitando rigorosamente esta hierarquia: Deus, família e trabalho, nesta ordem.

Usuário: {mensagem_usuario}
Conselheiro:
"""
    response = client_openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "system", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

# Extrai email
def extrair_email(texto):
    email_match = re.search(r'[\w\.-]+@[\w\.-]+', texto)
    if email_match:
        return email_match.group(0)
    return ""

# Extrai nome com limpeza
def extrair_nome(texto):
    email_match = re.search(r'[\w\.-]+@[\w\.-]+', texto)
    if email_match:
        nome = texto[:email_match.start()].strip()
    else:
        nome = texto.strip()

    nome = re.sub(r"(?i)(meu nome é|nome:|eu sou|sou)\s*", "", nome)
    return nome

# Endpoint principal
@app.post("/webhook")
async def receber_mensagem(request: Request):
    dados = await request.form()
    numero = dados.get('From').replace("whatsapp:", "").strip()
    mensagem_usuario = dados.get('Body')

    # Extrair nome e email
    email_extraido = extrair_email(mensagem_usuario)
    nome_extraido = extrair_nome(mensagem_usuario) if mensagem_usuario else ""

    # Validar e-mail
    email_validado = email_extraido if email_valido(email_extraido) else ""

    if verifica_pagante(numero):
        resposta_gpt = consulta_chatgpt(nome_extraido if nome_extraido else "Usuário", mensagem_usuario)
        enviar_whatsapp(resposta_gpt, numero_destino=numero)
        return {"resposta": resposta_gpt}

    # Gratuito: atualiza SEM duplicação
    interacoes, nome_salvo, email_salvo = atualiza_gratuitos(numero, nome_extraido, email_validado)

    # Boas-vindas só na primeira vez
    if interacoes == 1 and not nome_salvo and not email_salvo:
        mensagem_inicial = f"Olá! Seja bem-vindo(a) ao Meu Conselheiro Financeiro. 👋🏼\nMeu objetivo é ajudar você a colocar sua vida financeira no eixo — sempre respeitando o que é mais importante: sua família e seu propósito.\n\nPara começarmos, me envie seu **nome e seu e-mail** por aqui. É rápido e essencial pra continuarmos."
        enviar_whatsapp(mensagem_inicial, numero_destino=numero)
        return {"resposta": mensagem_inicial}

    # Se mandou email errado
    if email_extraido and not email_valido(email_extraido):
        mensagem_email_incorreto = "Ops! Parece que seu e-mail está incompleto ou incorreto. Por favor, me envie um e-mail válido para continuarmos!"
        enviar_whatsapp(mensagem_email_incorreto, numero_destino=numero)
        return {"resposta": mensagem_email_incorreto}

    # Se já tem nome e e-mail válidos, responde normal
    if nome_salvo and email_salvo:
        resposta_gpt = consulta_chatgpt(nome_salvo, mensagem_usuario)
        enviar_whatsapp(resposta_gpt, numero_destino=numero)
        return {"resposta": resposta_gpt}

    # Se preencheu só uma parte, aguarda
    mensagem_aguardo = "Perfeito! Agora me envie seu nome e e-mail para começarmos!"
    enviar_whatsapp(mensagem_aguardo, numero_destino=numero)
    return {"resposta": mensagem_aguardo}
