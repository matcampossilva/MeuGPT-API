import os
import openai
import requests
from fastapi import FastAPI, Request
from twilio.rest import Client
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pytz
import datetime
import re
import random
from gastos import registrar_gasto, categorizar, corrigir_gasto, atualizar_categoria, parsear_gastos_em_lote
from estado_usuario import salvar_estado, carregar_estado, resetar_estado
from gerar_resumo import gerar_resumo
from resgatar_contexto import buscar_conhecimento_relevante
from upgrade import verificar_upgrade_automatico
from armazenar_mensagem import armazenar_mensagem
from definir_limite import salvar_limite_usuario
from memoria_usuario import resumo_do_mes, verificar_limites
from emocional import detectar_emocao, aumento_pos_emocao
from planilhas import get_pagantes, get_gratuitos
from engajamento import avaliar_engajamento
from indicadores import get_indicadores

load_dotenv()
app = FastAPI()

openai.api_key = os.getenv("OPENAI_API_KEY")
client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
MESSAGING_SERVICE_SID = os.getenv("TWILIO_MESSAGING_SERVICE_SID")

# Função de leitura do prompt.txt para contexto inicial
with open("prompt.txt", "r") as f:
    prompt_base = f.read().strip()

# === PLANILHAS ===
def get_user_status(user_number):
    try:
        pagantes = get_pagantes().col_values(2)
        gratuitos = get_gratuitos().col_values(2)
        if user_number in pagantes:
            return "Pagantes"
        elif user_number in gratuitos:
            return "Gratuitos"
        else:
            return "Novo"
    except Exception as e:
        print(f"Erro ao verificar status do usuário: {e}")
        return "Novo"

