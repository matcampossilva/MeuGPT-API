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
import mensagens  # Novo módulo com mensagens padrão centralizadas

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

    # Mensagem padrão para cumprimentos rápidos
    if incoming_msg.lower() in ["olá", "oi", "bom dia", "boa tarde", "boa noite"]:
        resposta_curta = mensagens.saudacao_inicial()
        send_message(from_number, mensagens.estilo_msg(resposta_curta))
        return {"status": "saudação inicial enviada"}

    # Mensagem padrão sobre funcionalidades
    if "o que você faz" in incoming_msg.lower() or "funcionalidades" in incoming_msg.lower():
        resposta_funcionalidades = mensagens.funcionalidades()
        send_message(from_number, mensagens.estilo_msg(resposta_funcionalidades))
        return {"status": "funcionalidades informadas"}

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
        send_message(from_number, mensagens.estilo_msg(comandos))
        return {"status": "comandos enviados"}

    linha_usuario = sheet_usuario.row_values(sheet_usuario.col_values(2).index(from_number) + 1)
    name = linha_usuario[0].strip() if len(linha_usuario) > 0 else ""

    if estado.get("ultimo_fluxo") == "registro_gastos_continuo" and detectar_gastos(incoming_msg):
        gastos_novos = extrair_gastos(incoming_msg)
        if not gastos_novos:
            send_message(
                from_number,
                mensagens.estilo_msg(mensagens.erro_formato_gastos())
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

        send_message(from_number, mensagens.estilo_msg(mensagem.strip()))
        return {"status": "gastos processados via fluxo contínuo"}

    ultimo_fluxo = estado.get("ultimo_fluxo")

    if quer_resumo_mensal(incoming_msg):
        resumo = resumo_do_mes(from_number)
        limites = verificar_limites(from_number)
        send_message(from_number, mensagens.estilo_msg(resumo + "\n\n" + limites))
        return {"status": "resumo mensal enviado"}

    if any(t in incoming_msg.lower() for t in [
        "resumo do dia", "resumo de hoje", "quanto gastei hoje",
        "novo resumo", "resumo agora", "resumo atualizado",
        "quero o resumo", "meu resumo", "resumo aqui"
    ]):
        resumo = gerar_resumo(from_number, periodo="diario")
        send_message(from_number, mensagens.estilo_msg(resumo))
        return {"status": "resumo hoje enviado"}

    if any(t in incoming_msg.lower() for t in ["resumo de ontem", "quanto gastei ontem"]):
        ontem = datetime.datetime.now(pytz.timezone("America/Sao_Paulo")) - datetime.timedelta(days=1)
        resumo = gerar_resumo(from_number, periodo="custom", data_personalizada=ontem.date())
        send_message(from_number, mensagens.estilo_msg(resumo))
        return {"status": "resumo ontem enviado"}

    if verificar_upgrade_automatico(from_number):
        send_message(from_number, mensagens.estilo_msg(
            "🔓 Seu acesso premium foi liberado!\nBem-vindo ao grupo dos que escolheram dominar a vida financeira com dignidade e IA de primeira. 🙌"))

    linha_usuario = sheet_usuario.row_values(sheet_usuario.col_values(2).index(from_number) + 1)
    name = linha_usuario[0].strip() if len(linha_usuario) > 0 else ""
    email = linha_usuario[2].strip() if len(linha_usuario) > 2 else ""

    if passou_limite(sheet_usuario, sheet_usuario.col_values(2).index(from_number) + 1):
        send_message(from_number, mensagens.estilo_msg(mensagens.alerta_limite_gratuito(), leve=False))
        return {"status": "limite atingido"}

    # === REGISTRO DE GASTOS PADRÃO ===
    if detectar_gastos(incoming_msg):
        gastos_novos = extrair_gastos(incoming_msg)

        if not gastos_novos:
            send_message(from_number, estilo_msg(
                "❌ Não consegui entender os gastos. Confira se estão no formato correto:\n\n"
                "📌 Descrição – Valor – Forma de pagamento – Categoria (opcional)\n\n"
                "*Exemplos válidos:*\n"
                "• Uber – 20,00 – crédito\n"
                "• Combustível – 300,00 – débito\n"
                "• Farmácia – 50,00 – pix – Saúde\n\n"
                "📌 Pode enviar vários gastos de uma vez, um por linha."
            ))
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
            mensagem += "✅ *Gastos registrados com sucesso:*\n" + "\n".join(gastos_registrados)

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
                [f"{g['descricao'].capitalize()}, R${g['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") +
                 f", pago com {g['forma_pagamento']}."
                 for g in gastos_sem_categoria]
            )

            mensagem += (
                "\n\n🧐 Identifiquei alguns gastos sem categoria:\n\n" +
                lista_gastos +
                "\n\nSe quiser ajustar categorias, me envie agora as correções no formato:\n"
                "[descrição]: [categoria desejada]\n\n"
                "*Exemplo:* supermercado: alimentação\n\n"
                "Se não precisar ajustar, só me avise que posso registrar assim mesmo!"
            )

        send_message(from_number, estilo_msg(mensagem.strip()))
        return {"status": "gastos processados"}

    # === CONTINUA CONVERSA ===
    conversa_path = f"conversas/{from_number}.txt"
    if not os.path.exists("conversas"):
        os.makedirs("conversas")

    if not os.path.isfile(conversa_path):
        with open(conversa_path, "w") as f:
            f.write("")

    with open(conversa_path, "r") as f:
        linhas_conversa = f.readlines()

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

    with open("prompt.txt", "r") as arquivo_prompt:
        prompt_base = arquivo_prompt.read().strip()

    mensagens = [{"role": "system", "content": prompt_base}]

    contexto_resgatado = buscar_conhecimento_relevante(incoming_msg, top_k=6, categoria=categoria_detectada)
    if contexto_resgatado:
        mensagens.append({
            "role": "system",
            "content": f"Utilize este conhecimento detalhadamente ao responder:\n{contexto_resgatado}"
        })

    if ultimo_fluxo:
        mensagens.append({
            "role": "system",
            "content": f"O usuário está no fluxo atual: {ultimo_fluxo}."
        })

    for linha in historico_filtrado[-6:]:
        role = "user" if "Usuário:" in linha else "assistant"
        conteudo = linha.split(":", 1)[1].strip()
        mensagens.append({"role": role, "content": conteudo})

    mensagens.append({"role": "user", "content": incoming_msg})

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

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=mensagens,
            temperature=0.7,
        )
        reply = response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[ERRO OpenAI] {e}")
        reply = "⚠️ Tive um problema ao responder agora. Pode me mandar a mensagem de novo?"

    reply = re.sub(r'^(uai|tem base|bom demais|ô beleza)\s*[.!]?\s*', '', reply, flags=re.IGNORECASE).strip()

    if "[Nome]" in reply:
        primeiro_nome = name.split()[0] if name else ""
        reply = reply.replace("[Nome]", primeiro_nome)

    assuntos_sensiveis = ["violência", "agressão", "abuso", "depressão", "ansiedade", "suicídio", "divórcio", "separação", "terapia", "crise"]
    if any(termo in incoming_msg.lower() for termo in assuntos_sensiveis):
        disclaimer = (
            "⚠️ Lembre-se: Este GPT não substitui acompanhamento profissional especializado em saúde física, emocional, orientação espiritual direta ou consultoria financeira personalizada."
        )
        reply = f"{reply}\n\n{disclaimer}"

    with open(conversa_path, "a") as f:
        f.write(f"Conselheiro: {reply}\n")

    fuso = pytz.timezone("America/Sao_Paulo")
    data_msg = datetime.datetime.now(fuso).strftime("%Y-%m-%d %H:%M:%S")
    emocao = detectar_emocao(incoming_msg)
    if emocao:
        alerta = aumento_pos_emocao(from_number, emocao, data_msg)
        if alerta:
            send_message(from_number, estilo_msg(alerta))

    mensagem_estrela = avaliar_engajamento(from_number, incoming_msg)
    if mensagem_estrela:
        send_message(from_number, estilo_msg(mensagem_estrela))

    if not reply.strip():
        send_message(from_number, estilo_msg(
            "❌ Não consegui entender. Se estiver tentando registrar gastos, use o formato:\n"
            "📌 Descrição – Valor – Forma de pagamento – Categoria (opcional)"
        ))

    return {"status": "mensagem enviada"}

@app.get("/health")
def health_check():
    return {"status": "vivo, lúcido e com fé"}