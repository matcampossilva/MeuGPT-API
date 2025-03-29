import os
import openai
import pytz
import datetime
from fastapi import FastAPI, Request
from pydantic import BaseModel
from configuracoes import (
    verificar_usuario,
    atualizar_interacoes,
    registrar_usuario,
    obter_status_usuario,
)
from enviar_whatsapp import enviar_whatsapp as enviar_mensagem_whatsapp
from enviar_email import enviar_email

app = FastAPI()

openai.api_key = os.getenv("OPENAI_API_KEY")

# Mensagens padronizadas com tom comercial e adaptável
mensagem_boas_vindas = (
    "Antes da gente começar, me conta uma coisa: qual o seu nome e e-mail? 👇\n\n"
    "Preciso disso pra te liberar o acesso gratuito aqui no Meu Conselheiro Financeiro. A partir daqui, esquece robozinho engessado. "
    "Você vai ter uma conversa que mistura dinheiro, propósito e vida real. Sem enrolação. 💼🔥"
)

mensagem_aviso_limite = (
    "Faltam só {interacoes_restantes} interações gratuitas... e eu ainda tenho muito pra te mostrar. 🤏⏳\n\n"
    "Se você quiser seguir nessa jornada com liberdade total, clique aqui pra destravar tudo:\n\n"
    "[INSIRA O LINK DO PLANO PREMIUM AQUI]\n\n"
    "A escolha é sua. Mas se fosse comigo… eu já estaria lá dentro. 😎"
)

mensagem_limite_atingido = (
    "Seu acesso gratuito terminou. Mas ó… isso aqui é só o começo. 💥\n\n"
    "Quer continuar recebendo respostas personalizadas, alinhadas com sua vida financeira, familiar e espiritual? Então vem comigo:\n\n"
    "[INSIRA O LINK DO PLANO PREMIUM AQUI]\n\n"
    "Liberdade não se improvisa. Ela se constrói. Vamos nessa?"
)

@app.post("/webhook")
async def receber_mensagem(request: Request):
    form = await request.form()

    numero = form.get('From', '').replace('whatsapp:', '').strip()
    texto = form.get('Body', '').strip()

    nome = ""
    email = ""

    status, interacoes_restantes = obter_status_usuario(numero)

    if status == "bloqueado":
        enviar_mensagem_whatsapp(mensagem_limite_atingido, numero)
        return {"status": "bloqueado"}

    if not verificar_usuario(numero):
        if "@" in texto and "." in texto:
            nome = "Usuário"
            email = texto
            registrar_usuario(nome, numero, email)
            saudacao = gerar_resposta("Dê boas-vindas ao usuário com tom motivador e elegante.")
            enviar_mensagem_whatsapp(saudacao, numero)
        else:
            enviar_mensagem_whatsapp(mensagem_boas_vindas, numero)
        return {"status": "aguardando_dados"}

    if status == "gratuito":
        if interacoes_restantes == 0:
            enviar_mensagem_whatsapp(mensagem_limite_atingido, numero)
            return {"status": "limite_atingido"}
        elif interacoes_restantes == 3:
            enviar_mensagem_whatsapp(mensagem_aviso_limite.format(interacoes_restantes=interacoes_restantes), numero)

    resposta = gerar_resposta(texto)
    enviar_mensagem_whatsapp(resposta, numero)

    if status == "gratuito":
        atualizar_interacoes(numero)

    return {"status": "mensagem_enviada"}

def gerar_resposta(prompt_usuario):
    try:
        agora = datetime.datetime.now(pytz.timezone("America/Sao_Paulo"))
        data_hora_formatada = agora.strftime("%d/%m/%Y %H:%M")

        mensagens = [
            {
                "role": "system",
                "content": (
                    "Você é o Meu Conselheiro Financeiro, uma inteligência artificial criada para ajudar o usuário "
                    "a organizar sua vida financeira, familiar, profissional e espiritual. Sua linguagem é clara, elegante, direta e "
                    "amigável. Você é provocativo quando necessário, e não tem medo de dizer verdades. Você estimula a clareza de vida. "
                    "Hoje é " + data_hora_formatada + "."
                ),
            },
            {
                "role": "user",
                "content": prompt_usuario,
            },
        ]

        resposta = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=mensagens,
            temperature=0.7,
            max_tokens=1000,
        )

        return resposta.choices[0].message["content"].strip()

    except Exception as e:
        return f"Erro ao gerar resposta: {str(e)}"
