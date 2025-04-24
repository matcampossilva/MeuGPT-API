import random

def saudacao_inicial():
    return (
        "Olá! 👋🏼 Sou o seu Conselheiro Financeiro criado pelo Matheus Campos, CFP®. "
        "Tô aqui pra te ajudar a organizar suas finanças e sua vida, sempre colocando Deus, sua família e seu trabalho antes do dinheiro. "
        "Pra começarmos a organizar sua vida financeira, me diga seu nome completo e e-mail, por favor."
    )

def funcionalidades():
    return (
        "✍️ Posso te ajudar com:\n\n"
        "• Controle de gastos diários\n"
        "• Resumos financeiros diários, semanais e mensais\n"
        "• Alertas inteligentes para controle de gastos\n"
        "• Controle de despesas fixas mensais\n"
        "• Lembrete de pagamentos de contas\n"
        "• Solução de dívidas\n"
        "• Análises de empréstimos e investimentos\n"
        "• Orientação precisa em decisões financeiras\n"
        "• Planejamento financeiro personalizado (seguindo os seis pilares CFP®)\n"
        "• Orientações práticas para sua vida espiritual e familiar\n\n"
        "Por onde você quer começar?"
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
        "✍️ Posso te ajudar com:\n\n"
        "• Controle de gastos diários\n"
        "• Resumos financeiros diários, semanais e mensais\n"
        "• Alertas inteligentes para controle de gastos\n"
        "• Controle de despesas fixas mensais\n"
        "• Lembrete de pagamentos de contas\n"
        "• Solução de dívidas\n"
        "• Análises de empréstimos e investimentos\n"
        "• Orientação precisa em decisões financeiras\n"
        "• Planejamento financeiro personalizado (seguindo os seis pilares CFP®)\n"
        "• Orientações práticas para sua vida espiritual e familiar\n\n"
        "Por onde você quer começar?"
    )

def solicitacao_cadastro():
    return saudacao_inicial()

def alerta_limite_gratuito(contexto='geral'):
    mensagens_contextuais = {
        "casamento": (
            "⚠️ Você atingiu o limite da versão gratuita.\n\n"
            "Dinheiro não é só número, é paz dentro de casa, não é mesmo? "
            "Imagine você e seu cônjuge conversando com calma sobre dinheiro, sem brigas, sem pressão, "
            "transformando cada decisão financeira numa oportunidade para fortalecer a união entre vocês. "
            "O Premium foi criado justamente para isso: trazer clareza financeira e harmonia conjugal ao seu lar. "
            "Vamos dar esse passo juntos hoje?\n\n"
            "👉🏼 https://seulinkpremium.com"
        ),
        "dívidas": (
            "⚠️ Seu acesso gratuito terminou.\n\n"
            "Sei que dívidas preocupam e geram ansiedade, é difícil dormir tranquilo pensando em juros. "
            "E se você pudesse dormir com tranquilidade, sabendo exatamente como quitar essas dívidas "
            "e recuperar o controle das suas finanças? O Premium oferece exatamente esse plano de ação concreto. "
            "Não vale a pena trocar juros por tranquilidade?\n\n"
            "👉🏼 https://seulinkpremium.com"
        ),
        "controle_gastos": (
            "⚠️ Seu período gratuito chegou ao fim.\n\n"
            "Você já percebeu como pequenos gastos acumulados roubam grandes sonhos? "
            "Que tal substituir a dúvida por clareza absoluta e controle total sobre cada real gasto? "
            "Com o Premium, você decide onde vai parar seu dinheiro. Está pronto para assumir o controle "
            "definitivo da sua vida financeira hoje?\n\n"
            "👉🏼 https://seulinkpremium.com"
        ),
        "decisoes_financeiras": (
            "⚠️ Você esgotou seu limite gratuito.\n\n"
            "Eu sei como é difícil tomar decisões financeiras sem ter todas as informações claras. "
            "Quantas oportunidades já foram perdidas por falta de clareza? "
            "Com o Premium, cada decisão financeira passa a ser objetiva e certeira. "
            "Está pronto para trocar insegurança por decisões inteligentes e assertivas?\n\n"
            "👉🏼 https://seulinkpremium.com"
        ),
        "liberdade_espiritual": (
            "⚠️ Seu acesso gratuito encerrou.\n\n"
            "Dinheiro não precisa ser motivo de pressão, ansiedade ou culpa. "
            "Ele pode servir como instrumento para realizar seus valores mais profundos e trazer paz verdadeira "
            "ao seu coração. O Premium é exatamente essa ponte entre sua vida espiritual e sua vida material. "
            "Quer experimentar essa liberdade e paz hoje mesmo?\n\n"
            "👉🏼 https://seulinkpremium.com"
        ),
        "geral": (
            "⚠️ Você atingiu o limite gratuito.\n\n"
            "Sei como é frustrante querer mais da sua vida financeira, mas não saber por onde começar. "
            "Você merece clareza, tranquilidade e segurança sobre cada passo financeiro que der daqui pra frente. "
            "O Premium oferece exatamente isso, com estratégias personalizadas e acompanhamento próximo, todos os dias. "
            "Que tal começar hoje a transformar seu futuro financeiro de verdade?\n\n"
            "👉🏼 https://seulinkpremium.com"
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

def alerta_limite_excedido(categoria, total, limite, faixa):
    mensagens = {
        "50": [
            f"👀 Você já torrou 50% do limite mensal em *{categoria}*. Não tá cedo demais pra isso não, guerreiro?",
            f"⚠️ Metade do orçamento mensal de *{categoria}* já foi pro saco. Bora pisar no freio ou vai deixar pro mês que vem?",
        ],
        "70": [
            f"😬 Alerta vermelho: você já gastou 70% do limite mensal em *{categoria}*. Desse jeito vai ter que fazer milagre no fim do mês.",
            f"⚠️ Já queimou 70% do orçamento de *{categoria}*. A fatura tá batendo na sua porta igual testemunha de Jeová no domingo.",
        ],
        "90": [
            f"🚧 Chegou a 90% do limite em *{categoria}*. Seu orçamento tá mais apertado que calça skinny depois do rodízio.",
            f"😵‍💫 90% do orçamento em *{categoria}* já era. Quer testar os outros 10% ou parar enquanto dá tempo?",
        ],
        "100": [
            f"🔥 100% do orçamento pra *{categoria}* já foi. Parabéns pela façanha! Agora só falta explicar isso pra sua família.",
            f"🎉 Limite de *{categoria}* atingido! Seu prêmio? Uma bela dor de cabeça até o próximo mês.",
        ],
        ">100": [
            f"💸 Você já passou em {((total-limite)/limite)*100:.1f}% do limite pra *{categoria}*. Tá tentando zerar sua conta bancária ou entrar pro Guinness?",
            f"😈 Orçamento estourado em *{categoria}*! Continue assim e logo estará concorrendo ao título de maior patrocinador dos bancos do Brasil.",
            f"🚨 Atenção: você já superou o limite de *{categoria}* em {((total-limite)/limite)*100:.1f}%. Tá gastando como se tivesse cartão black ilimitado, hein?",
        ]
    }

    return random.choice(mensagens.get(faixa, mensagens[">100"]))