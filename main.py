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

# Função para enviar mensagem para usuários gratuitos
def mensagem_gratuito(nome, interacoes):
    if interacoes <= 7:
        return f"Olá, {nome}! 👋🏼 Aqui é o Meu Conselheiro Financeiro. Sempre que quiser clareza para alinhar sua vida financeira ao que realmente importa – sua família e seu propósito – é só me chamar!"
    elif interacoes in [8, 9]:
        return f"{nome}, seguimos juntos organizando tudo por aqui! 🔑 Lembre-se: você tem mais {10 - interacoes} interações gratuitas. Para ter acesso ilimitado e completo ao Meu Conselheiro Financeiro, é só clicar aqui: [link premium]."
    else:
        return f"{nome}, você chegou ao fim das suas interações gratuitas. 🚀 Quer destravar o acesso total ao Meu Conselheiro Financeiro e continuar evoluindo? Clique aqui: [link premium]."

# Endpoint principal
@app.post("/webhook")
async def receber_mensagem(request: Request):
    dados = await request.form()
    numero = dados.get('From')
    mensagem_usuario = dados.get('Body')
    nome = "Usuário"  # Você pode perguntar depois
    email = ""  # Também pode perguntar depois

    if verifica_pagante(numero):
        resposta_gpt = consulta_chatgpt(nome, mensagem_usuario)
        enviar_whatsapp(resposta_gpt, numero_destino=numero.replace("whatsapp:", ""))
        return {"resposta": resposta_gpt}
    else:
        interacoes = atualiza_gratuitos(numero, nome, email)
        if interacoes <= 10:
            resposta = f"Olá! Você tem mais {10 - interacoes} interações gratuitas restantes. Para acesso completo, clique aqui: [link premium]."
        else:
            resposta = f"Suas interações gratuitas acabaram! 🚀 Para acesso completo, clique aqui: [link premium]."
        enviar_whatsapp(resposta, numero_destino=numero.replace("whatsapp:", ""))
        return {"resposta": resposta}
