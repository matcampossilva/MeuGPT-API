from fastapi import FastAPI, Request
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import openai
import os
from enviar_whatsapp import enviar_whatsapp

app = FastAPI()

# Configurações Google Sheets
URL_GOOGLE_SHEETS = 'https://docs.google.com/spreadsheets/d/1bhnyG0-DaH3gE687_tUEy9kVI7rV-bxJl10bRKkDl2Y/edit?usp=sharing'
SHEET_PAGANTES = 'Pagantes'
SHEET_GRATUITOS = 'Gratuitos'
LIMIT_INTERACOES = 10  # Limite de interações gratuitas

# Configuração Google Sheets API
def conecta_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name('/etc/secrets/meugpt-api-sheets-92a9d439900d.json', scope)
    client = gspread.authorize(creds)
    return client

# Verifica se número é pagante
def verifica_pagante(numero):
    client = conecta_google_sheets()
    sheet = client.open_by_url(URL_GOOGLE_SHEETS).worksheet(SHEET_PAGANTES)
    lista = sheet.get_all_records()
    for linha in lista:
        if str(linha['WHATSAPP']) == numero and linha['STATUS'].upper() == 'ATIVO':
            return True
    return False

# Atualiza/Registra usuários gratuitos
def atualiza_gratuitos(numero, nome, email):
    client = conecta_google_sheets()
    sheet = client.open_by_url(URL_GOOGLE_SHEETS).worksheet(SHEET_GRATUITOS)
    lista = sheet.get_all_records()
    encontrado = False
    for i, linha in enumerate(lista):
        if str(linha['WHATSAPP']) == numero:
            novo_valor = int(linha['CONTADOR']) + 1
            sheet.update_cell(i+2, 4, novo_valor)  # coluna CONTADOR
            encontrado = True
            return novo_valor
    if not encontrado:
        sheet.append_row([nome, numero, email, 1])
        return 1

# Configuração OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Prompt fixo
PROMPT_BASE = """
Você é o Meu Conselheiro Financeiro pessoal, criado por Matheus Campos, CFP®.

Sua missão é organizar a vida financeira do usuário respeitando rigorosamente esta hierarquia: Deus, família e trabalho, nesta ordem.

O dinheiro serve ao homem, jamais o contrário. Seu objetivo é ajudar o usuário a usar o dinheiro com sabedoria, clareza e sem apego, alinhando sua vida financeira à sua missão espiritual e familiar.

Sua comunicação é sempre leve, amigável e intimista, com leve toque goiano (ex.: "Uai!", "Tem base?"), provocando sempre perguntas curtas para o usuário. Utilize emojis naturais e apropriados.

Seja conciso e prático, sem respostas muito longas. Oriente o usuário a lançar seus gastos, perguntar sobre dívidas, investimentos ou qualquer questão financeira.

Jamais mencione fontes ou arquivos, apenas incorpore os conhecimentos naturalmente. Nunca recomende divórcio. Para crises financeiras no casamento, sempre proponha estratégias práticas e espirituais alinhadas com São Josemaria Escrivá e a Doutrina Católica.
"""

# Função para consultar o ChatGPT
def consulta_chatgpt(nome, mensagem_usuario):
    mensagem_final = f"{PROMPT_BASE}\nUsuário: {mensagem_usuario}\nMeu Conselheiro Financeiro:"
    try:
        resposta = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": PROMPT_BASE},
                {"role": "user", "content": mensagem_usuario}
            ],
            max_tokens=500,
            temperature=0.7
        )
        return resposta['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f"❌ Ocorreu um erro ao consultar o GPT: {e}"

# Endpoint principal
from fastapi import Form

@app.post("/webhook")
async def receber_mensagem(
    Body: str = Form(...),
    From: str = Form(...),
):

    numero = From.replace("whatsapp:", "").replace("+", "").strip()
    nome = "Usuário"  # Nome genérico, pois Twilio não manda nome

    # A mensagem enviada pelo usuário
    mensagem_usuario = Body

    if verifica_pagante(numero):
        resposta_gpt = consulta_chatgpt(nome, mensagem_usuario)
        enviar_whatsapp(resposta_gpt, numero_destino=f"+{numero}")
        return {"resposta": resposta_gpt}
    else:
        interacoes = atualiza_gratuitos(numero, nome, email="")
        if interacoes <= LIMIT_INTERACOES:
            resposta = f"Olá! 🌟 Você está na versão gratuita ({interacoes}/{LIMIT_INTERACOES} interações). Para liberar acesso completo ao Meu Conselheiro Financeiro, clique aqui: [link para assinar]."
        else:
            resposta = f"Ei, seu limite gratuito acabou! 🚀 Quer liberar tudo? Acesse aqui: [link premium]."
        enviar_whatsapp(resposta, numero_destino=f"+{numero}")
        return {"resposta": resposta}
