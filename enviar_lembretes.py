import os
import pytz
from datetime import datetime, timedelta
from collections import defaultdict
from dotenv import load_dotenv
from planilhas import gs
from enviar_whatsapp import enviar_whatsapp

load_dotenv()

GOOGLE_SHEET_GASTOS_ID = os.getenv("GOOGLE_SHEET_GASTOS_ID")
fuso = pytz.timezone("America/Sao_Paulo")

def enviar_lembretes():
    aba_fixos = gs.open_by_key(GOOGLE_SHEET_GASTOS_ID).worksheet("Gastos Fixos")
    gastos_fixos = aba_fixos.get_all_records()

    hoje = datetime.now(fuso).date()
    lembretes_por_usuario = defaultdict(list)

    for gasto in gastos_fixos:
        dia_pagamento = int(gasto["DIA_DO_MÊS"])
        numero_usuario = gasto["NÚMERO"]
        descricao = gasto["DESCRIÇÃO"]
        valor_str = str(gasto["VALOR"]).replace("R$", "").replace(".", "").replace(",", ".").strip()
        try:
            valor_float = float(valor_str)
        except ValueError:
            print(f"[Erro Lembrete] Valor inválido para {descricao} do usuário {numero_usuario}: {gasto['VALOR']}")
            continue # Pula este gasto se o valor for inválido

        # Calcula a data do lembrete (um dia antes do pagamento)
        data_pagamento = hoje.replace(day=dia_pagamento)
        data_lembrete = data_pagamento - timedelta(days=1)

        # Verifica se hoje é dia de lembrete ou o próprio dia de pagamento
        if hoje == data_lembrete or hoje == data_pagamento:
            lembretes_por_usuario[numero_usuario].append({
                "descricao": descricao,
                "valor": valor_float, # Usa a variável corrigida
                "data_pagamento": data_pagamento.strftime("%d/%m/%Y")
            })

    # Enviar os lembretes via WhatsApp
    for numero, lembretes in lembretes_por_usuario.items():
        mensagem = "⏰ *Lembrete de pagamento das suas despesas fixas:*\n\n"
        for lembrete in lembretes:
            mensagem += (
                f"• {lembrete['descricao']} — R${lembrete['valor']:.2f} "
                f"(Vencimento: {lembrete['data_pagamento']})\n"
            )
        mensagem += "\nNão esqueça de pagar para evitar atrasos! 😉"
        enviar_whatsapp(numero, mensagem)

if __name__ == "__main__":
    enviar_lembretes()