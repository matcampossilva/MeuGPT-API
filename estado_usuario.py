import json
import os

ESTADO_DIR = "estados"

def get_path(numero):
    if not os.path.exists(ESTADO_DIR):
        os.makedirs(ESTADO_DIR)
    return os.path.join(ESTADO_DIR, f"{numero}.json")

def salvar_estado(numero, dados):
    caminho = get_path(numero)
    with open(caminho, "w") as f:
        json.dump(dados, f)

def carregar_estado(numero):
    caminho = get_path(numero)
    if not os.path.exists(caminho):
        return {}
    with open(caminho, "r") as f:
        return json.load(f)

def resetar_estado(numero):
    caminho = get_path(numero)
    if os.path.exists(caminho):
        os.remove(caminho)
