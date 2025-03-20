import os
from fastapi import FastAPI, Request
from openai import OpenAI
from twilio.rest import Client
from configuracoes import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, WHATSAPP_FROM
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz

# Configurações
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
GOOGLE_SHEETS_JSON = os.getenv('GOOGLE_SHEETS_JSON')
GOOGLE_SHEETS_URL = os.getenv('GOOGLE_SHEETS_URL')

# Inicialização de clientes
client_openai = OpenAI(api_key=OPENAI_API_KEY)
client_twilio = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Inicialização do FastAPI
app = FastAPI()

# Função para enviar WhatsApp
def enviar_whatsapp(mensagem, numero_destino):
    try:
        message = client_twilio.messages.create(
            from_=f'whatsapp:{WHATSAPP_FROM}',
            body=mensagem,
            to=f'whatsapp:{numero_destino}'
        )
        print(f"✅ WhatsApp enviado para {numero_destino}. SID: {message.sid}")
    except Exception as e:
        print(f"❌ Erro ao enviar WhatsApp: {e}")

# Função para verificar tipo de usuário
def verificar_usuario(numero):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_JSON, scope)
        client = gspread.authorize(creds)

        sheet_pagantes = client.open_by_url(GOOGLE_SHEETS_URL).worksheet("Pagantes")
        sheet_gratuitos = client.open_by_url(GOOGLE_SHEETS_URL).worksheet("Gratuitos")

        pagantes = sheet_pagantes.col_values(1)
        gratuitos = sheet_gratuitos.col_values(1)

        if numero in pagantes:
            return "pagante"
        elif numero in gratuitos:
            return "gratuito"
        else:
            # Adiciona o usuário na lista de gratuitos com contador zero
            sheet_gratuitos.append_row([numero, "0"])
            return "gratuito"
    except Exception as e:
        print(f"❌ Erro ao verificar usuário: {e}")
        return "erro"

# Função para atualizar contador de gratuitos
def atualizar_contador(numero):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_JSON, scope)
        client = gspread.authorize(creds)

        sheet = client.open_by_url(GOOGLE_SHEETS_URL).worksheet("Gratuitos")
        numeros = sheet.col_values(1)
        linha = numeros.index(numero) + 1
        contador = int(sheet.cell(linha, 2).value)
        contador += 1
        sheet.update_cell(linha, 2, str(contador))
        return contador
    except Exception as e:
        print(f"❌ Erro ao atualizar contador: {e}")
        return None

# Endpoint principal
@app.post("/webhook")
async def receber_mensagem(request: Request):
    dados = await request.form()
    mensagem = dados.get('Body')
    numero = dados.get('From').replace('whatsapp:', '')

    print(f"📩 Mensagem recebida de {numero}: {mensagem}")

    tipo_usuario = verificar_usuario(numero)

    if tipo_usuario == "pagante":
        # Usuário pagante – resposta ilimitada
        resposta = gerar_resposta_chatgpt(mensagem)
        enviar_whatsapp(resposta, numero)
    elif tipo_usuario == "gratuito":
        contador = atualizar_contador(numero)
        if contador is not None and contador <= 10:
            resposta = gerar_resposta_chatgpt(mensagem)
            enviar_whatsapp(f"Interação nº {contador} do usuário gratuito.\n\n{resposta}", numero)
        else:
            enviar_whatsapp("🚫 Você atingiu o limite de 10 interações gratuitas. Para continuar utilizando, entre em contato para se tornar um assinante!", numero)
    else:
        enviar_whatsapp("❌ Ocorreu um erro ao verificar seu cadastro. Tente novamente mais tarde.", numero)

    return {"status": "mensagem recebida"}

# Função para gerar resposta do ChatGPT
def gerar_resposta_chatgpt(pergunta):
    try:
        response = client_openai.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "Você é o Meu Conselheiro Financeiro, especializado em orientar famílias a organizar suas finanças e patrimônio. Responda sempre de forma clara e objetiva."},
                {"role": "user", "content": pergunta}
            ],
            max_tokens=500
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ Erro ao gerar resposta: {e}")
        return "Ocorreu um erro ao gerar a resposta. Tente novamente mais tarde."
