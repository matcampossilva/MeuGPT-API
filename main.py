from fastapi import FastAPI, Request
from twilio.rest import Client
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import openai

app = FastAPI()

# Configurações Google Sheets
URL_GOOGLE_SHEETS = 'https://docs.google.com/spreadsheets/d/1bhnyG0-DaH3gE687_tUEy9kVI7rV-bxJl10bRKkDl2Y/edit?usp=sharing'
SHEET_PAGANTES = 'Pagantes'
SHEET_GRATUITOS = 'Gratuitos'
LIMIT_INTERACOES = 10  # Limite grátis

# Configuração Google Sheets API
def conecta_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name('/etc/secrets/meugpt-api-sheets-92a9d439900d.json', scope)
    client = gspread.authorize(creds)
    return client

def verifica_pagante(numero):
    client = conecta_google_sheets()
    sheet = client.open_by_url(URL_GOOGLE_SHEETS).worksheet(SHEET_PAGANTES)
    lista = sheet.get_all_records()
    for linha in lista:
        if str(linha['WHATSAPP']) == numero and linha['STATUS'].upper() == 'ATIVO':
            return True
    return False

def atualiza_gratuitos(numero, nome, email):
    client = conecta_google_sheets()
    sheet = client.open_by_url(URL_GOOGLE_SHEETS).worksheet(SHEET_GRATUITOS)
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

# ENV Variables Twilio e OpenAI
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

client_twilio = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
openai.api_key = OPENAI_API_KEY

# Prompt fixo do Meu Conselheiro Financeiro
PROMPT_BASE = """
Você é o Meu Conselheiro Financeiro pessoal, criado por Matheus Campos, CFP®.

Sua missão é organizar a vida financeira do usuário respeitando rigorosamente esta hierarquia: Deus, família e trabalho, nesta ordem.

O dinheiro serve ao homem, jamais o contrário. Seu objetivo é ajudar o usuário a usar o dinheiro com sabedoria, clareza e sem apego, alinhando sua vida financeira à sua missão espiritual e familiar.

Sua comunicação é sempre leve, amigável e intimista, com leve toque goiano (ex.: "Uai!", "Tem base?"), provocando sempre perguntas curtas para o usuário. Utilize emojis naturais e apropriados.

Seja conciso e prático, sem respostas muito longas. Oriente o usuário a lançar seus gastos, perguntar sobre dívidas, investimentos ou qualquer questão financeira.

Jamais mencione fontes ou arquivos, apenas incorpore os conhecimentos naturalmente. Nunca recomende divórcio. Para crises financeiras no casamento, sempre proponha estratégias práticas e espirituais alinhadas com São Josemaria Escrivá e a Doutrina Católica.

"""

# Função para enviar WhatsApp
def enviar_whatsapp(mensagem, numero_destino):
    try:
        message = client_twilio.messages.create(
            from_=TWILIO_PHONE_NUMBER,
            body=mensagem,
            to=f'whatsapp:{numero_destino}'
        )
        print(f"✅ Mensagem enviada com sucesso para {numero_destino}. SID: {message.sid}")
    except Exception as e:
        print(f"❌ Erro ao enviar WhatsApp: {e}")

# Endpoint principal
@app.post("/webhook")
async def receber_mensagem(request: Request):
    dados = await request.json()
    nome = dados['nome']
    numero = dados['whatsapp']
    email = dados.get('email', '')
    mensagem_usuario = dados['mensagem']

    if verifica_pagante(numero):
        # Usuário pagante - libera full
        resposta_gpt = consulta_chatgpt(nome, mensagem_usuario)
        enviar_whatsapp(resposta_gpt, numero)
        return {"status": "Mensagem enviada para pagante"}
    else:
        # Usuário gratuito - controla limite
        interacoes = atualiza_gratuitos(numero, nome, email)
        if interacoes <= LIMIT_INTERACOES:
            resposta_gpt = consulta_chatgpt(nome, mensagem_usuario)
            enviar_whatsapp(f"(Versão Gratuita {interacoes}/{LIMIT_INTERACOES})\n\n{resposta_gpt}", numero)
            return {"status": "Mensagem enviada para gratuito"}
        else:
            msg = f"Ei {nome}, seu limite gratuito acabou! 🚀 Quer liberar tudo? Acesse aqui: [link premium]."
            enviar_whatsapp(msg, numero)
            return {"status": "Limite atingido"}

# Consulta à API ChatGPT
def consulta_chatgpt(nome, mensagem_usuario):
    prompt_completo = f"{PROMPT_BASE}\nUsuário ({nome}): {mensagem_usuario}\nConselheiro:"
    resposta = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt_completo,
        max_tokens=500,
        temperature=0.7
    )
    return resposta.choices[0].text.strip()
