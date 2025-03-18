from fastapi import FastAPI, Request
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from twilio.rest import Client
import os

app = FastAPI()

# Configurações Google Sheets
URL_GOOGLE_SHEETS = 'https://docs.google.com/spreadsheets/d/1bhnyG0-DaH3gE687_tUEy9kVI7rV-bxJl10bRKkDl2Y/edit?usp=sharing'
SHEET_PAGANTES = 'Pagantes'
SHEET_GRATUITOS = 'Gratuitos'
LIMIT_INTERACOES = 10  # Limite de interações gratuitas

# Configuração Google Sheets API
def conecta_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name('/etc/secrets/meugpt-api-sheets-92a9d439900d.json', scope)
    client = gspread.authorize(creds)
    return client

# Verifica se número é pagante
def verifica_pagante(numero):
    client = conecta_google_sheets()
    sheet = client.open_by_url(URL_GOOGLE_SHEETS).worksheet(SHEET_PAGANTES)
    lista = sheet.get_all_records()
    for linha in lista:
        if str(linha['WHATSAPP']) == numero and linha['STATUS'].upper() == 'ATIVO':
            return True
    return False

# Atualiza/Registra usuários gratuitos
def atualiza_gratuitos(numero, nome, email):
    client = conecta_google_sheets()
    sheet = client.open_by_url(URL_GOOGLE_SHEETS).worksheet(SHEET_GRATUITOS)
    lista = sheet.get_all_records()
    encontrado = False
    for i, linha in enumerate(lista):
        if str(linha['WHATSAPP']) == numero:
            novo_valor = int(linha['CONTADOR']) + 1
            sheet.update_cell(i+2, 4, novo_valor)  # coluna CONTADOR
            encontrado = True
            return novo_valor
    if not encontrado:
        sheet.append_row([nome, numero, email, 1])
        return 1

# Função para envio via WhatsApp (Twilio)
def enviar_whatsapp(numero_destino, mensagem):
    try:
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        whatsapp_number = os.getenv('TWILIO_WHATSAPP_NUMBER')

        client = Client(account_sid, auth_token)

        message = client.messages.create(
            body=mensagem,
            from_=f'whatsapp:{whatsapp_number}',
            to=f'whatsapp:+55{numero_destino}'
        )
        print(f"✅ Mensagem enviada para {numero_destino}. SID: {message.sid}")

    except Exception as e:
        print(f"❌ Erro ao enviar WhatsApp: {e}")

# Endpoint principal
@app.post("/webhook")
async def receber_mensagem(request: Request):
    dados = await request.json()
    nome = dados['nome']
    numero = dados['whatsapp']
    email = dados.get('email', '')
    mensagem_usuario = dados['mensagem'].lower()

    if verifica_pagante(numero):
        resposta = f"Olá {nome}! 🎯 Você é Premium. Pode informar seus gastos, dúvidas ou metas financeiras!"
    else:
        interacoes = atualiza_gratuitos(numero, nome, email)
        if interacoes <= LIMIT_INTERACOES:
            resposta = f"Olá {nome}! 🌟 Você está na versão gratuita ({interacoes}/{LIMIT_INTERACOES} interações). Para liberar acesso completo ao Meu Conselheiro Financeiro, clique aqui: [link para assinar]."
        else:
            resposta = f"Ei {nome}, seu limite gratuito acabou! 🚀 Quer liberar tudo? Acesse aqui: [link premium]."

    # Envia via WhatsApp automaticamente
    enviar_whatsapp(numero, resposta)

    # Retorno no terminal
    return {"resposta": resposta}
