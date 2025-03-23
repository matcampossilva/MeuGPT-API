from fastapi import FastAPI, Request
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from twilio.rest import Client
from openai import OpenAI
import os

app = FastAPI()

# Variáveis de ambiente
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
MESSAGING_SERVICE_SID = os.getenv('MESSAGING_SERVICE_SID')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

cliente_openai = OpenAI(api_key=OPENAI_API_KEY)

# Conectar ao Google Sheets
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
            novo_valor = int(linha['CONTADOR']) + 1
            sheet.update_cell(i+2, 4, novo_valor)
            return novo_valor
    sheet.append_row([nome, numero, email, 1])
    return 1

# Envia WhatsApp
def enviar_whatsapp(mensagem, numero_destino):
    client_twilio = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    client_twilio.messages.create(
        messaging_service_sid=MESSAGING_SERVICE_SID,
        body=mensagem,
        to=f'whatsapp:{numero_destino}'
    )

# Consulta ChatGPT
def consulta_chatgpt(nome, mensagem_usuario):
    resposta = cliente_openai.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": f"Você é o Conselheiro Financeiro criado por Matheus Campos. Trate o usuário {nome} de forma pessoal, leve e amigável."},
            {"role": "user", "content": mensagem_usuario}
        ]
    )
    return resposta.choices[0].message.content.strip()

@app.post("/webhook")
async def receber_mensagem(request: Request):
    dados = await request.form()
    numero = dados.get('From', '').replace('whatsapp:', '').replace('+', '')
    mensagem_usuario = dados.get('Body', '').strip()

    nome = "Usuário"
    email = ""

    if verifica_pagante(numero):
        resposta_gpt = consulta_chatgpt(nome, mensagem_usuario)
        enviar_whatsapp(resposta_gpt, numero_destino=f"+{numero}")
        return {"resposta": resposta_gpt}
    else:
        interacoes = atualiza_gratuitos(numero, nome, email)
        if interacoes <= 7:
            resposta = f"Conselho enviado! 👊🏼 Quer organizar sua vida financeira por completo? [Acesse aqui o Premium]"
        elif interacoes <= 10:
            restante = 10 - interacoes
            resposta = f"🚀 Faltam só {restante} interações grátis. Libere o acesso completo agora: [link premium]"
        else:
            resposta = "⏳ Seu limite gratuito acabou! Liberar acesso completo agora: [link premium]"
        enviar_whatsapp(resposta, numero_destino=f"+{numero}")
        return {"resposta": resposta}
