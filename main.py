from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from configuracoes import GOOGLE_SHEETS_URL
from enviar_whatsapp import enviar_whatsapp
from enviar_email import enviar_email
import requests

app = FastAPI()

class Gasto(BaseModel):
    usuario: str
    descricao: str
    categoria: str
    valor: float
    forma_pagamento: str

@app.post("/registrar_gasto")
def registrar_gasto(gasto: Gasto):
    dados = {
        'usuario': gasto.usuario,
        'descricao': gasto.descricao,
        'categoria': gasto.categoria,
        'valor': gasto.valor,
        'forma_pagamento': gasto.forma_pagamento
    }

    try:
        resposta = requests.post(GOOGLE_SHEETS_URL, json=dados)
        if resposta.status_code == 200:
            return {"status": "✅ Gasto registrado com sucesso."}
        else:
            raise HTTPException(status_code=400, detail="Erro ao registrar gasto no Sheets.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

