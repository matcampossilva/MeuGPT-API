import gspread
from datetime import datetime
from dotenv import load_dotenv
import os
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv()
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_SHEETS_KEY_FILE = os.getenv("GOOGLE_SHEETS_KEY_FILE")

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_KEY_FILE, scope)
gs = gspread.authorize(creds)

# === VERIFICA E AVISA UPGRADE ===
def verificar_upgrade_automatico(numero):
    try:
        planilha = gs.open_by_key(GOOGLE_SHEET_ID)
        aba_p = planilha.worksheet("Pagantes").col_values(2)
        aba_g = planilha.worksheet("Gratuitos")
        linha_usuario = aba_g.col_values(2)

        if numero in aba_p:
            if numero in linha_usuario:
                linha = linha_usuario.index(numero) + 1
                aba_g.update_cell(linha, 6, "99")  # Zera contagem para garantir desbloqueio
                return True
        return False
    except Exception as e:
        print(f"Erro ao verificar upgrade: {e}")
        return False

# Teste
if __name__ == "__main__":
    print(verificar_upgrade_automatico("+5562999999999"))