from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from registrar_gastos import registrar_gasto
from enviar_whatsapp import enviar_whatsapp
from enviar_email import enviar_email

app = FastAPI()

class Gasto(BaseModel):
    usuario: str
    descricao: str
    categoria: str
    valor: float
    forma_pagamento: str

class Mensagem(BaseModel):
    mensagem: str
    numero: str

class Email(BaseModel):
    destinatario: str
    assunto: str
    mensagem: str

@app.post("/registrar-gasto")
async def registrar_gasto_api(gasto: dict):
    try:
        registrar_gasto(
            gasto["descricao"], 
            gasto["categoria"], 
            gasto["valor"], 
            gasto["forma_pagamento"]
        )
        return {"status": "✅ Gasto registrado com sucesso!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/enviar-whatsapp")
async def enviar_whatsapp_api(dados: dict):
    try:
        from enviar_whatsapp import enviar_whatsapp
        enviar_whatsapp(dados["mensagem"], dados["numero"])
        return {"status": "Mensagem enviada com sucesso!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/enviar-email")
async def enviar_email_api(email: Email):
    try:
        from enviar_email import enviar_email
        enviar_email(email.destinatario, email.assunto, email.mensagem)
        return {"status": "Email enviado com sucesso!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
