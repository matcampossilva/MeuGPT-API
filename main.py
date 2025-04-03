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

openai.api_key = os.getenv("OPENAI_API_KEY")
client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
MESSAGING_SERVICE_SID = os.getenv("TWILIO_MESSAGING_SERVICE_SID")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_SHEETS_KEY_FILE = os.getenv("GOOGLE_SHEETS_KEY_FILE")

app = FastAPI()

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_KEY_FILE, scope)
gs = gspread.authorize(creds)


def format_number(raw_number):
    return raw_number.replace("whatsapp:", "").strip()

def extract_email(text):
    match = re.search(r'[\w\.-]+@[\w\.-]+', text)
    return match.group(0) if match else None

def extract_name(text):
    nome_limpo = text.strip()
    if len(nome_limpo.split()) >= 2 and not any(char in nome_limpo for char in "1234567890!@#$%¨&*()"):
        return nome_limpo
    return None

def nome_valido(text):
    if not text:
        return False
    nome = text.strip()
    return len(nome.split()) >= 2 and not any(char in nome for char in "0123456789!@#")

def capitalize_response(text):
    blocos = text.split("\n")
    return "\n".join(bloco.capitalize() if bloco and bloco[0].islower() else bloco for bloco in blocos)

def count_tokens(text):
    return len(text.split())

def send_message(to, body):
    client.messages.create(
        body=body,
        messaging_service_sid=MESSAGING_SERVICE_SID,
        to=f"whatsapp:{to}"
    )

def get_user_status(user_number):
    try:
        controle = gs.open_by_key(GOOGLE_SHEET_ID)
        pagantes = controle.worksheet("Pagantes").col_values(2)
        gratuitos = controle.worksheet("Gratuitos").col_values(2)

        if user_number in pagantes:
            return "Pagantes"
        elif user_number in gratuitos:
            return "Gratuitos"
        else:
            return "Novo"
    except Exception as e:
        print(f"Erro ao verificar status do usuário: {e}")
        return "Novo"

def get_user_sheet(user_number):
    status = get_user_status(user_number)
    controle = gs.open_by_key(GOOGLE_SHEET_ID)

    if status == "Pagantes":
        return controle.worksheet("Pagantes")
    elif status == "Gratuitos":
        return controle.worksheet("Gratuitos")
    else:
        now = datetime.now(pytz.timezone("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S")
        sheet = controle.worksheet("Gratuitos")
        sheet.append_row(["", user_number, "", now, 0, 0])
        return sheet

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    incoming_msg = form["Body"].strip()
    from_number = format_number(form["From"])
    sheet = get_user_sheet(from_number)

    values = sheet.col_values(2)
    row = values.index(from_number) + 1 if from_number in values else None

    name = sheet.cell(row, 1).value.strip() if sheet.cell(row, 1).value else ""
    email = sheet.cell(row, 3).value.strip() if sheet.cell(row, 3).value else ""

    captured_email = extract_email(incoming_msg)
    captured_name = extract_name(incoming_msg)

    # Se ainda não foi capturado o nome completo ou e-mail
    if not name or not email:
        if captured_email and not email:
            sheet.update_cell(row, 3, captured_email)
            email = captured_email

        if captured_name and not name and nome_valido(captured_name):
            sheet.update_cell(row, 1, captured_name)
            name = captured_name

        if not name and not email:
            send_message(from_number,
                "Ei! Que bom te ver por aqui. 🙌\n\n"
                "Antes da gente começar de verdade, preciso só de dois detalhes:\n\n"
                "👉 Seu nome completo (como quem assina um contrato importante)\n"
                "👉 Seu e-mail\n\n"
                "Pode mandar os dois aqui mesmo e já seguimos. 😉"
            )
            return {"status": "aguardando nome e email"}

        if name and not email:
            send_message(from_number,
                "Faltou só o e-mail agora. Vai lá, sem medo. 🙏")
            return {"status": "aguardando email"}

        if email and not name:
            send_message(from_number,
                "Faltou o nome completo — aquele que você usaria pra assinar um contrato importante. ✍️")
            return {"status": "aguardando nome"}

        if name and email:
            first_name = name.split()[0]
            welcome = (
                f"Perfeito, {first_name}! 👊\n\n"
                "Seus dados estão registrados. Agora sim, podemos começar de verdade. 😊\n\n"
                "Estou aqui pra te ajudar com suas finanças, seus investimentos, decisões sobre empréstimos "
                "e até com orientações práticas de vida espiritual e familiar.\n\n"
                "Me conta: qual é a principal situação financeira que você quer resolver hoje?"
            )
            send_message(from_number, welcome)
            return {"status": "cadastro completo"}

    # MEMÓRIA
    conversa_path = f"conversas/{from_number}.txt"
    os.makedirs("conversas", exist_ok=True)
    if not os.path.exists(conversa_path):
        with open(conversa_path, "w") as f:
            f.write("")

    with open(conversa_path, "a") as f:
        f.write(f"Usuário: {incoming_msg}\n")

    prompt_base = open("prompt.txt", "r").read()
    historico = open(conversa_path, "r").read()

    full_prompt = f"""{prompt_base}

{historico}
Conselheiro:"""

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": full_prompt}],
        temperature=0.7,
    )

    reply = response["choices"][0]["message"]["content"].strip()
    reply = capitalize_response(reply)

    with open(conversa_path, "a") as f:
        f.write(f"Conselheiro: {reply}\n")

    tokens = count_tokens(incoming_msg) + count_tokens(reply)
    sheet.update_cell(row, 5, int(sheet.cell(row, 5).value or 0) + tokens)
    sheet.update_cell(row, 6, int(sheet.cell(row, 6).value or 0) + 1)

    send_message(from_number, reply)
    return {"status": "mensagem enviada"}
