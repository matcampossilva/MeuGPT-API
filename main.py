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
GOOGLE_SHEET_GASTOS_ID = os.getenv("GOOGLE_SHEET_GASTOS_ID")
GOOGLE_SHEETS_KEY_FILE = os.getenv("GOOGLE_SHEETS_KEY_FILE")

app = FastAPI()

# PLANILHAS GOOGLE
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_KEY_FILE, scope)
gs = gspread.authorize(creds)

# ==== PLANILHAS ====

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
        sheet.append_row(["", user_number, "", now, 0, 0])  # Inclui coluna de interações zerada
        return sheet

def get_gastos_sheet():
    try:
        gastos = gs.open_by_key(GOOGLE_SHEET_GASTOS_ID)
        return gastos.worksheet("Gastos Diários")
    except Exception as e:
        print(f"Erro ao acessar planilha de gastos: {e}")
        return None

# ==== FUNÇÕES AUXILIARES ====

def format_number(raw_number):
    return raw_number.replace("whatsapp:", "").strip()

def extract_email(text):
    match = re.search(r'[\w\.-]+@[\w\.-]+', text)
    return match.group(0) if match else None

def extract_name(text):
    if " " in text.strip() and len(text.split()) >= 2:
        return text.strip()
    return None

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
    status = sheet.title
    if status != "Gratuitos":
        return False
    return get_interactions(sheet, row) >= 10

# ==== ENDPOINT PRINCIPAL ====

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    incoming_msg = form["Body"].strip()
    from_number = format_number(form["From"])

    # Garante que a pasta de conversas existe
    if not os.path.exists("conversas"):
        os.makedirs("conversas")

    sheet = get_user_sheet(from_number)
    values = sheet.col_values(2)
    row = values.index(from_number) + 1 if from_number in values else None

    name = sheet.cell(row, 1).value.strip() if sheet.cell(row, 1).value else ""
    email = sheet.cell(row, 3).value.strip() if sheet.cell(row, 3).value else ""

    # BLOQUEIO POR LIMITE
    if passou_limite(sheet, row):
        send_message(from_number, "⚠️ Você atingiu o limite gratuito de 10 interações.\n\nPra continuar com seu conselheiro financeiro pessoal (que é mais paciente que muita gente), acesse: https://seulinkpremium.com")
        return {"status": "limite atingido"}

    # ONBOARDING — coleta de nome e email com personalidade
    captured_email = extract_email(incoming_msg) if not email else None
    captured_name = extract_name(incoming_msg) if not name else None

    if not name or not email:
        if captured_name:
            sheet.update_cell(row, 1, captured_name)
            name = captured_name

        if captured_email:
            sheet.update_cell(row, 3, captured_email)
            email = captured_email

        if not name and not email:
            send_message(from_number, "Olá! 👋 Que bom ter você aqui.\n\nAntes de começarmos essa jornada financeira e (quem sabe) espiritual, preciso só do seu nome e do seu e-mail. Pode mandar os dois aqui mesmo. 🙏📩")
            return {"status": "aguardando nome e email"}

        if name and not email:
            send_message(from_number, "Faltou só o e-mail. Não fuja agora, estou começando a confiar em você. 📧")
            return {"status": "aguardando email"}

        if email and not name:
            send_message(from_number, "Quase lá. Agora me diz seu nome completo — aquele que você usaria numa reunião com o gerente do banco. ✍️")
            return {"status": "aguardando nome"}

        if name and email:
            welcome_msg = f"""Perfeito, {name}! 👊

Seus dados estão registrados. Agora sim, podemos começar de verdade. 😊

Estou aqui pra te ajudar com suas finanças, seus investimentos, decisões sobre empréstimos e até com orientações práticas de vida espiritual e familiar.

Me conta: qual é a principal situação financeira que você quer resolver hoje?"""
            send_message(from_number, welcome_msg)
            return {"status": "cadastro completo"}

    # MEMÓRIA DE CONVERSA
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

    with open(conversa_path, "a") as f:
        f.write(f"Conselheiro: {reply}\n")

    tokens = count_tokens(incoming_msg) + count_tokens(reply)
    sheet.update_cell(row, 5, int(sheet.cell(row, 5).value or 0) + tokens)
    increment_interactions(sheet, row)

    send_message(from_number, reply)
    return {"status": "mensagem enviada"}

# ==== ENDPOINT DE SAÚDE ====

@app.get("/health")
def health_check():
    return {"status": "vivo, lúcido e pronto pra mais boletos"}