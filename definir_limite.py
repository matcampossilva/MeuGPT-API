import random
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv
from enviar_whatsapp import enviar_whatsapp
from planilhas import get_gastos_diarios, get_limites

load_dotenv()

# === BUSCA LIMITES DEFINIDOS PELO USUÁRIO ===
def buscar_limites_do_usuario(numero_usuario):
    try:
        aba = get_limites()
        linhas = aba.get_all_records()
        limites = defaultdict(dict)

        for linha in linhas:
            if linha["NÚMERO"].strip() != numero_usuario:
                continue
            categoria = linha["CATEGORIA"].strip()
            limite_dia = linha.get("LIMITE_DIÁRIO", "")
            if isinstance(limite_dia, str):
                limite_dia = limite_dia.replace("R$", "").replace(",", ".").strip()
            try:
                limites[categoria] = float(limite_dia)
            except:
                continue

        return limites
    except Exception as e:
        print(f"Erro ao buscar limites: {e}")
        return {}

# === FRASES PERSONALIZADAS ===
def gerar_alerta_personalizado(categoria, total, limite, faixa):
    frases = {
        "50": [
            f"👀 Já foi 50% do seu limite em *{categoria}*. Cautela não mata, mas a fatura talvez mate."
        ],
        "70": [
            f"⚠️ Você já queimou 70% do que planejou pra *{categoria}*. Ainda é reversível, mas só se você largar o app do iFood agora. 🍔"
        ],
        "90": [
            f"🚧 Tá chegando no fim da linha: 90% do limite de *{categoria}* usado. Tá vivendo como se não houvesse amanhã, né? 😵‍💫"
        ],
        "100": [
            f"🔥 Limite de *{categoria}* estourado! Hora de esconder o cartão e fingir que o problema é o preço do arroz. 🍚💸"
        ],
        ">100": [
            f"😈 Só se vive uma vez, né? Compra mesmo. Ass: Satanás. Você já passou dos 100% do limite de *{categoria}*."
        ]
    }
    return random.choice(frases[faixa])

# === ALERTAS PERSONALIZADOS ===
def verificar_alertas():
    aba = get_gastos_diarios()
    dados = aba.get_all_records()
    hoje = datetime.now().date()

    usuarios_gastos = defaultdict(lambda: defaultdict(float))

    for linha in dados:
        numero = linha["NÚMERO"]
        try:
            data_gasto = datetime.strptime(linha["DATA DO GASTO"], "%d/%m/%Y").date()
            if data_gasto != hoje:
                continue
        except:
            continue

        valor_str = str(linha["VALOR (R$)"]).replace("R$", "").replace(",", ".").strip()
        try:
            valor = float(valor_str)
        except:
            valor = 0.0

        categoria = linha["CATEGORIA"] or "A DEFINIR"
        usuarios_gastos[numero][categoria] += valor

    for numero, categorias in usuarios_gastos.items():
        limites_user = buscar_limites_do_usuario(numero)
        for cat, total in categorias.items():
            limite_cat = limites_user.get(cat)
            if not limite_cat:
                continue

            percentual = (total / limite_cat) * 100
            faixa = None
            if 45 < percentual <= 55:
                faixa = "50"
            elif 65 < percentual <= 75:
                faixa = "70"
            elif 85 < percentual <= 95:
                faixa = "90"
            elif 95 < percentual <= 105:
                faixa = "100"
            elif percentual > 105:
                faixa = ">100"

            if faixa:
                mensagem = gerar_alerta_personalizado(cat, total, limite_cat, faixa)
                enviar_whatsapp(numero, mensagem)

# === NOVA FUNÇÃO PARA DEFINIR LIMITE PERSONALIZADO ===
def salvar_limite_usuario(numero, categoria, valor, tipo="mensal"):
    aba = get_limites()
    linhas = aba.get_all_records()
    linha_existente = None

    for i, linha in enumerate(linhas, start=2):  # começa na linha 2 por causa do cabeçalho
        if linha["NÚMERO"].strip() == numero and linha["CATEGORIA"].strip().lower() == categoria.lower():
            linha_existente = i
            break

    coluna = {
        "diario": 3,
        "semanal": 4,
        "mensal": 5
    }.get(tipo.lower(), 5)

    if linha_existente:
        aba.update_cell(linha_existente, coluna, valor)
    else:
        nova_linha = [numero, categoria, "", "", ""]
        nova_linha[coluna - 1] = valor
        aba.append_row(nova_linha)

# === EXECUÇÃO DIRETA ===
if __name__ == "__main__":
    verificar_alertas()
