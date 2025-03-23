from fastapi import FastAPI, Request
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from twilio.rest import Client
from openai import OpenAI
import os
import re

app = FastAPI()

TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
MESSAGING_SERVICE_SID = os.getenv('MESSAGING_SERVICE_SID')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

cliente_openai = OpenAI(api_key=OPENAI_API_KEY, http_client=None)

def conecta_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name('/etc/secrets/meugpt-api-sheets-92a9d439900d.json', scope)
    client = gspread.authorize(creds)
    return client

def verifica_pagante(numero):
    client = conecta_google_sheets()
    sheet = client.open_by_url('https://docs.google.com/spreadsheets/d/1bhnyG0-DaH3gE687_tUEy9kVI7rV-bxJl10bRKkDl2Y/edit?usp=sharing').worksheet('Pagantes')
    lista = sheet.get_all_records()
    for linha in lista:
        if linha['WHATSAPP'] == numero and linha['STATUS'].upper() == 'ATIVO':
            return True
    return False

def atualiza_gratuitos(numero, nome, email):
    client = conecta_google_sheets()
    sheet = client.open_by_url('https://docs.google.com/spreadsheets/d/1bhnyG0-DaH3gE687_tUEy9kVI7rV-bxJl10bRKkDl2Y/edit?usp=sharing').worksheet('Gratuitos')
    lista = sheet.get_all_records()
    for i, linha in enumerate(lista):
        if linha['WHATSAPP'] == numero:
            novo_valor = int(linha['CONTADOR']) + 1
            sheet.update_cell(i+2, 4, novo_valor)
            return novo_valor, linha['NOME']
    sheet.append_row([nome, numero, email, 1])
    return 1, nome

def enviar_whatsapp(mensagem, numero_destino):
    client_twilio = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    try:
        client_twilio.messages.create(
            messaging_service_sid=MESSAGING_SERVICE_SID,
            body=mensagem,
            to=f'whatsapp:{numero_destino}'
        )
    except Exception as e:
        print(f"Erro WhatsApp: {e}")

def extrair_dados_usuario(mensagem):
    prompt = f"""Extraia apenas nome e e-mail desta mensagem: "{mensagem}".
    Responda no formato: Nome: nome do usuário; Email: email do usuário.
    Caso não encontre algum deles, responda: Nome: Não informado; Email: Não informado."""
    resposta = cliente_openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "system", "content": prompt}]
    )
    dados = resposta.choices[0].message.content
    nome = re.search(r'Nome: (.*?);', dados)
    email = re.search(r'Email: (.+)', dados)
    nome = nome.group(1).strip() if nome else 'Não informado'
    email = email.group(1).strip() if email else 'Não informado'
    return nome, email

def consulta_chatgpt(nome, mensagem_usuario):
    prompt = f"""Você é o Meu Conselheiro Financeiro pessoal, criado por Matheus Campos, CFP®. Sua missão é organizar a vida financeira respeitando Deus, família e trabalho.
Usuário ({nome}): {mensagem_usuario}
Conselheiro:"""
    resposta = cliente_openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "system", "content": prompt}]
    )
    return resposta.choices[0].message.content.strip()

@app.post("/webhook")
async def receber_mensagem(request: Request):
    dados = await request.form()
    numero = dados.get('From', '').replace('whatsapp:', '')
    if not numero.startswith('+'):
        numero = '+' + numero

    mensagem_usuario = dados.get('Body', '').strip()

    if verifica_pagante(numero):
        resposta_gpt = consulta_chatgpt('Usuário Premium', mensagem_usuario)
        enviar_whatsapp(resposta_gpt, numero)
        return {"status": "premium"}

    sheet_gratuitos = conecta_google_sheets().open_by_url('https://docs.google.com/spreadsheets/d/1bhnyG0-DaH3gE687_tUEy9kVI7rV-bxJl10bRKkDl2Y/edit?usp=sharing').worksheet('Gratuitos')
    usuario_existente = sheet_gratuitos.find(numero)

    if not usuario_existente:
        nome, email = extrair_dados_usuario(mensagem_usuario)
        if nome == 'Não informado' or email == 'Não informado':
            enviar_whatsapp("Olá! 👋🏼 Que bom ter você aqui. Para começarmos nossa jornada financeira juntos, preciso apenas do seu nome e e-mail, por favor. Pode me mandar?", numero)
            return {"status": "dados pendentes"}
        interacoes, nome = atualiza_gratuitos(numero, nome, email)
        enviar_whatsapp(f"Seja muito bem-vindo(a), {nome}! 🎯 Estou aqui para te ajudar a organizar sua vida financeira colocando Deus, sua família e seu trabalho em primeiro lugar. Vamos juntos? Qual é seu principal objetivo financeiro hoje?", numero)
        return {"status": "boas-vindas"}

    interacoes, nome = atualiza_gratuitos(numero, 'Usuário', '')
    resposta_gpt = consulta_chatgpt(nome, mensagem_usuario)
    enviar_whatsapp(resposta_gpt, numero)
    return {"status": "gratuito"}
