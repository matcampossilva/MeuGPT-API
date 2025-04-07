import os
import gspread
from collections import defaultdict
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv()
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_SHEETS_KEY_FILE = os.getenv("GOOGLE_SHEETS_KEY_FILE")

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_KEY_FILE, scope)
gs = gspread.authorize(creds)

# === RANKING GERAL ===
def get_ranking_geral(top=5):
    try:
        aba = gs.open_by_key(GOOGLE_SHEET_ID).worksheet("Engajamento")
        dados = aba.get_all_records()
        pontuacoes = defaultdict(int)

        for linha in dados:
            numero = linha["NÚMERO"]
            try:
                pontuacoes[numero] += int(linha.get("PONTOS", 1))
            except:
                pontuacoes[numero] += 1

        ranking = sorted(pontuacoes.items(), key=lambda x: x[1], reverse=True)[:top]

        texto = ["🏆 *Ranking dos mais engajados:*\n"]
        emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]

        for i, (numero, pontos) in enumerate(ranking):
            num_mask = numero[:5] + "****" + numero[-2:]
            texto.append(f"{emojis[i]} {num_mask} – {pontos} estrela{'s' if pontos > 1 else ''}")

        texto.append("\nSeja honesto: você quer estar aqui em cima, né?")
        return "\n".join(texto)

    except Exception as e:
        return f"Erro ao gerar ranking: {e}"

# === RANKING INDIVIDUAL ===
def get_ranking_usuario(numero):
    try:
        aba = gs.open_by_key(GOOGLE_SHEET_ID).worksheet("Engajamento")
        dados = aba.get_all_records()
        total = 0

        for linha in dados:
            if linha["NÚMERO"] == numero:
                try:
                    total += int(linha.get("PONTOS", 1))
                except:
                    total += 1

        if total == 0:
            return "🤷‍♂️ Você ainda não tem nenhuma estrela registrada. Vamo reagir aí."
        elif total < 5:
            return f"⭐ Você já tem {total} estrela{'s' if total > 1 else ''}. Tá começando bem."
        else:
            return f"🌟 Você acumulou {total} estrelas até agora. Tá caminhando pra virar referência."  

    except Exception as e:
        return f"Erro ao consultar suas estrelas: {e}"

# Teste manual
if __name__ == "__main__":
    print(get_ranking_geral())
    print(get_ranking_usuario("+5562999999999"))