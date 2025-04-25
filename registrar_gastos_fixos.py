import datetime
import pytz
from planilhas import get_gastos_diarios, gs
from dotenv import load_dotenv
import os
load_dotenv()

GOOGLE_SHEET_GASTOS_ID = os.getenv("GOOGLE_SHEET_GASTOS_ID")

def registrar_gastos_fixos():
    aba_fixos = gs.open_by_key(GOOGLE_SHEET_GASTOS_ID).worksheet("Gastos Fixos")
    gastos_fixos = aba_fixos.get_all_records()

    aba_diarios = get_gastos_diarios()

    hoje = datetime.datetime.now(pytz.timezone("America/Sao_Paulo"))
    dia_atual = hoje.day
    mes_atual = hoje.month
    ano_atual = hoje.year

    for gasto in gastos_fixos:
        if gasto["DIA_DO_MÊS"] == dia_atual:
            aba_diarios.append_row([
                "",  # Nome vazio ou preencha automaticamente se desejar
                gasto["NÚMERO"],
                gasto["DESCRIÇÃO"],
                gasto["CATEGORIA"],
                gasto["VALOR"],
                gasto["FORMA_PGTO"],
                hoje.strftime("%d/%m/%Y"),
                hoje.strftime("%d/%m/%Y %H:%M:%S"),
                f"fixo-{mes_atual}-{ano_atual}-{gasto['DESCRIÇÃO']}-{gasto['VALOR']}"
            ])
    print("Gastos fixos registrados com sucesso!")

if __name__ == "__main__":
    registrar_gastos_fixos()

def salvar_gastos_fixos(numero_usuario, gastos_fixos):
    aba_fixos = gs.open_by_key(GOOGLE_SHEET_GASTOS_ID).worksheet("Gastos Fixos")
    hoje = datetime.datetime.now(pytz.timezone("America/Sao_Paulo"))
    dia_atual = hoje.day

    for gasto in gastos_fixos:
        aba_fixos.append_row([
            numero_usuario,
            gasto["descricao"],
            gasto["valor"],
            gasto["forma_pagamento"],
            gasto.get("categoria", "A DEFINIR"),
            dia_atual
        ])
    print("Novos gastos fixos salvos com sucesso.")