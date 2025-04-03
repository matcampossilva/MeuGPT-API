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

# ENV VARS
openai.api_key = os.getenv("OPENAI_API_KEY")
client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
MESSAGING_SERVICE_SID = os.getenv("TWILIO_MESSAGING_SERVICE_SID")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_SHEETS_KEY_FILE = os.getenv("GOOGLE_SHEETS_KEY_FILE")

app = FastAPI()

# GOOGLE SHEETS
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_KEY_FILE, scope)
gs = gspread.authorize(creds)

# === UTILITÁRIOS ===

def format_number(raw_number):
    return raw_number.replace("whatsapp:", "").strip()

def extract_email(text):
    match = re.search(r'[\w\.-]+@[\w\.-]+', text)
    return match.group(0) if match else None

def nome_valido(nome):
    return len(nome.split()) >= 2

def count_tokens(text):
    return len(text.split())

def send_message(to, body):
    client.messages.create(
        body=body,
        messaging_service_sid=MESSAGING_SERVICE_SID,
        to=f"whatsapp:{to}"
    )

def capitalizar_texto(texto):
    return '. '.join(frase.strip().capitalize() for frase in texto.split('. '))

# === PLANILHAS ===

def get_user_status(number):
    try:
        controle = gs.open_by_key(GOOGLE_SHEET_ID)
        pagantes = controle.worksheet("Pagantes").col_values(2)
        gratuitos = controle.worksheet("Gratuitos").col_values(2)

        if number in pagantes:
            return "Pagantes"
        elif number in gratuitos:
            return "Gratuitos"
        else:
            return "Novo"
    except:
        return "Novo"

def get_user_sheet(number):
    status = get_user_status(number)
    controle = gs.open_by_key(GOOGLE_SHEET_ID)

    if status == "Pagantes":
        return controle.worksheet("Pagantes")
    elif status == "Gratuitos":
        return controle.worksheet("Gratuitos")
    else:
        now = datetime.now(pytz.timezone("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S")
        sheet = controle.worksheet("Gratuitos")
        sheet.append_row(["", number, "", now, 0, 0])
        return sheet

# === ENDPOINT ===

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    incoming_msg = form["Body"].strip()
    from_number = format_number(form["From"])
    sheet = get_user_sheet(from_number)
    values = sheet.col_values(2)
    row = values.index(from_number) + 1

    name = sheet.cell(row, 1).value.strip() if sheet.cell(row, 1).value else ""
    email = sheet.cell(row, 3).value.strip() if sheet.cell(row, 3).value else ""

    captured_name = None
    captured_email = extract_email(incoming_msg)

    if not name or not email:
        if nome_valido(incoming_msg):
            captured_name = incoming_msg.strip()

        if captured_name:
            sheet.update_cell(row, 1, captured_name)
            name = captured_name

        if captured_email:
            sheet.update_cell(row, 3, captured_email)
            email = captured_email

        if not name and not email:
            send_message(from_number, "Ei! Que bom te ver por aqui. 🙌\n\nAntes da gente começar de verdade, preciso só de dois detalhes:\n👉 Seu nome completo (como quem assina um contrato importante)\n👉 Seu e-mail\n\nPode mandar os dois aqui mesmo e já seguimos. 😉")
            return {"status": "aguardando_nome_email"}

        if name and not email:
            send_message(from_number, "Faltou só o e-mail. Vai lá, sem medo. 🙏")
            return {"status": "aguardando_email"}

        if email and not name:
            send_message(from_number, "Faltou o nome completo — aquele que você usaria pra assinar um contrato importante. ✍️")
            return {"status": "aguardando_nome"}

        if name and email:
            primeiro_nome = name.split()[0]
            welcome = f"Perfeito, {primeiro_nome}! 👊\n\nSeus dados estão registrados. Agora sim, podemos começar de verdade. 😊\n\nEstou aqui pra te ajudar com suas finanças, seus investimentos, decisões sobre empréstimos e até com orientações práticas de vida espiritual e familiar.\n\nMe conta: qual é a principal situação financeira que você quer resolver hoje?"
            send_message(from_number, welcome)
            return {"status": "cadastro_completo"}

    # === MEMÓRIA DE CONVERSA ===
    conversa_path = f"conversas/{from_number}.txt"
    os.makedirs("conversas", exist_ok=True)

    with open(conversa_path, "a") as f:
        f.write(f"Usuário: {incoming_msg}\n")

    with open("prompt.txt", "r", encoding="utf-8") as f:
        prompt_base = f.read()

    with open(conversa_path, "r") as f:
        historico = f.read()

    full_prompt = f"{prompt_base}\n\n{historico}\nConselheiro:"

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": full_prompt}],
        temperature=0.7
    )

    reply = capitalizar_texto(response["choices"][0]["message"]["content"].strip())

    with open(conversa_path, "a") as f:
        f.write(f"Conselheiro: {reply}\n")

    tokens = count_tokens(incoming_msg) + count_tokens(reply)
    sheet.update_cell(row, 5, int(sheet.cell(row, 5).value or 0) + tokens)
    sheet.update_cell(row, 6, int(sheet.cell(row, 6).value or 0) + 1)

    send_message(from_number, reply)
    return {"status": "mensagem_enviada"}