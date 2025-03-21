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

# Configuração OpenAI - sem proxies
client_openai = OpenAI(api_key=OPENAI_API_KEY)

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
    encontrado = False
    for i, linha in enumerate(lista):
        if str(linha['WHATSAPP']) == numero:
            novo_valor = int(linha['CONTADOR']) + 1
            sheet.update_cell(i+2, 4, novo_valor)
            encontrado = True
            return novo_valor
    if not encontrado:
        sheet.append_row([nome, numero, email, 1])
        return 1

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
    resposta = client_openai.chat.completions.create(
        model="gpt-4-turbo",
        messages=[{"role": "system", "content": prompt}]
    )
    return resposta.choices[0].message.content.strip()

# Endpoint principal
@app.post("/webhook")
async def receber_mensagem(request: Request):
    dados = await request.json()
    nome = dados['nome']
    numero = dados['whatsapp']
    email = dados.get('email', '')
    mensagem_usuario = dados['mensagem']

    if verifica_pagante(numero):
        resposta_gpt = consulta_chatgpt(nome, mensagem_usuario)
        enviar_whatsapp(resposta_gpt, numero_destino=f"+55{numero}")
        return {"resposta": resposta_gpt}
    else:
        interacoes = atualiza_gratuitos(numero, nome, email)
        if interacoes <= 10:
            resposta = f"Olá {nome}! 🌟 Você está na versão gratuita ({interacoes}/10 interações). Para liberar acesso completo ao Meu Conselheiro Financeiro, clique aqui: [link]."
        else:
            resposta = f"Ei {nome}, seu limite gratuito acabou! 🚀 Quer liberar tudo? Acesse aqui: [link premium]."
        enviar_whatsapp(resposta, numero_destino=f"+55{numero}")
        return {"resposta": resposta}
