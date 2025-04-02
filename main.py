import os
import openai
from fastapi import FastAPI, Request
from twilio.rest import Client
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
import re

load_dotenv()

# VARIÁVEIS DE AMBIENTE
openai.api_key = os.getenv("OPENAI_API_KEY")
client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
MESSAGING_SERVICE_SID = os.getenv("TWILIO_MESSAGING_SERVICE_SID")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SHEET_NAME = os.getenv("SHEET_NAME")

app = FastAPI()

# PLANILHA GOOGLE
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("secrets/credentials.json", scope)
gs = gspread.authorize(creds)
sheet = gs.open_by_key(GOOGLE_SHEET_ID).worksheet(SHEET_NAME)

# FUNÇÕES AUXILIARES
def format_number(raw_number):
    return raw_number.replace("whatsapp:", "").strip()

def get_user_row(user_number):
    try:
        values = sheet.col_values(2)
        return values.index(user_number) + 1 if user_number in values else None
    except:
        return None

def update_user_data(row, name=None, email=None):
    if name:
        sheet.update_cell(row, 1, name.strip())
    if email:
        sheet.update_cell(row, 3, email.strip())

def create_user(user_number, name=None, email=None):
    now = datetime.now(pytz.timezone("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S")
    sheet.append_row([name or "", user_number, email or "", now, 0])

def extract_email(text):
    match = re.search(r'[\w\.-]+@[\w\.-]+', text)
    return match.group(0) if match else None

def extract_name(text):
    if " " in text.strip() and len(text.split()) >= 2:
        return text.strip()
    return None

def count_tokens(text):
    return len(text.split())

def update_token_count(row, tokens):
    count = int(sheet.cell(row, 5).value or 0)
    sheet.update_cell(row, 5, count + tokens)

def send_message(to, body):
    client.messages.create(
        body=body,
        messaging_service_sid=MESSAGING_SERVICE_SID,
        to=f"whatsapp:{to}"
    )

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    incoming_msg = form["Body"].strip()
    from_number = format_number(form["From"])

    row = get_user_row(from_number)

    if row:
        values = sheet.row_values(row)
        name = values[0].strip() if len(values) > 0 else ""
        email = values[2].strip() if len(values) > 2 else ""
    else:
        create_user(from_number)
        row = get_user_row(from_number)
        name = ""
        email = ""

    # === COLETA DE NOME E E-MAIL ===
    if not name or not email:
        captured_name = extract_name(incoming_msg) if not name else None
        captured_email = extract_email(incoming_msg) if not email else None

        if captured_name:
            update_user_data(row, name=captured_name)
            name = captured_name

        if captured_email:
            update_user_data(row, email=captured_email)
            email = captured_email

        if not name and not email:
            send_message(from_number, "Olá! 👋 Que bom ter você aqui.\n\nPara começarmos nossa jornada financeira juntos, preciso apenas do seu nome e e-mail, por favor. Pode me mandar?")
            return {"status": "aguardando nome e email"}

        if name and not email:
            send_message(from_number, "Só falta o e-mail agora pra eu liberar seu acesso. Pode mandar! 📧")
            return {"status": "aguardando email"}

        if email and not name:
            send_message(from_number, "Faltou só o nome completo. Pode mandar! ✍️")
            return {"status": "aguardando nome"}

        if name and email:
            welcome_msg = f"""Perfeito, {name}! 👊

Seus dados estão registrados. Agora sim, podemos começar de verdade. 😊

Estou aqui pra te ajudar com suas finanças, seus investimentos, decisões sobre empréstimos e até com orientações práticas de vida espiritual e familiar.

Me conta: qual é a principal situação financeira que você quer resolver hoje?"""
            send_message(from_number, welcome_msg)
            return {"status": "cadastro completo"}

    # === CONTINUA CONVERSA COM GPT ===
    prompt_base = open("prompt.txt", "r").read()

    full_prompt = f"""{prompt_base}

Usuário: {incoming_msg}
Conselheiro:"""

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": full_prompt}],
        temperature=0.7,
    )

    reply = response["choices"][0]["message"]["content"].strip()
    tokens = count_tokens(incoming_msg) + count_tokens(reply)
    update_token_count(row, tokens)
    send_message(from_number, reply)

    return {"status": "mensagem enviada"}