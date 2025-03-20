from fastapi import FastAPI, Request
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from twilio.rest import Client
import openai
import os

app = FastAPI()

# Configurações Google Sheets
URL_GOOGLE_SHEETS = 'https://docs.google.com/spreadsheets/d/1bhnyG0-DaH3gE687_tUEy9kVI7rV-bxJl10bRKkDl2Y/edit?usp=sharing'
SHEET_PAGANTES = 'Pagantes'
SHEET_GRATUITOS = 'Gratuitos'
LIMIT_INTERACOES = 10

# Variáveis de ambiente
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Configuração OpenAI API
openai.api_key = OPENAI_API_KEY

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

# Envio WhatsApp
def enviar_whatsapp(mensagem, numero_destino):
    client_twilio = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    try:
        message = client_twilio.messages.create(
            from_='whatsapp:+14155238886',
            body=mensagem,
            to=f'whatsapp:{numero_destino}'
        )
        print(f"✅ WhatsApp enviado para {numero_destino}. SID: {message.sid}")
    except Exception as e:
        print(f"❌ Erro no envio do WhatsApp: {e}")

# Consulta ChatGPT - corrigido
def consulta_chatgpt(nome, mensagem_usuario):
    prompt = f"""
Você é o Meu Conselheiro Financeiro pessoal, criado por Matheus Campos, CFP®.

Sua missão é organizar a vida financeira do usuário respeitando rigorosamente esta hierarquia: Deus, família e trabalho, nesta ordem.

O dinheiro serve ao homem, jamais o contrário. Seu objetivo é ajudar o usuário a usar o dinheiro com sabedoria, clareza e sem apego, alinhando sua vida financeira à sua missão espiritual e familiar.

Sua comunicação é sempre leve, amigável e intimista, com leve toque goiano (ex.: "Uai!", "Tem base?"), provocando sempre perguntas curtas para o usuário. Utilize emojis naturais e apropriados.

Jamais recomende divórcio. Sempre proponha estratégias práticas para crises financeiras no casamento, alinhadas com a Doutrina Católica.

Usuário: {mensagem_usuario}
Conselheiro:
"""

    resposta = openai.chat.completions.create(
        model="gpt-4",  # pode trocar por gpt-3.5-turbo se quiser economizar
        messages=[{"role": "system", "content": prompt}],
        max_tokens=300
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
        if interacoes <= LIMIT_INTERACOES:
            resposta = f"Olá {nome}! 🌟 Você está na versão gratuita ({interacoes}/{LIMIT_INTERACOES} interações). Para liberar acesso completo ao Meu Conselheiro Financeiro, clique aqui: [link para assinar]."
        else:
            resposta = f"Ei {nome}, seu limite gratuito acabou! 🚀 Quer liberar tudo? Acesse aqui: [link premium]."
        enviar_whatsapp(resposta, numero_destino=f"+55{numero}")
        return {"resposta": resposta}
