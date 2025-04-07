import requests
import datetime

# === CONSULTA INDICADORES ECONÔMICOS ===
def get_indicadores():
    hoje = datetime.date.today().isoformat()
    indicadores = {}

    try:
        # Selic diária (valor mais recente)
        r_selic = requests.get("https://api.bcb.gov.br/dados/serie/bcdata.sgs.11/dados/ultimos/1?formato=json")
        indicadores["selic"] = float(r_selic.json()[0]["valor"])
    except:
        indicadores["selic"] = None

    try:
        # CDI (não oficial, pega do mesmo endpoint para fins de simulação)
        r_cdi = requests.get("https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados/ultimos/1?formato=json")
        indicadores["cdi"] = float(r_cdi.json()[0]["valor"])
    except:
        indicadores["cdi"] = None

    try:
        # IPCA mensal mais recente
        r_ipca = requests.get("https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados/ultimos/1?formato=json")
        indicadores["ipca"] = float(r_ipca.json()[0]["valor"])
    except:
        indicadores["ipca"] = None

    try:
        # Ibovespa (via fonte alternativa, dado simulado por enquanto)
        r_ibov = requests.get("https://brapi.dev/api/quote/^BVSP")
        indicadores["ibovespa"] = r_ibov.json()["results"][0]["regularMarketPrice"]
    except:
        indicadores["ibovespa"] = None

    return indicadores

# === EXEMPLO DE USO ===
if __name__ == "__main__":
    dados = get_indicadores()
    for nome, valor in dados.items():
        print(f"{nome.upper()}: {valor if valor is not None else 'indisponível'}")