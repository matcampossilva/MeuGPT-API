import random

def saudacao_inicial():
    return (
        "Olá! 👋🏼 Sou o seu Conselheiro Financeiro criado pelo Matheus Campos, CFP®. "
        "Tô aqui pra te ajudar a organizar suas finanças e sua vida, sempre colocando Deus, sua família e seu trabalho antes do dinheiro. "
        "Pra começarmos a organizar sua vida financeira, me diga seu nome completo e e-mail, por favor."
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
        "Agora que já nos conhecemos melhor, vamos organizar suas finanças com clareza e propósito, sempre respeitando a ordem: Deus, família e trabalho. 🙏🏼👨‍👩‍👧‍👦💼\n\n"
        "Controle de gastos, resumos automáticos, solução de dívidas, investimentos ou vida espiritual e familiar... por onde quer começar?"
    )

def solicitacao_cadastro():
    return saudacao_inicial()

def alerta_limite_gratuito(contexto='geral'):
    mensagens_contextuais = {
        "casamento": (
            "⚠️ Você chegou ao fim da versão gratuita.\n\n"
            "Pergunte-se agora: Quer paz no casamento ou prefere continuar brigando por dinheiro? 🥲\n\n"
            "No Premium você tem estratégias personalizadas para acabar com estresse financeiro no seu relacionamento.\n\n"
            "👉🏼 Ative agora e proteja seu casamento: https://seulinkpremium.com"
        ),
        "dívidas": (
            "⚠️ Seu limite gratuito terminou.\n\n"
            "Pergunte-se agora: você realmente vai continuar pagando juros e financiando o lucro dos bancos, ou prefere assumir o controle definitivo das suas dívidas?\n\n"
            "Com o Premium, você tem planos concretos e personalizados para eliminar dívidas de uma vez por todas.\n\n"
            "👉🏼 Livre-se das dívidas agora: https://seulinkpremium.com"
        ),
        "controle_gastos": (
            "⚠️ Seu período gratuito acabou.\n\n"
            "Pergunte-se agora: quer continuar vivendo de suposições financeiras no escuro ou finalmente ter clareza absoluta e controle real sobre cada centavo que você gasta?\n\n"
            "Com o Premium, você passa a tomar decisões financeiras com total precisão, organização e segurança.\n\n"
            "👉🏼 Garanta agora o controle absoluto aqui: https://seulinkpremium.com"
        ),
        "decisoes_financeiras": (
            "⚠️ Você esgotou seu limite gratuito.\n\n"
            "Pergunte-se agora: quantas decisões financeiras erradas você ainda pode se dar ao luxo de cometer?\n\n"
            "O acesso Premium oferece respostas certeiras e objetivas para suas decisões financeiras diárias e estratégicas.\n\n"
            "👉🏼 Tome decisões inteligentes agora: https://seulinkpremium.com"
        ),
        "liberdade_espiritual": (
            "⚠️ Seu período gratuito chegou ao fim.\n\n"
            "Pergunte-se agora: você quer que seu dinheiro sirva aos seus valores mais profundos ou prefere continuar refém da pressão financeira?\n\n"
            "No Premium, dinheiro e espiritualidade trabalham juntos, dando clareza, liberdade e paz verdadeira para sua vida.\n\n"
            "👉🏼 Conquiste liberdade real agora: https://seulinkpremium.com"
        ),
        "geral": (
            "⚠️ Eita, seu limite gratuito acabou de bater no teto! 😬\n\n"
            "Vamos parar de brincar com suas finanças e entrar pro clube dos adultos responsáveis? "
            "Libere agora o acesso premium e tenha controle total das suas finanças, alertas personalizados e orientação VIP pra alcançar seus objetivos. 🚀💳\n\n"
            "👉🏼 Acesse agora aqui: https://seulinkpremium.com"
        )
    }

    return mensagens_contextuais.get(contexto, mensagens_contextuais["geral"])

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
        "❌ Não consegui entender seus gastos direito. 😵‍💫 \n\n"
        "Me ajuda mandando assim, por favor:\n\n"
        "📌 Descrição – Valor – Forma de pagamento – Categoria (opcional)\n\n"
        "Exemplo:\n• Uber – 20,00 – crédito\n• Farmácia – 50,00 – pix – Saúde\n\n"
        "Pode enviar vários, um por linha. 😉"
    )

def humor_acido_alerta():
    mensagens = {
        "alimentação": "Delivery de novo? Já pode pedir música no Fantástico. Bora cozinhar em casa hoje ou vai esperar a falência bater na porta? 🍔🤡",
        "roupas": "Mais roupa nova? Tá lançando coleção ou resolveu rasgar dinheiro com estilo? 🛍️🔥",
        "entretenimento": "Netflix, Disney+, Prime… Parabéns, você é oficialmente acionista majoritário das plataformas de streaming. Já pensou investir um pouco em você? 📺💸",
        "academia": "Que legal, já pagou a mensalidade da academia mais cara da cidade. Agora só falta você ir treinar. 🫢", 
        "geral": [
            "Seu cartão tá mais movimentado que metrô em horário de pico. Bora maneirar um pouco? 🚇😅",
            "Não é rico, mas adora um luxo, né? 🐩",
            "Ô Leônidas, cê tem que parar de arrumar essas confusão, meu! 🫣",
            "Essa semana tenha o mindset de um boleto. Porque um boleto sempre vence. Vamo pra cima! 🚀",
            "Compra, pô. É seu lazer. 👹",
             "Uai, passa vontade não, passa o cartãozinho. 👹"
        ]
    }
    
    categoria_escolhida = random.choice(list(mensagens.keys()))
    if isinstance(mensagens[categoria_escolhida], list):
        return random.choice(mensagens[categoria_escolhida])
    else:
        return mensagens[categoria_escolhida]

def disclaimer():
    return (
        "⚠️ Lembre-se: Este GPT não substitui acompanhamento profissional especializado em saúde física, emocional, "
        "orientação espiritual direta ou consultoria financeira personalizada."
    )

def estilo_msg(texto, leve=True):
    if leve and random.random() < 0.3:  # 30% de chance
        fechamento_personalizado = random.choice([
            "Vamos juntos! 🚀",
            "Conte comigo! 🤝",
            "Sigamos firmes! 💪🏼",
            "Tô com você! 🫡"
        ])
        return f"{texto}\n\n{fechamento_personalizado}"
    return texto