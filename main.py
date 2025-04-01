# Força rebuild no Render – ajuste técnico forçado

import os
import pytz
import re
from fastapi import FastAPI, Request
from enviar_whatsapp import enviar_whatsapp as enviar_mensagem_whatsapp
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime
from dotenv import load_dotenv
from logs.logger import registrar_erro
import openai

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

with open("prompt.txt", "r", encoding="utf-8") as file:
    prompt_base = file.read()

SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SHEETS_KEY_FILE")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE)
service = build('sheets', 'v4', credentials=credentials)
sheet = service.spreadsheets()

app = FastAPI()
MAX_INTERACOES_GRATUITAS = 10

def encontrar_usuario(numero, aba):
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=f"{aba}!A2:E").execute()
    valores = result.get("values", [])
    for i, row in enumerate(valores):
        if len(row) >= 2 and row[1] == numero:
            return i + 2, row
    return None, None

def adicionar_usuario(nome, numero, email, aba):
    now = datetime.now(pytz.timezone('America/Sao_Paulo')).strftime("%d/%m/%Y %H:%M:%S")
    sheet.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{aba}!A:E",
        valueInputOption="RAW",
        body={"values": [[nome, numero, email, now, 0]]}
    ).execute()

def atualizar_usuario(nome, numero, email, linha, aba):
    valores = [nome, numero, email]
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

def extrair_nome_email(texto):
    email_match = re.search(r"[\w\.-]+@[\w\.-]+", texto)
    email = email_match.group(0) if email_match else ""
    nome = texto.replace(email, "").strip() if email else texto.strip()

    # Valida se nome parece um nome real (2 palavras, sem números)
    if nome and (len(nome.split()) >= 2) and not any(char.isdigit() for char in nome):
        nome_valido = nome
    else:
        nome_valido = ""

    return nome_valido, email

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    numero_raw = form.get("From", "")
    numero = numero_raw.replace("whatsapp:", "").strip()
    if not numero.startswith("+"):
        numero = f"+55{numero.lstrip('0').lstrip('55')}"
    mensagem = form.get("Body", "").strip()

    if not numero or not mensagem:
        return {"status": "ignored"}

    linha_pagante, dados_pagante = encontrar_usuario(numero, "Pagantes")
    linha_gratuito, dados_gratuito = encontrar_usuario(numero, "Gratuitos")

    if not dados_pagante and not dados_gratuito:
        adicionar_usuario("", numero, "", "Gratuitos")
        enviar_mensagem_whatsapp(
            numero,
            "Olá! 👋🏼 Que bom ter você aqui.\n\nPara começarmos nossa jornada financeira juntos, preciso apenas do seu nome e e-mail, por favor. Pode me mandar?"
        )
        return {"status": "novo usuário"}

    if dados_gratuito:
        linha = linha_gratuito
        nome_atual = dados_gratuito[0] if len(dados_gratuito) >= 1 else ""
        email_atual = dados_gratuito[2] if len(dados_gratuito) >= 3 else ""

        nome_msg, email_msg = extrair_nome_email(mensagem)
        nome_final = nome_atual
        email_final = email_atual

        atualizou = False

        if email_msg and "@" in email_msg and "." in email_msg and not email_atual:
            email_final = email_msg
            atualizou = True

        if nome_msg and nome_msg != "" and not nome_atual:
            nome_final = nome_msg
            atualizou = True

        if atualizou:
            atualizar_usuario(nome_final, numero, email_final, linha, "Gratuitos")
            primeiro_nome = nome_final.split()[0].replace(".", "")
            enviar_mensagem_whatsapp(
                numero,
                f"Perfeito, {primeiro_nome}! 👊\n\nRecebi seus dados. Pode mandar sua dúvida agora."
            )

        interacoes = int(dados_gratuito[4]) if len(dados_gratuito) >= 5 else 0
        if interacoes >= MAX_INTERACOES_GRATUITAS:
            enviar_mensagem_whatsapp(
                numero,
                f"{nome_final.split()[0]}, você chegou ao limite de interações gratuitas. 😬\n\n"
                "Pra continuar tendo acesso ao Meu Conselheiro Financeiro e levar sua vida financeira pra outro nível, é só entrar aqui: [LINK PREMIUM] 🔒"
            )
            return {"status": "limite atingido"}

        atualizar_interacoes(linha, interacoes + 1)

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": prompt_base},
                {"role": "user", "content": mensagem}
            ]
        )
        resposta = response.choices[0].message["content"]
    except Exception as e:
        registrar_erro(f"Erro ao gerar resposta para o número {numero}: {e}")
        resposta = "Tivemos um problema técnico aqui 😵. Já estou vendo isso e logo voltamos ao normal!"

    enviar_mensagem_whatsapp(numero, resposta)
    return {"status": "ok"}