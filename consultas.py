# -*- coding: utf-8 -*-
"""
Funções auxiliares para consultas (ex: status de limites).
"""
import logging
import datetime
import pytz
# Assumindo que existe um módulo para operações com Google Sheets
# Se o nome for diferente, precisará ser ajustado.
from google_sheets_operations import ler_limites_usuario, ler_gastos_usuario_periodo

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

fuso_horario = pytz.timezone("America/Sao_Paulo")

def formatar_valor_brl(valor):
    """Formata um valor float para o padrão BRL (R$ 1.234,56)."""
    if valor is None:
        return "R$ 0,00"
    return f"R${valor:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

def consultar_status_limites(numero_usuario):
    """Consulta os limites definidos e os gastos do mês atual para calcular o status.

    Args:
        numero_usuario (str): Número do usuário formatado.

    Returns:
        str: Mensagem formatada com o status dos limites ou mensagem de erro/aviso.
    """
    try:
        logging.info(f"Consultando status dos limites para {numero_usuario}.")
        limites = ler_limites_usuario(numero_usuario)
        if not limites:
            return "Você ainda não definiu nenhum limite de gasto. Use o comando para definir limites primeiro."

        # Define o período como o mês atual
        hoje = datetime.datetime.now(fuso_horario)
        primeiro_dia_mes = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Não precisamos do último dia, a função ler_gastos_usuario_periodo deve lidar com isso
        # (Assumindo que ela filtra por mês/ano ou data >= primeiro_dia_mes)
        
        # Assumindo que ler_gastos_usuario_periodo retorna uma lista de dicionários
        # com pelo menos as chaves 'Categoria' e 'Valor'
        gastos_mes = ler_gastos_usuario_periodo(numero_usuario, primeiro_dia_mes)

        gastos_por_categoria = {}
        if gastos_mes:
            for gasto in gastos_mes:
                categoria = gasto.get("Categoria")
                valor = gasto.get("Valor")
                if categoria and valor is not None:
                    gastos_por_categoria[categoria] = gastos_por_categoria.get(categoria, 0) + valor
        
        logging.info(f"Limites encontrados: {limites}")
        logging.info(f"Gastos agregados do mês: {gastos_por_categoria}")

        resposta = [f"📊 Status dos seus limites para *{hoje.strftime('%B/%Y')}*:"]
        categorias_com_limite = set(limites.keys())
        categorias_com_gasto = set(gastos_por_categoria.keys())
        todas_categorias = sorted(list(categorias_com_limite.union(categorias_com_gasto)))

        for categoria in todas_categorias:
            limite = limites.get(categoria)
            gasto = gastos_por_categoria.get(categoria, 0)
            
            if limite is not None and limite > 0:
                percentual = (gasto / limite) * 100 if limite > 0 else 0
                status_emoji = "🟢" # Abaixo de 75%
                if percentual >= 100:
                    status_emoji = "🔴"
                elif percentual >= 75:
                    status_emoji = "🟠"
                
                resposta.append(f"{status_emoji} *{categoria}:* {formatar_valor_brl(gasto)} / {formatar_valor_brl(limite)} ({percentual:.0f}%)")
            elif limite is not None: # Limite definido mas é zero ou negativo (estranho, mas mostra)
                 resposta.append(f"⚪ *{categoria}:* {formatar_valor_brl(gasto)} / {formatar_valor_brl(limite)} (Limite inválido)")
            else: # Categoria com gasto mas sem limite definido
                resposta.append(f"❔ *{categoria}:* {formatar_valor_brl(gasto)} (Sem limite definido)")

        if len(resposta) == 1: # Apenas o cabeçalho
             return "Não encontrei dados suficientes para mostrar o status dos limites." # Caso algo dê muito errado

        return "\n".join(resposta)

    except Exception as e:
        logging.error(f"Erro ao consultar status dos limites para {numero_usuario}: {e}", exc_info=True)
        return f"⚠️ Desculpe, tive um problema ao consultar o status dos seus limites. Detalhe: {e}"

# Exemplo de uso (para teste local, se necessário)
if __name__ == '__main__':
    # Mock das funções do Google Sheets para teste local
    def ler_limites_usuario(num):
        if num == "+5511999998888":
            return {"Lazer": 1500.0, "Alimentação": 2000.0, "Frédéric": 1000.0}
        return {}
    
    def ler_gastos_usuario_periodo(num, inicio):
        if num == "+5511999998888":
            # Simula gastos de Maio
            if inicio.month == 5:
                 return [
                     {"Categoria": "Alimentação", "Valor": 120.0},
                     {"Categoria": "Lazer", "Valor": 250.0},
                     {"Categoria": "Lazer", "Valor": 476.0},
                     {"Categoria": "Moradia", "Valor": 250.0},
                     {"Categoria": "Frédéric", "Valor": 200.0},
                     {"Categoria": "Frédéric", "Valor": 476.0},
                 ]
        return []

    # Substitui as funções reais pelas mocks
    google_sheets_operations = type('obj', (object,), {
        'ler_limites_usuario': ler_limites_usuario,
        'ler_gastos_usuario_periodo': ler_gastos_usuario_periodo
    })()
    
    # Testa a função principal
    numero_teste = "+5511999998888"
    status = consultar_status_limites(numero_teste)
    print(status)

    numero_sem_limite = "+5511999997777"
    status_sem_limite = consultar_status_limites(numero_sem_limite)
    print(status_sem_limite)