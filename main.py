import os
import openai
import faiss
import pickle
import numpy as np
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from twilio.twiml.messaging_response import MessagingResponse
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz

# === CONFIG ===
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

SPREADSHEET_KEY = os.getenv("SPREADSHEET_KEY")
WHATSAPP_LIMIT = 10
TIMEZONE = pytz.timezone("America/Sao_Paulo")

INDEX_PATH = "vector_index/faiss.index"
CHUNKS_PATH = "vector_index/chunks.pkl"

# === FAISS + Vetorização ===
index = faiss.read_index(INDEX_PATH)
with open(CHUNKS_PATH, "rb") as f:
    texts = pickle.load(f)

def search_context(query, k=5):
    response = openai.Embedding.create(
        input=query,
        model="text-embedding-3-small"
    )
    embedding = np.array(response["data"][0]["embedding"]).astype("float32")
    distances, indices = index.search(np.array([embedding]), k)
    results = [texts[i] for i in indices[0] if i < len(texts)]
    return "\n---\n".join(results)

# === Sheets ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("meugpt-api-sheets-92a9d439900d.json", scope)
client = gspread.authorize(creds)

pagantes = client.open_by_key(SPREADSHEET_KEY).worksheet("Pagantes")
gratuitos = client.open_by_key(SPREADSHEET_KEY).worksheet("Gratuitos")

# === FastAPI ===
app = FastAPI()

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    user_message = form.get("Body", "").strip()
    sender = form.get("From", "")
    number = sender.replace("whatsapp:", "")

    nome, email = None, None

    user_row = find_user(pagantes, number)
    planilha = pagantes
    is_pagante = True

    if user_row is None:
        user_row = find_user(gratuitos, number)
        planilha = gratuitos
        is_pagante = False

    if user_row is None:
        now = datetime.now(TIMEZONE).strftime("%d/%m/%Y %H:%M:%S")
        gratuitos.append_row([now, number, "", "", 1])
        return responder("Olá! Antes de continuar, por favor, me diga seu *nome completo* e *e-mail*. Esses dados são obrigatórios para prosseguir. 😊")

    row_values = planilha.row_values(user_row)
    nome = row_values[2] if len(row_values) >= 3 else None
    email = row_values[3] if len(row_values) >= 4 else None
    interacoes = int(row_values[4]) if len(row_values) >= 5 else 0

    if not nome or not email:
        if "@" in user_message:
            email = user_message
        else:
            nome = user_message

        planilha.update_cell(user_row, 3, nome if nome else "")
        planilha.update_cell(user_row, 4, email if email else "")

        if not nome or not email:
            return responder("Perfeito! Agora me diga seu *e-mail* para continuarmos. 📧")

    if not is_pagante and interacoes >= WHATSAPP_LIMIT:
        return responder(
            f"Chegamos ao limite de interações gratuitas. 😔\n\n"
            "Se quiser continuar tendo acesso ao Meu Conselheiro Financeiro, clique no link abaixo e ative sua versão completa:\n"
            "*[link premium aqui]*"
        )

    if not is_pagante:
        interacoes += 1
        planilha.update_cell(user_row, 5, interacoes)

    contexto = search_context(user_message)
    prompt = (
        "Você é o Meu Conselheiro Financeiro, uma inteligência criada por Matheus Campos para ajudar pessoas a amadurecerem sua vida financeira, familiar, profissional e espiritual.\n\n"
        f"Contexto relevante dos arquivos de Matheus:\n{contexto}\n\n"
        f"Pergunta: {user_message}\n\n"
        "Resposta:"
    )

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Você é um planejador financeiro com visão católica e sabedoria prática. Seja direto, concreto e inspirador."},
            {"role": "user", "content": prompt}
        ]
    )

    resposta_final = response["choices"][0]["message"]["content"].strip()
    return responder(resposta_final)

# === Funções Auxiliares ===

def responder(msg):
    twiml = MessagingResponse()
    twiml.message(msg)
    return str(twiml)

def find_user(sheet, number):
    numbers = sheet.col_values(2)
    try:
        return numbers.index(number) + 1
    except ValueError:
        return None
