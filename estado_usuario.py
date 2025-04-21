import json
import os

def salvar_estado(user_number, estado):
    caminho = f"estados/{user_number}.json"
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as file:
        json.dump(estado, file)

def carregar_estado(user_number):
    caminho = f"estados/{user_number}.json"
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as file:
            return json.load(file)
    return {}

def resetar_estado(user_number):
    caminho = f"estados/{user_number}.json"
    if os.path.exists(caminho):
        os.remove(caminho)
    
def resposta_enviada_recentemente(user_number, resposta_atual):
    estado = carregar_estado(user_number)
    ultima_resposta = estado.get("ultima_resposta", "")
    return ultima_resposta.strip() == resposta_atual.strip()

def salvar_ultima_resposta(user_number, resposta_atual):
    estado = carregar_estado(user_number)
    estado["ultima_resposta"] = resposta_atual
    salvar_estado(user_number, estado)
