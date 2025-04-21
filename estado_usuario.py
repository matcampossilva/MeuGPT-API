import json
import os

def salvar_estado(user_number, estado):
    caminho = f"estados/{user_number}.json"
    with open(caminho, "w", encoding="utf-8") as file:
        json.dump(estado, file)

def carregar_estado(user_number):
    caminho = f"estados/{user_number}.json"
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as file:
            return json.load(file)
    return {}