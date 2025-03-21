from fastapi import FastAPI, Request
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from twilio.rest import Client
import openai
import os
import re

app = FastAPI()

# Variáveis de ambiente
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
MESSAGING_SERVICE_SID = os.getenv('MESSAGING_SERVICE_SID')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Configuração OpenAI
openai.api_key = OPENAI_API_KEY

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

# Atualiza gratuitos
def atualiza_gratuitos(numero, nome, email):
    client = conecta_google_sheets()
    sheet = client.open_by_url('https://docs.google.com/spreadsheets/d/1bhnyG0-DaH3gE687_tUEy9kVI7rV-bxJl10bRKkDl2Y/edit?usp=sharing').worksheet('Gratuitos')
    lista = sheet.get_all_records()
    for i, linha in enumerate(lista):
        if str(linha['WHATSAPP']) == numero:
            # Atualizar nome e email, se estiverem vazios
            if not linha['NOME'] and nome:
                sheet.update_cell(i+2, 1, nome)
            if not linha['EMAIL'] and email:
                sheet.update_cell(i+2, 3, email)
            novo_valor = int(linha['CONTADOR']) + 1
            sheet.update_cell(i+2, 4, novo_valor)
            return novo_valor, linha['NOME'] if linha['NOME'] else nome, linha['EMAIL'] if linha['EMAIL'] else email
    # Novo gratuito
    sheet.append_row([nome, numero, email, 1])
    return 1, nome, email

# Envio WhatsApp via Messaging Service
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
        print(f"❌ Erro no envio do WhatsApp: {e}")

# Consulta GPT
def consulta_chatgpt(nome, mensagem_usuario):
    prompt = f"""
Você é o Meu Conselheiro Financeiro pessoal, criado por Matheus Campos, CFP®.

Sua missão é organizar a vida financeira do usuário respeitando rigorosamente esta hierarquia: Deus, família e trabalho, nesta ordem.

Usuário: {mensagem_usuario}
Conselheiro:
"""
    resposta = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "system", "content": prompt}]
    )
    return resposta.choices[0].message['content'].strip()

# Detecta e extrai email
def extrair_email(texto):
    email_match = re.search(r'[\w\.-]+@[\w\.-]+', texto)
    if email_match:
        return email_match.group(0)
    return ""

# Endpoint principal
@app.post("/webhook")
async def receber_mensagem(request: Request):
    dados = await request.form()
    numero = dados.get('From').replace("whatsapp:", "").strip()
    mensagem_usuario = dados.get('Body')

    client = conecta_google_sheets()
    sheet = client.open_by_url('https://docs.google.com/spreadsheets/d/1bhnyG0-DaH3gE687_tUEy9kVI7rV-bxJl10bRKkDl2Y/edit?usp=sharing').worksheet('Gratuitos')
    lista = sheet.get_all_records()

    nome = ""
    email = ""

    # Verifica se o número já consta
    for i, linha in enumerate(lista):
        if str(linha['WHATSAPP']) == numero:
            nome = linha['NOME']
            email = linha['EMAIL']
            break

    # Tentar extrair email, se ele mandar
    email_extraido = extrair_email(mensagem_usuario)
    if email_extraido and not email:
        email = email_extraido

    # Se for pagante
    if verifica_pagante(numero):
        resposta_gpt = consulta_chatgpt(nome if nome else "Usuário", mensagem_usuario)
        enviar_whatsapp(resposta_gpt, numero_destino=numero)
        return {"resposta": resposta_gpt}

    # Se gratuito
    interacoes, nome_salvo, email_salvo = atualiza_gratuitos(numero, nome, email)

    # PRIMEIRA MENSAGEM clara e única se ainda não preencheu dados:
    if not nome_salvo or not email_salvo:
        mensagem_inicial = f"Olá! Seja bem-vindo(a) ao Meu Conselheiro Financeiro. 👋🏼\nNosso objetivo é ajudar você a colocar sua vida financeira no eixo — sempre respeitando o que é mais importante: sua família e seu propósito.\n\nPara começarmos, me envie seu **nome e seu e-mail** por aqui. É rápido e essencial pra continuarmos."
        enviar_whatsapp(mensagem_inicial, numero_destino=numero)
        return {"resposta": mensagem_inicial}

    # Se já tem dados, segue normal
    resposta = consulta_chatgpt(nome_salvo, mensagem_usuario)
    enviar_whatsapp(resposta, numero_destino=numero)
    return {"resposta": resposta}
