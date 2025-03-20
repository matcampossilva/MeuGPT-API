from fastapi import FastAPI, Request
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from openai import OpenAI
from enviar_whatsapp import enviar_whatsapp
import os

app = FastAPI()

# -------- CONFIGURAÇÕES --------
URL_GOOGLE_SHEETS = 'https://docs.google.com/spreadsheets/d/1bhnyG0-DaH3gE687_tUEy9kVI7rV-bxJl10bRKkDl2Y/edit?usp=sharing'
SHEET_PAGANTES = 'Pagantes'
SHEET_GRATUITOS = 'Gratuitos'
LIMIT_INTERACOES = 10  # Limite de interações gratuitas

# OPENAI API
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=OPENAI_API_KEY)

# -------- GOOGLE SHEETS --------
def conecta_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name('/etc/secrets/meugpt-api-sheets-92a9d439900d.json', scope)
    client = gspread.authorize(creds)
    return client

def verifica_pagante(numero):
    client = conecta_google_sheets()
    sheet = client.open_by_url(URL_GOOGLE_SHEETS).worksheet(SHEET_PAGANTES)
    lista = sheet.get_all_records()
    for linha in lista:
        if str(linha['WHATSAPP']) == numero and linha['STATUS'].upper() == 'ATIVO':
            return True
    return False

def atualiza_gratuitos(numero, nome, email):
    client = conecta_google_sheets()
    sheet = client.open_by_url(URL_GOOGLE_SHEETS).worksheet(SHEET_GRATUITOS)
    lista = sheet.get_all_records()
    encontrado = False
    for i, linha in enumerate(lista):
        if str(linha['WHATSAPP']) == numero:
            novo_valor = int(linha['CONTADOR']) + 1
            sheet.update_cell(i+2, 4, novo_valor)  # Atualiza coluna CONTADOR
            encontrado = True
            return novo_valor
    if not encontrado:
        sheet.append_row([nome, numero, email, 1])
        return 1

# -------- GPT CONSULTA --------
PROMPT_BASE = """
Você é o Meu Conselheiro Financeiro pessoal, criado por Matheus Campos, CFP®.

Sua missão é organizar a vida financeira do usuário respeitando rigorosamente esta hierarquia: Deus, família e trabalho, nesta ordem.

O dinheiro serve ao homem, jamais o contrário. Seu objetivo é ajudar o usuário a usar o dinheiro com sabedoria, clareza e sem apego, alinhando sua vida financeira à sua missão espiritual e familiar.

Sua comunicação é sempre leve, amigável e intimista, com leve toque goiano (ex.: "Uai!", "Tem base?"), provocando sempre perguntas curtas para o usuário. Utilize emojis naturais e apropriados.

Seja conciso e prático, sem respostas muito longas. Oriente o usuário a lançar seus gastos, perguntar sobre dívidas, investimentos ou qualquer questão financeira.

Jamais mencione fontes ou arquivos, apenas incorpore os conhecimentos naturalmente. Nunca recomende divórcio. Para crises financeiras no casamento, sempre proponha estratégias práticas e espirituais alinhadas com São Josemaria Escrivá e a Doutrina Católica.
"""

def consulta_chatgpt(nome, mensagem_usuario):
    mensagem_completa = f"{PROMPT_BASE}\nUsuário: {mensagem_usuario}\nConselheiro:"
    resposta = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": PROMPT_BASE},
            {"role": "user", "content": mensagem_usuario}
        ],
        max_tokens=500
    )
    return resposta.choices[0].message.content.strip()

# -------- ENDPOINT PRINCIPAL --------
@app.post("/webhook")
async def receber_mensagem(request: Request):
    dados = await request.json()
    nome = dados['nome']
    numero = dados['whatsapp']
    email = dados.get('email', '')
    mensagem_usuario = dados['mensagem']

    if verifica_pagante(numero):
        resposta_gpt = consulta_chatgpt(nome, mensagem_usuario)
        enviar_whatsapp(resposta_gpt, numero_destino=f"+55{numero}")
        return {"resposta": resposta_gpt}
    else:
        interacoes = atualiza_gratuitos(numero, nome, email)
        if interacoes <= LIMIT_INTERACOES:
            resposta = f"Olá {nome}! 🌟 Você está na versão gratuita ({interacoes}/{LIMIT_INTERACOES} interações). Para liberar acesso completo ao Meu Conselheiro Financeiro, clique aqui: [link para assinar]."
        else:
            resposta = f"Ei {nome}, seu limite gratuito acabou! 🚀 Quer liberar tudo? Acesse aqui: [link premium]."
        enviar_whatsapp(resposta, numero_destino=f"+55{numero}")
        return {"resposta": resposta}
