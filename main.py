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
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
    return nome, email

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    numero_raw = form.get("From", "")
    numero = numero_raw.replace("whatsapp:", "").strip()

    if not numero.startswith("+"):
        numero = f"+55{numero.lstrip('0').lstrip('55')}"

    # Validação contra erro de substituição do número pela mensagem
    if not numero or not re.match(r"^\+55\d{10,11}$", numero):
        registrar_erro(f"Erro: número de telefone inválido recebido - '{numero}'")
        return {"status": "número inválido"}

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
        nome = dados_gratuito[0] if len(dados_gratuito) >= 1 else ""
        email = dados_gratuito[2] if len(dados_gratuito) >= 3 else ""

        nome_msg, email_msg = extrair_nome_email(mensagem)

        if email_msg and "@" in email_msg and "." in email_msg:
            email = email_msg
        if nome_msg and len(nome_msg.split()) >= 2:
            nome = nome_msg

        if nome and email:
            atualizar_usuario(nome, numero, email, linha, "Gratuitos")
            primeiro_nome = nome.split()[0].replace(".", "")

            enviar_mensagem_whatsapp(
                numero,
                f"Perfeito, {primeiro_nome}! 👊\n\n"
                "Pode mandar sua dúvida financeira. Eu tô aqui pra te ajudar com clareza, sem papo furado. Bora? 💬💰"
            )

            interacoes = int(dados_gratuito[4]) if len(dados_gratuito) >= 5 else 0
            if interacoes >= MAX_INTERACOES_GRATUITAS:
                enviar_mensagem_whatsapp(
                    numero,
                    f"{primeiro_nome}, você chegou ao limite de interações gratuitas. 😬\n\n"
                    "Pra continuar tendo acesso ao Meu Conselheiro Financeiro e levar sua vida financeira pra outro nível, é só entrar aqui: [LINK PREMIUM] 🔒"
                )
                return {"status": "limite atingido"}

            atualizar_interacoes(linha, interacoes + 1)

        else:
            if not nome:
                enviar_mensagem_whatsapp(numero, "Faltou só o nome completo. Pode mandar! ✍️")
            elif not email:
                enviar_mensagem_whatsapp(numero, "Só falta o e-mail agora pra eu liberar seu acesso. Pode mandar! 📧")
            return {"status": "dados incompletos"}

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": prompt_base},
                {"role": "user", "content": mensagem}
            ]
        )
        resposta = response.choices[0].message.content
    except Exception as e:
        registrar_erro(f"Erro ao gerar resposta para o número {numero}: {e}")
        resposta = "Tivemos um problema técnico aqui 😵. Já estou vendo isso e logo voltamos ao normal!"

    enviar_mensagem_whatsapp(numero, resposta)
    return {"status": "ok"}