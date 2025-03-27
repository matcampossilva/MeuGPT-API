import os
import openai
import pytz
import datetime
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from twilio.rest import Client
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Inicializa FastAPI
app = FastAPI()

# Inicializa OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Inicializa Twilio
twilio_client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")

# Configura Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open("Controle de Usuários - MeuGPT")
aba_pagantes = sheet.worksheet("Pagantes")
aba_gratuitos = sheet.worksheet("Gratuitos")

# Função para identificar se é pagante ou gratuito
def buscar_usuario(telefone):
    telefone = f"+{telefone}" if not telefone.startswith("+") else telefone
    try:
        cell = aba_pagantes.find(telefone)
        return "pagante", cell.row
    except:
        try:
            cell = aba_gratuitos.find(telefone)
            return "gratuito", cell.row
        except:
            return None, None

# Função para processar entrada e atualizar planilha
def registrar_interacao(nome, telefone, email):
    status, row = buscar_usuario(telefone)
    telefone_formatado = f"+{telefone}" if not telefone.startswith("+") else telefone

    if status == "gratuito":
        aba_gratuitos.update_cell(row, 1, nome)
        aba_gratuitos.update_cell(row, 3, email)
        contador = int(aba_gratuitos.cell(row, 4).value or 0) + 1
        aba_gratuitos.update_cell(row, 4, contador)
        return contador
    elif status == "pagante":
        aba_pagantes.update_cell(row, 1, nome)
        aba_pagantes.update_cell(row, 3, email)
        return "ilimitado"
    else:
        nova_linha = [nome, telefone_formatado, email, 1]
        aba_gratuitos.append_row(nova_linha)
        return 1

# Função para envio de mensagem via WhatsApp
def enviar_mensagem(numero_destino, mensagem):
    twilio_client.messages.create(
        body=mensagem,
        from_=f"whatsapp:{TWILIO_WHATSAPP_NUMBER}",
        to=f"whatsapp:{numero_destino}"
    )

# Função principal para processar mensagem recebida
def processar_mensagem(telefone, texto):
    nome, email = None, None
    partes = texto.split("\n")
    for parte in partes:
        if "nome" in parte.lower():
            nome = parte.split(":")[-1].strip()
        elif "email" in parte.lower() or "e-mail" in parte.lower():
            email = parte.split(":")[-1].strip()

    if nome and email:
        interacao = registrar_interacao(nome, telefone, email)
        if interacao == 1:
            return f"Seja muito bem-vindo(a), {nome}! 🎯\nEstou aqui para te ajudar a organizar sua vida financeira colocando Deus, sua família e seu trabalho em primeiro lugar. Vamos juntos? Me conta: qual é o seu principal objetivo financeiro neste momento?"
        elif interacao == "ilimitado":
            return f"Bem-vindo de volta, {nome}! Pode me contar sua dúvida ou objetivo financeiro e vamos organizar isso juntos. 👊"
        elif isinstance(interacao, int):
            restantes = 10 - interacao
            if restantes > 0:
                return f"Perfeito, {nome}. Ainda temos {restantes} interações gratuitas. Qual sua dúvida agora?"
            else:
                return f"{nome}, seu limite gratuito de 10 interações foi atingido. Para continuar, acesse o plano completo aqui: [link]"
    else:
        status, row = buscar_usuario(telefone)
        if status:
            return "Qual sua dúvida ou objetivo financeiro? Me conta pra eu poder te ajudar agora. 💡"
        else:
            return "Olá! 👋🏻 Que bom ter você aqui. Para começarmos nossa jornada financeira juntos, preciso apenas do seu nome e e-mail, por favor. Pode me mandar?"

# Webhook que trata as mensagens
@app.post("/webhook")
async def webhook(request: Request):
    form = await request.form()
    telefone = form.get("From", "").replace("whatsapp:", "")
    texto = form.get("Body", "")

    resposta = processar_mensagem(telefone, texto)

    if resposta:
        enviar_mensagem(telefone, resposta)

    # Retorna resposta simples e compatível com Twilio
    return PlainTextResponse(content="OK", status_code=200)