def get_user_sheet(user_number):
    status = get_user_status(user_number)
    if status == "Pagantes":
        return get_pagantes()
    elif status == "Gratuitos":
        return get_gratuitos()
    else:
        now = datetime.datetime.now(pytz.timezone("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S")
        aba = get_gratuitos()
        aba.append_row(["", user_number, "", now, 0, 0])
        return aba

def nome_valido(text):
    if not text:
        return False
    partes = text.strip().split()
    if len(partes) < 2:
        return False
    if any(char in text for char in "@!?0123456789#%$*"):
        return False
    return True

def format_number(raw_number):
    return raw_number.replace("whatsapp:", "").strip()

def extract_email(text):
    match = re.search(r'[\w\.-]+@[\w\.-]+', text)
    return match.group(0) if match else None

def count_tokens(text):
    return len(text.split())

def send_message(to, body):
    if not body or not body.strip():
        print(f"[ERRO] Tentativa de enviar mensagem vazia para {to}. Ignorado.")
        return

    client.messages.create(
        body=body,
        messaging_service_sid=MESSAGING_SERVICE_SID,
        to=f"whatsapp:{to}"
    )

def get_interactions(sheet, row):
    try:
        val = sheet.cell(row, 6).value
        return int(val) if val else 0
    except:
        return 0

def increment_interactions(sheet, row):
    count = get_interactions(sheet, row) + 1
    sheet.update_cell(row, 6, count)
    return count

def passou_limite(sheet, row):
    status = sheet.title
    if status != "Gratuitos":
        return False
    return get_interactions(sheet, row) >= 10

def is_boas_vindas(text):
    saudacoes = ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite"]
    text = text.lower()
    return any(sauda in text for sauda in saudacoes)

def detectar_gastos(texto):
    linhas = texto.strip().split("\n")
    padrao = r"^(.*?)\s*[-–—]\s*(\d+(?:[.,]\d{2})?)\s*[-–—]\s*(crédito|débito|pix|boleto)(?:\s*[-–—]\s*(.*))?$"
    return any(re.match(padrao, linha.strip(), re.IGNORECASE) for linha in linhas)

def detectar_gastos_com_categoria_direta(texto):
    linhas = texto.strip().split("\n")
    # Normaliza hífens e travessões
    texto = texto.replace("–", "-").replace("—", "-").replace("−", "-")
    linhas = texto.split("\n")

    for linha in linhas:
        if re.search(r"[-–—]", linha) and re.search(r"\d{1,3}(?:[.,]\d{2})", linha) and any(p in linha.lower() for p in ["crédito", "débito", "pix", "boleto"]):
            return True
    return False

def extrair_gastos(texto):
    gastos, erros = parsear_gastos_em_lote(texto)

    if erros:
        print("[ERRO PARSE]:", erros)

    return gastos

def quer_corrigir_gasto(msg):
    termos = ["corrigir", "corrigir gasto", "consertar", "ajustar", "tá errado", "trocar valor"]
    return any(t in msg.lower() for t in termos) and detectar_gastos(msg)

def precisa_direcionamento(msg):
    frases_vagas = [
        "me ajuda", "preciso de ajuda", "me orienta", "o que eu faço",
        "não sei por onde começar", "como começar", "tô perdido", "me explica",
        "quero ajuda", "quero controlar", "quero começar", "começar a usar"
    ]
    msg = msg.lower()
    return any(frase in msg for frase in frases_vagas)

def quer_resumo_mensal(msg):
    msg = msg.lower()
    termos = [
        "quanto gastei", 
        "resumo do mês",
        "gastos do mês", 
        "como estão meus gastos",
        "meu resumo financeiro",
        "me mostra meus gastos",
        "meus gastos recentes",
        "gastando muito",
        "gastei demais"
    ]
    return any(t in msg for t in termos)

def quer_lista_comandos(texto):
    texto = texto.lower()
    termos = [
        "quais comandos", "comandos disponíveis", "o que você faz",
        "como usar", "me ajuda com comandos", "o que posso pedir",
        "me manda os comandos", "comando", "menu", "como funciona"
    ]
    return any(t in texto for t in termos)

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    incoming_msg = form["Body"].strip()
    from_number = format_number(form["From"])
    estado = carregar_estado(from_number)
    status_usuario = get_user_status(from_number)
    sheet_usuario = get_user_sheet(from_number)

    if quer_lista_comandos(incoming_msg):
        comandos = (
            "📋 *Comandos disponíveis:*\n"
            "/resumo – Ver seu resumo financeiro do dia\n"
            "/limites – Mostrar seus limites por categoria\n"
            "/relatorio – Análise completa dos seus gastos (em breve)\n"
            "/ranking – Ver o ranking dos usuários\n"
            "/minhas_estrelas – Ver suas estrelas acumuladas\n"
            "/ajuda – Mostrar esta lista de comandos"
        )
        send_message(from_number, comandos)
        return {"status": "comandos enviados"}
    
    linha_usuario = sheet_usuario.row_values(sheet_usuario.col_values(2).index(from_number) + 1)
    name = linha_usuario[0].strip() if len(linha_usuario) > 0 else ""

    if estado.get("ultimo_fluxo") == "registro_gastos_continuo" and detectar_gastos(incoming_msg):
        gastos_novos = extrair_gastos(incoming_msg)
        if not gastos_novos:
            send_message(
                from_number,
                "❌ Não consegui entender os gastos. Use este formato:\n\n"
                "📌 *Descrição – Valor – Forma de pagamento – Categoria (opcional)*\n\n"
                "*Exemplos válidos:*\n"
                "• Uber – 20,00 – crédito\n"
                "• Combustível – 300,00 – débito\n"
                "• Farmácia – 50,00 – pix – Saúde\n\n"
                "📌 Você pode mandar *vários gastos*, um por linha."
            )
            return {"status": "nenhum gasto extraído"}

        gastos_sem_categoria = [g for g in gastos_novos if not g.get("categoria")]
        gastos_completos = [g for g in gastos_novos if g.get("categoria")]

        fuso = pytz.timezone("America/Sao_Paulo")
        hoje = datetime.datetime.now(fuso).strftime("%d/%m/%Y")

        gastos_registrados = []
        for gasto in gastos_completos:
            descricao = gasto["descricao"].capitalize()
            valor = gasto["valor"]
            forma = gasto["forma_pagamento"]
            categoria = gasto["categoria"]

            registrar_gasto(
                nome_usuario=name,
                numero_usuario=from_number,
                descricao=descricao,
                valor=valor,
                forma_pagamento=forma,
                data_gasto=hoje,
                categoria_manual=categoria
            )

            valor_formatado = f"R${valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            gastos_registrados.append(f"{descricao} ({valor_formatado}): {categoria}")

        mensagem = ""
        if gastos_registrados:
            mensagem += "✅ *Gastos registrados:*\n" + "\n".join(gastos_registrados)

        if gastos_sem_categoria:
            estado_anterior = carregar_estado(from_number) or {}
            categorias_sugeridas = estado_anterior.get("categorias_sugeridas", {})

            for gasto in gastos_sem_categoria:
                descricao = gasto["descricao"].strip().lower()
                categoria_sug = categorizar(descricao) or "A DEFINIR"
                categorias_sugeridas[descricao] = categoria_sug

            estado_anterior.update({
                "ultimo_fluxo": "aguardando_categorias",
                "gastos_temp": gastos_sem_categoria,
                "categorias_sugeridas": categorias_sugeridas
            })

            salvar_estado(from_number, estado_anterior)

            lista_gastos = "\n".join(
                [f"{g['descricao'].capitalize()}, R${g['valor']}, pago com {g['forma_pagamento']}." for g in gastos_sem_categoria]
            )

            mensagem += (
                "\n\n"
                "Certo! Encontrei alguns gastos sem categoria:\n\n" +
                lista_gastos +
                "\n\nResponda agora indicando a categoria desejada com este formato:\n"
                "[descrição]: [categoria]\n\n"
                "*Exemplo:* supermercado: alimentação"
            )

        send_message(from_number, mensagem.strip())
        return {"status": "gastos processados via fluxo contínuo"}
    
    ultimo_fluxo = estado.get("ultimo_fluxo")
    
    if quer_resumo_mensal(incoming_msg):
        resumo = resumo_do_mes(from_number)
        limites = verificar_limites(from_number)
        send_message(from_number, resumo + "\n\n" + limites)
        return {"status": "resumo mensal enviado"}
    
    if any(t in incoming_msg.lower() for t in [
        "resumo do dia", "resumo de hoje", "quanto gastei hoje",
        "novo resumo", "resumo agora", "resumo atualizado",
        "quero o resumo", "meu resumo", "resumo aqui"
    ]):

        resumo = gerar_resumo(from_number, periodo="diario")
        send_message(from_number, resumo)
        return {"status": "resumo hoje enviado"}

    if any(t in incoming_msg.lower() for t in ["resumo de ontem", "quanto gastei ontem"]):
        ontem = datetime.datetime.now(pytz.timezone("America/Sao_Paulo")) - datetime.timedelta(days=1)
        resumo = gerar_resumo(from_number, periodo="custom", data_personalizada=ontem.date())
        send_message(from_number, resumo)
        return {"status": "resumo ontem enviado"}

    # === ⬇⬇ COMANDOS ESPECIAIS DO USUÁRIO (já funcionando no WhatsApp) ===
    if incoming_msg.startswith("/resumo"):
        resumo = gerar_resumo(from_number, periodo="diario")
        send_message(from_number, resumo)
        return {"status": "resumo enviado"}

    if incoming_msg.startswith("/limites"):
        from enviar_alertas import gerar_resumo_limites
        limites = gerar_resumo_limites(from_number)
        send_message(from_number, limites)
        return {"status": "limites enviados"}

    if incoming_msg.startswith("/relatorio"):
        from relatorio_formatado import gerar_relatorio
        relatorio = gerar_relatorio(from_number)
        send_message(from_number, relatorio)
        return {"status": "relatorio enviado"}
    
    if incoming_msg.startswith("/ranking"):
        from ranking import get_ranking_geral
        ranking = get_ranking_geral()
        send_message(from_number, ranking)
        return {"status": "ranking enviado"}

    if incoming_msg.startswith("/minhas_estrelas"):
        from ranking import get_ranking_usuario
        estrelas = get_ranking_usuario(from_number)
        send_message(from_number, estrelas)
        return {"status": "estrelas enviadas"}

    # === ⬆⬆ FIM DOS COMANDOS ESPECIAIS ===

    if not os.path.exists("conversas"):
        os.makedirs("conversas")

    status = status_usuario
    sheet = sheet_usuario
    values = sheet.col_values(2)
    row = values.index(from_number) + 1 if from_number in values else None

    if verificar_upgrade_automatico(from_number):
        send_message(from_number,
            "🔓 Seu acesso premium foi liberado!\nBem-vindo ao grupo dos que escolheram dominar a vida financeira com dignidade e IA de primeira. 🙌")

    linha_usuario = sheet.row_values(row)
    name = linha_usuario[0].strip() if len(linha_usuario) > 0 else ""
    email = linha_usuario[2].strip() if len(linha_usuario) > 2 else ""

    if passou_limite(sheet, row):
        send_message(from_number, "⚠️ Limite gratuito atingido. Acesse: https://seulinkpremium.com")
        return {"status": "limite atingido"}
    
    if any(p in incoming_msg.lower() for p in ["registrar gasto", "registrar meus gastos", "posso registrar", "lançar gasto", "lançar despesa", "adicionar gasto"]):
        send_message(from_number,
            "Claro! Para registrar seus gastos corretamente, siga este formato:\n\n"
            "📌 *Descrição - Valor - Forma de pagamento - Categoria (opcional)*\n\n"
            "*Exemplos:*\n"
            "• Uber - 20,00 - crédito\n"
            "• Combustível - 300,00 - débito\n"
            "• Farmácia - 50,00 - pix - Saúde\n\n"
            "Você pode mandar *vários gastos*, um por linha.\n"
            "Se não informar a categoria, vou identificar automaticamente. 😉"
        )
        salvar_estado(from_number, {"ultimo_fluxo": "registro_gastos_continuo"})
        return {"status": "orientacao registro de gastos enviada"}

    if not name or not email:
        linhas = incoming_msg.split("\n")
        captured_name = None
        captured_email = None

        for linha in linhas:
            linha = linha.strip()
            if not captured_email:
                possible_email = extract_email(linha)
                if possible_email:
                    captured_email = possible_email
                    continue
            if not captured_name and nome_valido(linha):
                captured_name = linha

        if captured_name and not name:
            sheet.update_cell(row, 1, captured_name)
            name = captured_name

        if captured_email and not email:
            sheet.update_cell(row, 3, captured_email)
            email = captured_email

        if not name and not email:
            send_message(from_number, "Olá! 👋🏼 Que bom ter você aqui.\n\nSou seu Conselheiro Financeiro pessoal, criado pelo Matheus Campos, CFP®.\nPara começarmos nossa jornada juntos, preciso apenas do seu nome e e-mail, por favor. Pode me mandar?")
            return {"status": "aguardando nome e email"}

        if not name:
            send_message(from_number, "Faltou seu nome completo. ✍️")
            return {"status": "aguardando nome"}

        if not email:
            send_message(from_number, "Agora me manda seu e-mail, por favor. 📧")
            return {"status": "aguardando email"}

        primeiro_nome = name.split()[0]
        welcome_msg = f"""Perfeito, {primeiro_nome}! 👊\n\nTô aqui pra te ajudar a organizar suas finanças e sua vida, sempre respeitando esta hierarquia: Deus, sua família e seu trabalho.\n\nPosso te ajudar com controle de gastos, resumos financeiros automáticos, alertas inteligentes no WhatsApp e email, análises de empréstimos e investimentos, além de orientações práticas para sua vida espiritual e familiar.\n\nPor onde quer começar?"""
        send_message(from_number, welcome_msg)
        return {"status": "cadastro completo"}
    
# === REGISTRO DE GASTOS PADRÃO ===
    if detectar_gastos(incoming_msg):
        gastos_novos = extrair_gastos(incoming_msg)

        if not gastos_novos:
            send_message(from_number, "❌ Não consegui entender os gastos. Verifique se estão no formato:\n\n*Descrição – Valor – Forma de pagamento – Categoria (opcional)*")
            return {"status": "nenhum gasto extraído"}

        gastos_sem_categoria = [g for g in gastos_novos if not g.get("categoria")]
        gastos_completos = [g for g in gastos_novos if g.get("categoria")]

        fuso = pytz.timezone("America/Sao_Paulo")
        hoje = datetime.datetime.now(fuso).strftime("%d/%m/%Y")

        gastos_registrados = []
        for gasto in gastos_completos:
            descricao = gasto["descricao"].capitalize()
            valor = gasto["valor"]
            forma = gasto["forma_pagamento"]
            categoria = gasto["categoria"]

            resultado = registrar_gasto(
                nome_usuario=name,
                numero_usuario=from_number,
                descricao=descricao,
                valor=valor,
                forma_pagamento=forma,
                data_gasto=hoje,
                categoria_manual=categoria
            )

            valor_formatado = f"R${valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            gastos_registrados.append(f"{descricao} ({valor_formatado}): {categoria}")

        mensagem = ""
        if gastos_registrados:
            mensagem += "*Gastos registrados:*\n" + "\n".join(gastos_registrados)

        if gastos_sem_categoria:
            estado_anterior = carregar_estado(from_number) or {}
            categorias_sugeridas = estado_anterior.get("categorias_sugeridas", {})

            for gasto in gastos_sem_categoria:
                descricao = gasto["descricao"].strip().lower()
                categoria_sug = categorizar(descricao) or "A DEFINIR"
                categorias_sugeridas[descricao] = categoria_sug

            estado_anterior.update({
                "ultimo_fluxo": "aguardando_categorias",
                "gastos_temp": gastos_sem_categoria,
                "categorias_sugeridas": categorias_sugeridas
            })

            salvar_estado(from_number, estado_anterior)

            lista_gastos = "\n".join(
                [f"{g['descricao'].capitalize()}, R${g['valor']}, pago com {g['forma_pagamento']}." for g in gastos_sem_categoria]
            )

            mensagem += (
                "\n\n"
                "Certo! Identifiquei os seguintes novos gastos sem categoria:\n\n" +
                lista_gastos +
                "\n\nSe quiser ajustar *categorias*, me envie agora as correções no formato:\n"
                "[descrição]: [categoria desejada]\n\n"
                "Exemplo: supermercado: alimentação\n\n"
                "Senão, sigo com o que identifiquei e registro já."
            )

        send_message(from_number, mensagem.strip())
        return {"status": "gastos processados"}
    
# === CORREÇÃO DE GASTO ===
    if quer_corrigir_gasto(incoming_msg):
        try:
            partes = re.sub(r"(?i)corrigir gasto:|corrigir|ajustar|trocar", "", incoming_msg).strip()
            match = re.match(
                r"(.*?)\s*[-–—]\s*(\d+(?:[.,]\d{2})?)\s*[-–—]\s*(crédito|débito|pix|boleto)\s*(?:[-–—]\s*(.*))?",
                partes, re.IGNORECASE
            )

            if not match:
                salvar_estado(from_number, {"ultimo_fluxo": "correcao_em_andamento"})
                send_message(from_number,
                    "⚠️ Parece que você quer corrigir um gasto, mas não entendi o que exatamente.")
                send_message(from_number,
                    "Exemplo: Almoço – 45,00 – crédito – Alimentação ou algo parecido.")
                return {"status": "aguardando detalhes de correção"}

            descricao = match.group(1).strip().capitalize()
            valor_raw = match.group(2)
            forma = match.group(3).strip().capitalize()
            categoria = match.group(4).strip().capitalize() if match.group(4) else "A DEFINIR"

            valor = float(re.sub(r"[^\d,]", "", valor_raw).replace(".", "").replace(",", "."))

            fuso = pytz.timezone("America/Sao_Paulo")
            hoje = datetime.datetime.now(fuso).strftime("%d/%m/%Y")

            sucesso = atualizar_categoria(from_number, descricao, hoje, categoria)

            if sucesso:
                send_message(from_number, f"✅ Gasto corrigido: {descricao} (R${valor:.2f}) – {categoria}")
                return {"status": "gasto corrigido"}
            else:
                send_message(from_number, f"❌ Não encontrei o gasto '{descricao}' registrado em {hoje}.")
                return {"status": "gasto não encontrado"}

        except Exception as e:
            print(f"[ERRO CORREÇÃO] {e}")
            send_message(from_number, "Erro ao tentar corrigir o gasto. Tente novamente com o formato:\n\n*Almoço – 45,00 – crédito – Alimentação*")
            return {"status": "erro na correção"}
    
    if detectar_gastos_com_categoria_direta(incoming_msg):
        gastos_identificados = []

        # Tenta primeiro: Descrição – Valor – Forma – Categoria (opcional)
        pattern1 = r"(.*?)\s*[-|–|—]\s*(\d+(?:[.,]\d{2})?)\s*[-|–|—]\s*(crédito|débito|pix|boleto)(?:\s*[-|–|—]\s*(.*))?"
        matches = re.findall(pattern1, incoming_msg, re.IGNORECASE)

        # Se falhar, tenta: Valor – Descrição – Forma – Categoria (opcional)
        if not matches:
            pattern2 = r"(\d+(?:[.,]\d{2})?)\s*[-|–|—]\s*(.*?)\s*[-|–|—]\s*(crédito|débito|pix|boleto)(?:\s*[-|–|—]\s*(.*))?"
            matches = re.findall(pattern2, incoming_msg, re.IGNORECASE)

        if not matches:
            send_message(from_number,
                "❌ Não consegui entender os gastos. Use o formato:\n"
                "📌 *Descrição – Valor – Forma de pagamento – Categoria (opcional)*\n\n"
                "Exemplos:\n"
                "• Uber – 20,00 – crédito\n"
                "• Combustível – 300,00 – débito\n"
                "• Farmácia – 50,00 – pix – Saúde\n\n"
                "Você pode mandar vários gastos, um por linha."
            )
            return {"status": "formato inválido para gastos diretos"}

        fuso = pytz.timezone("America/Sao_Paulo")
        hoje = datetime.datetime.now(fuso).strftime("%d/%m/%Y")
        linhas_confirmadas = []

        for match in matches:
            # Identifica a ordem automaticamente
            if re.match(r"\d", match[0]):  # Começa com valor
                valor_raw, descricao, forma, categoria_raw = match
            else:  # Começa com descrição
                descricao, valor_raw, forma, categoria_raw = match

            try:
                valor = float(re.sub(r"[^\d,]", "", valor_raw).replace(".", "").replace(",", "."))
                categoria = categoria_raw.strip().capitalize() if categoria_raw else categorizar(descricao) or "A DEFINIR"

                resultado = registrar_gasto(
                    nome_usuario=name,
                    numero_usuario=from_number,
                    descricao=descricao.strip().capitalize(),
                    valor=valor,
                    forma_pagamento=forma.strip().capitalize(),
                    data_gasto=hoje,
                    categoria_manual=categoria
                )

                valor_formatado = f"R${valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                linhas_confirmadas.append(f"{descricao.strip().capitalize()} ({valor_formatado}) – {categoria}")

            except Exception as e:
                print(f"[ERRO AO CONVERTER VALOR] {e}")
                continue

        send_message(from_number, "✅ *Gastos registrados:*\n\n" + "\n".join(linhas_confirmadas))
        return {"status": "gastos diretos com categoria processados"}        

    elif "pode seguir" in incoming_msg.lower():
        estado = carregar_estado(from_number)
        if estado.get("gastos_temp"):
            gastos = estado["gastos_temp"]
            categorias_sugeridas = estado.get("categorias_sugeridas", {})
            gastos_final = []

            fuso = pytz.timezone("America/Sao_Paulo")
            hoje = datetime.datetime.now(fuso).strftime("%d/%m/%Y")

            for gasto in gastos:
                descricao = gasto['descricao'].capitalize()
                valor = gasto['valor']
                forma = gasto['forma_pagamento']

                chave_descricao = descricao.lower()
                categoria = gasto.get("categoria") or categorias_sugeridas.get(chave_descricao) or "A DEFINIR"

                resultado = registrar_gasto(
                    nome_usuario=name,
                    numero_usuario=from_number,
                    descricao=descricao,
                    valor=valor,
                    forma_pagamento=forma,
                    data_gasto=hoje,
                    categoria_manual=categoria
                )

                valor_formatado = f"R${valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                gastos_final.append(f"{descricao} ({valor_formatado}): {resultado['categoria']}")

            resetar_estado(from_number)
            send_message(from_number, "Gastos registrados:\n" + "\n".join(gastos_final))
            return {"status": "gastos registrados com ajuste"}

    # === CONTINUA CONVERSA ===
    conversa_path = f"conversas/{from_number}.txt"
    if not os.path.exists("conversas"):
        os.makedirs("conversas")

    if not os.path.isfile(conversa_path):
        with open(conversa_path, "w") as f:
            f.write("")

    with open(conversa_path, "r") as f:
        linhas_conversa = f.readlines()

   # Só grava se 'reply' já foi gerado (evita erro antes da resposta da IA)
    if 'reply' in locals():
        if "[Nome]" in reply:
            if name and name.strip():
                primeiro_nome = name.split()[0]
                reply = reply.replace("[Nome]", primeiro_nome)
            else:
                reply = reply.replace("[Nome]", "")
        with open(conversa_path, "a") as f:
            f.write(f"Conselheiro: {reply}\n")

    historico_filtrado = [
        linha for linha in linhas_conversa
        if not any(frase in linha.lower() for frase in [
            "sou seu conselheiro financeiro",
            "sou o meu conselheiro financeiro",
            "perfeito,",
            "tô aqui pra te ajudar",
            "posso te ajudar com controle de gastos",
            "por onde quer começar"
        ])
    ]

    prompt_base = open("prompt.txt", "r").read()

    PALAVRAS_CHAVE_CATEGORIAS = {
        "espiritualidade": ["oração", "culpa", "confissão", "direção espiritual", "vida espiritual", "fé", "Deus", "confessar"],
        "financeiro": ["gasto", "dinheiro", "investimento", "renda", "salário", "orçamento", "juros", "empréstimo"],
        "casamento": ["cônjuge", "esposa", "marido", "matrimônio", "casamento", "vida a dois", "parceiro"],
        "dívidas": ["dívida", "devendo", "nome sujo", "negativado", "cobrança", "boleto atrasado"],
        "filosofia": ["virtude", "temperamento", "Aristóteles", "São Tomás", "ética", "filosofia", "psicologia"],
    }

    categoria_detectada = "geral"
    texto_lower = incoming_msg.lower()
    for categoria, palavras in PALAVRAS_CHAVE_CATEGORIAS.items():
        if any(palavra.lower() in texto_lower for palavra in palavras):
            categoria_detectada = categoria
            break

    contexto_resgatado = buscar_conhecimento_relevante(incoming_msg, top_k=3, categoria=categoria_detectada)

    mensagens = [{"role": "system", "content": prompt_base}]
    if ultimo_fluxo:
        mensagens.append({
            "role": "user",
            "content": f"O usuário está no fluxo: {ultimo_fluxo}. Responda de forma coerente com isso."
        })
    if contexto_resgatado:
        mensagens.append({"role": "user", "content": f"Conhecimento relevante:\n{contexto_resgatado}"})

    # === INTEGRAÇÃO COM INDICADORES ECONÔMICOS ===
    from indicadores import get_indicadores  # deixe esse import no topo do arquivo, se ainda não estiver

    termos_macro = ["empréstimo", "juros", "selic", "ipca", "cdi", "inflação", "investimento", "cenário econômico"]
    if any(palavra in incoming_msg.lower() for palavra in termos_macro):
        indicadores = get_indicadores()
        texto_indicadores = "\n".join([
            f"Taxa Selic: {indicadores.get('selic', 'indisponível')}%",
            f"CDI: {indicadores.get('cdi', 'indisponível')}%",
            f"IPCA (inflação): {indicadores.get('ipca', 'indisponível')}%",
            f"Ibovespa: {indicadores.get('ibovespa', 'indisponível')}"
        ])
        mensagens.append({
            "role": "user",
            "content": f"Indicadores econômicos atuais:\n{texto_indicadores}"
        })

    for linha in historico_filtrado[-6:]:
        if "Usuário:" in linha:
            mensagens.append({"role": "user", "content": linha.replace("Usuário:", "").strip()})
        elif "Conselheiro:" in linha:
            mensagens.append({"role": "assistant", "content": linha.replace("Conselheiro:", "").strip()})

    mensagens.append({"role": "user", "content": incoming_msg})

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-16k",
            messages=mensagens,
            temperature=0.7,
        )
        reply = response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[ERRO OpenAI] {e}")
        reply = "⚠️ Tive um problema ao responder agora. Pode me mandar a mensagem de novo?"

    reply = response["choices"][0]["message"]["content"].strip()
    # Substitui [Nome] pelo nome real salvo na planilha
    if "[Nome]" in reply:
        if name and name.strip():
            primeiro_nome = name.split()[0]
            reply = reply.replace("[Nome]", primeiro_nome)
        else:
            reply = reply.replace("[Nome]", "")  # Remove placeholder sem inventar apelido

    with open(conversa_path, "a") as f:
        f.write(f"Conselheiro: {reply}\n")

    armazenar_mensagem(from_number, "Usuário", incoming_msg)
    armazenar_mensagem(from_number, "Conselheiro", reply)

    tokens = count_tokens(incoming_msg) + count_tokens(reply)
    valor_atual = linha_usuario[4] if len(linha_usuario) > 4 else 0
    valor_atual = int(valor_atual) if valor_atual else 0
    sheet.update_cell(row, 5, valor_atual + tokens)

    increment_interactions(sheet, row)

    send_message(from_number, reply)

    # === Detectar emoção e possível relação com aumento de gasto ===
    fuso = pytz.timezone("America/Sao_Paulo")
    data_msg = datetime.datetime.now(fuso).strftime("%Y-%m-%d %H:%M:%S")
    emocao = detectar_emocao(incoming_msg)
    if emocao:
        alerta = aumento_pos_emocao(from_number, emocao, data_msg)
        if alerta:
            send_message(from_number, alerta)

    mensagem_estrela = avaliar_engajamento(from_number, incoming_msg)
    if mensagem_estrela:
        send_message(from_number, mensagem_estrela)

    if not reply or not reply.strip():
        send_message(
            from_number,
            "❌ Não consegui entender o que você quis dizer.\n\n"
            "Se estiver tentando registrar gastos, use o formato:\n\n"
            "📌 *Descrição – Valor – Forma de pagamento – Categoria (opcional)*\n\n"
            "*Exemplos válidos:*\n"
            "• Uber – 20,00 – crédito\n"
            "• Combustível – 300,00 – débito\n"
            "• Farmácia – 50,00 – pix – Saúde\n\n"
            "📎 Pode mandar *vários gastos de uma vez*, um por linha. Eu aguento."
        )

    return {"status": "mensagem enviada"}

@app.get("/health")
def health_check():
    return {"status": "vivo, lúcido e com fé"}