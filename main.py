from fastapi import FastAPI, Request
from openai import OpenAI
from enviar_whatsapp import enviar_whatsapp as enviar_mensagem_whatsapp
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
client = OpenAI()

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("meugpt-api-sheets-2e29d11818b1.json", scope)
google_client = gspread.authorize(creds)
sheet_pagantes = google_client.open("Clientes Meu Conselheiro Financeiro").worksheet("Pagantes")
sheet_gratuitos = google_client.open("Clientes Meu Conselheiro Financeiro").worksheet("Gratuitos")

@app.post("/webhook")
async def webhook(request: Request):
    form = await request.form()
    mensagem = form.get("Body")
    numero_usuario = form.get("From").replace("whatsapp:", "")

    dados_pagantes = sheet_pagantes.get_all_records()
    dados_gratuitos = sheet_gratuitos.get_all_records()

    numeros_pagantes = [str(dado['WhatsApp']) for dado in dados_pagantes]
    numeros_gratuitos = [str(dado['WhatsApp']) for dado in dados_gratuitos]

    if numero_usuario in numeros_pagantes:
        tipo_usuario = "pagante"
        nome_usuario = [dado['Nome'] for dado in dados_pagantes if dado['WhatsApp'] == numero_usuario][0]
        contador = None
    elif numero_usuario in numeros_gratuitos:
        tipo_usuario = "gratuito"
        usuario_atual = [dado for dado in dados_gratuitos if dado['WhatsApp'] == numero_usuario][0]
        contador = int(usuario_atual['Contador'])
        nome_usuario = usuario_atual['Nome']
    else:
        tipo_usuario = "novo"
        nome_usuario = ""
        contador = 0
        sheet_gratuitos.append_row([numero_usuario, "", "", contador])

    if tipo_usuario == "novo" or nome_usuario.strip() == "":
        if "@" in mensagem:
            nome, email = mensagem.split("\n")[0], mensagem.split("\n")[1]
            sheet_gratuitos.update_cell(numeros_gratuitos.index(numero_usuario)+2, 2, nome)
            sheet_gratuitos.update_cell(numeros_gratuitos.index(numero_usuario)+2, 3, email)
            resposta = f"Show, {nome}! ✅ Cadastro feito. Vamos começar! 🔥"
        else:
            resposta = ("Antes da gente começar, me conta uma coisa: qual o seu nome e e-mail? 👇\n\n"
                        "Preciso disso pra te liberar o acesso gratuito aqui no Meu Conselheiro Financeiro. "
                        "A partir daqui, esquece robozinho engessado. Você vai ter uma conversa que mistura "
                        "dinheiro, propósito e vida real. Sem enrolação. 💼🔥")
    else:
        if tipo_usuario == "gratuito" and contador >= 10:
            resposta = "⚠️ Você atingiu o limite de interações gratuitas. Acesse o Premium para continuar."
        else:
            resposta_openai = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[{"role": "user", "content": mensagem}]
            )
            resposta = resposta_openai.choices[0].message.content

            if tipo_usuario == "gratuito":
                contador += 1
                sheet_gratuitos.update_cell(numeros_gratuitos.index(numero_usuario)+2, 4, contador)

                if contador >= 7 and contador < 10:
                    resposta += (f"\n\n⚠️ Restam só {10 - contador} interações gratuitas! "
                                 "Considere o Premium para acesso completo.")

    enviar_mensagem_whatsapp(resposta, numero_usuario)

    return {"status": "Mensagem enviada"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=10000, reload=True)
