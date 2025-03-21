from fastapi import FastAPI, Request
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from twilio.rest import Client
import openai
import os

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

# Verifica se é pagante
def verifica_pagante(numero):
    client = conecta_google_sheets()
    sheet = client.open_by_url('https://docs.google.com/spreadsheets/d/1bhnyG0-DaH3gE687_tUEy9kVI7rV-bxJl10bRKkDl2Y/edit?usp=sharing').worksheet('Pagantes')
    lista = sheet.get_all_records()
    for linha in lista:
        if str(linha['WHATSAPP']) == numero and linha['STATUS'].upper() == 'ATIVO':
            return True
    return False

# Atualiza interação dos gratuitos
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

# Envia mensagem no WhatsApp via Twilio Messaging Service
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

# Consulta GPT com prompt
def consulta_chatgpt(mensagem_usuario):
    prompt = f"""
Você é o Meu Conselheiro Financeiro pessoal, criado por Matheus Campos, CFP®.

Sua missão é ajudar o usuário a ordenar sua vida financeira, articulando com sua vida familiar, profissional e espiritual. O dinheiro deve servir à família e ao propósito, não o contrário.

Usuário: {mensagem_usuario}
Conselheiro:
"""
    resposta = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "system", "content": prompt}]
    )
    return resposta.choices[0].message['content'].strip()

# Endpoint principal
@app.post("/webhook")
async def receber_mensagem(request: Request):
    dados = await request.form()
    nome = dados['nome']
    numero = dados['whatsapp']
    email = dados.get('email', '')
    mensagem_usuario = dados['mensagem']

    print(f"📥 Mensagem recebida de {numero}: {mensagem_usuario}")

    if verifica_pagante(numero):
        resposta_gpt = consulta_chatgpt(mensagem_usuario)
        enviar_whatsapp(resposta_gpt, numero_destino=numero)
        return {"resposta": resposta_gpt}
    else:
        interacoes = atualiza_gratuitos(numero, nome, email)
        if interacoes < 10:
            resposta = (
                f"Olá! 👋 Essa é uma versão gratuita com limite de interações.\n"
                f"Você ainda pode usar mais {10 - interacoes} vez(es). "
                f"Para ter acesso completo ao Meu Conselheiro Financeiro, clique aqui: [link premium]."
            )
        else:
            resposta = (
                f"Seu limite gratuito acabou. 🚀 Para desbloquear todo o potencial do Meu Conselheiro Financeiro, "
                f"acesse agora: [link premium]."
            )
        enviar_whatsapp(resposta, numero_destino=numero)
        return {"resposta": resposta}
