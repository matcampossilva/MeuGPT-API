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
import mensagens
from gastos import registrar_gasto, categorizar, corrigir_gasto, atualizar_categoria, parsear_gastos_em_lote
from estado_usuario import salvar_estado, carregar_estado, resetar_estado, resposta_enviada_recentemente, salvar_ultima_resposta
from gerar_resumo import gerar_resumo
from resgatar_contexto import buscar_conhecimento_relevante
from upgrade import verificar_upgrade_automatico
from armazenar_mensagem import armazenar_mensagem
from definir_limite import salvar_limite_usuario
from memoria_usuario import resumo_do_mes, verificar_limites, contexto_principal_usuario
from emocional import detectar_emocao, aumento_pos_emocao
from registrar_gastos_fixos import salvar_gastos_fixos
from planilhas import get_pagantes, get_gratuitos
from engajamento import avaliar_engajamento
from indicadores import get_indicadores
from enviar_alertas import verificar_alertas
from enviar_lembretes import enviar_lembretes

load_dotenv()
app = FastAPI()

openai.api_key = os.getenv("OPENAI_API_KEY")
client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
MESSAGING_SERVICE_SID = os.getenv("TWILIO_MESSAGING_SERVICE_SID")

# Função de leitura do prompt.txt para contexto inicial
with open("prompt.txt", "r") as arquivo_prompt:
    prompt_base = arquivo_prompt.read().strip()

# Complemento claro e incisivo de contexto obrigatório:
complemento_contextual = (
    "Você sempre trata o usuário pelo primeiro nome (que foi informado no início da conversa na resposta à saudação inicial) ou com um vocativo amigável e intimista. "
    "Você nunca recomenda divórcio ou separação por questões financeiras. "
    "O casamento é sagrado, indissolúvel e deve ser defendido com firmeza, clareza e profundidade espiritual. "
    "Seja sempre amigável, intimista, interessado e firme. Utilize explicitamente ensinamentos cristãos, católicos e do Opus Dei. "
    "Utilize o método de comunicação de Dale Carnegie, mostrando-se sempre interessado no usuário, demonstrando escuta ativa. "
    "Não use 'olá' no início de uma resposta se o usuário já tiver feito a primeira interação. "
    "Nunca sugira imediatamente ajuda externa (como conselheiros matrimoniais), a não ser que seja estritamente necessário após várias interações. "
    "Trate crises financeiras conjugais com responsabilidade cristã e financeira, lembrando sempre que a cruz matrimonial é uma oportunidade de crescimento espiritual e amadurecimento na vocação do casamento."
    "Trate questoões de moral e ética com os ensinamentos de Santo Tomás de Aquino e da doutrina católica. "
)

with open("prompt.txt", "r") as arquivo_prompt:
    prompt_base = arquivo_prompt.read().strip()

