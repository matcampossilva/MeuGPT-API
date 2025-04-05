import os
import openai
import requests
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
from resgatar_contexto import buscar_conhecimento_relevante

load_dotenv()
app = FastAPI()

openai.api_key = os.getenv("OPENAI_API_KEY")
client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
MESSAGING_SERVICE_SID = os.getenv("TWILIO_MESSAGING_SERVICE_SID")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_SHEET_GASTOS_ID = os.getenv("GOOGLE_SHEET_GASTOS_ID")
GOOGLE_SHEETS_KEY_FILE = os.getenv("GOOGLE_SHEETS_KEY_FILE")

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_KEY_FILE, scope)
gs = gspread.authorize(creds)

# === PLANILHAS ===
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

def nome_valido(text):
    if not text:
        return False
    partes = text.strip().split()
    if len(partes) < 2:
        return False
    if any(char in text for char in "@!?0123456789#%$*"):
        return False
    return True

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
                gastos.append({"descricao": descricao, "valor": valor, "forma_pagamento": forma})
            except ValueError:
                continue
    return gastos

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    incoming_msg = form["Body"].strip()
    from_number = format_number(form["From"])

    if not os.path.exists("conversas"):
        os.makedirs("conversas")

    status = get_user_status(from_number)
    sheet = get_user_sheet(from_number)
    values = sheet.col_values(2)
    row = values.index(from_number) + 1 if from_number in values else None

    name = sheet.cell(row, 1).value.strip() if sheet.cell(row, 1).value else ""
    email = sheet.cell(row, 3).value.strip() if sheet.cell(row, 3).value else ""
    contexto_pessoal = sheet.cell(row, 7).value.strip() if sheet.cell(row, 7).value else ""

    if passou_limite(sheet, row):
        send_message(from_number, "⚠️ Limite gratuito atingido. Acesse: https://seulinkpremium.com")
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
                    continue
            if not captured_name and nome_valido(linha):
                captured_name = linha

        if captured_name and not name:
            sheet.update_cell(row, 1, captured_name)
            name = captured_name

        if captured_email and not email:
            sheet.update_cell(row, 3, captured_email)
            email = captured_email

        if not name and not email:
            send_message(from_number,
                "Olá! 👋🏼 Que bom ter você aqui.\n\n"
                "Sou seu Conselheiro Financeiro pessoal, criado pelo Matheus Campos, CFP.\n"
                "Para começarmos nossa jornada juntos, preciso apenas do seu nome e e-mail, por favor. Pode me mandar?")
            return {"status": "aguardando nome e email"}

        if not name:
            send_message(from_number, "Faltou seu nome completo. ✍️")
            return {"status": "aguardando nome"}

        if not email:
            send_message(from_number, "Agora me manda seu e-mail, por favor. 📧")
            return {"status": "aguardando email"}

        primeiro_nome = name.split()[0]
        welcome_msg = f"""Perfeito, {primeiro_nome}! 👊\n\nTô aqui pra te ajudar a organizar suas finanças e sua vida, sempre respeitando esta hierarquia: Deus, sua família e seu trabalho.\n\nPosso te ajudar com controle de gastos, resumos financeiros automáticos, alertas inteligentes no WhatsApp e email, análises de empréstimos e investimentos, além de orientações práticas para sua vida espiritual e familiar.\n\nPor onde quer começar?"""
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
                resultado = registrar_gasto(name, from_number, gasto["descricao"], gasto["valor"], gasto["forma_pagamento"])
                resultados.append(f"{gasto['descricao']}: {resultado['categoria']}")
            send_message(from_number, "Gastos registrados:\n" + "\n".join(resultados))
            return {"status": "gastos registrados"}

    # Media
    if form.get("NumMedia") and int(form.get("NumMedia")) > 0:
        media_url = form.get("MediaUrl0")
        media_type = form.get("MediaContentType0")
        r = requests.get(media_url)
        filename = media_url.split("/")[-1]
        path = f"uploads/{filename}"
        os.makedirs("uploads", exist_ok=True)
        with open(path, "wb") as f:
            f.write(r.content)
        send_message(from_number, f"📎 Arquivo salvo: {filename}")
        return {"status": "arquivo salvo"}

    if "gastei" in incoming_msg.lower() and "mês" in incoming_msg.lower():
        resumo = gerar_resumo(numero_usuario=from_number, periodo="mensal")
        send_message(from_number, resumo)
        return {"status": "resumo mensal enviado"}

    if "gastei" in incoming_msg.lower() and "hoje" in incoming_msg.lower():
        resumo = gerar_resumo(numero_usuario=from_number, periodo="diario")
        send_message(from_number, resumo)
        return {"status": "resumo diário enviado"}

    conversa_path = f"conversas/{from_number}.txt"
    with open(conversa_path, "a") as f:
        f.write(f"Usuário: {incoming_msg}\n")

    # Lê e filtra o histórico para evitar ecoar mensagens introdutórias
    with open(conversa_path, "r") as f:
        linhas_conversa = f.readlines()

    historico_filtrado = []
    for linha in linhas_conversa:
        if any(frase in linha.lower() for frase in [
            "sou seu conselheiro financeiro",
            "sou o meu conselheiro financeiro",
            "perfeito,",
            "tô aqui pra te ajudar",
            "posso te ajudar com controle de gastos",
            "por onde quer começar"
        ]):
            continue
        historico_filtrado.append(linha)

    historico = "".join(historico_filtrado).strip()

    prompt_base = open("prompt.txt", "r").read()

    contexto_resgatado = buscar_conhecimento_relevante(incoming_msg, top_k=3)

    full_prompt = f"""{prompt_base}

    # Conhecimento relevante:
    {contexto_resgatado}

    # Conversa recente:
    {historico}
    Conselheiro:"""

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-16k",
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

@app.get("/health")
def health_check():
    return {"status": "vivo, lúcido e com fé"}