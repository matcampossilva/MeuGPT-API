import random

def saudacao_inicial():
    return (
        "Olá! 👋🏼 Sou o seu Conselheiro Financeiro criado pelo Matheus Campos, CFP®. "
        "Tô aqui pra te ajudar a organizar suas finanças e sua vida, sempre colocando Deus, sua família e seu trabalho antes do dinheiro. "
        "Me conta uma coisa: por onde quer começar?"
    )

def funcionalidades():
    return (
        "Posso te ajudar com controle de gastos, resumos financeiros automáticos, alertas inteligentes no WhatsApp, "
        "solução de dívidas, análises de empréstimos e investimentos, além de orientações práticas para sua vida espiritual e familiar. "
        "Por onde quer começar?"
    )

def solicitacao_cadastro():
    return (
        "Olá! 👋🏼 Sou seu Conselheiro Financeiro pessoal, criado pelo Matheus Campos, CFP®. "
        "Pra começarmos a organizar sua vida financeira, me diga seu nome completo e e-mail, por favor."
    )

def cadastro_completo(primeiro_nome):
    return (
        f"Perfeito, {primeiro_nome}! 👊🏼\n\n"
        "Agora que já nos conhecemos melhor, bora organizar suas finanças com clareza e propósito, sempre respeitando a ordem: Deus, família e trabalho. 🙏🏼👨‍👩‍👧‍👦💼\n\n"
        "Controle de gastos, resumos automáticos, solução de dívidas, investimentos ou vida espiritual ou familiar... por onde quer começar?"
    )

def alerta_limite_gratuito():
    return (
        "⚠️ Eita, seu limite gratuito acabou de bater no teto! 😬\n\n"
        "Bora parar de brincar com suas finanças e entrar pro clube dos adultos responsáveis? "
        "Libere agora o acesso premium e tenha controle total das suas finanças, alertas personalizados e orientação VIP pra alcançar seus objetivos. 🚀💳\n\n"
        "👉🏼 Acesse aqui: https://seulinkpremium.com"
    )

def registro_gastos_orientacao():
    return (
        "Claro! Para registrar seus gastos corretamente, siga este formato:\n\n"
        "📌 *Descrição - Valor - Forma de pagamento - Categoria (opcional)*\n\n"
        "*Exemplos:*\n"
        "• Uber - 20,00 - crédito\n"
        "• Combustível - 300,00 - débito\n"
        "• Farmácia - 50,00 - pix - Saúde\n\n"
        "Você pode mandar *vários gastos*, um por linha.\n"
        "Se não informar a categoria, vou identificar automaticamente. 😉"
    )

def erro_formato_gastos():
    return (
        "❌ Não consegui entender seus gastos direito.\n\n"
        "Me ajuda mandando assim, por favor:\n\n"
        "📌 Descrição – Valor – Forma de pagamento – Categoria (opcional)\n\n"
        "Exemplo:\n• Uber – 20,00 – crédito\n• Farmácia – 50,00 – pix – Saúde\n\n"
        "Pode enviar vários, um por linha. 😉"
    )

def humor_acido_alerta():
    mensagens = [
        "Olha só! Vai gastar todo seu dinheiro em iFood mesmo ou sobrou algum trocado pro aporte do mês? 🤡",
        "Que legal, já pagou a mensalidade da academia mais cara da cidade. Agora só falta você ir treinar. 🫢",
        "Uai! Tá investindo forte em roupas novas ou resolveu abrir uma loja? 😒",
        "Netflix, Disney+, HBO… Cê já pensou em assistir menos séries e mais seu dinheiro crescendo? 👀",
        "Não é rico, mas se dá certos luxos, né? 🐩",
        "Feliz no simples? 🛥️",
        "Ô Leônidas, cê tem que parar de arrumar essas confusão, meu! 🫣",
        "Essa semana tenha o mindset de um boleto. Porque um boleto sempre vence. Vamo pra cima! 🚀",
        "Uai, passa vontade não, passa o cartãozinho. 👹",
        "Sinceramente, vou me abster de comentários porque sou da igreja. 🤝",
        "Compra, pô. É seu lazer. 👹",
        "Judas foi falso, mas você, hein... 😒"
    ]
    return random.choice(mensagens)

def disclaimer():
    return (
        "⚠️ Lembre-se: Este GPT não substitui acompanhamento profissional especializado em saúde física, emocional, "
        "orientação espiritual direta ou consultoria financeira personalizada."
    )

def estilo_msg(texto, leve=True):
    fechamento_personalizado = random.choice([
        "Vamos juntos! 🚀",
        "Conte comigo! 🤝",
        "Sigamos firmes! 💪🏼",
        "Tô com você! 🫡"
    ])
    return f"{texto}\n\n{fechamento_personalizado}"