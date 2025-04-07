import os
import gspread
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv()
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_SHEETS_KEY_FILE = os.getenv("GOOGLE_SHEETS_KEY_FILE")

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_KEY_FILE, scope)
gs = gspread.authorize(creds)

fuso = pytz.timezone("America/Sao_Paulo")
hoje = datetime.now(fuso).date()

# === CHECA SE USUÁRIO JÁ GANHOU ESTRELA POR MOTIVO HOJE ===
def ja_ganhou_hoje(numero, motivo):
    try:
        aba = gs.open_by_key(GOOGLE_SHEET_ID).worksheet("Engajamento")
        registros = aba.get_all_records()
        for linha in registros:
            if linha["NÚMERO"] == numero and linha["MOTIVO"] == motivo:
                data = datetime.strptime(linha["DATA"], "%d/%m/%Y %H:%M:%S").date()
                if data == hoje:
                    return True
        return False
    except:
        return False

# === VERIFICA PADRÕES DE ENGAJAMENTO ===
def avaliar_engajamento(numero, texto):
    texto = texto.lower()
    mensagens = []

    # 1. Registro de gasto antes das 18h
    agora = datetime.now(fuso)
    if any(p in texto for p in ["r$", ",00", ".00", "gastei", "comprei", "pix", "- débito", "- crédito"]) and agora.hour < 18:
        motivo = "Registro de gasto antes das 18h"
        if not ja_ganhou_hoje(numero, motivo):
            registrar_estrela(numero, motivo)
            mensagens.append("⭐️ Você registrou seus gastos antes das 18h. Isso é disciplina de quem vai longe. Parabéns!")

    # 2. Registro de gasto zero (também conta)
    if any(p in texto for p in ["gasto zero", "sem gasto", "não gastei"]):
        motivo = "Registro de dia sem gastos"
        if not ja_ganhou_hoje(numero, motivo):
            registrar_estrela(numero, motivo)
            mensagens.append("🧘‍♂️ Você anotou que não teve gastos hoje. Isso é autocontrole e constância. Estrela merecida.")

    # 3. Esmola ou caridade
    if any(p in texto for p in ["esmola", "mendigo", "doação", "caridade", "ajudei alguém"]):
        motivo = "Fez ato de caridade"
        if not ja_ganhou_hoje(numero, motivo):
            registrar_estrela(numero, motivo)
            mensagens.append("🙏 Você fez uma doação ou ajudou alguém. Isso vale mais que planilha. Deus vê. Eu também. ⭐️")

    # 4. Relatou aumento de renda
    if any(p in texto for p in ["ganhei mais", "novo cliente", "freela", "freelancer", "extra", "aumentei a renda"]):
        motivo = "Buscou ou conquistou aumento de renda"
        if not ja_ganhou_hoje(numero, motivo):
            registrar_estrela(numero, motivo)
            mensagens.append("💪 Você aumentou sua renda. Isso sim é virar o jogo. Estrela conquistada com suor.")

    # 5. Aporte mensal detectado
    if any(p in texto for p in ["aporte", "investi", "guardei", "poupança"]):
        motivo = "Cumpriu o aporte mensal"
        if not ja_ganhou_hoje(numero, motivo):
            registrar_estrela(numero, motivo)
            mensagens.append("📈 Aporte registrado. Você honrou o compromisso consigo mesmo. Estrela garantida.")

    return "\n\n".join(mensagens) if mensagens else None

# === EXEMPLO ===
if __name__ == "__main__":
    print(avaliar_engajamento("+5562999022021", "Hoje não gastei nada, só ajudei um mendigo com 10 reais."))