mensagens_gpt = [
    {"role": "system", "content": prompt_base},
    {"role": "system", "content": complemento_contextual},
    {"role": "system", "content": "Sempre consulte a pasta Knowledge via embeddings para complementar respostas de acordo com o contexto."}
]

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
    user_number = format_number(user_number)
    aba_pagantes = get_pagantes()
    aba_gratuitos = get_gratuitos()

    pagantes = aba_pagantes.col_values(2)
    gratuitos = aba_gratuitos.col_values(2)

    if user_number in pagantes:
        return aba_pagantes
    elif user_number in gratuitos:
        return aba_gratuitos
    else:
        now = datetime.datetime.now(pytz.timezone("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S")
        aba_gratuitos.append_row(["", user_number, "", now, 0, 0])
        return aba_gratuitos

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
    return raw_number.replace("whatsapp:", "").replace("+", "").replace(" ", "").strip()

def extract_email(text):
    match = re.search(r'[\w\.-]+@[\w\.-]+', text)
    return match.group(0) if match else None

def count_tokens(text):
    return len(text.split())

def send_message(to, body):
    if not body or not body.strip():
        print(f"[ERRO] Tentativa de enviar mensagem vazia para {to}. Ignorado.")
        return
    if resposta_enviada_recentemente(to, body):
        print("[DEBUG] Resposta duplicada detectada e não enviada.")
        return

    partes = [body[i:i+1500] for i in range(0, len(body), 1500)]
    for parte in partes:
        client.messages.create(
            body=parte,
            messaging_service_sid=MESSAGING_SERVICE_SID,
            to=f"whatsapp:{to}"
        )

    salvar_ultima_resposta(to, body)

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
    padrao = r"^[a-zA-ZáéíóúÁÉÍÓÚãõÃÕêÊôÔçÇ ]+[-–]\s*\d{1,3}(?:[.,]\d{2})\s*[-–]\s*(crédito|débito|pix|boleto)(?:\s*[-–]\s*[a-zA-ZáéíóúÁÉÍÓÚãõÃÕêÊôÔçÇ ]+)?$"
    return all(re.match(padrao, linha.strip(), re.IGNORECASE) for linha in linhas)

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

def get_tokens(sheet, row):
    try:
        val = sheet.cell(row, 5).value
        return int(val) if val else 0
    except:
        return 0

def increment_tokens(sheet, row, novos_tokens):
    tokens_atuais = get_tokens(sheet, row)
    sheet.update_cell(row, 5, tokens_atuais + novos_tokens)
    return tokens_atuais + novos_tokens

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    incoming_msg = form["Body"].strip()
    from_number = format_number(form["From"])

    estado = carregar_estado(from_number)
    ultima_msg = estado.get("ultima_msg", "")

    if incoming_msg == ultima_msg:
        print("[DEBUG] Mensagem duplicada detectada e ignorada.")
        return {"status": "mensagem duplicada ignorada"}

    estado["ultima_msg"] = incoming_msg
    salvar_estado(from_number, estado)

    sheet_usuario = get_user_sheet(from_number)

    try:
        linha_index = sheet_usuario.col_values(2).index(from_number) + 1
        linha_usuario = sheet_usuario.row_values(linha_index)
    except ValueError:
        now = datetime.datetime.now(pytz.timezone("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S")
        sheet_usuario.append_row(["", from_number, "", now, 0, 0])
        linha_index = sheet_usuario.col_values(2).index(from_number) + 1
        linha_usuario = ["", from_number, "", now, 0, 0]

    increment_interactions(sheet_usuario, linha_index)

    name = linha_usuario[0].strip() if len(linha_usuario[0].strip()) > 0 else "Usuário"
    email = linha_usuario[2].strip() or None

    tokens = count_tokens(incoming_msg)
    increment_tokens(sheet_usuario, linha_index, tokens)

    if is_boas_vindas(incoming_msg):
        if not name or not email:
            send_message(from_number, mensagens.estilo_msg(mensagens.solicitacao_cadastro()))
            estado["ultimo_fluxo"] = "aguardando_cadastro"
            salvar_estado(from_number, estado)
            return {"status": "aguardando nome e email"}

        if estado.get("saudacao_realizada"):
            send_message(from_number, mensagens.estilo_msg("Já estou aqui com você! Como posso te ajudar agora? 😉"))
            return {"status": "saudação já realizada"}

        resposta_curta = mensagens.cadastro_completo(name.split()[0])
        send_message(from_number, mensagens.estilo_msg(resposta_curta))
        estado["ultimo_fluxo"] = "cadastro_completo"
        estado["saudacao_realizada"] = True
        salvar_estado(from_number, estado)
        return {"status": "cadastro completo"}

    if not name or not email:
        linhas = incoming_msg.split("\n")
        nome_capturado = next((linha.title() for linha in linhas if nome_valido(linha)), None)
        email_capturado = next((extract_email(linha).lower() for linha in linhas if extract_email(linha)), None)

        if nome_capturado:
            sheet_usuario.update_cell(linha_index, 1, nome_capturado)
            name = nome_capturado

        if email_capturado:
            sheet_usuario.update_cell(linha_index, 3, email_capturado)
            email = email_capturado

        if not name and not email:
            send_message(from_number, mensagens.estilo_msg(mensagens.solicitacao_cadastro()))
            return {"status": "aguardando nome e email"}

        if not name:
            send_message(from_number, mensagens.estilo_msg("Faltou seu nome completo. ✍️"))
            return {"status": "aguardando nome"}

        if not email:
            send_message(from_number, mensagens.estilo_msg("Agora me manda seu e-mail, por favor. 📧"))
            return {"status": "aguardando email"}

        primeiro_nome = name.split()[0]
        send_message(from_number, mensagens.estilo_msg(mensagens.cadastro_completo(primeiro_nome)))
        estado["ultimo_fluxo"] = "cadastro_completo"
        estado["saudacao_realizada"] = True
        salvar_estado(from_number, estado)
        return {"status": "cadastro completo"}

    if estado.get("ultimo_fluxo") != "cadastro_completo":
        estado["ultimo_fluxo"] = "cadastro_completo"
        salvar_estado(from_number, estado)

    if estado.get("ultimo_fluxo") == "escuta_ativa":
        historico_relevante.append(f"Usuário: {incoming_msg}")
    
    # Mensagem padrão sobre funcionalidades
    if "o que você faz" in incoming_msg.lower() or "funcionalidades" in incoming_msg.lower():
        resposta_funcionalidades = mensagens.funcionalidades()
        send_message(from_number, mensagens.estilo_msg(resposta_funcionalidades))
        return {"status": "funcionalidades informadas"}

    if incoming_msg.strip().lower() in ["/comandos", "/ajuda"]:
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
    
    if "despesas fixas" in incoming_msg.lower() or "gastos fixos" in incoming_msg.lower():
        if detectar_gastos(incoming_msg):
            gastos_fixos, erros = parsear_gastos_em_lote(incoming_msg)

            if erros:
                send_message(from_number, mensagens.estilo_msg(mensagens.erro_formato_gastos()))
                return {"status": "erro nos gastos fixos"}

            salvar_gastos_fixos(from_number, gastos_fixos)

            total_gastos = sum(gasto["valor"] for gasto in gastos_fixos)
            mensagem = "✅ *Suas despesas fixas foram salvas!*\n"
            mensagem += "\n".join([f"{g['descricao']} - R${g['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") for g in gastos_fixos])
            mensagem += f"\n\n*Total mensal:* R${total_gastos:,.2f}\n\n".replace(",", "X").replace(".", ",").replace("X", ".")
            mensagem += "Quer definir limites mensais para esses gastos e receber alertas quando atingidos?"

            send_message(from_number, mensagens.estilo_msg(mensagem))

            return {"status": "gastos fixos registrados"}

        else:
            send_message(from_number, mensagens.estilo_msg(mensagens.registro_gastos_orientacao()))
            return {"status": "aguardando formato correto gastos fixos"}

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

            resposta_registro = registrar_gasto(
                nome_usuario=name,
                numero_usuario=from_number.replace("whatsapp:", "").replace("+", "").strip(),
                descricao=descricao,
                valor=valor,
                forma_pagamento=forma,
                data_gasto=hoje,
                categoria_manual=categoria
            )

            if resposta_registro["status"] != "ok":
                print(f"[ERRO] {resposta_registro['mensagem']}")

            estado["ultimo_fluxo"] = "gastos_registrados"
            salvar_estado(from_number, estado)
        
            valor_formatado = f"R${valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            gastos_registrados.append(f"{descricao} ({valor_formatado}): {categoria}")

        mensagem = ""
        if gastos_registrados:
            # Calcula o somatório por categoria
            categorias_totais = {}
            for gasto in gastos_completos + gastos_sem_categoria:
                categoria = gasto.get('categoria', 'A DEFINIR')
                categorias_totais[categoria] = categorias_totais.get(categoria, 0) + gasto['valor']

            # Formata o somatório
            somatorio_msg = "\n".join([
                f"{categoria}: R${valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                for categoria, valor in categorias_totais.items()
            ])

            mensagem = "✅ *Gastos registrados com sucesso!*\n\n"
            mensagem += "📊 *Total por categoria:*\n" + somatorio_msg
            mensagem += "\n\nVocê gostaria de definir limites para essas categorias e receber alertas automáticos quando atingir esses limites?"

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

    if estado.get("ultimo_fluxo") == "cadastro_completo":
        interacoes = get_interactions(sheet_usuario, linha_index)
        if interacoes >= 10:
            contexto_usuario = contexto_principal_usuario(from_number, ultima_msg=incoming_msg)
            mensagem_alerta = mensagens.alerta_limite_gratuito(contexto_usuario)
            send_message(from_number, mensagens.estilo_msg(mensagem_alerta, leve=False))
            return {"status": "limite atingido"}

    # === REGISTRO DE GASTOS PADRÃO ===
     # Instrução clara para registrar gastos (se o usuário pedir ajuda diretamente sobre gastos)
    if any(frase in incoming_msg.lower() for frase in [
        "quero registrar gastos",
        "quero relacionar meus gastos",
        "quero anotar gastos",
        "como faço pra registrar gastos",
        "quero lançar gastos",
        "ajuda para registrar gastos",
        "controle inteligente e automático de gastos",
        "controle automático de gastos",
        "controle inteligente de gastos",
        "controlar meus gastos",
        "controle de gastos"
    ]):
        send_message(from_number, mensagens.estilo_msg(mensagens.orientacao_controle_gastos()))
        estado["ultimo_fluxo"] = "aguardando_opcao_controle_gastos"
        salvar_estado(from_number, estado)

        return {"status": "orientacao controle gastos enviada"}

    if estado.get("ultimo_fluxo") == "aguardando_opcao_controle_gastos":
        if "1" in incoming_msg:
            send_message(from_number, mensagens.estilo_msg(
                "Ótima escolha! Vamos relacionar suas despesas fixas mensais.\n"
                "Mande cada despesa fixa neste formato:\n"
                "📌 Descrição – Valor – Dia do mês que vence\n\n"
                "Exemplo:\n"
                "Aluguel – 2500,00 – 05\n"
                "Internet – 100,00 – 15"
            ))
            estado["ultimo_fluxo"] = "aguardando_gastos_fixos"
            salvar_estado(from_number, estado)
            return {"status": "aguardando gastos fixos"}

        elif "2" in incoming_msg:
            send_message(from_number, mensagens.estilo_msg(mensagens.registro_gastos_orientacao()))
            estado["ultimo_fluxo"] = "registro_gastos_continuo"
            salvar_estado(from_number, estado)
            return {"status": "aguardando registro gastos"}

        elif "3" in incoming_msg:
            send_message(from_number, mensagens.estilo_msg(
                "Perfeito! Vamos definir seus limites por categoria. Para isso, envie cada categoria e o valor mensal desejado assim:\n"
                "📌 Categoria – Valor limite\n\n"
                "Exemplo:\n"
                "Alimentação – 1500,00\n"
                "Lazer – 500,00\n"
                "Transporte – 800,00"
            ))
            estado["ultimo_fluxo"] = "aguardando_limites_categoria"
            salvar_estado(from_number, estado)
            return {"status": "aguardando limites por categoria"}
    
    if detectar_gastos(incoming_msg):
        gastos_novos, erros = parsear_gastos_em_lote(incoming_msg)

        if erros:
            send_message(from_number, mensagens.estilo_msg(
                "⚠️ Alguns gastos não foram reconhecidos:\n" + "\n".join(erros)
            ))

        if not gastos_novos:
            send_message(from_number, mensagens.estilo_msg(
                "❌ Não consegui entender os gastos que você mandou.\n\n"
                "Use este formato exato:\n\n"
                "📌 *Descrição – Valor – Forma de pagamento – Categoria (opcional)*\n\n"
                "*Exemplos válidos:*\n"
                "• Uber – 20,00 – crédito\n"
                "• Combustível – 300,00 – débito\n"
                "• Farmácia – 50,00 – pix – Saúde\n\n"
                "📎 Pode mandar vários gastos, um por linha."
            ))
            return {"status": "nenhum gasto extraído"}

        fuso = pytz.timezone("America/Sao_Paulo")
        hoje = datetime.datetime.now(fuso).strftime("%d/%m/%Y")

        gastos_registrados = []

        for gasto in gastos_novos:
            descricao = gasto["descricao"].capitalize()
            valor = gasto["valor"]
            forma = gasto["forma_pagamento"]
            categoria = gasto.get("categoria") or categorizar(descricao)

            resposta_registro = registrar_gasto(
                nome_usuario=name,
                numero_usuario=from_number.replace("whatsapp:", "").replace("+", "").strip(),
                descricao=descricao,
                valor=valor,
                forma_pagamento=forma,
                data_gasto=hoje,
                categoria_manual=categoria
            )

            if resposta_registro["status"] != "ok":
                print(f"[ERRO] {resposta_registro['mensagem']}")

            valor_formatado = f"R${valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            gastos_registrados.append(f"{descricao} – {valor_formatado} – {forma} – {categoria}")

        mensagem_final = "Registro anotado, meu amigo! Aqui está o resumo dos seus gastos do dia:\n\n"
        mensagem_final += "\n".join(gastos_registrados)

        send_message(from_number, mensagens.estilo_msg(mensagem_final))

        return {"status": "gastos registrados"}

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
            "perfeito,",
            "tô aqui pra te ajudar",
            "posso te ajudar com controle de gastos",
            "por onde quer começar"
        ])
    ]
  
    historico_relevante = historico_filtrado[-4:]
  
    def precisa_escuta_ativa(historico, assunto_atual):
        return not any(assunto_atual in linha.lower() for linha in historico)

    PALAVRAS_CHAVE_CATEGORIAS = {
        "espiritualidade": ["oração", "culpa", "confissão", "direção espiritual", "vida espiritual", "fé", "deus", "confessar"],
        "financeiro": ["gasto", "dinheiro", "investimento", "renda", "salário", "orçamento", "juros", "empréstimo"],
        "casamento": ["cônjuge", "esposa", "marido", "matrimônio", "casamento", "vida a dois", "parceiro"],
        "dívidas": ["dívida", "devendo", "nome sujo", "negativado", "cobrança", "boleto atrasado"],
        "filosofia": ["virtude", "temperamento", "aristóteles", "santo tomás", "ética", "filosofia", "psicologia"],
    }

    categoria_detectada = "geral"
    texto_lower = incoming_msg.lower()
    for categoria, palavras in PALAVRAS_CHAVE_CATEGORIAS.items():
        if any(palavra.lower() in texto_lower for palavra in palavras):
            categoria_detectada = categoria
            break

    assuntos_sensiveis_escuta = ["casamento", "espiritualidade", "dívidas", "filosofia", "financeiro"]

    if categoria_detectada in assuntos_sensiveis_escuta:
        if precisa_escuta_ativa(historico_relevante, categoria_detectada):
            resposta_escuta = mensagens.pergunta_escuta_ativa(categoria_detectada)
            send_message(from_number, mensagens.estilo_msg(resposta_escuta))
            estado["ultimo_fluxo"] = "escuta_ativa"
            salvar_estado(from_number, estado)
            return {"status": "aguardando mais contexto do usuário"}

    if ultimo_fluxo == "escuta_ativa":
        prompt_escuta_ativa = (
            "O usuário acaba de fornecer mais contexto sobre um assunto importante ou sensível que você perguntou anteriormente. "
            "Agora, com essa informação adicional, responda diretamente e de maneira acolhedora ao contexto específico apresentado pelo usuário. "
            "Não repita perguntas. Ofereça orientações práticas e claras alinhadas aos valores cristãos, familiares e financeiros do método Matheus Campos, CFP®. "
            "Utilize o estilo amigável, firme e interessado de Dale Carnegie. Seja breve, prático e direto ao ponto."
        )
        mensagens_gpt.append({"role": "system", "content": prompt_escuta_ativa})
        estado["ultimo_fluxo"] = "cadastro_completo"
        salvar_estado(from_number, estado)
    
    with open("prompt.txt", "r") as arquivo_prompt:
        prompt_base = arquivo_prompt.read().strip()

    mensagens_gpt = [
        {"role": "system", "content": prompt_base},
        {"role": "system", "content": complemento_contextual},
        {"role": "system", "content": "Sempre consulte primeiro os arquivos da pasta Knowledge para respostas, respeitando rigorosamente o prompt definido por Matheus Campos. Só então, caso necessário, complemente com sua própria base de dados."}
    ]

    termos_resumo_financeiro = ["resumo", "resumo do dia", "resumo financeiro", "quanto gastei", "gastos hoje"]
    if any(termo in incoming_msg.lower() for termo in termos_resumo_financeiro):
        contexto_resgatado = ""
    else:
        contexto_resgatado = buscar_conhecimento_relevante(incoming_msg, categoria=categoria_detectada, top_k=4)
    # print(f"[DEBUG] Conteúdo recuperado da knowledge: {contexto_resgatado}")
    if contexto_resgatado:
        mensagens_gpt.append({
            "role": "system",
            "content": (
                "Ao responder, baseie-se prioritariamente nas informações a seguir, respeitando fielmente "
                "o estilo, tom, e os princípios contidos:\n\n"
                f"{contexto_resgatado}"
            )
        })

    if ultimo_fluxo:
        mensagens_gpt.append({
            "role": "system",
            "content": f"O usuário está no seguinte fluxo: {ultimo_fluxo}."
        })

    for linha in historico_relevante:
        if ":" in linha:
            role = "user" if "Usuário:" in linha else "assistant"
            conteudo = linha.split(":", 1)[1].strip()
            mensagens_gpt.append({"role": role, "content": conteudo})
        else:
            # print(f"[DEBUG] Linha ignorada no histórico por falta de ':': {linha}")
            pass # adicionado para evitar IndentationError após comentário

    mensagens_gpt.append({"role": "user", "content": incoming_msg})

    termos_macro = ["empréstimo", "juros", "selic", "ipca", "cdi", "inflação", "investimento", "cenário econômico"]
    if any(palavra in incoming_msg.lower() for palavra in termos_macro):
        indicadores = get_indicadores()
        texto_indicadores = "\n".join([
            f"Taxa Selic: {indicadores.get('selic', 'indisponível')}%",
            f"CDI: {indicadores.get('cdi', 'indisponível')}%",
            f"IPCA (inflação): {indicadores.get('ipca', 'indisponível')}%",
            f"Ibovespa: {indicadores.get('ibovespa', 'indisponível')}"
        ])
        mensagens_gpt.append({
            "role": "user",
            "content": f"Indicadores econômicos atuais:\n{texto_indicadores}"
        })

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=mensagens_gpt,
            temperature=0.7,
        )
        reply = response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        # print(f"[ERRO OpenAI] {e}")
        reply = "⚠️ Tive um problema ao responder agora. Pode me mandar a mensagem de novo?"

    reply = re.sub(r'^(uai|tem base|bom demais)\s*[.!]?\s*', '', reply, flags=re.IGNORECASE).strip()

    if "[Nome]" in reply:
        primeiro_nome = name.split()[0] if name else ""
        reply = reply.replace("[Nome]", primeiro_nome)

    assuntos_sensiveis = ["violência", "agressão", "abuso", "depressão", "ansiedade", "suicídio", "terapia"]
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
            send_message(from_number, mensagens.estilo_msg(alerta))

    # mensagem_estrela = avaliar_engajamento(from_number, incoming_msg)
    # if mensagem_estrela:
        # send_message(from_number, mensagens.estilo_msg(mensagem_estrela))

    verificar_alertas()

    # print(f"[DEBUG] reply gerado pelo GPT: {reply}")
    # print(f"[DEBUG] Enviando mensagem para {from_number}")

    if reply.strip():
        send_message(from_number, mensagens.estilo_msg(reply))
        # print("[DEBUG] Mensagem enviada.")
    else:
        send_message(from_number, mensagens.estilo_msg(
            "❌ Não consegui entender. Se estiver tentando registrar gastos, use o formato:\n"
            "📌 Descrição – Valor – Forma de pagamento – Categoria (opcional)"
        ))
        # print("[DEBUG] Mensagem padrão enviada por falta de reply.")

    return {"status": "mensagem enviada"}

@app.get("/health")
def health_check():
    return {"status": "vivo, lúcido e com fé"}