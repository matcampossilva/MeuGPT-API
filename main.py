import os
import openai
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from twilio.rest import Client
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
import re

load_dotenv()
app = FastAPI()

# === VARIÁVEIS DE AMBIENTE ===
openai.api_key = os.getenv("OPENAI_API_KEY")
client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
MESSAGING_SERVICE_SID = os.getenv("TWILIO_MESSAGING_SERVICE_SID")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_SHEETS_KEY_FILE = os.getenv("GOOGLE_SHEETS_KEY_FILE")

# === PLANILHA ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_KEY_FILE, scope)
gs = gspread.authorize(creds)

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
    except:
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
    
# === VALIDAÇÃO DE NOME ===
def nome_valido(text):
    if not text
        return False
    partes = text.strip().split()
    if len(partes) < 2:
        return False
    if any(char in text for char in "@!?0123456789#%$*"):
        return False
    if "meu nome" in text.lower() or "já mandei" in text.lower() or "é" in text.lower():
        return False
    return True

# === AUXILIARES ===
def format_number(raw_number):
    return raw_number.replace("whatsapp:", "").strip()

def extract_email(text):
    match = re.search(r'[\w\.-]+@[\w\.-]+', text)
    return match.group(0) if match else None

def count_tokens(text):
    return len(text.split())

def send_message(to, body):
    client.messages.create(
        body=body,
        messaging_service_sid=MESSAGING_SERVICE_SID,
        to=f"whatsapp:{to}"
    )

def get_interactions(sheet, row):
    try:
        val = sheet.cell(row, 6).value
        return int(val) if val else 0
    except:
        return 0

def increment_interactions(sheet, row):
    count = get_interactions(sheet, row) + 1
    sheet.update_cell(row, 6, count)
    return count

def passou_limite(sheet, row):
    return sheet.title == "Gratuitos" and get_interactions(sheet, row) >= 10

def is_boas_vindas(text):
    return text.lower() in ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite"]

# === WEBHOOK PRINCIPAL ===
@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    incoming_msg = form["Body"].strip()
    from_number = format_number(form["From"])

    if not os.path.exists("conversas"):
        os.makedirs("conversas")

    status = get_user_status(from_number)

    if status == "Novo":
        if is_boas_vindas(incoming_msg):
            send_message(from_number,
                "Ei! Que bom te ver por aqui. 🙌\n\n"
                "Antes da gente começar de verdade, preciso só de dois detalhes:\n"
                "👉 Seu nome completo (como quem assina um contrato importante)\n"
                "👉 Seu e-mail\n\n"
                "Pode mandar os dois aqui mesmo e já seguimos. 😉")
            return {"status": "mensagem de boas-vindas enviada"}
        sheet = get_user_sheet(from_number)
        values = sheet.col_values(2)
        row = values.index(from_number) + 1 if from_number in values else None
    else:
        sheet = get_user_sheet(from_number)
        values = sheet.col_values(2)
        row = values.index(from_number) + 1 if from_number in values else None

    name = sheet.cell(row, 1).value.strip() if sheet.cell(row, 1).value else ""
    email = sheet.cell(row, 3).value.strip() if sheet.cell(row, 3).value else ""

    if passou_limite(sheet, row):
        send_message(from_number,
            "⚠️ Você atingiu o limite gratuito de 10 interações.\n\n"
            "Pra continuar com seu conselheiro financeiro pessoal (que é mais paciente que muita gente), acesse: https://seulinkpremium.com")
        return {"status": "limite atingido"}

    captured_email = extract_email(incoming_msg) if not email else None
    captured_name = incoming_msg if not name and nome_valido(incoming_msg) else None

    if not name or not email:
        if captured_name:
            sheet.update_cell(row, 1, captured_name)
            name = captured_name

        if captured_email:
            sheet.update_cell(row, 3, captured_email)
            email = captured_email

        if not name and not email:
            send_message(from_number,
                "Ei! Que bom te ver por aqui. 🙌\n\n"
                "Antes da gente começar de verdade, preciso só de dois detalhes:\n"
                "👉 Seu nome completo (como quem assina um contrato importante)\n"
                "👉 Seu e-mail\n\n"
                "Pode mandar os dois aqui mesmo e já seguimos. 😉")
            return {"status": "aguardando nome e email"}

        if name and not email:
            send_message(from_number, "Faltou só o e-mail. Vai lá, sem medo. 🙏")
            return {"status": "aguardando email"}

        if email and not name:
            send_message(from_number,
                "Faltou o nome completo — aquele que você usaria pra assinar um contrato importante. ✍️")
            return {"status": "aguardando nome"}

        if name and email:
            primeiro_nome = name.split()[0]
            welcome_msg = f"""Perfeito, {primeiro_nome}! 👊

Seus dados estão registrados. Agora sim, podemos começar de verdade. 😊

Estou aqui pra te ajudar com suas finanças, seus investimentos, decisões sobre empréstimos e até com orientações práticas de vida espiritual e familiar.

Me conta: qual é a principal situação financeira que você quer resolver hoje?"""
            send_message(from_number, welcome_msg)
            return {"status": "cadastro completo"}

    conversa_path = f"conversas/{from_number}.txt"
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

    # Remove "olá" mesmo no meio do texto
    reply = re.sub(r"(?i)\b(ol[áa])[!,.\s]*", "", reply, count=1).strip().capitalize()

    with open(conversa_path, "a") as f:
        f.write(f"Conselheiro: {reply}\n")

    tokens = count_tokens(incoming_msg) + count_tokens(reply)
    sheet.update_cell(row, 5, int(sheet.cell(row, 5).value or 0) + tokens)
    increment_interactions(sheet, row)

    send_message(from_number, reply)
    return {"status": "mensagem enviada"}

@app.get("/health")
def health_check():
    return {"status": "vivo, lúcido e com fé"}

@app.get("/reset_user")
def reset_user(numero: str):
    try:
        path = f"conversas/{numero}.txt"
        if os.path.exists(path):
            os.remove(path)
        sheet = get_user_sheet(numero)
        values = sheet.col_values(2)
        row = values.index(numero) + 1 if numero in values else None
        if row:
            sheet.update_cell(row, 5, 0)
            sheet.update_cell(row, 6, 0)
        return JSONResponse(content={"status": "reset completo"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"erro": str(e)})