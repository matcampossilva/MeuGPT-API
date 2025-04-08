from planilhas import get_gastos_diarios
from datetime import datetime, timedelta
import pytz
import re

gatilhos_emocionais = {
    "ansiedade": ["ansioso", "tô ansioso", "angústia", "aflição", "nervoso", "estressado", "estresse"],
    "tristeza": ["triste", "pra baixo", "deprimido", "chateado", "decepcionado"],
    "cansaço": ["cansado", "exausto", "sem forças", "sobrecarregado"],
    "solidão": ["sozinho", "solitário", "ninguém me entende"],
    "impulsividade": ["não resisti", "comprei sem pensar", "me empolguei", "mereço", "só dessa vez"],
    "culpa": ["me arrependi", "gastei à toa", "não devia", "fui fraco", "sem controle"]
}

def detectar_emocao(mensagem):
    mensagem = mensagem.lower()
    for emo, palavras in gatilhos_emocionais.items():
        for termo in palavras:
            if termo in mensagem:
                return emo
    return None

def aumento_pos_emocao(numero_usuario, emocao, data_mensagem):
    aba = get_gastos_diarios()
    registros = aba.get_all_values()[1:]

    fuso = pytz.timezone("America/Sao_Paulo")
    data_base = datetime.strptime(data_mensagem, "%Y-%m-%d %H:%M:%S")
    dias_limite = data_base + timedelta(days=2)

    categoria_alvo = "Alimentação"
    total = 0

    for linha in registros:
        if linha[1].strip() != numero_usuario:
            continue
        try:
            data_gasto = datetime.strptime(linha[6], "%d/%m/%Y")
            if data_base <= data_gasto <= dias_limite:
                if linha[3] == categoria_alvo:
                    total += float(linha[4])
        except:
            continue

    if total >= 100:  # Limite que define "aumento"
        return f"Notei que após expressar sinais de *{emocao}*, seus gastos com {categoria_alvo} aumentaram para R$ {total:.2f}. Pode ser só coincidência… ou um padrão que vale a pena refletir."
    return None