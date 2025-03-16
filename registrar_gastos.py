import requests
from configuracoes import GOOGLE_SHEETS_URL

def registrar_gasto(descricao, categoria, valor, forma_pagamento):
    dados = {
        'descricao': descricao,
        'categoria': categoria,
        'valor': valor,
        'forma_pagamento': forma_pagamento
    }

    try:
        resposta = requests.post(GOOGLE_SHEETS_URL, json=dados)
        if resposta.status_code == 200:
            print("✅ Gasto registrado no Google Sheets.")
        else:
            print("❌ Erro na planilha:", resposta.text)
    except Exception as e:
        print(f"❌ Falha na conexão: {e}")

if __name__ == "__main__":
    registrar_gasto("Teste Google Sheets Matheus", "Automação", 25.50, "Cartão de Crédito")
