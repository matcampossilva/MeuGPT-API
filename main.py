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
from gastos import registrar_gasto
from gerar_resumo import gerar_resumo

# === INICIALIZAÇÃO ===
load_dotenv()
app = FastAPI()

# === AMBIENTE ===
openai.api_key = os.getenv("OPENAI_API_KEY")
client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
MESSAGING_SERVICE_SID = os.getenv("TWILIO_MESSAGING_SERVICE_SID")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_SHEET_GASTOS_ID = os.getenv("GOOGLE_SHEET_GASTOS_ID")
GOOGLE_SHEETS_KEY_FILE = os.getenv("GOOGLE_SHEETS_KEY_FILE")

# === PLANILHAS GOOGLE ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_KEY_FILE, scope)
gs = gspread.authorize(creds)

# === PLANILHA ===
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

# === VALIDAÇÃO DE NOME ===
def nome_valido(text):
    if not text:
        return False
    partes = text.strip().split()
    if len(partes) < 2:
        return False
    if any(char in text for char in "@!?0123456789#%$*"):
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
    status = sheet.title
    if status != "Gratuitos":
        return False
    return get_interactions(sheet, row) >= 10

def is_boas_vindas(text):
    saudacoes = ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite"]
    text = text.lower()
    return any(sauda in text for sauda in saudacoes)

def detectar_gastos(texto):
    return any(moeda in texto for moeda in ["R$", ",00", ".00", "gastei", "comprei", "- débito", "- crédito", "pix"])

def extrair_gastos(texto):
    linhas = texto.split("\n")
    gastos = []
    for linha in linhas:
        match = re.search(r"(\d{1,3}(?:[\.,]\d{2})?)\s*[-–—]\s*(.*?)\s*[-–—]\s*(\w+)", linha.strip(), re.IGNORECASE)
        if match:
            valor_raw = match.group(1).replace(".", "").replace(",", ".")
            descricao = match.group(2).strip().capitalize()
            forma = match.group(3).strip().capitalize()
            try:
                valor = float(valor_raw)
                gastos.append({
                    "descricao": descricao,
                    "valor": valor,
                    "forma_pagamento": forma
                })
            except ValueError:
                continue
    return gastos

# === ENDPOINT PRINCIPAL ===
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
                "Olá! 👋🏼 Que bom ter você aqui.\n\n"
                "Sou seu Conselheiro Financeiro pessoal. Para começarmos nossa jornada juntos, preciso apenas do seu nome e e-mail, por favor. Pode me mandar?")
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

    if not name or not email:
        linhas = incoming_msg.split("\n")
        captured_name = None
        captured_email = None

        for linha in linhas:
            linha = linha.strip()
            if not captured_email:
                possible_email = extract_email(linha)
                if possible_email:
                    captured_email = possible_email
            if not captured_name and nome_valido(linha):
                captured_name = linha

        if captured_name and not name:
            sheet.update_cell(row, 1, captured_name)
            name = captured_name

        if captured_email and not email:
            sheet.update_cell(row, 3, captured_email)
            email = captured_email

        if not name:
            send_message(from_number,
                "Faltou só seu nome completo — preciso fazer seu cadastro, senão perco meu emprego. ✍️")
            return {"status": "aguardando nome"}

        if not email:
            send_message(from_number,
                "Agora me manda seu e-mail, por favor. 📧")
            return {"status": "aguardando email"}

        primeiro_nome = name.split()[0]
        welcome_msg = f"""Perfeito, {primeiro_nome}! 👊\n\nFico feliz em te ver por aqui. Agora sim, podemos caminhar juntos — com clareza, propósito e leveza. 😄\n\nSou seu Conselheiro Financeiro pessoal. Tô aqui pra te ajudar a colocar ordem nas finanças sem deixar de lado o que realmente importa: Deus, sua família e sua missão.\n\nMe conta: o que tá tirando sua paz hoje na parte financeira?"""
        send_message(from_number, welcome_msg)
        return {"status": "cadastro completo"}

    if "resumo" in incoming_msg.lower():
        resumo = gerar_resumo(numero_usuario=from_number, periodo="diário")
        send_message(from_number, resumo)
        return {"status": "resumo enviado"}

    if detectar_gastos(incoming_msg):
        gastos = extrair_gastos(incoming_msg)
        if gastos:
            resultados = []
            for gasto in gastos:
                resultado = registrar_gasto(
                    nome_usuario=name,
                    numero_usuario=from_number,
                    descricao=gasto["descricao"],
                    valor=gasto["valor"],
                    forma_pagamento=gasto["forma_pagamento"]
                )
                resultados.append(f"{gasto['descricao']}: {resultado['categoria']}")

            resumo = "\n".join(resultados)
            confirmacao = f"Tudo certo! 🧾 Seus gastos foram registrados:\n\n{resumo}"
            send_message(from_number, confirmacao)
            return {"status": "gastos registrados"}

    conversa_path = f"conversas/{from_number}.txt"
    with open(conversa_path, "a") as f:
        f.write(f"Usuário: {incoming_msg}\n")

    prompt_base = open("prompt.txt", "r").read()
    historico = open(conversa_path, "r").read()

    full_prompt = f"""{prompt_base}\n\n{historico}
Conselheiro:"""

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": full_prompt}],
        temperature=0.7,
    )

    reply = response["choices"][0]["message"]["content"].strip()

    if historico.count("Usuário:") > 1:
        if reply.lower().startswith("olá"):
            reply = re.sub(r"(?i)^olá[!,.\s]*", "", reply).strip().capitalize()

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