import os
import pytz
from fastapi import FastAPI, Request
from enviar_whatsapp import enviar_whatsapp as enviar_mensagem_whatsapp
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime
from dotenv import load_dotenv
import openai

# Carregar variáveis de ambiente
load_dotenv()

# API Key direto no objeto global
openai.api_key = os.getenv("OPENAI_API_KEY")

# Google Sheets setup
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SHEETS_KEY_FILE")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE)
service = build('sheets', 'v4', credentials=credentials)
sheet = service.spreadsheets()

app = FastAPI()

MAX_INTERACOES_GRATUITAS = 10

# Funções auxiliares
def encontrar_usuario(numero, aba):
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=f"{aba}!A2:D").execute()
    valores = result.get("values", [])
    for i, row in enumerate(valores):
        if len(row) >= 1 and row[0] == numero:
            return i + 2, row  # linha e dados
    return None, None

def adicionar_usuario(numero, nome, email, aba):
    now = datetime.now(pytz.timezone('America/Sao_Paulo')).strftime("%d/%m/%Y %H:%M:%S")
    sheet.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{aba}!A:D",
        valueInputOption="RAW",
        body={"values": [[numero, nome, email, now]]}
    ).execute()

def atualizar_usuario(numero, nome, email, linha, aba):
    valores = [numero, nome, email]
    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{aba}!A{linha}:C{linha}",
        valueInputOption="RAW",
        body={"values": [valores]}
    ).execute()

def atualizar_interacoes(linha, interacoes):
    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"Gratuitos!E{linha}",
        valueInputOption="RAW",
        body={"values": [[interacoes]]}
    ).execute()

# Endpoint do Webhook do WhatsApp
@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    numero_raw = form.get("From", "")
    numero = numero_raw.replace("whatsapp:", "").strip()

    # Normaliza número para formato internacional
    if not numero.startswith("+"):
        numero = f"+55{numero.lstrip('0').lstrip('55')}"

    mensagem = form.get("Body", "").strip()
    
    if not numero or not mensagem:
        return {"status": "ignored"}

    # Buscar usuário nas planilhas
    linha_pagante, dados_pagante = encontrar_usuario(numero, "Pagantes")
    linha_gratuito, dados_gratuito = encontrar_usuario(numero, "Gratuitos")

    # Caso novo usuário
    if not dados_pagante and not dados_gratuito:
        enviar_mensagem_whatsapp(numero,
            "Antes da gente começar, me conta uma coisa: qual o seu nome e e-mail? 👇\n\n"
            "Preciso disso pra te liberar o acesso gratuito aqui no Meu Conselheiro Financeiro. "
            "A partir daqui, esquece robozinho engessado. Você vai ter uma conversa que mistura dinheiro, propósito e vida real. Sem enrolação. 💼🔥"
        )
        adicionar_usuario(numero, "", "", "Gratuitos")
        return {"status": "novo usuário"}

    # Se for usuário gratuito
    if dados_gratuito:
        linha = linha_gratuito
        nome, email = "", ""
        if len(dados_gratuito) >= 2:
            nome = dados_gratuito[1]
        if len(dados_gratuito) >= 3:
            email = dados_gratuito[2]

        # Captura nome e email
        if not nome or not email:
            partes = mensagem.split()
            if "@" in mensagem:
                email = mensagem
                nome = " ".join(partes[:-1])
            else:
                nome = mensagem if not nome else nome

            atualizar_usuario(numero, nome, email, linha, "Gratuitos")

            if nome and email:
                enviar_mensagem_whatsapp(numero,
                    f"Perfeito, {nome.split()[0]}! 👊\n\n"
                    "Pode mandar sua dúvida financeira. Eu tô aqui pra te ajudar com clareza, sem papo furado. Bora? 💬💰"
                )
            else:
                enviar_mensagem_whatsapp(numero, "Só falta o e-mail agora pra eu liberar seu acesso. Pode mandar! 📧")
            return {"status": "dados atualizados"}

        # Controle de interações
        interacoes = int(dados_gratuito[4]) if len(dados_gratuito) >= 5 else 0
        if interacoes >= MAX_INTERACOES_GRATUITAS:
            enviar_mensagem_whatsapp(numero,
                f"{nome.split()[0]}, você chegou ao limite de interações gratuitas. 😬\n\n"
                "Pra continuar tendo acesso ao Meu Conselheiro Financeiro e levar sua vida financeira pra outro nível, é só entrar aqui: [LINK PREMIUM] 🔒"
            )
            return {"status": "limite atingido"}
        
        atualizar_interacoes(linha, interacoes + 1)

    # Se chegou aqui, é pagante ou gratuito liberado
    prompt_base = (
        "Você é o Meu Conselheiro Financeiro, um assistente que ajuda famílias a ganharem clareza financeira, "
        "com foco em propósito, patrimônio e vida real. Você mistura temas como dinheiro, vocação, fé, maturidade pessoal, "
        "educação dos filhos, e decisões patrimoniais de médio e longo prazo. "
        "Responda com profundidade, sem ser superficial. Não use linguagem de IA. Fale com autoridade e humanidade."
    )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": prompt_base},
                {"role": "user", "content": mensagem}
            ]
        )
        resposta = response["choices"][0]["message"]["content"]
    except Exception as e:
        resposta = f"Erro ao gerar resposta:\n\n{e}"

    enviar_mensagem_whatsapp(numero, resposta)
    return {"status": "ok"}
